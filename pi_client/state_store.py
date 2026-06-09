import json
from pathlib import Path
from typing import Any


class StateStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.data = {}
            return
        self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set_many(self, values: dict[str, Any]) -> None:
        self.data.update(values)
        self.save()

    def clear(self) -> None:
        self.data = {}
        self.save()
