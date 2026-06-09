import { IsIn, IsOptional, IsUUID } from 'class-validator';

export class StartCallDto {
  @IsUUID()
  from_device_id: string;

  @IsOptional()
  @IsUUID()
  contact_id?: string;

  @IsOptional()
  @IsIn(['raspberry'])
  to?: 'raspberry';
}
