/**
 * Lead scoring configuration — the single source of truth for point values.
 * Adjust weights here; nothing in the UI hard-codes scoring logic.
 * Score is normalized/clamped to 0-100 by `scoreLead()` in engine.ts.
 */
export const SCORING_WEIGHTS = {
  askedAboutService: 10,
  askedAboutPrice: 10,
  askedAboutAvailability: 20,
  specifiedPreferredDate: 15,
  specifiedPreferredTime: 15,
  askedToBook: 25,
  previousCustomer: 10,
  highValueService: 10,
  positiveSentiment: 5,
  complaint: -20,
  stoppedResponding: -10,
} as const;

export type ScoringReasonKey = keyof typeof SCORING_WEIGHTS;

export const SCORING_REASON_LABELS: Record<ScoringReasonKey, string> = {
  askedAboutService: "Asked about service",
  askedAboutPrice: "Asked about price",
  askedAboutAvailability: "Asked about availability",
  specifiedPreferredDate: "Specified preferred date",
  specifiedPreferredTime: "Specified preferred time",
  askedToBook: "Asked to book",
  previousCustomer: "Previous customer",
  highValueService: "High-value service",
  positiveSentiment: "Positive sentiment",
  complaint: "Complaint",
  stoppedResponding: "Stopped responding",
};

/** Services at/above this price count as "high value" for scoring purposes. */
export const HIGH_VALUE_SERVICE_THRESHOLD = 300;

export const TEMPERATURE_BANDS = [
  { max: 29, label: "COLD" as const },
  { max: 49, label: "WARM" as const },
  { max: 69, label: "QUALIFIED" as const },
  { max: 84, label: "HOT" as const },
  { max: 100, label: "VERY_HOT" as const },
];

export function temperatureForScore(score: number) {
  const clamped = Math.max(0, Math.min(100, score));
  return TEMPERATURE_BANDS.find((b) => clamped <= b.max)!.label;
}
