import {
  ConnectedSocket,
  MessageBody,
  OnGatewayConnection,
  OnGatewayDisconnect,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Logger } from '@nestjs/common';
import { Server, Socket } from 'socket.io';
import { AuthService } from '../auth/auth.service';
import { RealtimeService } from './realtime.service';

interface AuthedSocket extends Socket {
  deviceId?: string;
}

@WebSocketGateway({
  cors: { origin: '*' },
  path: '/ws',
})
export class RealtimeGateway implements OnGatewayConnection, OnGatewayDisconnect {
  private readonly logger = new Logger(RealtimeGateway.name);

  @WebSocketServer()
  server!: Server;

  constructor(
    private readonly auth: AuthService,
    private readonly realtime: RealtimeService,
  ) {}

  afterInit(server: Server) {
    this.realtime.bindServer(server);
  }

  async handleConnection(client: AuthedSocket) {
    try {
      const deviceId = String(client.handshake.auth?.device_id ?? client.handshake.query?.device_id ?? '');
      const token = String(client.handshake.auth?.auth_token ?? client.handshake.query?.auth_token ?? '');
      if (!deviceId || !token) {
        client.disconnect(true);
        return;
      }
      await this.auth.verifyDeviceToken(deviceId, token);
      client.deviceId = deviceId;
      await this.realtime.markOnline(deviceId, client.id);
    } catch (error) {
      this.logger.warn(`Socket rejected: ${error instanceof Error ? error.message : String(error)}`);
      client.disconnect(true);
    }
  }

  async handleDisconnect(client: AuthedSocket) {
    await this.realtime.markOfflineBySocket(client.id);
  }

  @SubscribeMessage('heartbeat')
  async heartbeat(
    @ConnectedSocket() client: AuthedSocket,
    @MessageBody() body: { device_id?: string },
  ) {
    const deviceId = client.deviceId ?? body.device_id;
    if (!deviceId || deviceId !== client.deviceId) {
      client.disconnect(true);
      return;
    }
    await this.realtime.heartbeat(deviceId, client.id);
    client.emit('heartbeat_ack', {});
  }

  @SubscribeMessage('call_signal')
  async callSignal(
    @ConnectedSocket() client: AuthedSocket,
    @MessageBody() body: { session_id?: string; signal_type?: string; [key: string]: unknown },
  ) {
    if (!client.deviceId || !body.session_id || !body.signal_type) {
      client.disconnect(true);
      return;
    }
    await this.realtime.routeCallSignal(client.deviceId, body.session_id, body.signal_type, body);
  }
}
