import { Injectable } from '@nestjs/common';
import { CallStatus, Device, DeviceType } from '@prisma/client';
import axios from 'axios';
import FormData = require('form-data');
import { CallsService } from '../calls/calls.service';
import { badRequest, forbidden, notFound } from '../common/errors';
import { PrismaService } from '../prisma/prisma.service';
import { RealtimeService } from '../realtime/realtime.service';
import { PipelineAResultDto } from './dto/pipeline-a-result.dto';
import { PipelineBResultDto } from './dto/pipeline-b-result.dto';
import { PipelineStartDto } from './dto/pipeline-start.dto';

@Injectable()
export class PipelineService {
  constructor(
    private readonly calls: CallsService,
    private readonly prisma: PrismaService,
    private readonly realtime: RealtimeService,
  ) {}

  async startA(dto: PipelineStartDto, file: Express.Multer.File, device: Device) {
    if (!file) {
      throw badRequest('Video file is required as multipart field "file"');
    }
    if (device.deviceType !== DeviceType.raspberry) {
      throw forbidden('Pipeline A uploads must come from Raspberry Pi');
    }

    const session = await this.calls.getActiveSession(dto.session_id);
    this.assertSessionParticipant(session.id, device.id, [session.callerDeviceId, session.calleeDeviceId]);
    if (session.status === CallStatus.ended) {
      throw badRequest('Cannot upload to an ended session');
    }

    await this.forwardMultipart(session.serverAUrl, file, { session_id: session.id });
    return { accepted: true, session_id: session.id };
  }

  async resultA(dto: PipelineAResultDto) {
    const session = await this.calls.getActiveSession(dto.session_id);
    const mobile = await this.findSessionDeviceByType(session.callerDeviceId, session.calleeDeviceId, DeviceType.mobile);
    await this.realtime.sendToDevice(mobile.id, 'ai_text', { session_id: session.id, text: dto.text });
    return { delivered: true };
  }

  async startB(dto: PipelineStartDto, file: Express.Multer.File, device: Device) {
    if (!file) {
      throw badRequest('Audio file is required as multipart field "file"');
    }
    if (device.deviceType !== DeviceType.mobile) {
      throw forbidden('Pipeline B uploads must come from a mobile device');
    }

    const session = await this.calls.getActiveSession(dto.session_id);
    this.assertSessionParticipant(session.id, device.id, [session.callerDeviceId, session.calleeDeviceId]);
    if (session.status === CallStatus.ended) {
      throw badRequest('Cannot upload to an ended session');
    }

    await this.forwardMultipart(session.serverBUrl, file, { session_id: session.id });
    return { accepted: true, session_id: session.id };
  }

  async resultB(dto: PipelineBResultDto) {
    const session = await this.calls.getActiveSession(dto.session_id);
    const raspberry = await this.findSessionDeviceByType(session.callerDeviceId, session.calleeDeviceId, DeviceType.raspberry);
    await this.realtime.sendToDevice(raspberry.id, 'ai_video', {
      session_id: session.id,
      video_url: dto.video_url,
    });
    return { delivered: true };
  }

  private assertSessionParticipant(sessionId: string, deviceId: string, participants: string[]) {
    if (!participants.includes(deviceId)) {
      throw forbidden(`Device is not part of session ${sessionId}`);
    }
  }

  private async findSessionDeviceByType(callerDeviceId: string, calleeDeviceId: string, deviceType: DeviceType) {
    const device = await this.prisma.device.findFirst({
      where: {
        id: { in: [callerDeviceId, calleeDeviceId] },
        deviceType,
        deletedAt: null,
      },
    });
    if (!device) {
      throw notFound(`No ${deviceType} device found in session`);
    }
    return device;
  }

  private async forwardMultipart(url: string, file: Express.Multer.File, fields: Record<string, string>) {
    const form = new FormData();
    Object.entries(fields).forEach(([key, value]) => form.append(key, value));
    form.append('file', file.buffer, {
      filename: file.originalname || 'upload.bin',
      contentType: file.mimetype,
      knownLength: file.size,
    });

    await axios.post(url, form, {
      headers: form.getHeaders(),
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
      timeout: 60_000,
    });
  }
}
