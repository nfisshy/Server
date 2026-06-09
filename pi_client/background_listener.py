from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from queue import Queue
from typing import Any

from config import load_config
from realtime_client import RealtimeClient
from state_store import StateStore


class BackgroundListener:
    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parent
        self.config = load_config()
        self.state = StateStore(self.config["state_file"])
        self.events: Queue = Queue()
        self.realtime: RealtimeClient | None = None
        self.gui_process: subprocess.Popen | None = None
        self.pending_call_path = self.base_dir / "pending_call.json"

    def run(self) -> None:
        while True:
            self.state.load()
            if not self.state.get("device_id") or not self.state.get("auth_token"):
                print("Raspberry is not registered yet. Open GUI once and press Register Raspberry.", flush=True)
                time.sleep(5)
                continue

            self._connect()
            self._event_loop()

    def _connect(self) -> None:
        if self.realtime:
            self.realtime.stop()
        self.realtime = RealtimeClient(
            self.config["server_base_url"],
            self.config["socketio_path"],
            self.state.get("device_id"),
            self.state.get("auth_token"),
            self.events,
        )
        self.realtime.start()

    def _event_loop(self) -> None:
        while True:
            name, payload = self.events.get()
            if name == "socket_status":
                print(f"WebSocket {'online' if payload.get('connected') else 'offline'}", flush=True)
            elif name == "socket_error":
                print(f"WebSocket error: {payload.get('message')}", flush=True)
            elif name == "incoming_call":
                self._open_gui_for_call(payload)
                return

    def _open_gui_for_call(self, payload: dict[str, Any]) -> None:
        self.pending_call_path.write_text(json.dumps(payload), encoding="utf-8")
        print(f"Incoming call. Opening GUI for session {payload.get('session_id')}", flush=True)

        if self.realtime:
            self.realtime.stop()

        self.gui_process = subprocess.Popen(
            [sys.executable, "app.py", "--pending-call", str(self.pending_call_path)],
            cwd=str(self.base_dir),
        )

        if self.gui_process:
            self.gui_process.wait()
        time.sleep(2)


if __name__ == "__main__":
    BackgroundListener().run()
