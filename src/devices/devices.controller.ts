import { Body, Controller, Post, UseGuards } from '@nestjs/common';
import { Device, DeviceType } from '@prisma/client';
import { CurrentDevice } from '../auth/current-device.decorator';
import { DeviceAuthGuard } from '../auth/device-auth.guard';
import { forbidden } from '../common/errors';
import { DevicesService } from './devices.service';
import { RegisterDeviceDto } from './dto/register-device.dto';
import { PairDeviceDto } from './dto/pair-device.dto';
import { UpdateFcmTokenDto } from './dto/update-fcm-token.dto';

@Controller('devices')
export class DevicesController {
  constructor(private readonly devices: DevicesService) {}

  @Post('register')
  register(@Body() dto: RegisterDeviceDto) {
    return this.devices.register(dto);
  }

  @UseGuards(DeviceAuthGuard)
  @Post('pair')
  pair(@Body() dto: PairDeviceDto, @CurrentDevice() device: Device) {
    if (device.deviceType !== DeviceType.mobile) {
      throw forbidden('Only mobile devices can pair with a Raspberry Pi PIN');
    }
    if (dto.mobile_device_id !== device.id) {
      throw forbidden('Pairing mobile_device_id must match authenticated device');
    }
    return this.devices.pair(dto);
  }

  @UseGuards(DeviceAuthGuard)
  @Post('fcm-token')
  updateFcmToken(@Body() dto: UpdateFcmTokenDto, @CurrentDevice() device: Device) {
    return this.devices.updateFcmToken(device.id, dto.fcm_token);
  }
}
