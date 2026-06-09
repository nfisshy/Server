import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as admin from 'firebase-admin';

@Injectable()
export class FcmService {
  private readonly logger = new Logger(FcmService.name);
  private enabled = false;

  constructor(config: ConfigService) {
    const raw = config.get<string>('FCM_SERVICE_ACCOUNT_JSON');
    if (!raw) {
      this.enabled = false;
      return;
    }

    const credential = admin.credential.cert(JSON.parse(raw));
    if (admin.apps.length === 0) {
      admin.initializeApp({ credential });
    }
    this.enabled = true;
  }

  async sendIncomingCall(token: string | null, payload: {
    session_id: string;
    caller_name: string;
    call_type: string;
  }) {
    if (!this.enabled) {
      this.logger.error('FCM NOT CONFIGURED');
      return false;
    }

    if (!token) {
      this.logger.error('TARGET DEVICE HAS NO FCM TOKEN');
      return false;
    }

      await admin.messaging().send({
        token,
        data: payload,
        android: {
          priority: 'high',
          ttl: 120000,
        },
        apns: { payload: { aps: { contentAvailable: true, sound: 'default' } } },
      });
    return true;
  }
}
