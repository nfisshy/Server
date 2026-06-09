from __future__ import annotations

import tempfile
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from queue import Queue
from typing import Any

from api_client import ApiClient


class MediaWorker:
    def __init__(self, api: ApiClient, config: dict[str, Any], events: Queue) -> None:
        self.api = api
        self.config = config
        self.events = events
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.upload_executor: ThreadPoolExecutor | None = None
        self.pending_uploads: set[Future] = set()
        self.pending_lock = threading.Lock()

    def start_video_upload(self, session_id: str) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._opencv_loop, args=(session_id,), name="opencv-camera", daemon=True)
        self.thread.start()

    def stop_video_upload(self) -> None:
        self.stop_event.set()
        if self.upload_executor:
            self.upload_executor.shutdown(wait=False, cancel_futures=True)
            self.upload_executor = None
        with self.pending_lock:
            self.pending_uploads.clear()

    def play_video(self, url: str) -> None:
        import subprocess

        command = [str(part).format(url=url) for part in self.config["player_command"]]
        try:
            subprocess.Popen(command)
            self.events.put(("media_status", {"message": "Playing received video"}))
        except Exception as exc:
            self.events.put(("media_error", {"message": f"Cannot play video: {exc}"}))

    def _opencv_loop(self, session_id: str) -> None:
        try:
            import cv2
        except Exception as exc:
            self.events.put(("media_error", {"message": f"OpenCV import failed: {exc}"}))
            return

        camera_index = int(self.config.get("camera_index", 0))
        camera_fps = int(self.config.get("camera_fps", 30))
        sample_fps = int(self.config.get("sample_fps", 15))
        sample_interval = 1.0 / max(sample_fps, 1)
        chunk_frames = int(self.config.get("chunk_frames", 15))
        width = int(self.config.get("frame_width", 640))
        height = int(self.config.get("frame_height", 480))
        jpeg_quality = int(self.config.get("jpeg_quality", 72))
        warmup_seconds = float(self.config.get("camera_warmup_seconds", 1.2))
        preview_fps = float(self.config.get("preview_max_fps", 12))
        preview_interval = 1.0 / max(preview_fps, 1)
        preview_width = int(self.config.get("preview_width", 426))
        preview_height = int(self.config.get("preview_height", 320))
        upload_workers = int(self.config.get("upload_workers", 2))
        max_pending_uploads = int(self.config.get("max_pending_uploads", 4))

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            self.events.put(("media_error", {"message": f"Cannot open camera index {camera_index}"}))
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, camera_fps)
        self.events.put(("media_status", {"message": "OpenCV camera started"}))
        self.upload_executor = ThreadPoolExecutor(max_workers=max(upload_workers, 1), thread_name_prefix="chunk-upload")

        started = time.perf_counter()
        last_sample_at = 0.0
        last_preview_at = 0.0
        current_chunk: list[bytes] = []

        try:
            while not self.stop_event.is_set():
                loop_start = time.perf_counter()
                ok, frame = cap.read()
                if not ok or frame is None:
                    self.events.put(("media_error", {"message": "Camera frame read failed"}))
                    time.sleep(0.05)
                    continue

                frame = cv2.resize(frame, (width, height))
                now = time.perf_counter()
                if now - started < warmup_seconds:
                    continue

                if now - last_preview_at >= preview_interval:
                    preview = self._encode_preview_ppm(cv2, frame, preview_width, preview_height)
                    if preview:
                        self.events.put(("camera_frame", {"ppm": preview}))
                    last_preview_at = now

                if now - last_sample_at < sample_interval:
                    self._sleep_for_camera_fps(loop_start, camera_fps)
                    continue

                encoded = self._encode_jpeg(cv2, frame, jpeg_quality)
                if encoded:
                    current_chunk.append(encoded)
                    last_sample_at = now

                if len(current_chunk) >= chunk_frames:
                    self._submit_upload(session_id, current_chunk, max_pending_uploads)
                    current_chunk = []

                self._sleep_for_camera_fps(loop_start, camera_fps)

            if current_chunk:
                self._submit_upload(session_id, current_chunk, max_pending_uploads)
        except Exception as exc:
            self.events.put(("media_error", {"message": f"OpenCV camera loop failed: {exc}"}))
        finally:
            cap.release()
            if self.upload_executor:
                self.upload_executor.shutdown(wait=False, cancel_futures=True)
                self.upload_executor = None
            self.events.put(("media_status", {"message": "Camera stopped"}))

    @staticmethod
    def _encode_jpeg(cv2: Any, frame: Any, quality: int) -> bytes | None:
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        return encoded.tobytes() if ok else None

    @staticmethod
    def _encode_preview_ppm(cv2: Any, frame: Any, width: int, height: int) -> bytes | None:
        preview = cv2.resize(frame, (width, height))
        rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        header = f"P6\n{width} {height}\n255\n".encode("ascii")
        return header + rgb.tobytes()

    def _submit_upload(self, session_id: str, frames: list[bytes], max_pending_uploads: int) -> None:
        if not self.upload_executor:
            return
        with self.pending_lock:
            self.pending_uploads = {future for future in self.pending_uploads if not future.done()}
            if max_pending_uploads > 0 and len(self.pending_uploads) >= max_pending_uploads:
                self.events.put(("media_status", {"message": "Dropped video chunk because uploads are backed up"}))
                return
            future = self.upload_executor.submit(self._upload_chunk, session_id, list(frames))
            self.pending_uploads.add(future)

    @staticmethod
    def _sleep_for_camera_fps(loop_start: float, camera_fps: int) -> None:
        elapsed = time.perf_counter() - loop_start
        sleep_seconds = max(0.0, (1.0 / max(camera_fps, 1)) - elapsed)
        if sleep_seconds:
            time.sleep(sleep_seconds)

    def _upload_chunk(self, session_id: str, frames: list[bytes]) -> None:
        if not frames:
            return
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "chunk.mjpeg"
            path.write_bytes(b"".join(frames))
            try:
                started = time.monotonic()
                self.api.upload_video_chunk(session_id, path)
                elapsed = time.monotonic() - started
                self.events.put(("media_status", {"message": f"Uploaded {len(frames)} frames in {elapsed:.1f}s"}))
            except Exception as exc:
                self.events.put(("media_error", {"message": f"Video upload failed: {exc}"}))
