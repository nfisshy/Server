import { Module } from '@nestjs/common';
import { AuthModule } from '../auth/auth.module';
import { DevicesModule } from '../devices/devices.module';
import { FcmModule } from '../fcm/fcm.module';
import { RealtimeModule } from '../realtime/realtime.module';
import { CallsController } from './calls.controller';
import { CallsService } from './calls.service';

@Module({
  imports: [AuthModule, DevicesModule, FcmModule, RealtimeModule],
  controllers: [CallsController],
  providers: [CallsService],
  exports: [CallsService],
})
export class CallsModule {}
