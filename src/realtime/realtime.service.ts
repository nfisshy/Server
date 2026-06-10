import { Injectable, Logger } from '@nestjs/common';
import { Server } from 'socket.io';
import { CallSession, CallStatus } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import { RedisService } from '../redis/redis.service';

@Injectable()
export class RealtimeService {
  private readonly logger = new Logger(RealtimeService.name);
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
      .sadd(`device:sockets:${deviceId}`, socketId)
      .expire(`device:sockets:${deviceId}`, 75)
      .set(`socket:${socketId}`, deviceId, 'EX', 75)
      .exec();
    this.logger.log(`ONLINE device=${deviceId} socket=${socketId}`);
  }

  async markOfflineBySocket(socketId: string) {
    const deviceId = await this.redis.client.get(`socket:${socketId}`);
    if (!deviceId) {
      return;
    }
    const currentSocketId = await this.redis.client.get(`device:online:${deviceId}`);
    const tx = this.redis.client.multi().del(`socket:${socketId}`).srem(`device:sockets:${deviceId}`, socketId);
    if (currentSocketId === socketId) {
      const remaining = await this.redis.client.smembers(`device:sockets:${deviceId}`);
      const nextSocketId = remaining.find((id) => id !== socketId && this.server?.sockets.sockets.has(id));
      if (nextSocketId) {
        tx.set(`device:online:${deviceId}`, nextSocketId, 'EX', 75);
      } else {
        tx.del(`device:online:${deviceId}`);
      }
    }
    await tx.exec();
    this.logger.log(`OFFLINE socket=${socketId} device=${deviceId}`);
  }

  async heartbeat(deviceId: string, socketId: string) {
    await this.markOnline(deviceId, socketId);
  }

  async isOnline(deviceId: string) {
    return (await this.getLiveSocketIds(deviceId)).length > 0;
  }

  async sendToDevice(deviceId: string, event: string, payload: Record<string, unknown>) {
    if (!this.server) {
      this.logger.warn(`SEND ${event} device=${deviceId} failed: server_not_bound`);
      return false;
    }
    const socketIds = await this.getLiveSocketIds(deviceId);
    if (socketIds.length === 0) {
      this.logger.warn(`SEND ${event} device=${deviceId} failed: no_live_socket`);
      return false;
    }
    for (const socketId of socketIds) {
      this.server.to(socketId).emit(event, payload);
    }
    this.logger.log(`SEND ${event} device=${deviceId} sockets=${socketIds.length} payload=${this.shortPayload(payload)}`);
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
    this.logger.log(`CALL_SIGNAL session=${sessionId} from=${fromDeviceId} to=${targetDeviceId} type=${signalType}`);
    return this.sendToDevice(targetDeviceId, 'peer_signal', {
      session_id: session.id,
      from_device_id: fromDeviceId,
      signal_type: signalType,
      sent_at: new Date().toISOString(),
      ...payload,
    });
  }

  private async getLiveSocketIds(deviceId: string) {
    if (!this.server) {
      return [];
    }
    const socketIds = new Set<string>();
    const latestSocketId = await this.redis.client.get(`device:online:${deviceId}`);
    if (latestSocketId) {
      socketIds.add(latestSocketId);
    }
    for (const socketId of await this.redis.client.smembers(`device:sockets:${deviceId}`)) {
      socketIds.add(socketId);
    }

    const liveSocketIds = [...socketIds].filter((socketId) => this.server!.sockets.sockets.has(socketId));
    const staleSocketIds = [...socketIds].filter((socketId) => !liveSocketIds.includes(socketId));
    if (staleSocketIds.length > 0) {
      const tx = this.redis.client.multi();
      for (const socketId of staleSocketIds) {
        tx.srem(`device:sockets:${deviceId}`, socketId).del(`socket:${socketId}`);
      }
      if (latestSocketId && staleSocketIds.includes(latestSocketId)) {
        if (liveSocketIds[0]) {
          tx.set(`device:online:${deviceId}`, liveSocketIds[0], 'EX', 75);
        } else {
          tx.del(`device:online:${deviceId}`);
        }
      }
      await tx.exec();
      this.logger.warn(`CLEAN_STALE_SOCKETS device=${deviceId} stale=${staleSocketIds.length}`);
    }
    return liveSocketIds;
  }

  private shortPayload(payload: Record<string, unknown>) {
    const sessionId = payload.session_id ? ` session=${payload.session_id}` : '';
    const type = payload.signal_type ? ` type=${payload.signal_type}` : '';
    const callType = payload.call_type ? ` call_type=${payload.call_type}` : '';
    return `${sessionId}${type}${callType}`.trim();
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
