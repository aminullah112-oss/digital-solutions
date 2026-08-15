import Link from "next/link";
import {
  MessageSquare,
  UserPlus,
  Flame,
  BadgeCheck,
  CalendarCheck,
  TrendingUp,
  Wallet,
  Bot,
  Siren,
  Clock,
  ArrowRight,
} from "lucide-react";
import { getDashboardSnapshot, getRecentAiEvents, getAttentionQueueCount, getFollowUpCount } from "@/lib/data/dashboard";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { LiveActivityFeed } from "@/components/dashboard/live-activity-feed";
import { prisma } from "@/lib/db/prisma";
import { formatCurrency } from "@/lib/utils";

export default async function CommandCenterPage() {
  const [snapshot, events, attentionCount, followUpCount, hotLeadPreview] = await Promise.all([
    getDashboardSnapshot(),
    getRecentAiEvents(30),
    getAttentionQueueCount(),
    getFollowUpCount(),
    prisma.lead.findMany({
      where: { temperature: { in: ["HOT", "VERY_HOT"] } },
      orderBy: { score: "desc" },
      take: 5,
      include: { customer: true, service: true },
    }),
  ]);

  return (
    <div className="mx-auto max-w-[1400px] p-4 md:p-6">
      <div className="mb-5">
        <h1 className="text-lg font-semibold tracking-tight">Salon AI Command Center</h1>
        <p className="text-xs text-muted">Live view of every conversation, lead, and booking across all channels.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiCard label="Messages Today" value={snapshot.messagesToday.toLocaleString()} icon={MessageSquare} accent="accent" />
        <KpiCard label="New Leads" value={snapshot.newLeadsToday.toLocaleString()} icon={UserPlus} />
        <KpiCard label="Hot Leads" value={snapshot.hotLeads.toLocaleString()} icon={Flame} accent="hot" />
        <KpiCard label="Qualified" value={snapshot.qualifiedLeads.toLocaleString()} icon={BadgeCheck} accent="success" />
        <KpiCard label="Bookings" value={snapshot.totalBookings.toLocaleString()} icon={CalendarCheck} sublabel={`${snapshot.bookingsToday} today`} />
        <KpiCard label="Conversion Rate" value={`${snapshot.conversionRate}%`} icon={TrendingUp} accent="accent" />
        <KpiCard label="Revenue" value={formatCurrency(snapshot.revenue)} icon={Wallet} accent="revenue" />
        <KpiCard label="AI Resolution Rate" value={`${snapshot.aiResolutionRate}%`} icon={Bot} accent="success" />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="h-[520px]">
            <LiveActivityFeed initialEvents={events.map((e) => ({ ...e, createdAt: e.createdAt.toISOString() }))} />
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <Link href="/attention" className="glass-panel block p-4 transition-colors hover:border-danger/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-semibold text-danger">
                <Siren className="size-4" /> ATTENTION QUEUE
              </div>
              <ArrowRight className="size-3.5 text-muted" />
            </div>
            <p className="mono-num mt-2 text-2xl font-semibold text-danger">{attentionCount}</p>
            <p className="text-[11px] text-muted">conversation{attentionCount === 1 ? "" : "s"} need a human right now</p>
          </Link>

          <Link href="/followups" className="glass-panel block p-4 transition-colors hover:border-revenue/30">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-semibold text-revenue">
                <Clock className="size-4" /> FOLLOW-UPS
              </div>
              <ArrowRight className="size-3.5 text-muted" />
            </div>
            <p className="mono-num mt-2 text-2xl font-semibold text-revenue">{followUpCount}</p>
            <p className="text-[11px] text-muted">leads waiting on a nudge</p>
          </Link>

          <div className="glass-panel flex-1 p-4">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-hot">
              <Flame className="size-4" /> TOP HOT LEADS
            </div>
            <div className="space-y-2">
              {hotLeadPreview.length === 0 && <p className="text-xs text-muted">No hot leads yet.</p>}
              {hotLeadPreview.map((lead) => (
                <Link
                  key={lead.id}
                  href={`/inbox/${lead.conversationId ?? ""}`}
                  className="flex items-center justify-between rounded-md px-1.5 py-1.5 text-xs hover:bg-white/[0.04]"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium">{lead.customer.name}</p>
                    <p className="truncate text-[11px] text-muted">{lead.service?.name ?? lead.intent}</p>
                  </div>
                  <span className="mono-num shrink-0 font-semibold text-hot">{lead.score}</span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
