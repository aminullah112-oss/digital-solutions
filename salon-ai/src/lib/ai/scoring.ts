import { SCORING_WEIGHTS, SCORING_REASON_LABELS, temperatureForScore, HIGH_VALUE_SERVICE_THRESHOLD, type ScoringReasonKey } from "./scoring-config";
import type { NlpResult } from "./nlp";

export interface ScoreEvent {
  reason: string;
  points: number;
  key: ScoringReasonKey;
}

export interface ScoringInput {
  nlp: NlpResult;
  previousCustomer: boolean;
  servicePrice: number | null;
  hasPreferredDate: boolean;
  hasPreferredTime: boolean;
  stoppedResponding?: boolean;
}

export function scoreConversationTurn(input: ScoringInput): ScoreEvent[] {
  const events: ScoreEvent[] = [];
  const add = (key: ScoringReasonKey) =>
    events.push({ key, reason: SCORING_REASON_LABELS[key], points: SCORING_WEIGHTS[key] });

  if (input.nlp.askedAboutService) add("askedAboutService");
  if (input.nlp.askedAboutPrice) add("askedAboutPrice");
  if (input.nlp.askedAboutAvailability) add("askedAboutAvailability");
  if (input.hasPreferredDate) add("specifiedPreferredDate");
  if (input.hasPreferredTime) add("specifiedPreferredTime");
  if (input.nlp.askedToBook) add("askedToBook");
  if (input.previousCustomer) add("previousCustomer");
  if (input.servicePrice !== null && input.servicePrice >= HIGH_VALUE_SERVICE_THRESHOLD) add("highValueService");
  if (input.nlp.sentiment === "POSITIVE") add("positiveSentiment");
  if (input.nlp.isComplaint) add("complaint");
  if (input.stoppedResponding) add("stoppedResponding");

  return events;
}

/** Sums all historical score events for a lead and clamps to 0-100. */
export function aggregateScore(events: { points: number }[]): number {
  const raw = events.reduce((sum, e) => sum + e.points, 0);
  return Math.max(0, Math.min(100, raw));
}

export function classifyTemperature(score: number) {
  return temperatureForScore(score);
}

/** Rough booking-probability heuristic derived from score + explicit booking intent. */
export function estimateBookingProbability(score: number, askedToBook: boolean) {
  const base = score;
  return Math.max(0, Math.min(100, askedToBook ? Math.max(base, 70) : base - 10));
}
