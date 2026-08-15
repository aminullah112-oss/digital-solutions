"use client";
import { useState } from "react";
import { Radio } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";

export function DemoModeToggle({ initialEnabled }: { initialEnabled: boolean }) {
  const [enabled, setEnabled] = useState(initialEnabled);
  const [busy, setBusy] = useState(false);
  const { push } = useToast();

  async function toggle(next: boolean) {
    setBusy(true);
    setEnabled(next);
    try {
      const res = await fetch("/api/simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: next }),
      });
      if (!res.ok) throw new Error();
      push({
        kind: "info",
        title: next ? "Live simulation started" : "Live simulation stopped",
        description: next ? "Simulated inbound messages will appear every 10–20s." : undefined,
      });
    } catch {
      setEnabled(!next);
      push({ kind: "error", title: "Couldn't update simulation state" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-2 rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1.5">
      <Radio className={enabled ? "size-3.5 text-hot live-dot" : "size-3.5 text-muted"} />
      <span className="hidden text-xs text-muted sm:inline">Demo simulation</span>
      <Switch checked={enabled} disabled={busy} onCheckedChange={toggle} />
    </div>
  );
}
