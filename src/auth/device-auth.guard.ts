import { CanActivate, ExecutionContext, Injectable } from '@nestjs/common';
import { AuthService } from './auth.service';
import { forbidden } from '../common/errors';

@Injectable()
export class DeviceAuthGuard implements CanActivate {
  constructor(private readonly auth: AuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest();
    const deviceId = request.header('x-device-id') ?? request.body?.device_id;
    const header = request.header('authorization');
    const token = header?.startsWith('Bearer ') ? header.slice(7) : undefined;

    if (!deviceId || !token) {
      throw forbidden('x-device-id and Bearer auth token are required');
    }

    request.device = await this.auth.verifyDeviceToken(deviceId, token);
    return true;
  }
}
