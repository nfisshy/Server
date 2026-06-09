import { IsString, MinLength } from 'class-validator';

export class UpdateFcmTokenDto {
  @IsString()
  @MinLength(1)
  fcm_token: string;
}
