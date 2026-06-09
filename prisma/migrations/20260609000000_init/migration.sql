CREATE TYPE "DeviceType" AS ENUM ('raspberry', 'mobile');
CREATE TYPE "CallStatus" AS ENUM ('ringing', 'active', 'ended');
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE "devices" (
  "id" TEXT NOT NULL DEFAULT gen_random_uuid()::text,
  "device_type" "DeviceType" NOT NULL,
  "owner_name" TEXT,
  "auth_token_hash" TEXT NOT NULL,
  "fcm_token" TEXT,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  "deleted_at" TIMESTAMP(3),
  CONSTRAINT "devices_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "contacts" (
  "id" TEXT NOT NULL DEFAULT gen_random_uuid()::text,
  "raspberry_device_id" TEXT NOT NULL,
  "mobile_device_id" TEXT NOT NULL,
  "display_name" TEXT NOT NULL,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "contacts_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "call_sessions" (
  "id" TEXT NOT NULL DEFAULT gen_random_uuid()::text,
  "caller_device_id" TEXT NOT NULL,
  "callee_device_id" TEXT NOT NULL,
  "status" "CallStatus" NOT NULL DEFAULT 'ringing',
  "started_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "answered_at" TIMESTAMP(3),
  "ended_at" TIMESTAMP(3),
  "server_a_url" TEXT NOT NULL,
  "server_b_url" TEXT NOT NULL,
  "end_reason" TEXT,
  CONSTRAINT "call_sessions_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "audit_logs" (
  "id" TEXT NOT NULL DEFAULT gen_random_uuid()::text,
  "actor_id" TEXT,
  "action" TEXT NOT NULL,
  "metadata" JSONB,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "audit_logs_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "devices_single_active_raspberry" ON "devices" ("device_type") WHERE "device_type" = 'raspberry' AND "deleted_at" IS NULL;
CREATE INDEX "devices_device_type_idx" ON "devices" ("device_type");
CREATE UNIQUE INDEX "contacts_raspberry_device_id_mobile_device_id_key" ON "contacts" ("raspberry_device_id", "mobile_device_id");
CREATE INDEX "contacts_mobile_device_id_idx" ON "contacts" ("mobile_device_id");
CREATE INDEX "call_sessions_caller_device_id_idx" ON "call_sessions" ("caller_device_id");
CREATE INDEX "call_sessions_callee_device_id_idx" ON "call_sessions" ("callee_device_id");
CREATE INDEX "call_sessions_status_idx" ON "call_sessions" ("status");
CREATE INDEX "audit_logs_actor_id_idx" ON "audit_logs" ("actor_id");
CREATE INDEX "audit_logs_action_idx" ON "audit_logs" ("action");

ALTER TABLE "contacts" ADD CONSTRAINT "contacts_raspberry_device_id_fkey" FOREIGN KEY ("raspberry_device_id") REFERENCES "devices"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "contacts" ADD CONSTRAINT "contacts_mobile_device_id_fkey" FOREIGN KEY ("mobile_device_id") REFERENCES "devices"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "call_sessions" ADD CONSTRAINT "call_sessions_caller_device_id_fkey" FOREIGN KEY ("caller_device_id") REFERENCES "devices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "call_sessions" ADD CONSTRAINT "call_sessions_callee_device_id_fkey" FOREIGN KEY ("callee_device_id") REFERENCES "devices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
