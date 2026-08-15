import { prisma } from "@/lib/db/prisma";
import type { ServiceLexicon } from "./nlp";

export async function getServiceLexicon(): Promise<ServiceLexicon[]> {
  const services = await prisma.service.findMany({ where: { active: true }, orderBy: { name: "asc" } });
  return services.map((s) => ({
    id: s.id,
    name: s.name,
    price: s.price,
    keywords: [s.category, s.nameAr ?? ""].filter(Boolean),
  }));
}

export async function getBusinessSettings() {
  let settings = await prisma.businessSettings.findUnique({ where: { id: "default" } });
  if (!settings) {
    settings = await prisma.businessSettings.create({
      data: {
        id: "default",
        salonName: "Lumière Salon & Spa",
        address: "Al Olaya District, Riyadh, Saudi Arabia",
        phone: "+966 50 123 4567",
        openingHours: { sat_thu: "10:00 - 22:00", fri: "16:00 - 22:00" },
        socials: { instagram: "@lumiere.riyadh", whatsapp: "+966501234567" },
        channelsEnabled: { whatsapp: true, instagram: true, facebook: true, website: true },
      },
    });
  }
  return settings;
}

export async function getActivePromotionSnippet(serviceId: string | null): Promise<string> {
  const now = new Date();
  const promo = await prisma.promotion.findFirst({
    where: {
      active: true,
      startDate: { lte: now },
      endDate: { gte: now },
      ...(serviceId ? { services: { some: { serviceId } } } : {}),
    },
  });
  if (!promo) return "Let me know if you'd like the full price list or to book an appointment.";
  return `We currently have "${promo.name}" — ${promo.discountPct}% off, running until ${promo.endDate.toDateString()}.`;
}

export async function findFaqAnswer(text: string): Promise<string | null> {
  const faqs = await prisma.fAQ.findMany();
  const lower = text.toLowerCase();
  const hit = faqs.find((f) => lower.includes(f.question.toLowerCase().slice(0, 12)));
  return hit?.answer ?? null;
}
