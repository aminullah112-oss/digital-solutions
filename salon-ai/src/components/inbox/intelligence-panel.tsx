"use client";
import { useState } from "react";
import { ChevronDown, ChevronUp, Phone, Calendar, Clock3, UserCog } from "lucide-react";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import { TemperatureBadge, SentimentBadge, IntentBadge } from "@/components/shared/badges";
import { Badge } from "@/components/ui/badge";
import { recommendAction } from "@/lib/ai/recommendation";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

interface Staff {
  id: string;
  name: string;
}

export interface IntelligenceData {
  customer: {
    name: string;
    phone: string | null;
    firstContactAt: string;
    lastContactAt: string;
  };
  channel: string;
  previousConversations: number;
  lead: {
    intent: string;
    sentiment: string;
    temperature: string;
    score: number;
    estimatedValue: number;
    bookingProbability: number;
    serviceName: string | null;
    preferredDate: string | null;
    preferredTime: string | null;
    scoreEvents: { reason: string; points: number }[];
  } | null;
  openHandoffReason: string | null;
  assignedStaffId: string | null;
  staffOptions: Staff[];
  conversationId: string;
}

export function IntelligencePanel({ data }: { data: IntelligenceData }) {
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [assignedStaffId, setAssignedStaffId] = useState(data.assignedStaffId ?? "");

  const recommendation = data.lead
    ? recommendAction({
        intent: data.lead.intent,
        temperature: data.lead.temperature,
        hasOpenHandoff: !!data.openHandoffReason,
        handoffReason: data.openHandoffReason,
      })
    : null;

  async function onAssign(staffId: string) {
    setAssignedStaffId(staffId);
    await fetch(`/api/conversations/${data.conversationId}/assign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ staffId: staffId || null }),
    });
  }

  return (
    <div className="hidden w-[300px] shrink-0 overflow-y-auto border-l border-white/10 p-4 xl:block">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">Customer</p>
      <div className="glass-panel space-y-1.5 p-3 text-xs">
        <p className="text-sm font-semibold">{data.customer.name}</p>
        {data.customer.phone && (
          <p className="flex items-center gap-1.5 text-muted">
            <Phone className="size-3" /> {data.customer.phone}
          </p>
        )}
        <p className="flex items-center gap-1.5 text-muted">
          <Calendar className="size-3" /> First contact {formatRelativeTime(data.customer.firstContactAt)}
        </p>
        <p className="flex items-center gap-1.5 text-muted">
          <Clock3 className="size-3" /> Last contact {formatRelativeTime(data.customer.lastContactAt)}
        </p>
        <p className="text-muted-2">{data.previousConversations} previous conversation{data.previousConversations === 1 ? "" : "s"}</p>
      </div>

      <p className="mb-2 mt-4 text-[11px] font-semibold uppercase tracking-wide text-muted">Assigned Staff</p>
      <Select value={assignedStaffId} onValueChange={onAssign}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Unassigned" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="">Unassigned</SelectItem>
          {data.staffOptions.map((s) => (
            <SelectItem key={s.id} value={s.id}>
              {s.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {data.lead && (
        <>
          <p className="mb-2 mt-4 text-[11px] font-semibold uppercase tracking-wide text-muted">AI Intelligence</p>
          <div className="glass-panel space-y-2.5 p-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted">Intent</span>
              <IntentBadge intent={data.lead.intent} />
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted">Service</span>
              <span className="font-medium">{data.lead.serviceName ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted">Lead Score</span>
              <span className="mono-num font-semibold">{data.lead.score}/100</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted">Temperature</span>
              <TemperatureBadge temperature={data.lead.temperature} />
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted">Sentiment</span>
              <SentimentBadge sentiment={data.lead.sentiment} />
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted">Estimated Value</span>
              <span className="font-medium text-revenue">{formatCurrency(data.lead.estimatedValue)}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted">Booking Probability</span>
              <span className="font-medium">{data.lead.bookingProbability}%</span>
            </div>
            {(data.lead.preferredDate || data.lead.preferredTime) && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted">Preferred</span>
                <span className="font-medium">{[data.lead.preferredDate, data.lead.preferredTime].filter(Boolean).join(" · ")}</span>
              </div>
            )}
          </div>

          <button
            onClick={() => setShowBreakdown((s) => !s)}
            className="mt-2 flex w-full items-center justify-between rounded-md px-1 py-1.5 text-[11px] text-muted hover:text-foreground"
          >
            <span>Why this score?</span>
            {showBreakdown ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
          </button>
          {showBreakdown && (
            <div className="space-y-1 rounded-md border border-white/10 bg-white/[0.02] p-2.5">
              {data.lead.scoreEvents.length === 0 && <p className="text-[11px] text-muted">No scoring events yet.</p>}
              {data.lead.scoreEvents.map((e, i) => (
                <div key={i} className="flex items-center justify-between text-[11px]">
                  <span className="text-muted">{e.reason}</span>
                  <span className={e.points >= 0 ? "font-medium text-success" : "font-medium text-danger"}>
                    {e.points >= 0 ? "+" : ""}
                    {e.points}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {recommendation && (
        <>
          <p className="mb-2 mt-4 text-[11px] font-semibold uppercase tracking-wide text-muted">AI Recommendation</p>
          <div className="glass-panel space-y-2 p-3">
            <p className="text-xs leading-relaxed text-foreground/90">{recommendation.text}</p>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted">Priority</span>
              <Badge variant={recommendation.priority === "HIGH" ? "danger" : recommendation.priority === "MEDIUM" ? "warning" : "outline"}>
                {recommendation.priority}
              </Badge>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
