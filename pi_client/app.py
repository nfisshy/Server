from __future__ import annotations

import argparse
import json
import time
import tkinter as tk
from pathlib import Path
from queue import Empty, Queue
from tkinter import messagebox, ttk
from typing import Any

from api_client import ApiClient, ApiError
from autostart import enable_background_listener
from config import load_config
from media_worker import MediaWorker
from realtime_client import RealtimeClient
from ringtone import RingtonePlayer
from state_store import StateStore


class RaspberryApp(tk.Tk):
    def __init__(self, pending_call_path: str | None = None) -> None:
        super().__init__()
        self.title("Blind Assist Raspberry")
        self.attributes("-fullscreen", True)
        self.configure(bg="#111827")

        self.config_data = load_config()
        self.state = StateStore(self.config_data["state_file"])
        self.events: Queue = Queue()
        self.api = ApiClient(
            self.config_data["server_base_url"],
            self.state.get("device_id"),
            self.state.get("auth_token"),
        )
        self.media = MediaWorker(self.api, self.config_data, self.events)
        self.ringtone = RingtonePlayer(self.config_data)
        self.realtime: RealtimeClient | None = None
        self.current_session_id: str | None = None
        self.current_peer_name: str | None = None
        self.call_state: str | None = None
        self.incoming_after_id: str | None = None
        self.camera_label: tk.Label | None = None
        self.camera_photo: Any = None
        self.call_status_label: tk.Label | None = None
        self.pending_call_path = pending_call_path
        self.history_path = Path(self.config_data["history_file"])

        self._build_style()
        self._bind_keys()
        self._start_realtime_if_ready()

        if self._needs_onboarding():
            self.show_onboarding()
        else:
            self.show_home("contacts")

        self._load_pending_call()
        self.after(150, self._drain_events)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Arial", 34, "bold"), background="#111827", foreground="#f9fafb")
        style.configure("Body.TLabel", font=("Arial", 18), background="#111827", foreground="#d1d5db")
        style.configure("Muted.TLabel", font=("Arial", 14), background="#111827", foreground="#9ca3af")
        style.configure("Big.TButton", font=("Arial", 18, "bold"), padding=18)
        style.configure("Tab.TButton", font=("Arial", 16), padding=12)

    def _bind_keys(self) -> None:
        self.bind("<Escape>", lambda _event: self.attributes("-fullscreen", False))
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _needs_onboarding(self) -> bool:
        return (
            not self.state.get("device_id")
            or not self.state.get("auth_token")
            or not self.state.get("pin")
            or not self.state.get("permanent_pin")
        )

    def clear(self) -> None:
        self.deiconify()
        self.camera_label = None
        self.call_status_label = None
        if self.incoming_after_id:
            self.after_cancel(self.incoming_after_id)
            self.incoming_after_id = None
        for child in self.winfo_children():
            child.destroy()

    def show_onboarding(self) -> None:
        self.clear()
        frame = tk.Frame(self, bg="#111827")
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        box = tk.Frame(frame, bg="#111827")
        box.grid(row=0, column=0)
        ttk.Label(box, text="Register Raspberry Pi", style="Title.TLabel").pack(pady=12)
        ttk.Label(
            box,
            text=(
                "This Raspberry Pi needs a permanent PIN before it can receive calls.\n"
                "Press the button below once. The PIN will represent this Raspberry Pi."
            ),
            style="Body.TLabel",
            justify="center",
        ).pack(pady=18)
        ttk.Button(box, text="Register And Create PIN", style="Big.TButton", command=self.register).pack(pady=20)
        ttk.Button(box, text="Exit App", style="Big.TButton", command=self.destroy).pack(pady=8)
        ttk.Label(box, text=f"Server: {self.config_data['server_base_url']}", style="Muted.TLabel").pack(pady=12)

    def show_home(self, tab: str = "contacts") -> None:
        self.clear()
        root = tk.Frame(self, bg="#f3f4f6")
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        header = tk.Frame(root, bg="#111827", height=90)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        tk.Label(header, text="Blind Assist", bg="#111827", fg="#f9fafb", font=("Arial", 24, "bold")).grid(
            row=0, column=0, padx=24, pady=18, sticky="w"
        )
        pin = self.state.get("pin", "-")
        tk.Label(header, text=f"PIN: {pin}", bg="#111827", fg="#93c5fd", font=("Arial", 18, "bold")).grid(
            row=0, column=1, padx=14, sticky="e"
        )
        tk.Button(
            header,
            text="Exit",
            bg="#374151",
            fg="#ffffff",
            activebackground="#1f2937",
            font=("Arial", 14, "bold"),
            padx=18,
            pady=8,
            command=self.destroy,
        ).grid(row=0, column=2, padx=20, sticky="e")

        tabs = tk.Frame(root, bg="#e5e7eb")
        tabs.grid(row=1, column=0, sticky="nsew")
        tabs.columnconfigure(0, weight=1)
        tabs.rowconfigure(1, weight=1)

        nav = tk.Frame(tabs, bg="#e5e7eb")
        nav.grid(row=0, column=0, sticky="ew", padx=18, pady=16)
        ttk.Button(nav, text="Contacts", style="Tab.TButton", command=lambda: self.show_home("contacts")).pack(
            side="left", padx=8
        )
        ttk.Button(nav, text="Conversation History", style="Tab.TButton", command=lambda: self.show_home("history")).pack(
            side="left", padx=8
        )

        content = tk.Frame(tabs, bg="#e5e7eb")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=12)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        if tab == "history":
            self._render_history(content)
        else:
            self._render_contacts(content)

    def _render_contacts(self, parent: tk.Frame) -> None:
        try:
            contacts = self.api.get_contacts()
        except Exception as exc:
            tk.Label(parent, text=f"Cannot load contacts: {exc}", bg="#e5e7eb", fg="#991b1b", font=("Arial", 16)).pack(
                anchor="w"
            )
            return

        if not contacts:
            tk.Label(
                parent,
                text="No contacts yet. Pair a mobile app using the permanent PIN above.",
                bg="#e5e7eb",
                fg="#374151",
                font=("Arial", 18),
            ).pack(anchor="w")
            return

        for contact in contacts:
            mobile = contact.get("mobileDevice", {})
            name = contact.get("displayName") or mobile.get("ownerName") or "Mobile"
            mobile_pin = mobile.get("pairingPin") or "-"
            mobile_id = mobile.get("id") or "-"
            row = tk.Frame(parent, bg="#ffffff", padx=18, pady=14)
            row.pack(fill="x", pady=8)
            row.columnconfigure(0, weight=1)
            tk.Label(row, text=name, bg="#ffffff", fg="#111827", font=("Arial", 20, "bold")).grid(
                row=0, column=0, sticky="w"
            )
            tk.Label(
                row,
                text=f"PIN: {mobile_pin}  Device: {str(mobile_id)[:8]}",
                bg="#ffffff",
                fg="#6b7280",
                font=("Arial", 12),
            ).grid(row=1, column=0, sticky="w", pady=(4, 0))
            tk.Button(
                row,
                text="Call",
                bg="#16a34a",
                fg="#ffffff",
                activebackground="#15803d",
                font=("Arial", 16, "bold"),
                padx=28,
                pady=10,
                command=lambda cid=contact["id"], cname=name: self.start_call(cid, cname),
            ).grid(row=0, column=1, sticky="e")

    def _render_history(self, parent: tk.Frame) -> None:
        history = self._load_history()
        if not history:
            tk.Label(parent, text="No conversations yet.", bg="#e5e7eb", fg="#374151", font=("Arial", 18)).pack(
                anchor="w"
            )
            return

        for item in reversed(history[-80:]):
            row = tk.Frame(parent, bg="#ffffff", padx=18, pady=12)
            row.pack(fill="x", pady=6)
            title = f"{item.get('direction', 'call')} - {item.get('name', 'Unknown')}"
            detail = f"{item.get('status', '-')}, session {item.get('session_id', '-')}"
            tk.Label(row, text=title, bg="#ffffff", fg="#111827", font=("Arial", 16, "bold")).pack(anchor="w")
            tk.Label(row, text=detail, bg="#ffffff", fg="#6b7280", font=("Arial", 12)).pack(anchor="w")

    def show_incoming(self, payload: dict[str, Any]) -> None:
        self.clear()
        self.current_session_id = payload["session_id"]
        caller = payload.get("caller_name", "Mobile caller")
        self._append_history("incoming", caller, self.current_session_id, "ringing")
        self.ringtone.start()

        frame = tk.Frame(self, bg="#020617")
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        box = tk.Frame(frame, bg="#020617")
        box.grid(row=0, column=0)
        tk.Label(box, text=caller, bg="#020617", fg="#f9fafb", font=("Arial", 42, "bold")).pack(pady=12)
        tk.Label(box, text="Incoming call", bg="#020617", fg="#cbd5e1", font=("Arial", 22)).pack(pady=8)

        actions = tk.Frame(box, bg="#020617")
        actions.pack(pady=60)
        tk.Button(
            actions,
            text="Decline",
            bg="#dc2626",
            fg="#ffffff",
            activebackground="#b91c1c",
            font=("Arial", 24, "bold"),
            padx=44,
            pady=26,
            command=lambda: self.end_call("declined"),
        ).pack(side="left", padx=50)
        tk.Button(
            actions,
            text="Accept",
            bg="#16a34a",
            fg="#ffffff",
            activebackground="#15803d",
            font=("Arial", 24, "bold"),
            padx=44,
            pady=26,
            command=self.answer_call,
        ).pack(side="left", padx=50)

        timeout_ms = int(self.config_data["incoming_timeout_seconds"]) * 1000
        self.incoming_after_id = self.after(timeout_ms, lambda: self.end_call("missed"))

    def show_active_call(self) -> None:
        self.clear()
        self.attributes("-fullscreen", True)
        frame = tk.Frame(self, bg="#000000")
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.camera_label = tk.Label(
            frame,
            text="Starting camera...",
            bg="#000000",
            fg="#f9fafb",
            font=("Arial", 34, "bold"),
            compound="center",
        )
        self.camera_label.grid(row=0, column=0, sticky="nsew")

        top_bar = tk.Frame(frame, bg="#000000")
        top_bar.place(relx=0.5, rely=0.04, anchor="n")
        self.call_status_label = tk.Label(
            top_bar,
            text="Camera is starting. Video chunks will be sent automatically.",
            bg="#000000",
            fg="#f9fafb",
            font=("Arial", 14, "bold"),
        )
        self.call_status_label.pack()

        controls = tk.Frame(frame, bg="#000000")
        controls.place(relx=0.5, rely=0.92, anchor="center")
        tk.Button(
            controls,
            text="End Call",
            bg="#dc2626",
            fg="#ffffff",
            activebackground="#b91c1c",
            font=("Arial", 22, "bold"),
            padx=52,
            pady=18,
            command=lambda: self.end_call("ended_by_raspberry"),
        ).pack()

        if self.current_session_id:
            self.media.start_video_upload(self.current_session_id)

    def show_outgoing_ringing(self) -> None:
        self.clear()
        frame = tk.Frame(self, bg="#020617")
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        box = tk.Frame(frame, bg="#020617")
        box.grid(row=0, column=0)
        tk.Label(
            box,
            text=self.current_peer_name or "Mobile",
            bg="#020617",
            fg="#f9fafb",
            font=("Arial", 42, "bold"),
        ).pack(pady=12)
        tk.Label(box, text="Calling...", bg="#020617", fg="#cbd5e1", font=("Arial", 24)).pack(pady=8)
        tk.Button(
            box,
            text="Cancel Call",
            bg="#dc2626",
            fg="#ffffff",
            activebackground="#b91c1c",
            font=("Arial", 24, "bold"),
            padx=44,
            pady=24,
            command=lambda: self.end_call("cancelled_by_raspberry"),
        ).pack(pady=70)

    def register(self) -> None:
        try:
            result = self.api.register_raspberry()
            self.state.set_many(
                {
                    "device_id": result["device_id"],
                    "auth_token": result["auth_token"],
                    "pin": result["pin"],
                    "permanent_pin": True,
                }
            )
            self.api.set_auth(result["device_id"], result["auth_token"])
            self._start_realtime_if_ready()
            self.enable_background(show_success=False)
            messagebox.showinfo("Registered", f"Raspberry PIN: {result['pin']}")
            self.show_home("contacts")
        except Exception as exc:
            messagebox.showerror("Register failed", str(exc))

    def enable_background(self, show_success: bool = True) -> None:
        if not self.state.get("device_id") or not self.state.get("auth_token"):
            messagebox.showwarning("Background listener", "Register Raspberry before enabling background listener.")
            return
        autostart = enable_background_listener()
        if autostart.ok and show_success:
            messagebox.showinfo("Background listener", autostart.message)
        if not autostart.ok:
            messagebox.showwarning("Background listener", autostart.message)

    def start_call(self, contact_id: str, name: str) -> None:
        try:
            session = self.api.start_call(contact_id)
            self.current_session_id = session["session_id"]
            self.current_peer_name = name
            self.call_state = "ringing_outgoing"
            self._append_history("outgoing", name, self.current_session_id, "ringing")
            self.show_outgoing_ringing()
        except Exception as exc:
            messagebox.showerror("Call failed", str(exc))

    def answer_call(self) -> None:
        if not self.current_session_id:
            return
        try:
            self.ringtone.stop()
            self.api.answer_call(self.current_session_id)
            self.call_state = "active"
            self._append_history("incoming", self.current_peer_name or "Mobile caller", self.current_session_id, "active")
            self.show_active_call()
        except Exception as exc:
            messagebox.showerror("Answer failed", str(exc))

    def end_call(self, reason: str = "ended_by_raspberry") -> None:
        if not self.current_session_id:
            self.ringtone.stop()
            self.media.stop_video_upload()
            self.show_home("contacts")
            return

        session_id = self.current_session_id
        peer_name = self.current_peer_name or "Unknown"
        self.ringtone.stop()
        self.media.stop_video_upload()
        try:
            self.api.end_call(session_id, reason)
        except ApiError:
            pass
        self._append_history("call", peer_name, session_id, reason)
        self.current_session_id = None
        self.current_peer_name = None
        self.call_state = None
        self.show_home("contacts")

    def _start_realtime_if_ready(self) -> None:
        device_id = self.state.get("device_id")
        auth_token = self.state.get("auth_token")
        if not device_id or not auth_token:
            return
        if self.realtime:
            self.realtime.stop()
        self.realtime = RealtimeClient(
            self.config_data["server_base_url"],
            self.config_data["socketio_path"],
            device_id,
            auth_token,
            self.events,
        )
        self.realtime.start()

    def _drain_events(self) -> None:
        latest_camera_frame: bytes | None = None
        try:
            while True:
                name, payload = self.events.get_nowait()
                if name == "camera_frame":
                    latest_camera_frame = payload.get("ppm")
                    continue
                self._handle_event(name, payload)
        except Empty:
            pass
        if latest_camera_frame:
            self._render_camera_frame(latest_camera_frame)
        self.after(150, self._drain_events)

    def _handle_event(self, name: str, payload: dict[str, Any]) -> None:
        if name == "incoming_call":
            self.current_peer_name = payload.get("caller_name", "Mobile caller")
            self.call_state = "ringing_incoming"
            self.show_incoming(payload)
        elif name == "call_accepted":
            self.current_session_id = payload.get("session_id", self.current_session_id)
            self.call_state = "active"
            self.show_active_call()
        elif name == "call_ended":
            was_ringing = self.call_state in {"ringing_outgoing", "ringing_incoming"}
            reason = payload.get("reason", "call_ended")
            self.current_session_id = None
            self.current_peer_name = None
            self.call_state = None
            self.ringtone.stop()
            self.media.stop_video_upload()
            self.show_home("contacts")
            if was_ringing:
                messagebox.showinfo("Call ended", f"Call was not answered: {reason}")
        elif name == "ai_video":
            url = payload.get("video_url")
            if url:
                self.media.play_video(url)
        elif name == "camera_frame":
            self._render_camera_frame(payload.get("ppm"))
        elif name == "media_status":
            if self.call_status_label:
                self.call_status_label.configure(text=payload.get("message", "Camera active"))
        elif name == "media_error":
            message = payload.get("message", str(payload))
            if self.call_status_label:
                self.call_status_label.configure(text=message, fg="#fca5a5")
            print(message, flush=True)

    def _render_camera_frame(self, ppm: bytes | None) -> None:
        if not ppm or not self.camera_label:
            return
        try:
            self.camera_photo = tk.PhotoImage(data=ppm, format="PPM")
            self.camera_label.configure(image=self.camera_photo, text="")
            if self.call_status_label:
                self.call_status_label.configure(text="Camera live - sending video chunks", fg="#bbf7d0")
        except Exception as exc:
            if self.call_status_label:
                self.call_status_label.configure(text=f"Cannot render camera frame: {exc}", fg="#fca5a5")

    def _load_pending_call(self) -> None:
        if not self.pending_call_path:
            return
        path = Path(self.pending_call_path)
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            path.unlink(missing_ok=True)
            self.show_incoming(payload)
            self.lift()
            self.attributes("-topmost", True)
            self.after(1200, lambda: self.attributes("-topmost", False))
        except Exception as exc:
            print(f"Cannot load pending call: {exc}", flush=True)

    def _load_history(self) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        try:
            return json.loads(self.history_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _append_history(self, direction: str, name: str, session_id: str, status: str) -> None:
        history = self._load_history()
        history.append(
            {
                "ts": int(time.time()),
                "direction": direction,
                "name": name,
                "session_id": session_id,
                "status": status,
            }
        )
        self.history_path.write_text(json.dumps(history[-300:], indent=2), encoding="utf-8")

    def destroy(self) -> None:
        self.ringtone.stop()
        self.media.stop_video_upload()
        if self.realtime:
            self.realtime.stop()
        super().destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pending-call")
    args = parser.parse_args()
    RaspberryApp(pending_call_path=args.pending_call).mainloop()
