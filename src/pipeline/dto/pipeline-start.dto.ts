import { IsUUID } from 'class-validator';

export class PipelineStartDto {
  @IsUUID()
  session_id: string;
}
