"use client";
import Link from "next/link";
import { useState } from "react";
import { Send, Clock, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatRelativeTime } from "@/lib/utils";
import { useToast } from "@/components/ui/toast";

export interface FollowUpRow {
  id: string;
  reason: string;
  suggestedMessage: string;
  createdAt: string;
  scheduledFor: string | null;
  customer: { name: string };
  conversation: { id: string } | null;
  lead: { score: number; service: { name: string } | null } | null;
}

export function FollowUpList({ initial }: { initial: FollowUpRow[] }) {
  const [items, setItems] = useState(initial);
  const { push } = useToast();

  async function act(id: string, action: "send" | "schedule" | "complete" | "ignore") {
    try {
      const res = await fetch(`/api/followups/${id}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: action === "schedule" ? JSON.stringify({}) : undefined,
      });
      if (!res.ok) throw new Error();
      setItems((prev) => prev.filter((i) => i.id !== id));
      push({
        kind: "success",
        title: action === "send" ? "Follow-up sent" : action === "schedule" ? "Scheduled for tomorrow" : action === "complete" ? "Marked completed" : "Follow-up ignored",
      });
    } catch {
      push({ kind: "error", title: "Action failed — try again" });
    }
  }

  if (items.length === 0) {
    return <p className="glass-panel p-8 text-center text-sm text-muted">No follow-ups pending. Every warm lead has been nudged.</p>;
  }

  return (
    <div className="space-y-2">
      {items.map((f) => (
        <div key={f.id} className="glass-panel p-3.5">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium">{f.customer.name}</p>
                {f.lead && <Badge variant="accent">Score {f.lead.score}</Badge>}
                {f.lead?.service && <Badge variant="outline">{f.lead.service.name}</Badge>}
              </div>
              <p className="mt-0.5 text-xs text-muted">{f.reason}</p>
            </div>
            <span className="text-[10px] text-muted-2">{formatRelativeTime(f.createdAt)}</span>
          </div>

          <div className="mt-2 rounded-md border border-dashed border-accent/25 bg-accent/[0.05] p-2.5 text-xs text-foreground/90">
            {f.suggestedMessage}
          </div>

          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={() => act(f.id, "send")}>
              <Send className="size-3.5" /> Approve & Send
            </Button>
            <Button size="sm" variant="secondary" onClick={() => act(f.id, "schedule")}>
              <Clock className="size-3.5" /> Schedule
            </Button>
            <Button size="sm" variant="outline" onClick={() => act(f.id, "complete")}>
              <CheckCircle2 className="size-3.5" /> Mark Done
            </Button>
            <Button size="sm" variant="ghost" onClick={() => act(f.id, "ignore")}>
              <XCircle className="size-3.5" /> Ignore
            </Button>
            {f.conversation && (
              <Link href={`/inbox/${f.conversation.id}`} className="ml-auto text-[11px] text-accent hover:underline">
                View conversation
              </Link>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
