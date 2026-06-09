ALTER TABLE "devices" ADD COLUMN "pairing_pin" TEXT;
CREATE UNIQUE INDEX "devices_pairing_pin_key" ON "devices"("pairing_pin");
