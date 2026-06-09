import { IsString, IsUUID } from 'class-validator';

export class PipelineAResultDto {
  @IsUUID()
  session_id: string;

  @IsString()
  text: string;
}
