import { Body, Controller, Get, Param, Post, UseGuards } from '@nestjs/common';
import { CurrentDevice } from '../auth/current-device.decorator';
import { DeviceAuthGuard } from '../auth/device-auth.guard';
import { forbidden } from '../common/errors';
import { CallsService } from './calls.service';
import { AnswerCallDto } from './dto/answer-call.dto';
import { EndCallDto } from './dto/end-call.dto';
import { StartCallDto } from './dto/start-call.dto';
import { Device } from '@prisma/client';

@UseGuards(DeviceAuthGuard)
@Controller('call')
export class CallsController {
  constructor(private readonly calls: CallsService) {}

  @Post('start')
  start(@Body() dto: StartCallDto, @CurrentDevice() device: Device) {
    if (dto.from_device_id !== device.id) {
      throw forbidden('Caller must match authenticated device');
    }
    return this.calls.start(dto, device);
  }

  @Post('answer')
  answer(@Body() dto: AnswerCallDto, @CurrentDevice() device: Device) {
    if (dto.device_id !== device.id) {
      throw forbidden('Answering device must match authenticated device');
    }
    return this.calls.answer(dto);
  }

  @Post('end')
  end(@Body() dto: EndCallDto, @CurrentDevice() device: Device) {
    if (dto.device_id !== device.id) {
      throw forbidden('Ending device must match authenticated device');
    }
    return this.calls.end(dto);
  }

  @Get(':sessionId')
  getSession(@Param('sessionId') sessionId: string, @CurrentDevice() device: Device) {
    return this.calls.getSessionForDevice(sessionId, device.id);
  }
}
