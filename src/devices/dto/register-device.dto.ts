import { IsEnum, IsOptional, IsString, MinLength, ValidateIf } from 'class-validator';
import { DeviceType } from '@prisma/client';

export class RegisterDeviceDto {
  @IsEnum(DeviceType)
  device_type: DeviceType;

  @ValidateIf((dto: RegisterDeviceDto) => dto.device_type === DeviceType.mobile)
  @IsString()
  @MinLength(1)
  owner_name?: string;

  @IsOptional()
  @IsString()
  fcm_token?: string;
}
