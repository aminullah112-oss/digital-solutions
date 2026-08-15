"use client";
import { useState } from "react";
import { Save } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

const OPTIONS = [
  { key: "notifyHotLead", label: "Hot Lead Notification", desc: "Alert when a conversation reaches HOT or VERY HOT temperature." },
  { key: "notifyComplaint", label: "Complaint Notification", desc: "Alert immediately when the AI detects a complaint." },
  { key: "notifyBooking", label: "Booking Notification", desc: "Alert when a new booking is created." },
  { key: "notifyHandoff", label: "Human Handoff Notification", desc: "Alert when a conversation is escalated to staff." },
];

export function NotificationsTab({ initial }: { initial: Record<string, boolean> }) {
  const [values, setValues] = useState(initial);
  const [saving, setSaving] = useState(false);
  const { push } = useToast();

  async function save() {
    setSaving(true);
    const res = await fetch("/api/settings", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) });
    setSaving(false);
    if (!res.ok) return push({ kind: "error", title: "Couldn't save notification settings" });
    push({ kind: "success", title: "Notification settings saved" });
  }

  return (
    <div className="max-w-xl space-y-2">
      {OPTIONS.map((o) => (
        <div key={o.key} className="glass-panel flex items-center justify-between p-3.5">
          <div>
            <p className="text-sm font-medium">{o.label}</p>
            <p className="text-xs text-muted">{o.desc}</p>
          </div>
          <Switch checked={values[o.key] ?? false} onCheckedChange={(v) => setValues({ ...values, [o.key]: v })} />
        </div>
      ))}
      <Button size="sm" onClick={save} disabled={saving}>
        <Save className="size-3.5" /> {saving ? "Saving…" : "Save Notifications"}
      </Button>
    </div>
  );
}
