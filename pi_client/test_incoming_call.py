from __future__ import annotations

import argparse
import sys
from typing import Any

import requests


def request(method: str, url: str, **kwargs: Any) -> Any:
    response = requests.request(method, url, timeout=15, **kwargs)
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise RuntimeError(f"{response.status_code}: {detail}")
    return response.json() if response.content else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate a mobile app calling the Raspberry Pi.")
    parser.add_argument("--server", default="http://172.20.10.3:3000")
    parser.add_argument("--pin", required=True, help="Current 6-digit PIN shown by Raspberry setup screen.")
    parser.add_argument("--owner", default="Test Mobile")
    args = parser.parse_args()

    server = args.server.rstrip("/")

    print("Registering fake mobile...")
    mobile = request(
        "POST",
        f"{server}/devices/register",
        json={
            "device_type": "mobile",
            "owner_name": args.owner,
            "fcm_token": "test-fcm-token",
        },
    )

    mobile_device_id = mobile["device_id"]
    auth_token = mobile["auth_token"]
    headers = {
        "x-device-id": mobile_device_id,
        "Authorization": f"Bearer {auth_token}",
    }

    print(f"Fake mobile id: {mobile_device_id}")
    print("Pairing fake mobile with Raspberry PIN...")
    pair = request(
        "POST",
        f"{server}/devices/pair",
        headers=headers,
        json={
            "pin": args.pin,
            "mobile_device_id": mobile_device_id,
        },
    )
    print(f"Paired contact: {pair['contact_id']}")

    print("Starting mobile -> Raspberry call...")
    session = request(
        "POST",
        f"{server}/call/start",
        headers=headers,
        json={
            "from_device_id": mobile_device_id,
            "to": "raspberry",
        },
    )
    print(f"Call session created: {session['session_id']}")
    print("If the Raspberry listener is online, its GUI should open and ring now.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
