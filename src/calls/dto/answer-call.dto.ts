import { IsUUID } from 'class-validator';

export class AnswerCallDto {
  @IsUUID()
  session_id: string;

  @IsUUID()
  device_id: string;
}
