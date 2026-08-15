"use client";
import { useState } from "react";
import { Save, Bot, UserCheck, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useToast } from "@/components/ui/toast";

const MODES = [
  { value: "FULL_AUTO", label: "Full Auto", icon: Bot, desc: "AI answers and sends replies immediately for anything it can handle confidently." },
  { value: "ASSISTED", label: "Assisted", icon: UserCheck, desc: "AI auto-sends routine replies, but queues lower-confidence ones for staff approval." },
  { value: "HUMAN_APPROVAL", label: "Human Approval", icon: ShieldCheck, desc: "Every AI reply is drafted but held until a staff member approves and sends it." },
];

export function AiModeTab({ initial }: { initial: string }) {
  const [mode, setMode] = useState(initial);
  const [saving, setSaving] = useState(false);
  const { push } = useToast();

  async function save() {
    setSaving(true);
    const res = await fetch("/api/settings", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ aiMode: mode }) });
    setSaving(false);
    if (!res.ok) return push({ kind: "error", title: "Couldn't update AI mode" });
    push({ kind: "success", title: `AI mode set to ${mode.replace("_", " ")}` });
  }

  return (
    <div className="max-w-xl space-y-3">
      {MODES.map((m) => {
        const Icon = m.icon;
        return (
          <button
            key={m.value}
            onClick={() => setMode(m.value)}
            className={cn(
              "flex w-full items-start gap-3 rounded-lg border p-3.5 text-left transition-colors",
              mode === m.value ? "border-accent/40 bg-accent/[0.06]" : "border-white/10 hover:bg-white/[0.03]"
            )}
          >
            <div className={cn("mt-0.5 flex size-8 items-center justify-center rounded-md", mode === m.value ? "bg-accent/15 text-accent" : "bg-white/[0.05] text-muted")}>
              <Icon className="size-4" />
            </div>
            <div>
              <p className="text-sm font-medium">{m.label}</p>
              <p className="text-xs text-muted">{m.desc}</p>
            </div>
          </button>
        );
      })}
      <Button size="sm" onClick={save} disabled={saving}>
        <Save className="size-3.5" /> {saving ? "Saving…" : "Save AI Mode"}
      </Button>
    </div>
  );
}
