from __future__ import annotations

from pathlib import Path
from typing import Any

import requests


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str, device_id: str | None = None, auth_token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        self.auth_token = auth_token
        self.session = requests.Session()

    def set_auth(self, device_id: str, auth_token: str) -> None:
        self.device_id = device_id
        self.auth_token = auth_token

    def register_raspberry(self) -> dict[str, Any]:
        return self._request("POST", "/devices/register", json={"device_type": "raspberry"}, auth=False)

    def get_contacts(self) -> list[dict[str, Any]]:
        return self._request("GET", "/contacts/raspberry")

    def start_call(self, contact_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/call/start",
            json={"from_device_id": self.device_id, "contact_id": contact_id},
        )

    def answer_call(self, session_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/call/answer",
            json={"session_id": session_id, "device_id": self.device_id},
        )

    def end_call(self, session_id: str, reason: str = "ended_by_raspberry") -> dict[str, Any]:
        return self._request(
            "POST",
            "/call/end",
            json={"session_id": session_id, "device_id": self.device_id, "reason": reason},
        )

    def upload_video_chunk(self, session_id: str, path: Path) -> dict[str, Any]:
        content_type = "video/x-motion-jpeg" if path.suffix.lower() in {".mjpeg", ".mjpg"} else "video/h264"
        with path.open("rb") as file_handle:
            files = {"file": (path.name, file_handle, content_type)}
            data = {"session_id": session_id}
            return self._request("POST", "/pipeline/a/start", data=data, files=files, timeout=90)

    def _headers(self) -> dict[str, str]:
        if not self.device_id or not self.auth_token:
            raise ApiError("Device is not registered yet")
        return {"x-device-id": self.device_id, "Authorization": f"Bearer {self.auth_token}"}

    def _request(self, method: str, path: str, auth: bool = True, timeout: int = 15, **kwargs: Any) -> Any:
        headers = kwargs.pop("headers", {})
        if auth:
            headers.update(self._headers())

        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            timeout=timeout,
            **kwargs,
        )
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise ApiError(f"{response.status_code}: {detail}")
        if not response.content:
            return {}
        return response.json()
