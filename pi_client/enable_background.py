from __future__ import annotations

from autostart import enable_background_listener


if __name__ == "__main__":
    result = enable_background_listener()
    print(result.message)
    raise SystemExit(0 if result.ok else 1)
