import {
  getLeadSourceBreakdown,
  getConversionFunnel,
  getServiceDemand,
  getRevenueByChannel,
  getRevenueByService,
  getRevenueByStaff,
  getResponsePerformance,
} from "@/lib/data/analytics";
import { BarPanel } from "@/components/analytics/bar-panel";
import { FunnelPanel } from "@/components/analytics/funnel-panel";
import { formatCurrency } from "@/lib/utils";

function formatSeconds(s: number) {
  if (s < 60) return `${s}s`;
  return `${Math.round(s / 60)}m`;
}

export default async function AnalyticsPage() {
  const [sources, funnel, services, revenueChannel, revenueService, revenueStaff, response] = await Promise.all([
    getLeadSourceBreakdown(),
    getConversionFunnel(),
    getServiceDemand(),
    getRevenueByChannel(),
    getRevenueByService(),
    getRevenueByStaff(),
    getResponsePerformance(),
  ]);

  return (
    <div className="mx-auto max-w-[1300px] p-4 md:p-6">
      <div className="mb-5">
        <h1 className="text-lg font-semibold tracking-tight">Analytics</h1>
        <p className="text-xs text-muted">Where leads come from, what converts, and what it's worth.</p>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="glass-panel p-3">
          <p className="text-[10px] uppercase tracking-wide text-muted">AI Response Rate</p>
          <p className="mono-num mt-1 text-xl font-semibold text-accent">{response.aiResponseRate}%</p>
        </div>
        <div className="glass-panel p-3">
          <p className="text-[10px] uppercase tracking-wide text-muted">AI Resolution Rate</p>
          <p className="mono-num mt-1 text-xl font-semibold text-success">{response.aiResolutionRate}%</p>
        </div>
        <div className="glass-panel p-3">
          <p className="text-[10px] uppercase tracking-wide text-muted">Avg AI Response</p>
          <p className="mono-num mt-1 text-xl font-semibold">{formatSeconds(response.avgAiResponseSeconds)}</p>
        </div>
        <div className="glass-panel p-3">
          <p className="text-[10px] uppercase tracking-wide text-muted">Avg Human Response</p>
          <p className="mono-num mt-1 text-xl font-semibold">{formatSeconds(response.avgHumanResponseSeconds)}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <FunnelPanel stages={funnel} />
        <BarPanel
          title="Lead Sources"
          data={sources.map((s) => ({ channel: s.channel, count: s.count }))}
          dataKey="count"
          labelKey="channel"
          color="var(--accent-2)"
        />
        <BarPanel
          title="Service Demand (Enquiries)"
          data={services.map((s) => ({ name: s.name, enquiries: s.enquiries }))}
          dataKey="enquiries"
          labelKey="name"
          color="var(--warm)"
        />
        <BarPanel
          title="Revenue by Channel"
          data={revenueChannel.map((r) => ({ channel: r.channel, revenue: r.revenue }))}
          dataKey="revenue"
          labelKey="channel"
          color="var(--revenue)"
          valueFormatter={formatCurrency}
        />
        <BarPanel
          title="Revenue by Service"
          data={revenueService.map((r) => ({ name: r.name, revenue: r.revenue }))}
          dataKey="revenue"
          labelKey="name"
          color="var(--success)"
          valueFormatter={formatCurrency}
        />
        <BarPanel
          title="Revenue by Staff"
          data={revenueStaff.map((r) => ({ name: r.name, revenue: r.revenue }))}
          dataKey="revenue"
          labelKey="name"
          color="var(--accent)"
          valueFormatter={formatCurrency}
        />
      </div>
    </div>
  );
}
