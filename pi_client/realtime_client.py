from __future__ import annotations

import threading
import time
from queue import Queue
from typing import Any

import socketio


class RealtimeClient:
    def __init__(
        self,
        server_base_url: str,
        socketio_path: str,
        device_id: str,
        auth_token: str,
        events: Queue,
    ) -> None:
        self.server_base_url = server_base_url.rstrip("/")
        self.socketio_path = socketio_path
        self.device_id = device_id
        self.auth_token = auth_token
        self.events = events
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=0, logger=False, engineio_logger=False)
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.heartbeat_thread: threading.Thread | None = None
        self._bind_events()

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name="socketio", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.sio.connected:
            self.sio.disconnect()

    def _bind_events(self) -> None:
        @self.sio.event
        def connect() -> None:
            print(f"[PI_WS] connected device={self.device_id}", flush=True)
            self.events.put(("socket_status", {"connected": True}))
            self._start_heartbeat()

        @self.sio.event
        def disconnect() -> None:
            print(f"[PI_WS] disconnected device={self.device_id}", flush=True)
            self.events.put(("socket_status", {"connected": False}))

        @self.sio.on("incoming_call")
        def incoming_call(data: dict[str, Any]) -> None:
            print(f"[PI_WS] incoming_call {data}", flush=True)
            self.events.put(("incoming_call", data))

        @self.sio.on("call_accepted")
        def call_accepted(data: dict[str, Any]) -> None:
            print(f"[PI_WS] call_accepted {data}", flush=True)
            self.events.put(("call_accepted", data))

        @self.sio.on("call_ended")
        def call_ended(data: dict[str, Any]) -> None:
            print(f"[PI_WS] call_ended {data}", flush=True)
            self.events.put(("call_ended", data))

        @self.sio.on("peer_signal")
        def peer_signal(data: dict[str, Any]) -> None:
            print(f"[PI_WS] peer_signal {data}", flush=True)
            self.events.put(("peer_signal", data))

        @self.sio.on("ai_video")
        def ai_video(data: dict[str, Any]) -> None:
            self.events.put(("ai_video", data))

        @self.sio.on("heartbeat_ack")
        def heartbeat_ack(data: dict[str, Any]) -> None:
            self.events.put(("heartbeat_ack", data))

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.sio.connect(
                    self.server_base_url,
                    socketio_path=self.socketio_path,
                    auth={"device_id": self.device_id, "auth_token": self.auth_token},
                    transports=["websocket"],
                )
                self.sio.wait()
            except Exception as exc:
                print(f"[PI_WS] connect_error {exc}", flush=True)
                self.events.put(("socket_error", {"message": str(exc)}))
                time.sleep(3)

    def _start_heartbeat(self) -> None:
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            return
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, name="heartbeat", daemon=True)
        self.heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self.stop_event.is_set():
            if self.sio.connected:
                try:
                    print(f"[PI_WS] heartbeat device={self.device_id}", flush=True)
                    self.sio.emit("heartbeat", {"device_id": self.device_id})
                except Exception as exc:
                    self.events.put(("socket_error", {"message": str(exc)}))
            time.sleep(30)

    def send_call_signal(self, session_id: str, signal_type: str) -> None:
        if not self.sio.connected:
            print(f"[PI_WS] skip_call_signal disconnected session={session_id} type={signal_type}", flush=True)
            return
        try:
            print(f"[PI_WS] emit_call_signal session={session_id} type={signal_type}", flush=True)
            self.sio.emit("call_signal", {"session_id": session_id, "signal_type": signal_type})
        except Exception as exc:
            self.events.put(("socket_error", {"message": str(exc)}))
