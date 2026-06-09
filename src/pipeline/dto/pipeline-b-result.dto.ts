import { IsString, IsUUID } from 'class-validator';

export class PipelineBResultDto {
  @IsUUID()
  session_id: string;

  @IsString()
  video_url: string;
}
