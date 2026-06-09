import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = {
    "server_base_url": "http://172.20.10.3:3000",
    "socketio_path": "ws",
    "state_file": "state.json",
    "history_file": "call_history.json",
    "incoming_timeout_seconds": 60,
    "video_chunk_seconds": 1.5,
    "video_chunk_interval_seconds": 0.2,
    "capture_command": [
        "libcamera-vid",
        "-t",
        "{duration_ms}",
        "--width",
        "640",
        "--height",
        "480",
        "--framerate",
        "15",
        "--fullscreen",
        "--codec",
        "h264",
        "-o",
        "{output}",
    ],
    "player_command": ["mpv", "--fs", "--really-quiet", "{url}"],
    "ringtone_command": ["aplay", "{file}"],
}


def load_config() -> dict[str, Any]:
    path = Path("config.json")
    if not path.exists():
        return DEFAULT_CONFIG.copy()
    config = DEFAULT_CONFIG.copy()
    config.update(json.loads(path.read_text(encoding="utf-8")))
    return config
