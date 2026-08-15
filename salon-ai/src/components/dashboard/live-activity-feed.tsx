"use client";
import { useRef, useState } from "react";
import { Brain, MessageCircle, Siren, CalendarCheck, Gauge, Clock, UserPlus, Radio } from "lucide-react";
import { usePolling } from "@/lib/hooks/use-polling";
import { formatRelativeTime, cn } from "@/lib/utils";
import { ChannelBadge } from "@/components/shared/channel-badge";

interface AiEventRow {
  id: string;
  type: string;
  channel: string;
  customerName: string;
  summary: string;
  createdAt: string;
}

const EVENT_META: Record<string, { icon: typeof Brain; label: string; className: string }> = {
  PROCESSING: { icon: Brain, label: "AI PROCESSING", className: "text-accent bg-accent/10" },
  AI_RESPONDED: { icon: MessageCircle, label: "AI RESPONDED", className: "text-accent bg-accent/10" },
  HUMAN_HANDOFF: { icon: Siren, label: "HUMAN HANDOFF", className: "text-danger bg-danger/10" },
  BOOKING_CREATED: { icon: CalendarCheck, label: "BOOKING CREATED", className: "text-success bg-success/10" },
  LEAD_SCORED: { icon: Gauge, label: "LEAD SCORED", className: "text-warm bg-warm/10" },
  FOLLOW_UP_CREATED: { icon: Clock, label: "FOLLOW-UP CREATED", className: "text-revenue bg-revenue/10" },
  CUSTOMER_IDENTIFIED: { icon: UserPlus, label: "NEW CONVERSATION", className: "text-muted bg-white/[0.06]" },
};

export function LiveActivityFeed({ initialEvents }: { initialEvents: AiEventRow[] }) {
  const [events, setEvents] = useState<AiEventRow[]>(initialEvents);
  const cursor = useRef<string | undefined>(initialEvents[0]?.createdAt);

  usePolling(
    async () => {
      const url = cursor.current ? `/api/events/recent?since=${encodeURIComponent(cursor.current)}` : "/api/events/recent";
      const res = await fetch(url);
      if (!res.ok) return null;
      const data = await res.json();
      if (data.events?.length) {
        cursor.current = data.events[0].createdAt;
        setEvents((prev) => [...data.events, ...prev].slice(0, 40));
      }
      return null;
    },
    4000,
    []
  );

  return (
    <div className="glass-panel flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
        <Radio className="size-3.5 text-hot live-dot" />
        <p className="text-xs font-semibold tracking-wide">LIVE AI ACTIVITY</p>
      </div>
      <div className="flex-1 space-y-1 overflow-y-auto p-2">
        {events.length === 0 && (
          <p className="p-4 text-center text-xs text-muted">No activity yet. Turn on Demo simulation to see it live.</p>
        )}
        {events.map((e) => {
          const meta = EVENT_META[e.type] ?? EVENT_META.PROCESSING;
          const Icon = meta.icon;
          return (
            <div key={e.id} className="event-enter flex items-start gap-2.5 rounded-md px-2 py-2 hover:bg-white/[0.03]">
              <div className={cn("mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md", meta.className)}>
                <Icon className="size-3.5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 text-[10px] font-semibold tracking-wide text-muted">
                  {meta.label}
                  <ChannelBadge channel={e.channel} compact />
                </div>
                <p className="truncate text-xs text-foreground/90">
                  <span className="font-medium">{e.customerName}</span> — {e.summary}
                </p>
              </div>
              <span className="shrink-0 text-[10px] text-muted-2">{formatRelativeTime(e.createdAt)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
