import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { CallSession, CallStatus, Device, DeviceType } from '@prisma/client';
import { badRequest, forbidden, notFound } from '../common/errors';
import { DevicesService } from '../devices/devices.service';
import { FcmService } from '../fcm/fcm.service';
import { PrismaService } from '../prisma/prisma.service';
import { RedisService } from '../redis/redis.service';
import { RealtimeService } from '../realtime/realtime.service';
import { AnswerCallDto } from './dto/answer-call.dto';
import { EndCallDto } from './dto/end-call.dto';
import { StartCallDto } from './dto/start-call.dto';

@Injectable()
export class CallsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly redis: RedisService,
    private readonly realtime: RealtimeService,
    private readonly devices: DevicesService,
    private readonly fcm: FcmService,
    private readonly config: ConfigService,
  ) {}

  async start(dto: StartCallDto, caller: Device) {
    if (caller.deviceType === DeviceType.raspberry) {
      return this.startFromRaspberry(dto, caller);
    }
    return this.startFromMobile(dto, caller);
  }

  async answer(dto: AnswerCallDto) {
    const session = await this.getSession(dto.session_id);
    if (![session.callerDeviceId, session.calleeDeviceId].includes(dto.device_id)) {
      throw forbidden('Device is not part of this session');
    }
    if (session.status === CallStatus.ended) {
      throw badRequest('Cannot answer an ended call');
    }

    const updated = await this.prisma.callSession.update({
      where: { id: session.id },
      data: { status: CallStatus.active, answeredAt: new Date() },
    });
    await this.cacheSession(updated);

    const otherDeviceId = dto.device_id === updated.callerDeviceId ? updated.calleeDeviceId : updated.callerDeviceId;
    await this.realtime.sendToDevice(otherDeviceId, 'call_accepted', { session_id: updated.id });
    return this.serialize(updated);
  }

  async end(dto: EndCallDto) {
    const session = await this.getSession(dto.session_id);
    if (![session.callerDeviceId, session.calleeDeviceId].includes(dto.device_id)) {
      throw forbidden('Device is not part of this session');
    }

    const updated = await this.prisma.callSession.update({
      where: { id: session.id },
      data: { status: CallStatus.ended, endedAt: new Date(), endReason: dto.reason ?? 'ended_by_device' },
    });
    await this.redis.client.del(`session:${updated.id}`);
    await Promise.all([
      this.realtime.sendToDevice(updated.callerDeviceId, 'call_ended', {
        session_id: updated.id,
        reason: updated.endReason,
      }),
      this.realtime.sendToDevice(updated.calleeDeviceId, 'call_ended', {
        session_id: updated.id,
        reason: updated.endReason,
      }),
    ]);
    return this.serialize(updated);
  }

  async getActiveSession(sessionId: string) {
    return this.getSession(sessionId);
  }

  async getSessionForDevice(sessionId: string, deviceId: string) {
    const session = await this.getSession(sessionId);
    if (![session.callerDeviceId, session.calleeDeviceId].includes(deviceId)) {
      throw forbidden('Device is not part of this session');
    }
    return this.serialize(session);
  }

  private async startFromRaspberry(dto: StartCallDto, caller: Device) {
    if (!dto.contact_id) {
      throw badRequest('contact_id is required when Raspberry Pi starts a call');
    }
    const contact = await this.prisma.contact.findFirst({
      where: { id: dto.contact_id, raspberryDeviceId: caller.id },
      include: { mobileDevice: true },
    });
    if (!contact || contact.mobileDevice.deletedAt) {
      throw notFound('Target mobile contact not found');
    }

    const session = await this.createSession(caller.id, contact.mobileDeviceId);
    const payload = {
      session_id: session.id,
      caller_name: caller.ownerName ?? 'Raspberry Pi',
      call_type: 'raspberry_to_mobile',
    };
    const delivered = await this.realtime.sendToDevice(contact.mobileDeviceId, 'incoming_call', payload);
    if (!delivered) {
      await this.fcm.sendIncomingCall(contact.mobileDevice.fcmToken, payload);
    }
    return this.serialize(session);
  }

  private async startFromMobile(dto: StartCallDto, caller: Device) {
    if (dto.to !== 'raspberry') {
      throw badRequest('Mobile calls must set to: "raspberry"');
    }

    const pairedContact = await this.prisma.contact.findFirst({
      where: {
        mobileDeviceId: caller.id,
        raspberryDevice: {
          deviceType: DeviceType.raspberry,
          deletedAt: null,
        },
      },
      include: { raspberryDevice: true },
      orderBy: { createdAt: 'desc' },
    });

    const raspberry = pairedContact?.raspberryDevice ?? (await this.devices.findRaspberry());
    if (!raspberry) {
      throw notFound('Raspberry Pi device not found');
    }
    if (!(await this.realtime.isOnline(raspberry.id))) {
      throw badRequest('Raspberry Pi is offline');
    }

    const session = await this.createSession(caller.id, raspberry.id);
    await this.realtime.sendToDevice(raspberry.id, 'incoming_call', {
      session_id: session.id,
      caller_name: caller.ownerName ?? 'Mobile caller',
      call_type: 'mobile_to_raspberry',
    });
    return this.serialize(session);
  }

  private async createSession(callerDeviceId: string, calleeDeviceId: string) {
    const session = await this.prisma.callSession.create({
      data: {
        callerDeviceId,
        calleeDeviceId,
        status: CallStatus.ringing,
        serverAUrl: this.config.get<string>('SERVER_A_URL') ?? '',
        serverBUrl: this.config.get<string>('SERVER_B_URL') ?? '',
      },
    });
    await this.cacheSession(session);
    return session;
  }

  private async getSession(sessionId: string) {
    const cached = await this.redis.client.get(`session:${sessionId}`);
    if (cached) {
      return JSON.parse(cached) as CallSession;
    }
    const session = await this.prisma.callSession.findUnique({ where: { id: sessionId } });
    if (!session) {
      throw notFound('Session not found');
    }
    await this.cacheSession(session);
    return session;
  }

  private async cacheSession(session: CallSession) {
    await this.redis.client.set(`session:${session.id}`, JSON.stringify(session), 'EX', 86400);
  }

  private serialize(session: CallSession) {
    return {
      session_id: session.id,
      caller_device_id: session.callerDeviceId,
      callee_device_id: session.calleeDeviceId,
      status: session.status,
      started_at: session.startedAt,
      answered_at: session.answeredAt,
      ended_at: session.endedAt,
      server_a_url: session.serverAUrl,
      server_b_url: session.serverBUrl,
    };
  }
}
