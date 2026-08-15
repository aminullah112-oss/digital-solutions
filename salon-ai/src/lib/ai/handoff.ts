import type { HandoffPriority, HandoffReason } from "@prisma/client";
import type { NlpResult } from "./nlp";

export interface HandoffDecision {
  required: boolean;
  reason: HandoffReason | null;
  priority: HandoffPriority;
  note: string;
}

export interface HandoffContext {
  nlp: NlpResult;
  consecutiveLowConfidenceTurns: number;
  consecutiveAiRejections: number;
}

const LOW_CONFIDENCE_THRESHOLD = 0.35;

export function evaluateHandoff(ctx: HandoffContext): HandoffDecision {
  const { nlp } = ctx;

  if (nlp.isComplaint) {
    return { required: true, reason: "COMPLAINT", priority: "HIGH", note: "Customer expressed dissatisfaction." };
  }
  if (nlp.requestsRefund) {
    return { required: true, reason: "REFUND_REQUEST", priority: "HIGH", note: "Customer asked about a refund." };
  }
  if (nlp.requestsManager) {
    return { required: true, reason: "MANAGER_REQUESTED", priority: "HIGH", note: "Customer asked to speak with a manager." };
  }
  if (ctx.consecutiveAiRejections >= 2) {
    return {
      required: true,
      reason: "REPEATED_REJECTION",
      priority: "MEDIUM",
      note: "Customer rejected the AI's suggestions multiple times.",
    };
  }
  if (nlp.intentConfidence < LOW_CONFIDENCE_THRESHOLD) {
    return {
      required: true,
      reason: "LOW_AI_CONFIDENCE",
      priority: "LOW",
      note: "AI could not confidently classify this message.",
    };
  }
  if (nlp.intent === "GENERAL_INQUIRY" && ctx.consecutiveLowConfidenceTurns >= 2) {
    return {
      required: true,
      reason: "OUT_OF_KNOWLEDGE",
      priority: "MEDIUM",
      note: "Question is outside the AI's knowledge base.",
    };
  }

  return { required: false, reason: null, priority: "LOW", note: "" };
}
