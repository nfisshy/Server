from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


SERVICE_NAME = "blind-assist-listener.service"


class AutostartResult:
    def __init__(self, ok: bool, message: str) -> None:
        self.ok = ok
        self.message = message


def enable_background_listener() -> AutostartResult:
    base_dir = Path(__file__).resolve().parent
    python_path = Path(sys.executable).resolve()
    service_dir = Path.home() / ".config" / "systemd" / "user"
    service_dir.mkdir(parents=True, exist_ok=True)

    display = os.environ.get("DISPLAY", ":0")
    xauthority = os.environ.get("XAUTHORITY", str(Path.home() / ".Xauthority"))
    service_path = service_dir / SERVICE_NAME
    service_path.write_text(
        "\n".join(
            [
                "[Unit]",
                "Description=Blind Assist Raspberry Background Listener",
                "After=network-online.target",
                "Wants=network-online.target",
                "",
                "[Service]",
                "Type=simple",
                f"WorkingDirectory={base_dir}",
                f"ExecStart={python_path} {base_dir / 'background_listener.py'}",
                "Restart=always",
                "RestartSec=3",
                "Environment=PYTHONUNBUFFERED=1",
                f"Environment=DISPLAY={display}",
                f"Environment=XAUTHORITY={xauthority}",
                "",
                "[Install]",
                "WantedBy=default.target",
                "",
            ]
        ),
        encoding="utf-8",
    )

    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=10)
        subprocess.run(["systemctl", "--user", "enable", SERVICE_NAME], check=True, timeout=10)
        subprocess.run(["systemctl", "--user", "restart", SERVICE_NAME], check=True, timeout=10)
        return AutostartResult(True, "Background listener enabled with systemd user service.")
    except Exception as exc:
        desktop_result = _install_desktop_autostart(base_dir, python_path)
        if desktop_result.ok:
            return AutostartResult(
                True,
                f"systemd user failed ({exc}). Desktop autostart fallback was installed.",
            )
        return AutostartResult(False, f"Cannot enable background listener: {exc}; {desktop_result.message}")


def _install_desktop_autostart(base_dir: Path, python_path: Path) -> AutostartResult:
    try:
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        desktop_file = autostart_dir / "blind-assist-listener.desktop"
        desktop_file.write_text(
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    "Name=Blind Assist Listener",
                    f"Exec={python_path} {base_dir / 'background_listener.py'}",
                    f"Path={base_dir}",
                    "Terminal=false",
                    "X-GNOME-Autostart-enabled=true",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return AutostartResult(True, "Desktop autostart installed.")
    except Exception as exc:
        return AutostartResult(False, f"Desktop autostart fallback failed: {exc}")
