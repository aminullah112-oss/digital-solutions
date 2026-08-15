import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

export function KpiCard({
  label,
  value,
  icon: Icon,
  accent = "default",
  sublabel,
}: {
  label: string;
  value: string;
  icon: LucideIcon;
  accent?: "default" | "hot" | "success" | "revenue" | "accent";
  sublabel?: string;
}) {
  const accentClass = {
    default: "text-foreground",
    hot: "text-hot",
    success: "text-success",
    revenue: "text-revenue",
    accent: "text-accent",
  }[accent];

  const iconBg = {
    default: "bg-white/[0.06] text-muted",
    hot: "bg-hot/10 text-hot",
    success: "bg-success/10 text-success",
    revenue: "bg-revenue/10 text-revenue",
    accent: "bg-accent/10 text-accent",
  }[accent];

  return (
    <div className="glass-panel p-4">
      <div className="flex items-start justify-between">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</p>
        <div className={cn("flex size-7 items-center justify-center rounded-md", iconBg)}>
          <Icon className="size-3.5" />
        </div>
      </div>
      <p className={cn("mono-num mt-2 text-2xl font-semibold", accentClass)}>{value}</p>
      {sublabel && <p className="mt-0.5 text-[11px] text-muted-2">{sublabel}</p>}
    </div>
  );
}
