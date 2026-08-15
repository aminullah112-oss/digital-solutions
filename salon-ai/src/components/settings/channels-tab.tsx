"use client";
import { useState } from "react";
import { Save } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { ChannelBadge } from "@/components/shared/channel-badge";

const CHANNELS = [
  { key: "whatsapp", channel: "WHATSAPP", webhook: "/api/webhooks/whatsapp", envVars: ["WHATSAPP_VERIFY_TOKEN", "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"] },
  { key: "instagram", channel: "INSTAGRAM", webhook: "/api/webhooks/instagram", envVars: ["INSTAGRAM_VERIFY_TOKEN", "META_APP_SECRET"] },
  { key: "facebook", channel: "FACEBOOK", webhook: "/api/webhooks/facebook", envVars: ["FACEBOOK_VERIFY_TOKEN", "FACEBOOK_PAGE_ACCESS_TOKEN"] },
  { key: "website", channel: "WEBSITE", webhook: "/api/webhooks/website", envVars: ["WEBSITE_CHAT_TOKEN"] },
];

export function ChannelsTab({ initial }: { initial: Record<string, boolean> }) {
  const [enabled, setEnabled] = useState(initial);
  const [saving, setSaving] = useState(false);
  const { push } = useToast();

  async function save() {
    setSaving(true);
    const res = await fetch("/api/settings", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ channelsEnabled: enabled }) });
    setSaving(false);
    if (!res.ok) return push({ kind: "error", title: "Couldn't save channel settings" });
    push({ kind: "success", title: "Channel settings saved" });
  }

  return (
    <div className="max-w-2xl space-y-3">
      {CHANNELS.map((c) => (
        <div key={c.key} className="glass-panel p-3.5">
          <div className="flex items-center justify-between">
            <ChannelBadge channel={c.channel} />
            <Switch checked={enabled[c.key] ?? false} onCheckedChange={(v) => setEnabled({ ...enabled, [c.key]: v })} />
          </div>
          <p className="mt-2 text-[11px] text-muted-2">
            Webhook: <code className="text-accent">{c.webhook}</code>
          </p>
          <p className="text-[11px] text-muted-2">Requires: {c.envVars.join(", ")}</p>
        </div>
      ))}
      <Button size="sm" onClick={save} disabled={saving}>
        <Save className="size-3.5" /> {saving ? "Saving…" : "Save Channels"}
      </Button>
    </div>
  );
}
