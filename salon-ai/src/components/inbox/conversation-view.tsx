"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Send, CheckCircle2, ChevronLeft, Loader2 } from "lucide-react";
import { usePolling } from "@/lib/hooks/use-polling";
import { cn, formatRelativeTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ConversationStatusBadge } from "@/components/shared/badges";
import { ChannelBadge } from "@/components/shared/channel-badge";
import { useToast } from "@/components/ui/toast";

interface MessageRow {
  id: string;
  sender: "CUSTOMER" | "AI" | "STAFF" | "SYSTEM";
  text: string;
  language: string;
  metadata: unknown;
  createdAt: string;
}

export interface ConversationDetail {
  id: string;
  channel: string;
  status: string;
  customer: { id: string; name: string; phone: string | null };
  messages: MessageRow[];
}

function isPending(metadata: unknown): boolean {
  return Boolean(metadata && typeof metadata === "object" && (metadata as Record<string, unknown>).pending === true);
}

export function ConversationView({ initial }: { initial: ConversationDetail }) {
  const [detail, setDetail] = useState(initial);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { push } = useToast();

  useEffect(() => {
    setDetail(initial);
  }, [initial.id]);

  const polled = usePolling<ConversationDetail | null>(
    async () => {
      const res = await fetch(`/api/conversations/${initial.id}`);
      if (!res.ok) return null;
      const json = await res.json();
      return json.conversation;
    },
    4000,
    [initial.id]
  );

  useEffect(() => {
    if (polled) setDetail(polled as ConversationDetail);
  }, [polled]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [detail.messages.length]);

  useEffect(() => {
    fetch(`/api/conversations/${initial.id}/read`, { method: "POST" }).catch(() => {});
  }, [initial.id]);

  async function sendMessage() {
    if (!draft.trim()) return;
    setSending(true);
    try {
      const res = await fetch(`/api/conversations/${detail.id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: draft.trim() }),
      });
      if (!res.ok) throw new Error();
      setDraft("");
      const refreshed = await fetch(`/api/conversations/${detail.id}`).then((r) => r.json());
      setDetail(refreshed.conversation);
    } catch {
      push({ kind: "error", title: "Couldn't send message" });
    } finally {
      setSending(false);
    }
  }

  async function approve(messageId: string) {
    try {
      const res = await fetch(`/api/conversations/${detail.id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messageId }),
      });
      if (!res.ok) throw new Error();
      const refreshed = await fetch(`/api/conversations/${detail.id}`).then((r) => r.json());
      setDetail(refreshed.conversation);
      push({ kind: "success", title: "Reply approved & sent" });
    } catch {
      push({ kind: "error", title: "Couldn't approve reply" });
    }
  }

  async function resolve() {
    await fetch(`/api/conversations/${detail.id}/resolve`, { method: "POST" });
    const refreshed = await fetch(`/api/conversations/${detail.id}`).then((r) => r.json());
    setDetail(refreshed.conversation);
    push({ kind: "success", title: "Conversation marked resolved" });
  }

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div className="flex items-center gap-2">
          <Link href="/inbox" className="text-muted hover:text-foreground lg:hidden">
            <ChevronLeft className="size-4" />
          </Link>
          <div>
            <p className="text-sm font-semibold">{detail.customer.name}</p>
            <div className="mt-0.5 flex items-center gap-1.5">
              <ChannelBadge channel={detail.channel} />
              <ConversationStatusBadge status={detail.status} />
            </div>
          </div>
        </div>
        <Button size="sm" variant="secondary" onClick={resolve} disabled={detail.status === "RESOLVED"}>
          <CheckCircle2 className="size-3.5" /> Mark Resolved
        </Button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {detail.messages.map((m) => {
          const pending = isPending(m.metadata);
          const fromBusiness = m.sender === "AI" || m.sender === "STAFF";
          if (m.sender === "SYSTEM") {
            return (
              <p key={m.id} className="text-center text-[11px] text-muted-2">
                {m.text}
              </p>
            );
          }
          return (
            <div key={m.id} className={cn("flex", fromBusiness ? "justify-end" : "justify-start")}>
              <div
                className={cn(
                  "max-w-[75%] rounded-lg px-3 py-2 text-sm",
                  m.sender === "CUSTOMER" && "bg-white/[0.06] text-foreground",
                  m.sender === "AI" && (pending ? "border border-dashed border-accent/40 bg-accent/[0.06] text-foreground" : "bg-accent/15 text-foreground"),
                  m.sender === "STAFF" && "bg-success/15 text-foreground"
                )}
              >
                <div className="mb-0.5 flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-muted">
                  {m.sender === "AI" ? (pending ? "AI draft — pending approval" : "AI") : m.sender}
                </div>
                <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>
                <div className="mt-1 flex items-center justify-between gap-2">
                  <span className="text-[10px] text-muted-2">{formatRelativeTime(m.createdAt)}</span>
                  {pending && (
                    <button
                      onClick={() => approve(m.id)}
                      className="inline-flex items-center gap-1 rounded-full bg-accent/20 px-2 py-0.5 text-[10px] font-medium text-accent hover:bg-accent/30"
                    >
                      <CheckCircle2 className="size-3" /> Approve & Send
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      <div className="flex items-center gap-2 border-t border-white/10 p-3">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
          placeholder="Reply as staff…"
          className="flex-1 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm outline-none focus:border-accent/40"
        />
        <Button size="sm" onClick={sendMessage} disabled={sending || !draft.trim()}>
          {sending ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
          Send
        </Button>
      </div>
    </div>
  );
}
