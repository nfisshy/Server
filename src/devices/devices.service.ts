import { Injectable } from '@nestjs/common';
import { DeviceType, Prisma } from '@prisma/client';
import { randomInt } from 'crypto';
import { AuthService } from '../auth/auth.service';
import { badRequest, notFound } from '../common/errors';
import { PrismaService } from '../prisma/prisma.service';
import { PairDeviceDto } from './dto/pair-device.dto';
import { RegisterDeviceDto } from './dto/register-device.dto';

@Injectable()
export class DevicesService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly auth: AuthService,
  ) {}

  async register(dto: RegisterDeviceDto) {
    if (dto.device_type === DeviceType.raspberry) {
      const existing = await this.findRaspberry();
      if (existing) {
        const token = await this.auth.issueToken(existing);
        await this.prisma.device.update({
          where: { id: existing.id },
          data: { authTokenHash: await this.auth.hashToken(token) },
        });
        const pin = existing.pairingPin ?? (await this.createPin(existing.id));
        return { device_id: existing.id, device_type: existing.deviceType, auth_token: token, pin };
      }
    }

    const device = await this.prisma.device.create({
      data: {
        deviceType: dto.device_type,
        ownerName: dto.owner_name,
        fcmToken: dto.fcm_token,
        authTokenHash: 'pending',
      },
    });
    const token = await this.auth.issueToken(device);
    await this.prisma.device.update({
      where: { id: device.id },
      data: { authTokenHash: await this.auth.hashToken(token) },
    });

    if (device.deviceType === DeviceType.raspberry || device.deviceType === DeviceType.mobile) {
      const pin = await this.createPin(device.id);
      return { device_id: device.id, device_type: device.deviceType, auth_token: token, pin };
    }

    return { device_id: device.id, device_type: device.deviceType, auth_token: token };
  }

  async pair(dto: PairDeviceDto) {
    const [raspberry, mobile] = await Promise.all([
      this.prisma.device.findFirst({
        where: { pairingPin: dto.pin, deviceType: DeviceType.raspberry, deletedAt: null },
      }),
      this.prisma.device.findFirst({
        where: { id: dto.mobile_device_id, deviceType: DeviceType.mobile, deletedAt: null },
      }),
    ]);

    if (!raspberry) {
      throw notFound('Raspberry Pi PIN not found');
    }
    if (!mobile) {
      throw notFound('Mobile device not found');
    }

    const contact = await this.prisma.contact.upsert({
      where: {
        raspberryDeviceId_mobileDeviceId: {
          raspberryDeviceId: raspberry.id,
          mobileDeviceId: mobile.id,
        },
      },
      update: { displayName: mobile.ownerName ?? 'Mobile contact' },
      create: {
        raspberryDeviceId: raspberry.id,
        mobileDeviceId: mobile.id,
        displayName: mobile.ownerName ?? 'Mobile contact',
      },
    });

    await this.audit(mobile.id, 'device.paired', { raspberry_device_id: raspberry.id, contact_id: contact.id });

    return { contact_id: contact.id, raspberry_device_id: raspberry.id, mobile_device_id: mobile.id };
  }

  async updateFcmToken(deviceId: string, fcmToken: string) {
    await this.prisma.device.update({
      where: { id: deviceId },
      data: { fcmToken },
    });
    return { updated: true };
  }

  async findRaspberry() {
    return this.prisma.device.findFirst({
      where: { deviceType: DeviceType.raspberry, deletedAt: null },
      orderBy: { createdAt: 'asc' },
    });
  }

  private async createPin(raspberryDeviceId: string) {
    for (let attempt = 0; attempt < 10; attempt += 1) {
      const pin = randomInt(100000, 1000000).toString();
      const existing = await this.prisma.device.findUnique({ where: { pairingPin: pin } });
      if (!existing) {
        await this.prisma.device.update({
          where: { id: raspberryDeviceId },
          data: { pairingPin: pin },
        });
        return pin;
      }
    }
    throw badRequest('Unable to generate PIN');
  }

  private audit(actorId: string, action: string, metadata: Prisma.InputJsonObject) {
    return this.prisma.auditLog.create({ data: { actorId, action, metadata } });
  }
}
