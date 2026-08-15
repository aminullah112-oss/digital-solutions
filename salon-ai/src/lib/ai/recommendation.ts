export interface RecommendationInput {
  intent: string;
  temperature: string;
  hasOpenHandoff: boolean;
  handoffReason?: string | null;
}

export interface Recommendation {
  text: string;
  priority: "LOW" | "MEDIUM" | "HIGH";
}

/** Simple, explainable rule-set — mirrors the scoring engine's transparency principle. */
export function recommendAction(input: RecommendationInput): Recommendation {
  if (input.hasOpenHandoff) {
    return {
      text: `This conversation needs a human right now (${(input.handoffReason ?? "escalated").toLowerCase().replace(/_/g, " ")}). Review and respond directly.`,
      priority: "HIGH",
    };
  }
  if (input.intent === "BOOKING" || input.intent === "AVAILABILITY") {
    return {
      text: "Customer appears ready to book. Offer available appointment times and confirm as soon as possible.",
      priority: "HIGH",
    };
  }
  if (["HOT", "VERY_HOT"].includes(input.temperature)) {
    return {
      text: "High-intent lead. Prioritize a fast, personal reply to convert before interest cools.",
      priority: "HIGH",
    };
  }
  if (["QUALIFIED", "WARM"].includes(input.temperature)) {
    return {
      text: "Promising lead. Share pricing or availability details and invite them to book.",
      priority: "MEDIUM",
    };
  }
  return {
    text: "Low urgency for now. Keep the conversation warm and check back if it goes quiet.",
    priority: "LOW",
  };
}
