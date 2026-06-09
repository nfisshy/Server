import { Injectable } from '@nestjs/common';
import { Server } from 'socket.io';
import { RedisService } from '../redis/redis.service';

@Injectable()
export class RealtimeService {
  private server?: Server;

  constructor(private readonly redis: RedisService) {}

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
}
