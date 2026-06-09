import { Injectable } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcrypt';
import { Device } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import { forbidden } from '../common/errors';

export interface DeviceTokenPayload {
  sub: string;
  device_type: string;
}

@Injectable()
export class AuthService {
  constructor(
    private readonly jwt: JwtService,
    private readonly prisma: PrismaService,
  ) {}

  async issueToken(device: Pick<Device, 'id' | 'deviceType'>) {
    return this.jwt.signAsync({
      sub: device.id,
      device_type: device.deviceType,
    } satisfies DeviceTokenPayload);
  }

  async hashToken(token: string) {
    return bcrypt.hash(token, 12);
  }

  async verifyDeviceToken(deviceId: string, token: string) {
    const payload = await this.jwt.verifyAsync<DeviceTokenPayload>(token);
    if (payload.sub !== deviceId) {
      throw forbidden('Token does not belong to device');
    }

    const device = await this.prisma.device.findFirst({
      where: { id: deviceId, deletedAt: null },
    });
    if (!device) {
      throw forbidden('Device is not registered');
    }

    const matches = await bcrypt.compare(token, device.authTokenHash);
    if (!matches) {
      throw forbidden('Invalid auth token');
    }

    return device;
  }
}
