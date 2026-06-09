from __future__ import annotations

import math
import subprocess
import threading
import time
import wave
from pathlib import Path
from typing import Any


class RingtonePlayer:
    def __init__(self, config: dict[str, Any], ringtone_file: str = "ringtone.wav") -> None:
        self.config = config
        self.ringtone_path = Path(ringtone_file)
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.process: subprocess.Popen | None = None
        self._ensure_ringtone_file()

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, name="ringtone", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def _loop(self) -> None:
        template = self.config.get("ringtone_command", ["aplay", "{file}"])
        command = [str(part).format(file=str(self.ringtone_path)) for part in template]
        while not self.stop_event.is_set():
            try:
                self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                while self.process.poll() is None and not self.stop_event.is_set():
                    time.sleep(0.1)
                if self.process.poll() is None:
                    self.process.terminate()
            except Exception:
                time.sleep(1)
            time.sleep(0.25)

    def _ensure_ringtone_file(self) -> None:
        if self.ringtone_path.exists():
            return

        sample_rate = 44100
        duration = 1.2
        amplitude = 16000
        frequencies = (880, 660)

        with wave.open(str(self.ringtone_path), "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            for index in range(int(sample_rate * duration)):
                phase = index / sample_rate
                envelope = 1.0 if phase % 0.6 < 0.42 else 0.0
                value = sum(math.sin(2 * math.pi * freq * phase) for freq in frequencies) / len(frequencies)
                sample = int(amplitude * envelope * value)
                wav.writeframesraw(sample.to_bytes(2, byteorder="little", signed=True))
