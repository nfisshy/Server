import { Module } from '@nestjs/common';
import { MulterModule } from '@nestjs/platform-express';
import { AuthModule } from '../auth/auth.module';
import { CallsModule } from '../calls/calls.module';
import { RealtimeModule } from '../realtime/realtime.module';
import { PipelineController } from './pipeline.controller';
import { PipelineService } from './pipeline.service';

@Module({
  imports: [
    AuthModule,
    CallsModule,
    RealtimeModule,
    MulterModule.register({
      limits: { fileSize: Number(process.env.MAX_UPLOAD_BYTES ?? 52_428_800) },
    }),
  ],
  controllers: [PipelineController],
  providers: [PipelineService],
})
export class PipelineModule {}
