# Main Routing Server

NestJS backend for blind-assist real-time communication. All client and AI traffic routes through this server.

## Runtime Services

- PostgreSQL: persistent devices, contacts, call logs, audit logs.
- Redis: active sessions, WebSocket socket mappings, online status.
- Firebase Cloud Messaging: fallback push for offline mobile incoming calls.

## Setup

```bash
cp .env.example .env
docker compose up -d
npm install
npm run prisma:generate
npm run prisma:deploy
npm run start:dev
```

## Auth

`POST /devices/register` returns `device_id`, permanent `pin`, and `auth_token` for Raspberry Pi. All protected HTTP calls require:

```text
x-device-id: <device_id>
authorization: Bearer <auth_token>
```

WebSocket clients connect to `/ws` with `auth.device_id` and `auth.auth_token`.

## Main Endpoints

- `POST /devices/register`
- `POST /devices/fcm-token`
- `POST /devices/pair`
- `GET /contacts/raspberry`
- `DELETE /contacts/:contactId`
- `POST /call/start`
- `POST /call/answer`
- `POST /call/end`
- `POST /pipeline/a/start` multipart field `file`
- `POST /pipeline/a/result`
- `POST /pipeline/b/start` multipart field `file`
- `POST /pipeline/b/result`

## Routing Rules

- Raspberry Pi calls must provide a `contact_id`; the server resolves exactly one mobile device.
- Mobile calls must set `to: "raspberry"`; the server resolves the single active Raspberry Pi.
- If the Raspberry Pi is offline, mobile-originated calls are rejected.
- If a target mobile is offline, the session is created and FCM is attempted.
- Pipeline A accepts Raspberry video uploads and emits `ai_text` to the mobile party.
- Pipeline B accepts mobile audio uploads and emits `ai_video` to the Raspberry Pi.

## WebSocket Events

Server emits: `incoming_call`, `call_accepted`, `call_ended`, `ai_text`, `ai_video`, `heartbeat_ack`.

Client sends `heartbeat` every 30 seconds. Online status expires after 75 seconds if heartbeat stops.
