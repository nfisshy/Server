import { Controller, Delete, Get, Param, UseGuards } from '@nestjs/common';
import { Device, DeviceType } from '@prisma/client';
import { CurrentDevice } from '../auth/current-device.decorator';
import { DeviceAuthGuard } from '../auth/device-auth.guard';
import { forbidden } from '../common/errors';
import { ContactsService } from './contacts.service';

@UseGuards(DeviceAuthGuard)
@Controller('contacts')
export class ContactsController {
  constructor(private readonly contacts: ContactsService) {}

  @Get('raspberry')
  listForRaspberry(@CurrentDevice() device: Device) {
    if (device.deviceType !== DeviceType.raspberry) {
      throw forbidden('Only Raspberry Pi can list Raspberry contacts');
    }
    return this.contacts.listForRaspberry(device.id);
  }

  @Delete(':contactId')
  remove(@Param('contactId') contactId: string, @CurrentDevice() device: Device) {
    if (device.deviceType !== DeviceType.raspberry) {
      throw forbidden('Only Raspberry Pi can remove contacts');
    }
    return this.contacts.remove(contactId, device.id);
  }
}
