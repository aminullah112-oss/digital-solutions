"use client";
import Link from "next/link";
import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChannelBadge } from "@/components/shared/channel-badge";
import { formatRelativeTime } from "@/lib/utils";
import { useToast } from "@/components/ui/toast";

export interface HandoffRow {
  id: string;
  reason: string;
  priority: "LOW" | "MEDIUM" | "HIGH";
  note: string | null;
  createdAt: string;
  conversation: { id: string; channel: string; customer: { name: string } };
}

const PRIORITY_META: Record<string, { emoji: string; variant: "danger" | "warning" | "outline" }> = {
  HIGH: { emoji: "🔴", variant: "danger" },
  MEDIUM: { emoji: "🟠", variant: "warning" },
  LOW: { emoji: "🟡", variant: "outline" },
};

export function AttentionList({ initial }: { initial: HandoffRow[] }) {
  const [items, setItems] = useState(initial);
  const { push } = useToast();

  async function resolve(id: string) {
    setItems((prev) => prev.filter((i) => i.id !== id));
    try {
      const res = await fetch(`/api/handoffs/${id}/resolve`, { method: "POST" });
      if (!res.ok) throw new Error();
      push({ kind: "success", title: "Marked resolved" });
    } catch {
      push({ kind: "error", title: "Couldn't resolve — refresh and try again" });
    }
  }

  if (items.length === 0) {
    return <p className="glass-panel p-8 text-center text-sm text-muted">Nothing needs human attention right now. 🎉</p>;
  }

  return (
    <div className="space-y-2">
      {items.map((h) => {
        const meta = PRIORITY_META[h.priority];
        return (
          <div key={h.id} className="glass-panel flex items-center justify-between gap-3 p-3.5">
            <div className="flex min-w-0 items-center gap-3">
              <Badge variant={meta.variant}>
                {meta.emoji} {h.priority}
              </Badge>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{h.reason.replace(/_/g, " ")}</p>
                <div className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
                  <ChannelBadge channel={h.conversation.channel} compact />
                  {h.conversation.customer.name}
                  <span className="text-muted-2">· {formatRelativeTime(h.createdAt)}</span>
                </div>
                {h.note && <p className="mt-0.5 truncate text-[11px] text-muted-2">{h.note}</p>}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Link href={`/inbox/${h.conversation.id}`}>
                <Button size="sm" variant="secondary">
                  Open
                </Button>
              </Link>
              <Button size="sm" variant="outline" onClick={() => resolve(h.id)}>
                <CheckCircle2 className="size-3.5" /> Resolve
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
