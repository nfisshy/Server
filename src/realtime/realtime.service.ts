import { Injectable } from '@nestjs/common';
import { Server } from 'socket.io';
import { CallSession, CallStatus } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import { RedisService } from '../redis/redis.service';

@Injectable()
export class RealtimeService {
  private server?: Server;

  constructor(
    private readonly redis: RedisService,
    private readonly prisma: PrismaService,
  ) {}

  bindServer(server: Server) {
    this.server = server;
  }

  async markOnline(deviceId: string, socketId: string) {
    await this.redis.client
      .multi()
      .set(`device:online:${deviceId}`, socketId, 'EX', 75)
      .set(`socket:${socketId}`, deviceId, 'EX', 75)
      .exec();
  }

  async markOfflineBySocket(socketId: string) {
    const deviceId = await this.redis.client.get(`socket:${socketId}`);
    if (!deviceId) {
      return;
    }
    const currentSocketId = await this.redis.client.get(`device:online:${deviceId}`);
    const tx = this.redis.client.multi().del(`socket:${socketId}`);
    if (currentSocketId === socketId) {
      tx.del(`device:online:${deviceId}`);
    }
    await tx.exec();
  }

  async heartbeat(deviceId: string, socketId: string) {
    await this.markOnline(deviceId, socketId);
  }

  async isOnline(deviceId: string) {
    return Boolean(await this.redis.client.get(`device:online:${deviceId}`));
  }

  async sendToDevice(deviceId: string, event: string, payload: Record<string, unknown>) {
    const socketId = await this.redis.client.get(`device:online:${deviceId}`);
    if (!socketId || !this.server) {
      return false;
    }
    this.server.to(socketId).emit(event, payload);
    return true;
  }

  async routeCallSignal(
    fromDeviceId: string,
    sessionId: string,
    signalType: string,
    payload: Record<string, unknown> = {},
  ) {
    const session = await this.getSession(sessionId);
    if (!session || session.status === CallStatus.ended) {
      return false;
    }
    if (![session.callerDeviceId, session.calleeDeviceId].includes(fromDeviceId)) {
      return false;
    }

    const targetDeviceId =
      fromDeviceId === session.callerDeviceId ? session.calleeDeviceId : session.callerDeviceId;
    return this.sendToDevice(targetDeviceId, 'peer_signal', {
      session_id: session.id,
      from_device_id: fromDeviceId,
      signal_type: signalType,
      sent_at: new Date().toISOString(),
      ...payload,
    });
  }

  private async getSession(sessionId: string) {
    const cached = await this.redis.client.get(`session:${sessionId}`);
    if (cached) {
      return JSON.parse(cached) as CallSession;
    }
    const session = await this.prisma.callSession.findUnique({ where: { id: sessionId } });
    if (!session) {
      return null;
    }
    await this.redis.client.set(`session:${session.id}`, JSON.stringify(session), 'EX', 86400);
    return session;
  }
}
