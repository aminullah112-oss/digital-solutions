export const SIMULATED_MESSAGES: string[] = [
  "Hi! Do you have availability for a haircut tomorrow at 4pm?",
  "How much is the hydrafacial?",
  "Can I book balayage this Thursday at 2pm please",
  "What are your opening hours today?",
  "Do you have any promotions on hair coloring right now?",
  "I'd like to book a gel manicure, is 5pm free today?",
  "Tell me more about the keratin treatment",
  "Is parking available near the salon?",
  "I need to reschedule my appointment to next week",
  "Can I cancel my Friday booking please",
  "This is really disappointing, I've been waiting for 30 minutes with no update",
  "مرحبا كم سعر تنظيف البشرة؟",
  "Do you accept walk-ins on weekends?",
  "I want to book bridal makeup, do you have this Saturday free?",
  "How much is a full body massage?",
  "Can I get the same stylist as last time for my haircut tomorrow?",
  "I want a refund, I'm not happy with how my color turned out",
  "What products do you use for facials?",
  "Do you have Moroccan bath available this weekend?",
  "thanks so much, can I book the same service again next Tuesday at 3pm",
];

export const SIMULATED_CHANNELS = ["WHATSAPP", "INSTAGRAM", "FACEBOOK", "WEBSITE"] as const;

const FIRST_NAMES = ["Sara", "Noura", "Lina", "Huda", "Rima", "Dana", "Alanoud", "Ohoud", "Basma", "Njoud", "Aljohara", "Ftoon"];
const LAST_NAMES = ["Al-Otaibi", "Al-Harbi", "Al-Ghamdi", "Al-Qahtani", "Al-Zahrani", "Al-Shehri", "Al-Mutairi", "Al-Dosari"];

export function randomNewCustomerName() {
  const f = FIRST_NAMES[Math.floor(Math.random() * FIRST_NAMES.length)];
  const l = LAST_NAMES[Math.floor(Math.random() * LAST_NAMES.length)];
  return `${f} ${l}`;
}
