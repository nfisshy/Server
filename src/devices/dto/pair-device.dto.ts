import { IsString, Length, Matches, IsUUID } from 'class-validator';

export class PairDeviceDto {
  @IsString()
  @Length(6, 6)
  @Matches(/^\d{6}$/)
  pin: string;

  @IsUUID()
  mobile_device_id: string;
}
