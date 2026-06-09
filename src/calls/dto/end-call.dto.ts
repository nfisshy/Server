import { IsOptional, IsString, IsUUID } from 'class-validator';

export class EndCallDto {
  @IsUUID()
  session_id: string;

  @IsUUID()
  device_id: string;

  @IsOptional()
  @IsString()
  reason?: string;
}
