import "dotenv/config";
import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";
import { processInboundMessage } from "../src/lib/ai/pipeline";
import { scanForFollowUps } from "../src/lib/ai/followup";

const prisma = new PrismaClient();

async function hash(pw: string) {
  return bcrypt.hash(pw, 10);
}

async function main() {
  console.log("Seeding Salon AI Command Center demo data...");

  // ── Clean slate ──────────────────────────────────────────────────────
  await prisma.$transaction([
    prisma.analyticsEvent.deleteMany(),
    prisma.aiEvent.deleteMany(),
    prisma.humanHandoff.deleteMany(),
    prisma.followUp.deleteMany(),
    prisma.leadScore.deleteMany(),
    prisma.lead.deleteMany(),
    prisma.booking.deleteMany(),
    prisma.message.deleteMany(),
    prisma.conversationTag.deleteMany(),
    prisma.conversation.deleteMany(),
    prisma.customer.deleteMany(),
    prisma.campaign.deleteMany(),
    prisma.promotionService.deleteMany(),
    prisma.promotion.deleteMany(),
    prisma.fAQ.deleteMany(),
    prisma.policy.deleteMany(),
    prisma.staffService.deleteMany(),
    prisma.staff.deleteMany(),
    prisma.auditLog.deleteMany(),
    prisma.user.deleteMany(),
    prisma.businessSettings.deleteMany(),
    prisma.service.deleteMany(),
  ]);

  // ── Business settings ────────────────────────────────────────────────
  await prisma.businessSettings.create({
    data: {
      id: "default",
      salonName: "Lumière Salon & Spa",
      address: "Al Olaya District, Riyadh, Saudi Arabia",
      phone: "+966 50 123 4567",
      openingHours: { sat_thu: "10:00 - 22:00", fri: "16:00 - 22:00" },
      socials: { instagram: "@lumiere.riyadh", whatsapp: "+966501234567" },
      aiMode: "ASSISTED",
      demoMode: true,
      channelsEnabled: { whatsapp: true, instagram: true, facebook: true, website: true },
    },
  });

  // ── Users (auth) ──────────────────────────────────────────────────────
  const [adminUser, managerUser, staffUser] = await Promise.all([
    prisma.user.create({
      data: { name: "Aminah Al-Faisal", email: "admin@lumiere.sa", passwordHash: await hash("salon123"), role: "ADMIN" },
    }),
    prisma.user.create({
      data: { name: "Yousef Al-Amri", email: "manager@lumiere.sa", passwordHash: await hash("salon123"), role: "MANAGER" },
    }),
    prisma.user.create({
      data: { name: "Reem Al-Otaibi", email: "staff@lumiere.sa", passwordHash: await hash("salon123"), role: "STAFF" },
    }),
  ]);

  // ── Services ─────────────────────────────────────────────────────────
  const serviceDefs = [
    { name: "Haircut & Blow Dry", nameAr: "قص وتصفيف الشعر", description: "Precision cut and professional blow-dry finish.", price: 600, durationMin: 45, category: "Hair" },
    { name: "Hair Coloring", nameAr: "صبغة شعر", description: "Full color service using ammonia-free formulas.", price: 3500, durationMin: 150, category: "Hair" },
    { name: "Balayage & Highlights", nameAr: "بالياج وهايلايت", description: "Hand-painted highlights for a natural sun-kissed look.", price: 5500, durationMin: 180, category: "Hair" },
    { name: "Keratin Treatment", nameAr: "كيراتين", description: "Smoothing treatment that reduces frizz for up to 4 months.", price: 6500, durationMin: 180, category: "Hair" },
    { name: "Hair Styling", nameAr: "تصفيف الشعر", description: "Blow-dry, curls, or updo styling for any occasion.", price: 900, durationMin: 45, category: "Hair" },
    { name: "Classic Manicure", nameAr: "مانيكير كلاسيك", description: "Nail shaping, cuticle care, and polish.", price: 400, durationMin: 40, category: "Nails" },
    { name: "Gel Manicure", nameAr: "مانيكير جل", description: "Long-lasting gel polish manicure.", price: 700, durationMin: 50, category: "Nails" },
    { name: "Spa Pedicure", nameAr: "بديكير سبا", description: "Relaxing foot soak, exfoliation, and polish.", price: 800, durationMin: 60, category: "Nails" },
    { name: "Classic Facial", nameAr: "تنظيف بشرة كلاسيكي", description: "Deep cleansing facial suited to all skin types.", price: 1200, durationMin: 60, category: "Skin" },
    { name: "Hydrafacial", nameAr: "هايدرافيشل", description: "Medical-grade hydradermabrasion for instant glow.", price: 3800, durationMin: 75, category: "Skin" },
    { name: "Full Body Massage", nameAr: "مساج كامل الجسم", description: "60-minute relaxation massage with aromatic oils.", price: 2200, durationMin: 60, category: "Spa" },
    { name: "Moroccan Bath", nameAr: "حمام مغربي", description: "Traditional exfoliating bath and steam ritual.", price: 1800, durationMin: 90, category: "Spa" },
    { name: "Bridal Makeup", nameAr: "مكياج عروس", description: "Full bridal makeup with trial session included.", price: 35000, durationMin: 120, category: "Makeup" },
    { name: "Party Makeup", nameAr: "مكياج سهرة", description: "Glam makeup application for events.", price: 6000, durationMin: 60, category: "Makeup" },
    { name: "Waxing (Arms & Legs)", nameAr: "إزالة شعر بالشمع", description: "Full arms and legs waxing.", price: 900, durationMin: 45, category: "Skin" },
  ];
  const services = await Promise.all(
    serviceDefs.map((s) => prisma.service.create({ data: { ...s, active: true } }))
  );
  const svc = (name: string) => services.find((s) => s.name === name)!;

  // ── Staff ────────────────────────────────────────────────────────────
  const staffDefs = [
    { name: "Aisha Al-Rashid", role: "Senior Colorist", cats: ["Hair"], workingHours: "Sat-Thu 10:00-19:00" },
    { name: "Noor Abdullah", role: "Nail Artist", cats: ["Nails"], workingHours: "Sat-Thu 11:00-20:00" },
    { name: "Fatima Al-Zahrani", role: "Esthetician", cats: ["Skin", "Spa"], workingHours: "Sat-Thu 10:00-19:00" },
    { name: "Layla Hassan", role: "Makeup Artist", cats: ["Makeup"], workingHours: "Sat-Thu 12:00-22:00" },
    { name: "Reem Al-Otaibi", role: "Senior Stylist", cats: ["Hair"], workingHours: "Sat-Thu 10:00-19:00", userId: staffUser.id },
    { name: "Mariam Youssef", role: "Massage Therapist", cats: ["Spa"], workingHours: "Sat-Thu 11:00-20:00" },
  ];
  for (const s of staffDefs) {
    const staff = await prisma.staff.create({
      data: { name: s.name, role: s.role, workingHours: s.workingHours, userId: (s as any).userId },
    });
    const matching = services.filter((sv) => s.cats.includes(sv.category));
    await prisma.staffService.createMany({ data: matching.map((m) => ({ staffId: staff.id, serviceId: m.id })) });
  }

  // ── FAQs ─────────────────────────────────────────────────────────────
  await prisma.fAQ.createMany({
    data: [
      { question: "What are your opening hours?", answer: "We're open Saturday to Thursday 10AM-10PM, and Friday 4PM-10PM.", category: "general" },
      { question: "Do you accept walk-ins?", answer: "We recommend booking ahead, but walk-ins are welcome subject to availability.", category: "booking" },
      { question: "Where are you located?", answer: "We're in Al Olaya District, Riyadh — 5 minutes from Kingdom Centre.", category: "general" },
      { question: "Do you offer bridal packages?", answer: "Yes! Our bridal package includes a trial session, hair, and makeup — ask us for current pricing.", category: "services" },
      { question: "Is parking available?", answer: "Yes, free valet parking is available at the building entrance.", category: "general" },
      { question: "Can I bring my own products?", answer: "Of course — just let your stylist know when you arrive.", category: "policy" },
      { question: "Do you use organic products?", answer: "We use a mix of premium organic and dermatologist-tested product lines.", category: "services" },
      { question: "Is there a men's section?", answer: "Lumière is a women-only salon.", category: "general" },
    ],
  });

  // ── Policies ─────────────────────────────────────────────────────────
  await prisma.policy.createMany({
    data: [
      { type: "cancellation", title: "Cancellation Policy", content: "Cancellations within 4 hours of the appointment incur a 50% charge." },
      { type: "refund", title: "Refund Policy", content: "Service dissatisfaction is reviewed case-by-case within 48 hours of the visit." },
      { type: "late_arrival", title: "Late Arrival Policy", content: "Arrivals more than 15 minutes late may need to be rescheduled." },
      { type: "booking", title: "Booking Policy", content: "Bookings can be made via WhatsApp, Instagram, Facebook, our website, or by phone." },
      { type: "payment", title: "Payment Policy", content: "We accept cash, all major cards, mada, and Apple Pay." },
    ],
  });

  // ── Promotions ───────────────────────────────────────────────────────
  const now = new Date();
  const inDays = (d: number) => new Date(now.getTime() + d * 86_400_000);
  await prisma.promotion.create({
    data: {
      name: "Hair Color Refresh Week",
      description: "20% off all hair coloring and balayage services",
      discountPct: 20,
      startDate: inDays(-5),
      endDate: inDays(10),
      active: true,
      services: { create: [{ serviceId: svc("Hair Coloring").id }, { serviceId: svc("Balayage & Highlights").id }] },
    },
  });
  await prisma.promotion.create({
    data: {
      name: "Bridal Season Offer",
      description: "Complimentary trial session with every Bridal Makeup booking",
      discountPct: 10,
      startDate: inDays(-10),
      endDate: inDays(30),
      active: true,
      services: { create: [{ serviceId: svc("Bridal Makeup").id }] },
    },
  });

  console.log("Business, users, services, staff, knowledge base seeded.");

  // ── Customers + realistic AI-processed conversations ───────────────────
  type Scenario = {
    name: string;
    phone: string;
    channel: "WHATSAPP" | "INSTAGRAM" | "FACEBOOK" | "WEBSITE";
    previousCustomer?: boolean;
    turns: string[];
    stale?: boolean; // if true, backdate lastMessageAt so it qualifies for follow-up
    daysAgo?: number; // when the conversation happened
  };

  const scenarios: Scenario[] = [
    { name: "Sarah Al-Qahtani", phone: "+966501110001", channel: "INSTAGRAM", turns: ["Hi! Do you have hair coloring available tomorrow at 6pm? I'd like to book please"] },
    { name: "Noor Al-Harbi", phone: "+966501110002", channel: "WHATSAPP", turns: ["Hi, how much is a facial?", "Ok what about the Hydrafacial specifically?"] },
    { name: "Aisha Mohammed", phone: "+966501110003", channel: "INSTAGRAM", turns: ["This is honestly the worst service I've had, I waited 40 minutes past my appointment and nobody apologized. Unacceptable."] },
    { name: "Maryam Al-Otaibi", phone: "+966501110004", channel: "WHATSAPP", turns: ["Hi! Are you free this Thursday for hair styling? I have an event", "6pm works, can we book it"] },
    { name: "Fatima Al-Zahrani", phone: "+966501110005", channel: "FACEBOOK", turns: ["What are your opening hours?", "Great, thank you! And are you open on Fridays too?"] },
    { name: "Layla Al-Ghamdi", phone: "+966501110006", channel: "WEBSITE", turns: ["Do you have any current offers on bridal makeup?", "Perfect, how do I reserve a trial session?"] },
    { name: "Reem Al-Dosari", phone: "+966501110007", channel: "WHATSAPP", turns: ["I need to cancel my appointment for Friday please", "It's under my name, thank you for your help"] },
    { name: "Hessa Al-Mutairi", phone: "+966501110008", channel: "INSTAGRAM", turns: ["Can I move my Saturday appointment to Sunday instead?", "Sunday 5pm would be perfect"] },
    { name: "Lama Al-Shammari", phone: "+966501110009", channel: "WHATSAPP", turns: ["مرحبا، كم سعر صبغة الشعر؟", "تمام شكرا، ممكن احجز بكرة الساعة 5"] },
    { name: "Dana Al-Subaie", phone: "+966501110010", channel: "INSTAGRAM", previousCustomer: true, turns: ["Hey! Loved my last keratin treatment 😍 want to book another one tomorrow at 5pm"] },
    { name: "Rania Al-Amri", phone: "+966501110011", channel: "WHATSAPP", turns: ["Do you have availability for a gel manicure today?", "5pm works for me, let's book it"] },
    { name: "Sara Al-Qurashi", phone: "+966501110012", channel: "FACEBOOK", turns: ["Tell me more about your keratin treatment", "Sounds great, how much does it cost?"] },
    { name: "Nada Al-Harthi", phone: "+966501110013", channel: "WEBSITE", turns: ["I want a refund, my hair color came out completely wrong and the stylist was rude about it"] },
    { name: "Amal Al-Rashidi", phone: "+966501110014", channel: "WHATSAPP", turns: ["Hi, do you do Moroccan bath?", "How much is it and can I book Thursday 7pm"] },
    { name: "Wafa Al-Balawi", phone: "+966501110015", channel: "INSTAGRAM", turns: ["Is there parking near the salon?", "Perfect, thank you!"] },
    { name: "Haifa Al-Zahrani", phone: "+966501110016", channel: "WHATSAPP", turns: ["I'd like to book a full body massage tomorrow at 2pm please"] },
    { name: "Ghada Al-Ahmadi", phone: "+966501110017", channel: "INSTAGRAM", turns: ["how much is balayage"], stale: true },
    { name: "Jawaher Al-Saud", phone: "+966501110018", channel: "WHATSAPP", previousCustomer: true, turns: ["Hi again! Can I get the classic facial this Sunday at 4pm, want to book"] },
    { name: "Munira Al-Faisal", phone: "+966501110019", channel: "FACEBOOK", turns: ["do you have promotions on hair coloring right now?", "Amazing, can I come this Wednesday at 2pm?"] },
    { name: "Abeer Al-Anazi", phone: "+966501110020", channel: "WEBSITE", turns: ["I spoke to someone yesterday and was told the wrong price for waxing, I want to speak to the manager please"] },
    { name: "Shahad Al-Otaibi", phone: "+966501110021", channel: "WHATSAPP", turns: ["what is the price of party makeup"], stale: true },
    { name: "Rawan Al-Ghamdi", phone: "+966501110022", channel: "INSTAGRAM", turns: ["Are you open on Friday?", "Perfect, see you then"] },
    { name: "Lina Khalil", phone: "+966501110023", channel: "WHATSAPP", turns: ["Hi! Do you have spa pedicure available tomorrow at 11am? want to book"] },
    { name: "Yasmin Farouk", phone: "+966501110024", channel: "INSTAGRAM", turns: ["tell me about your hydrafacial treatment"], stale: true },
    { name: "Zainab Al-Hassan", phone: "+966501110025", channel: "WHATSAPP", turns: ["اهلا، ابي احجز مكياج سهرة بكرة الساعة 6"] },
    { name: "Alia Al-Mansour", phone: "+966501110026", channel: "FACEBOOK", turns: ["Do you accept walk-ins?", "Got it, I'll try to book ahead next time", "Thanks for the info!"] },
    { name: "Hanan Al-Qahtani", phone: "+966501110027", channel: "WEBSITE", previousCustomer: true, turns: ["Hi, I'm a regular here — can I book balayage this Wednesday at 3pm please"] },
    { name: "Nouf Al-Dossary", phone: "+966501110028", channel: "WHATSAPP", turns: ["how much is a classic manicure", "ok can I book it for tomorrow at 3pm"] },
    { name: "Reema Al-Harbi", phone: "+966501110029", channel: "INSTAGRAM", turns: ["This is the third time my appointment has been delayed, I'm really frustrated and considering not coming back"] },
    { name: "Tala Al-Shehri", phone: "+966501110030", channel: "WHATSAPP", turns: ["I'd like to book bridal makeup, do you have this Saturday at 12pm free?"] },
    { name: "Aliyah Bakr", phone: "+966501110031", channel: "FACEBOOK", turns: ["what products do you use, are they organic?", "great, that's exactly what I was looking for"] },
    { name: "Salma Al-Ruwaili", phone: "+966501110032", channel: "WEBSITE", turns: ["is haircut available today at 5pm, want to book"] },
    { name: "Bushra Al-Yami", phone: "+966501110033", channel: "WHATSAPP", turns: ["how much does keratin treatment cost"], stale: true },
    { name: "Manal Al-Zayed", phone: "+966501110034", channel: "INSTAGRAM", previousCustomer: true, turns: ["Hi! can I rebook my usual hydrafacial for tomorrow at 1pm"] },
    { name: "Rasha Al-Otaibi", phone: "+966501110035", channel: "WHATSAPP", turns: ["thank you so much for yesterday, the service was amazing 😍 can I book the same haircut again Thursday 4pm"] },
    { name: "Iman Al-Qurashi", phone: "+966501110036", channel: "FACEBOOK", turns: ["do you have any offers on nails", "no worries, I'll book a gel manicure anyway for Monday 4pm"] },
    { name: "Dalal Al-Mutlaq", phone: "+966501110037", channel: "WEBSITE", turns: ["can someone call me back, my last message wasn't answered properly and I'm not happy"] },
    { name: "Areej Al-Faraj", phone: "+966501110038", channel: "WHATSAPP", turns: ["I want to book Moroccan bath this Tuesday at 5pm please"] },
    { name: "Ruba Al-Sayed", phone: "+966501110039", channel: "INSTAGRAM", turns: ["Awful experience today, the staff was rude and my appointment was a complete waste of time. I'm disappointed and angry"] },
    { name: "Deema Al-Qassab", phone: "+966501110040", channel: "WHATSAPP", turns: ["I want a refund for my last visit, it was terrible and I want to complain formally"] },
  ];

  let bookingsCreated = 0;
  let complaintsCreated = 0;

  for (const scenario of scenarios) {
    const customer = await prisma.customer.create({
      data: {
        name: scenario.name,
        phone: scenario.phone,
        source: scenario.channel,
        status: "NEW",
        totalBookings: scenario.previousCustomer ? 2 : 0,
        totalSpend: scenario.previousCustomer ? 6500 : 0,
        lastVisitAt: scenario.previousCustomer ? inDays(-20) : null,
      },
    });

    const conversation = await prisma.conversation.create({
      data: { customerId: customer.id, channel: scenario.channel, status: "OPEN" },
    });
    await prisma.customer.update({ where: { id: customer.id }, data: { totalConversations: { increment: 1 } } });

    let result;
    for (const text of scenario.turns) {
      result = await processInboundMessage({ conversationId: conversation.id, text });
    }

    if (result?.bookingCreated) bookingsCreated++;
    if (result?.handoffCreated) complaintsCreated++;

    if (scenario.stale) {
      const staleDate = new Date(Date.now() - 26 * 3_600_000);
      await prisma.conversation.update({ where: { id: conversation.id }, data: { lastMessageAt: staleDate } });
    }
  }

  console.log(`Processed ${scenarios.length} conversations through the AI pipeline (${bookingsCreated} bookings, ${complaintsCreated} handoffs).`);

  // ── Extra plain customers (no conversation yet) to round out the CRM ──
  const extraNames = [
    "Sumaya Al-Ghanim", "Nawal Al-Harbi", "Hind Al-Saif", "Maha Al-Rasheed", "Khadija Al-Amoudi",
    "Fajer Al-Qadi", "Rahaf Al-Enezi", "Jana Al-Fahad", "Mai Al-Rasheed", "Sahar Al-Balawi",
    "Randa Al-Osaimi", "Farah Al-Nasser",
  ];
  for (let i = 0; i < extraNames.length; i++) {
    const isActive = i % 3 === 0;
    await prisma.customer.create({
      data: {
        name: extraNames[i],
        phone: `+96650122${(1000 + i).toString().slice(-4)}`,
        source: (["WHATSAPP", "INSTAGRAM", "FACEBOOK", "WEBSITE"] as const)[i % 4],
        status: isActive ? "ACTIVE_CUSTOMER" : i % 5 === 0 ? "INACTIVE" : "LEAD",
        totalBookings: isActive ? 3 : 0,
        totalSpend: isActive ? 9500 : 0,
        totalConversations: 0,
        lastVisitAt: isActive ? inDays(-15) : null,
      },
    });
  }

  // Mark two long-time customers as VIP for CRM status diversity
  const vipCandidates = await prisma.customer.findMany({ where: { status: "ACTIVE_CUSTOMER" }, take: 2 });
  for (const c of vipCandidates) {
    await prisma.customer.update({ where: { id: c.id }, data: { status: "VIP", totalSpend: 42000, totalBookings: 8 } });
  }

  // ── A few completed / confirmed bookings with history for revenue analytics ──
  const bookedCustomers = await prisma.customer.findMany({ where: { status: { in: ["ACTIVE_CUSTOMER", "VIP"] } } });
  const staffList = await prisma.staff.findMany();
  for (const [i, c] of bookedCustomers.entries()) {
    const service = services[i % services.length];
    await prisma.booking.create({
      data: {
        customerId: c.id,
        serviceId: service.id,
        staffId: staffList[i % staffList.length].id,
        date: inDays(-10 - i),
        durationMin: service.durationMin,
        status: "COMPLETED",
        source: c.source,
        price: service.price,
        notes: "Historical visit",
      },
    });
  }

  // ── Run the follow-up scanner so stale conversations surface immediately ──
  const followUps = await scanForFollowUps({ staleAfterMs: 20 * 3_600_000, minScore: 20 });
  console.log(`Created ${followUps.length} follow-up suggestions.`);

  const counts = await Promise.all([
    prisma.customer.count(),
    prisma.conversation.count(),
    prisma.message.count(),
    prisma.lead.count(),
    prisma.booking.count(),
    prisma.humanHandoff.count(),
  ]);
  console.log(
    `Done. Customers=${counts[0]} Conversations=${counts[1]} Messages=${counts[2]} Leads=${counts[3]} Bookings=${counts[4]} Handoffs=${counts[5]}`
  );
  console.log(`Login as ${adminUser.email} / ${managerUser.email} / ${staffUser.email} — password: salon123`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
