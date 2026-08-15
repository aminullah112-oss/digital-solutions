import { Brain, Lightbulb, TrendingUp, Target, Gauge } from "lucide-react";
import { generateInsights } from "@/lib/ai/advisor";

export default async function AdvisorPage() {
  const insights = await generateInsights();

  return (
    <div className="mx-auto max-w-[900px] p-4 md:p-6">
      <div className="mb-5 flex items-center gap-2.5">
        <div className="flex size-9 items-center justify-center rounded-lg bg-accent/15 text-accent">
          <Brain className="size-5" />
        </div>
        <div>
          <h1 className="text-lg font-semibold tracking-tight">AI Business Advisor</h1>
          <p className="text-xs text-muted">Insights generated from your live conversation and booking data.</p>
        </div>
      </div>

      {insights.length === 0 && (
        <p className="glass-panel p-8 text-center text-sm text-muted">Not enough data yet to generate insights — keep the AI processing conversations.</p>
      )}

      <div className="space-y-3">
        {insights.map((insight, i) => (
          <div key={insight.id} className="glass-panel p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="flex size-6 items-center justify-center rounded-full bg-accent/12 text-[11px] font-semibold text-accent">
                  {i + 1}
                </span>
                <p className="text-sm font-semibold">{insight.title}</p>
              </div>
              <div className="flex shrink-0 items-center gap-1.5 text-[10px] text-muted">
                <Gauge className="size-3" />
                {insight.confidence}% confidence
              </div>
            </div>

            <div className="mt-3 space-y-2 pl-8 text-xs leading-relaxed">
              <p className="text-foreground/90">{insight.whatHappened}</p>
              <p className="flex items-start gap-1.5 text-muted">
                <TrendingUp className="mt-0.5 size-3 shrink-0" /> {insight.whyItMatters}
              </p>
              <p className="flex items-start gap-1.5 rounded-md border border-dashed border-accent/25 bg-accent/[0.05] p-2 text-foreground/90">
                <Lightbulb className="mt-0.5 size-3 shrink-0 text-accent" /> {insight.recommendation}
              </p>
              <p className="flex items-start gap-1.5 text-success">
                <Target className="mt-0.5 size-3 shrink-0" /> {insight.expectedImpact}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
