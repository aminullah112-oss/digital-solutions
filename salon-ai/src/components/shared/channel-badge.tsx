import { MessageCircle, Camera, ThumbsUp, Globe } from "lucide-react";
import { cn } from "@/lib/utils";

const CHANNEL_META: Record<string, { icon: typeof MessageCircle; label: string; color: string }> = {
  WHATSAPP: { icon: MessageCircle, label: "WhatsApp", color: "var(--wa)" },
  INSTAGRAM: { icon: Camera, label: "Instagram", color: "var(--ig)" },
  FACEBOOK: { icon: ThumbsUp, label: "Facebook", color: "var(--fb)" },
  WEBSITE: { icon: Globe, label: "Website", color: "var(--web)" },
};

export function ChannelBadge({ channel, compact = false }: { channel: string; compact?: boolean }) {
  const meta = CHANNEL_META[channel] ?? CHANNEL_META.WEBSITE;
  const Icon = meta.icon;
  if (compact) {
    return <Icon className="size-3" style={{ color: meta.color }} />;
  }
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium"
      style={{ color: meta.color, borderColor: `color-mix(in srgb, ${meta.color} 35%, transparent)`, background: `color-mix(in srgb, ${meta.color} 12%, transparent)` }}
    >
      <Icon className="size-3" />
      {meta.label}
    </span>
  );
}
