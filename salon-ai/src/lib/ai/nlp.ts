import type { Intent, Language, Sentiment, Urgency } from "@prisma/client";

export interface ServiceLexicon {
  id: string;
  name: string;
  price: number;
  keywords: string[];
}

export interface NlpResult {
  language: Language;
  intent: Intent;
  intentConfidence: number;
  matchedServiceId: string | null;
  sentiment: Sentiment;
  urgency: Urgency;
  askedAboutService: boolean;
  askedAboutPrice: boolean;
  askedAboutAvailability: boolean;
  askedToBook: boolean;
  isComplaint: boolean;
  requestsManager: boolean;
  requestsRefund: boolean;
  extracted: {
    name: string | null;
    phone: string | null;
    email: string | null;
    preferredDate: string | null;
    preferredTime: string | null;
    budget: number | null;
  };
}

const ARABIC_RANGE = /[؀-ۿ]/;

function detectLanguage(text: string): Language {
  const hasArabic = ARABIC_RANGE.test(text);
  const hasLatin = /[a-zA-Z]/.test(text);
  if (hasArabic && hasLatin) return "MIXED";
  if (hasArabic) return "AR";
  return "EN";
}

const BOOKING_WORDS = ["book", "appointment", "reserve", "schedule", "slot", "احجز", "حجز", "موعد"];
const PRICE_WORDS = ["price", "cost", "how much", "inr", "rupees", "rs.", "rs ", "₹", "سعر", "كم سعر", "تكلفة", "روبية"];
const AVAILABILITY_WORDS = ["available", "availability", "free", "open", "tomorrow", "today", "متاح", "فاضي", "بكرة", "اليوم"];
const CANCEL_WORDS = ["cancel", "cancellation", "الغاء", "إلغاء"];
const RESCHEDULE_WORDS = ["reschedule", "change my", "move my appointment", "تأجيل", "تغيير الموعد"];
const COMPLAINT_WORDS = [
  "worst", "terrible", "awful", "angry", "disappointed", "unacceptable", "refund", "complain", "complaint",
  "rude", "waited", "waste", "sيء", "سيء", "زعلان", "غاضب", "استرجاع", "شكوى", "أسوأ",
];
const MANAGER_WORDS = ["manager", "owner", "supervisor", "مدير", "المسؤول"];
const REFUND_WORDS = ["refund", "money back", "استرداد", "استرجاع الفلوس"];
const PROMO_WORDS = ["promo", "discount", "offer", "deal", "عرض", "خصم"];
const POSITIVE_WORDS = ["thanks", "thank you", "great", "love", "perfect", "excellent", "amazing", "😍", "❤️", "👍", "شكرا", "ممتاز", "رائع", "حلو"];
const NEGATIVE_WORDS = ["bad", "not happy", "hate", "never again", "😡", "👎", "زعلانة", "مو حلو"];

function includesAny(text: string, words: string[]) {
  const lower = text.toLowerCase();
  return words.some((w) => lower.includes(w.toLowerCase()));
}

export function detectService(text: string, services: ServiceLexicon[]): string | null {
  const lower = text.toLowerCase();

  // Pass 1: exact service-name matches take priority (most specific).
  // Longest name first, so "Bridal Makeup" wins over a shorter unrelated match.
  const byNameLength = [...services].sort((a, b) => b.name.length - a.name.length);
  for (const s of byNameLength) {
    if (lower.includes(s.name.toLowerCase())) return s.id;
  }

  // Pass 2: fall back to looser keyword/category matches only if no name matched.
  for (const s of services) {
    for (const kw of s.keywords) {
      if (kw && lower.includes(kw.toLowerCase())) return s.id;
    }
  }
  return null;
}

function extractPhone(text: string): string | null {
  const match = text.match(/(?:\+?966|0)?5\d{8}\b|\+?\d[\d\s-]{7,}\d/);
  return match ? match[0].replace(/\s+/g, "") : null;
}

function extractEmail(text: string): string | null {
  const match = text.match(/[\w.+-]+@[\w-]+\.[\w.-]+/);
  return match ? match[0] : null;
}

function extractPreferredDate(text: string): string | null {
  const lower = text.toLowerCase();
  const days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
  if (lower.includes("tomorrow") || lower.includes("بكرة") || lower.includes("غدا")) return "tomorrow";
  if (lower.includes("today") || lower.includes("اليوم")) return "today";
  for (const d of days) if (lower.includes(d)) return d;
  const dateMatch = text.match(/\b(\d{1,2})[\/\-](\d{1,2})\b/);
  if (dateMatch) return dateMatch[0];
  return null;
}

function extractPreferredTime(text: string): string | null {
  const match = text.match(/\b(1[0-2]|0?[1-9])(:[0-5]\d)?\s?(am|pm|AM|PM)\b/);
  if (match) return match[0];
  const arabicTime = text.match(/الساعة\s?\d{1,2}/);
  if (arabicTime) return arabicTime[0];
  return null;
}

function extractBudget(text: string): number | null {
  const match = text.match(/(?:₹|rs\.?|inr)?\s?(\d{2,6})\s?(?:₹|rs\.?|inr|روبية)?/i);
  if (!match) return null;
  const n = Number(match[1]);
  return n >= 100 && n <= 200000 ? n : null;
}

export function runNlp(text: string, services: ServiceLexicon[]): NlpResult {
  const language = detectLanguage(text);
  const askedToBook = includesAny(text, BOOKING_WORDS);
  const askedAboutPrice = includesAny(text, PRICE_WORDS);
  const askedAboutAvailability = includesAny(text, AVAILABILITY_WORDS);
  const isCancel = includesAny(text, CANCEL_WORDS);
  const isReschedule = includesAny(text, RESCHEDULE_WORDS);
  const isComplaint = includesAny(text, COMPLAINT_WORDS);
  const requestsManager = includesAny(text, MANAGER_WORDS);
  const requestsRefund = includesAny(text, REFUND_WORDS);
  const isPromo = includesAny(text, PROMO_WORDS);
  const matchedServiceId = detectService(text, services);
  const askedAboutService = matchedServiceId !== null;

  const positive = includesAny(text, POSITIVE_WORDS);
  const negative = includesAny(text, NEGATIVE_WORDS) || isComplaint;
  const sentiment: Sentiment = negative ? "NEGATIVE" : positive ? "POSITIVE" : "NEUTRAL";

  let intent: Intent = "GENERAL_INQUIRY";
  let intentConfidence = 0.5;
  if (isComplaint || requestsRefund) {
    intent = "COMPLAINT";
    intentConfidence = 0.9;
  } else if (isCancel) {
    intent = "CANCELLATION";
    intentConfidence = 0.85;
  } else if (isReschedule) {
    intent = "RESCHEDULE";
    intentConfidence = 0.85;
  } else if (askedToBook) {
    intent = "BOOKING";
    intentConfidence = 0.9;
  } else if (askedAboutAvailability) {
    intent = "AVAILABILITY";
    intentConfidence = 0.8;
  } else if (askedAboutPrice) {
    intent = "PRICE_INQUIRY";
    intentConfidence = 0.8;
  } else if (isPromo) {
    intent = "PROMOTION";
    intentConfidence = 0.7;
  } else if (askedAboutService) {
    intent = "SERVICE_INFORMATION";
    intentConfidence = 0.7;
  } else {
    intentConfidence = 0.55;
  }

  const urgency: Urgency = isComplaint || requestsRefund ? "HIGH" : askedToBook || askedAboutAvailability ? "MEDIUM" : "LOW";

  return {
    language,
    intent,
    intentConfidence,
    matchedServiceId,
    sentiment,
    urgency,
    askedAboutService,
    askedAboutPrice,
    askedAboutAvailability,
    askedToBook,
    isComplaint,
    requestsManager,
    requestsRefund,
    extracted: {
      name: null,
      phone: extractPhone(text),
      email: extractEmail(text),
      preferredDate: extractPreferredDate(text),
      preferredTime: extractPreferredTime(text),
      budget: extractBudget(text),
    },
  };
}
