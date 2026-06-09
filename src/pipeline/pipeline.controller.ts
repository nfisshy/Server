import { Body, Controller, Post, UploadedFile, UseGuards, UseInterceptors } from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { Device } from '@prisma/client';
import { CurrentDevice } from '../auth/current-device.decorator';
import { DeviceAuthGuard } from '../auth/device-auth.guard';
import { PipelineAResultDto } from './dto/pipeline-a-result.dto';
import { PipelineBResultDto } from './dto/pipeline-b-result.dto';
import { PipelineStartDto } from './dto/pipeline-start.dto';
import { PipelineService } from './pipeline.service';

@Controller('pipeline')
export class PipelineController {
  constructor(private readonly pipeline: PipelineService) {}

  @UseGuards(DeviceAuthGuard)
  @Post('a/start')
  @UseInterceptors(FileInterceptor('file'))
  startA(
    @Body() dto: PipelineStartDto,
    @UploadedFile() file: Express.Multer.File,
    @CurrentDevice() device: Device,
  ) {
    return this.pipeline.startA(dto, file, device);
  }

  @Post('a/result')
  resultA(@Body() dto: PipelineAResultDto) {
    return this.pipeline.resultA(dto);
  }

  @UseGuards(DeviceAuthGuard)
  @Post('b/start')
  @UseInterceptors(FileInterceptor('file'))
  startB(
    @Body() dto: PipelineStartDto,
    @UploadedFile() file: Express.Multer.File,
    @CurrentDevice() device: Device,
  ) {
    return this.pipeline.startB(dto, file, device);
  }

  @Post('b/result')
  resultB(@Body() dto: PipelineBResultDto) {
    return this.pipeline.resultB(dto);
  }
}
