import { BadRequestException, ForbiddenException, NotFoundException } from '@nestjs/common';

export const notFound = (message: string) => new NotFoundException({ message });
export const badRequest = (message: string) => new BadRequestException({ message });
export const forbidden = (message: string) => new ForbiddenException({ message });
