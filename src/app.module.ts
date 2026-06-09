import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { HttpModule } from '@nestjs/axios';
import { AuthModule } from './auth/auth.module';
import { CallsModule } from './calls/calls.module';
import { ContactsModule } from './contacts/contacts.module';
import { DevicesModule } from './devices/devices.module';
import { FcmModule } from './fcm/fcm.module';
import { PipelineModule } from './pipeline/pipeline.module';
import { PrismaModule } from './prisma/prisma.module';
import { RedisModule } from './redis/redis.module';
import { RealtimeModule } from './realtime/realtime.module';
import { AppController } from './app.controller';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    HttpModule,
    PrismaModule,
    RedisModule,
    AuthModule,
    DevicesModule,
    ContactsModule,
    FcmModule,
    RealtimeModule,
    CallsModule,
    PipelineModule,
  ],
  controllers: [AppController],
})
export class AppModule {}
