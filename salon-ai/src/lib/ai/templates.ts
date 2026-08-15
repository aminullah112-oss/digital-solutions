import type { AIReplyContext, AIReplyResult } from "./provider";
import { formatRupees } from "@/lib/utils";

const AR_GREETINGS = ["اهلا", "أهلاً"];

function isArabic(lang: string) {
  return lang === "AR" || lang === "MIXED";
}

export async function buildTemplateReply(ctx: AIReplyContext): Promise<AIReplyResult> {
  const ar = isArabic(ctx.language);
  const name = ctx.customerName.split(" ")[0];

  switch (ctx.intent) {
    case "PRICE_INQUIRY": {
      if (ctx.serviceName && ctx.servicePrice) {
        return {
          confidence: 0.9,
          text: ar
            ? `أهلاً ${name}! ${ctx.serviceName} يبدأ من ${formatRupees(ctx.servicePrice)}. تحبين أشوف لك موعد متاح؟`
            : `Hi ${name}! ${ctx.serviceName} starts from ${formatRupees(ctx.servicePrice)}. Would you like me to check available appointments?`,
        };
      }
      return {
        confidence: 0.6,
        text: ar
          ? `أهلاً ${name}، تقدر تخبرني أي خدمة يهمك عشان أعطيك السعر بالضبط؟`
          : `Hi ${name}, could you tell me which service you're interested in so I can share the exact price?`,
      };
    }
    case "AVAILABILITY":
      return {
        confidence: 0.85,
        text: ar
          ? `أكيد، خليني أتحقق من المواعيد المتاحة${ctx.serviceName ? ` لـ${ctx.serviceName}` : ""} وأرجع لك بأقرب وقت.`
          : `Sure — let me check availability${ctx.serviceName ? ` for ${ctx.serviceName}` : ""} and get back to you with the nearest slots.`,
      };
    case "BOOKING":
      return {
        confidence: 0.9,
        text: ar
          ? `رائع ${name}! خليني أثبت لك الحجز${ctx.serviceName ? ` لـ${ctx.serviceName}` : ""}. تفضلين تاريخ ووقت معين؟`
          : `Great, ${name}! Let's get ${ctx.serviceName ?? "your appointment"} booked. Do you have a preferred date and time?`,
      };
    case "SERVICE_INFORMATION":
      return {
        confidence: 0.75,
        text: ar
          ? `${ctx.serviceName ?? "هذه الخدمة"} من أشهر خدماتنا في ${ctx.businessName}. ${ctx.knowledgeSnippet}`
          : `${ctx.serviceName ?? "That service"} is one of our most popular treatments at ${ctx.businessName}. ${ctx.knowledgeSnippet}`,
      };
    case "PROMOTION":
      return {
        confidence: 0.7,
        text: ar
          ? `عندنا عروض حالية! ${ctx.knowledgeSnippet}`
          : `We do have current promotions running! ${ctx.knowledgeSnippet}`,
      };
    case "CANCELLATION":
      return {
        confidence: 0.75,
        text: ar
          ? `لا مشكلة، بلغني رقم الحجز أو الاسم والوقت وبساعدك تلغين الموعد.`
          : `No problem — share your booking reference or the name/time on the appointment and I'll help you cancel it.`,
      };
    case "RESCHEDULE":
      return {
        confidence: 0.75,
        text: ar
          ? `تمام، تحبين تنقلين الموعد ليوم أو وقت ثاني؟ خبريني الوقت المناسب.`
          : `Sure — what date or time would work better for you? I'll move your appointment.`,
      };
    case "GENERAL_INQUIRY":
    default:
      return {
        confidence: 0.55,
        text: ar
          ? `${AR_GREETINGS[0]} ${name}! كيف أقدر أساعدك اليوم؟`
          : `Hi ${name}! How can I help you today — services, pricing, or booking an appointment?`,
      };
  }
}
