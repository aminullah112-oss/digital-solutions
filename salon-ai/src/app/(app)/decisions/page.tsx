import Link from "next/link";
import { Flame, AlertTriangle, Wallet, Siren, TrendingUp, Bot } from "lucide-react";
import {
  getActNowLeads,
  getRevenueOpportunity,
  getCustomerRisk,
  getGrowthOpportunity,
  getAutomationOpportunity,
} from "@/lib/data/decisions";
import { listFollowUps } from "@/lib/data/attention";
import { formatCurrency } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

function Panel({
  icon: Icon,
  title,
  accent,
  children,
}: {
  icon: typeof Flame;
  title: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <div className="glass-panel p-4">
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold" style={{ color: accent }}>
        <Icon className="size-4" /> {title}
      </div>
      {children}
    </div>
  );
}

export default async function DecisionCenterPage() {
  const [actNow, revenueOpp, risk, growth, automation, followUps] = await Promise.all([
    getActNowLeads(),
    getRevenueOpportunity(),
    getCustomerRisk(),
    getGrowthOpportunity(),
    getAutomationOpportunity(),
    listFollowUps(),
  ]);

  return (
    <div className="mx-auto max-w-[1300px] p-4 md:p-6">
      <div className="mb-5">
        <h1 className="text-lg font-semibold tracking-tight">AI Decision Center</h1>
        <p className="text-xs text-muted">Where to focus right now, ranked by what actually moves revenue.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Panel icon={Flame} title="ACT NOW — READY TO BOOK" accent="var(--hot)">
          <div className="space-y-1.5">
            {actNow.length === 0 && <p className="text-xs text-muted">No hot unbooked leads right now.</p>}
            {actNow.map((l) => (
              <Link key={l.id} href={`/inbox/${l.conversationId ?? ""}`} className="flex items-center justify-between rounded-md px-1.5 py-1.5 text-xs hover:bg-white/[0.04]">
                <div className="min-w-0">
                  <p className="truncate font-medium">{l.customer.name}</p>
                  <p className="truncate text-[11px] text-muted">{l.service?.name ?? l.intent}</p>
                </div>
                <Badge variant="hot">{l.score}</Badge>
              </Link>
            ))}
          </div>
        </Panel>

        <Panel icon={AlertTriangle} title="FOLLOW UP — LIKELY TO CONVERT" accent="var(--warm)">
          <div className="space-y-1.5">
            {followUps.length === 0 && <p className="text-xs text-muted">Nothing pending.</p>}
            {followUps.slice(0, 8).map((f) => (
              <Link key={f.id} href="/followups" className="flex items-center justify-between rounded-md px-1.5 py-1.5 text-xs hover:bg-white/[0.04]">
                <div className="min-w-0">
                  <p className="truncate font-medium">{f.customer.name}</p>
                  <p className="truncate text-[11px] text-muted">{f.lead?.service?.name ?? f.reason}</p>
                </div>
                {f.lead && <Badge variant="warning">{f.lead.score}</Badge>}
              </Link>
            ))}
          </div>
        </Panel>

        <Panel icon={Wallet} title="REVENUE OPPORTUNITY" accent="var(--revenue)">
          <p className="mono-num mb-2 text-2xl font-semibold text-revenue">{formatCurrency(revenueOpp.total)}</p>
          <p className="mb-2 text-[11px] text-muted">sitting in unresolved qualified+ leads</p>
          <div className="space-y-1.5">
            {revenueOpp.leads.slice(0, 5).map((l) => (
              <Link key={l.id} href={`/inbox/${l.conversationId ?? ""}`} className="flex items-center justify-between rounded-md px-1.5 py-1 text-xs hover:bg-white/[0.04]">
                <span className="truncate">{l.customer.name}</span>
                <span className="shrink-0 text-revenue">{formatCurrency(l.estimatedValue)}</span>
              </Link>
            ))}
          </div>
        </Panel>

        <Panel icon={Siren} title="CUSTOMER RISK" accent="var(--danger)">
          <div className="space-y-1.5">
            {risk.length === 0 && <p className="text-xs text-muted">No active complaints. 🎉</p>}
            {risk.map((h) => (
              <Link key={h.id} href={`/inbox/${h.conversation.id}`} className="flex items-center justify-between rounded-md px-1.5 py-1.5 text-xs hover:bg-white/[0.04]">
                <div className="min-w-0">
                  <p className="truncate font-medium">{h.conversation.customer.name}</p>
                  <p className="truncate text-[11px] text-muted">{h.note}</p>
                </div>
                <Badge variant="danger">{h.reason.replace(/_/g, " ")}</Badge>
              </Link>
            ))}
          </div>
        </Panel>

        <Panel icon={TrendingUp} title="GROWTH OPPORTUNITY" accent="var(--success)">
          <div className="space-y-1.5">
            {growth.map((g) => (
              <div key={g.service.id} className="flex items-center justify-between rounded-md px-1.5 py-1.5 text-xs">
                <span className="truncate font-medium">{g.service.name}</span>
                <span className="text-success">{g.enquiries} enquiries</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel icon={Bot} title="AUTOMATION OPPORTUNITY" accent="var(--accent)">
          <p className="mono-num mb-1 text-2xl font-semibold text-accent">{automation.aiShare}%</p>
          <p className="mb-2 text-[11px] text-muted">of replies are already automated ({automation.aiResolutionRate}% resolved without a human)</p>
          <p className="text-xs text-foreground/80">
            {automation.staffCount > automation.aiCount
              ? `Staff typed ${automation.staffCount} manual replies — review the Attention Queue for patterns to add to the knowledge base.`
              : "Automation coverage is strong. Keep staff focused on complex, high-value conversations."}
          </p>
        </Panel>
      </div>
    </div>
  );
}
