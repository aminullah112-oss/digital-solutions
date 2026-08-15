"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { usePolling } from "@/lib/hooks/use-polling";
import { cn, formatRelativeTime, initials } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ChannelBadge } from "@/components/shared/channel-badge";
import { Badge } from "@/components/ui/badge";

export interface ConversationListItem {
  id: string;
  channel: string;
  status: string;
  unreadCount: number;
  lastMessageAt: string;
  customer: { id: string; name: string; phone: string | null };
  lead: { score: number; temperature: string; intent: string; sentiment: string; serviceName: string | null } | null;
  lastMessagePreview: string;
  assignedStaff: { name: string } | null;
  hasOpenHandoff: boolean;
  hasOpenFollowUp: boolean;
}

const FILTERS = [
  "All",
  "WhatsApp",
  "Instagram",
  "Facebook",
  "Website",
  "Unread",
  "Hot Leads",
  "Follow-up",
  "Human Required",
  "Booking",
  "Complaint",
] as const;

function applyFilter(items: ConversationListItem[], filter: string, query: string) {
  let result = items;
  switch (filter) {
    case "WhatsApp":
      result = result.filter((c) => c.channel === "WHATSAPP");
      break;
    case "Instagram":
      result = result.filter((c) => c.channel === "INSTAGRAM");
      break;
    case "Facebook":
      result = result.filter((c) => c.channel === "FACEBOOK");
      break;
    case "Website":
      result = result.filter((c) => c.channel === "WEBSITE");
      break;
    case "Unread":
      result = result.filter((c) => c.unreadCount > 0);
      break;
    case "Hot Leads":
      result = result.filter((c) => c.lead && ["HOT", "VERY_HOT"].includes(c.lead.temperature));
      break;
    case "Follow-up":
      result = result.filter((c) => c.hasOpenFollowUp);
      break;
    case "Human Required":
      result = result.filter((c) => c.status === "HUMAN_REQUIRED" || c.hasOpenHandoff);
      break;
    case "Booking":
      result = result.filter((c) => c.lead?.intent === "BOOKING");
      break;
    case "Complaint":
      result = result.filter((c) => c.lead?.intent === "COMPLAINT" || c.hasOpenHandoff);
      break;
    default:
      break;
  }
  if (query.trim()) {
    const q = query.toLowerCase();
    result = result.filter(
      (c) => c.customer.name.toLowerCase().includes(q) || c.customer.phone?.toLowerCase().includes(q) || c.lastMessagePreview.toLowerCase().includes(q)
    );
  }
  return result;
}

export function ConversationList({
  initial,
  selectedId,
}: {
  initial: ConversationListItem[];
  selectedId?: string;
}) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All");
  const [query, setQuery] = useState("");

  const data = usePolling<ConversationListItem[]>(
    async () => {
      const res = await fetch("/api/conversations");
      if (!res.ok) return initial;
      const json = await res.json();
      return json.conversations;
    },
    5000,
    []
  );

  const items = data ?? initial;
  const filtered = useMemo(() => applyFilter(items, filter, query), [items, filter, query]);

  return (
    <div className="flex h-full w-full flex-col border-r border-white/10 lg:w-[340px] lg:shrink-0">
      <div className="border-b border-white/10 p-3">
        <div className="relative mb-2">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search conversations…"
            className="w-full rounded-md border border-white/10 bg-white/[0.03] py-1.5 pl-8 pr-3 text-xs outline-none focus:border-accent/40"
          />
        </div>
        <div className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "rounded-full border px-2 py-0.5 text-[10px] transition-colors",
                filter === f ? "border-accent/40 bg-accent/12 text-accent" : "border-white/10 text-muted hover:text-foreground"
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 && <p className="p-6 text-center text-xs text-muted">No conversations match this filter.</p>}
        {filtered.map((c) => (
          <Link
            key={c.id}
            href={`/inbox/${c.id}`}
            className={cn(
              "flex items-start gap-2.5 border-b border-white/5 px-3 py-3 transition-colors hover:bg-white/[0.03]",
              selectedId === c.id && "bg-accent/[0.07]"
            )}
          >
            <Avatar>
              <AvatarFallback>{initials(c.customer.name)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-sm font-medium">{c.customer.name}</p>
                <span className="shrink-0 text-[10px] text-muted-2">{formatRelativeTime(c.lastMessageAt)}</span>
              </div>
              <p className="mt-0.5 truncate text-xs text-muted">{c.lastMessagePreview || "No messages yet"}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-1">
                <ChannelBadge channel={c.channel} />
                {c.lead && ["HOT", "VERY_HOT"].includes(c.lead.temperature) && <Badge variant="hot">{c.lead.score}</Badge>}
                {c.hasOpenHandoff && <Badge variant="danger">Needs human</Badge>}
                {c.unreadCount > 0 && <Badge variant="accent">{c.unreadCount} new</Badge>}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
