import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { notFound } from '../common/errors';

@Injectable()
export class ContactsService {
  constructor(private readonly prisma: PrismaService) {}

  async listForRaspberry(raspberryDeviceId: string) {
    return this.prisma.contact.findMany({
      where: { raspberryDeviceId },
      include: {
        mobileDevice: {
          select: { id: true, ownerName: true, fcmToken: true, createdAt: true, updatedAt: true },
        },
      },
      orderBy: { createdAt: 'asc' },
    });
  }

  async remove(contactId: string, raspberryDeviceId: string) {
    const contact = await this.prisma.contact.findFirst({
      where: { id: contactId, raspberryDeviceId },
    });
    if (!contact) {
      throw notFound('Contact not found for this Raspberry Pi');
    }

    await this.prisma.contact.delete({ where: { id: contactId } });
    await this.prisma.auditLog.create({
      data: { actorId: raspberryDeviceId, action: 'contact.removed', metadata: { contact_id: contactId } },
    });
    return { removed: true };
  }
}
