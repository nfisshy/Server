from __future__ import annotations

import subprocess
import tempfile
import threading
import time
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
        self.player_process: subprocess.Popen | None = None

    def start_video_upload(self, session_id: str) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._video_loop, args=(session_id,), name="video-uploader", daemon=True)
        self.thread.start()

    def stop_video_upload(self) -> None:
        self.stop_event.set()

    def play_video(self, url: str) -> None:
        command = [str(part).format(url=url) for part in self.config["player_command"]]
        try:
            if self.player_process and self.player_process.poll() is None:
                self.player_process.terminate()
            self.player_process = subprocess.Popen(command)
            self.events.put(("media_status", {"message": "Playing received video"}))
        except Exception as exc:
            self.events.put(("media_error", {"message": f"Cannot play video: {exc}"}))

    def _video_loop(self, session_id: str) -> None:
        duration_seconds = float(self.config["video_chunk_seconds"])
        duration_ms = int(duration_seconds * 1000)
        interval = float(self.config["video_chunk_interval_seconds"])

        while not self.stop_event.is_set():
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "chunk.h264"
                command = [
                    str(part).format(duration_ms=duration_ms, output=str(output))
                    for part in self.config["capture_command"]
                ]
                try:
                    started = time.monotonic()
                    subprocess.run(
                        command,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=duration_seconds + 5,
                    )
                    if output.exists() and output.stat().st_size > 0:
                        self.api.upload_video_chunk(session_id, output)
                        elapsed = time.monotonic() - started
                        self.events.put(("media_status", {"message": f"Uploaded video chunk in {elapsed:.1f}s"}))
                except Exception as exc:
                    self.events.put(("media_error", {"message": f"Video upload failed: {exc}"}))
                    time.sleep(2)
            time.sleep(interval)
