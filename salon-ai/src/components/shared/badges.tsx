import { Badge } from "@/components/ui/badge";

const TEMP_VARIANT: Record<string, "default" | "hot" | "warning" | "success" | "outline"> = {
  COLD: "outline",
  WARM: "warning",
  QUALIFIED: "success",
  HOT: "hot",
  VERY_HOT: "hot",
};

export function TemperatureBadge({ temperature }: { temperature: string }) {
  return (
    <Badge variant={TEMP_VARIANT[temperature] ?? "default"}>
      {temperature.replace("_", " ")}
    </Badge>
  );
}

const SENTIMENT_VARIANT: Record<string, "success" | "danger" | "default"> = {
  POSITIVE: "success",
  NEGATIVE: "danger",
  NEUTRAL: "default",
};

export function SentimentBadge({ sentiment }: { sentiment: string }) {
  return <Badge variant={SENTIMENT_VARIANT[sentiment] ?? "default"}>{sentiment}</Badge>;
}

export function IntentBadge({ intent }: { intent: string }) {
  return <Badge variant="accent">{intent.replace("_", " ")}</Badge>;
}

const STATUS_VARIANT: Record<string, "default" | "accent" | "danger" | "success" | "warning" | "outline"> = {
  OPEN: "outline",
  AI_HANDLING: "accent",
  HUMAN_REQUIRED: "danger",
  WAITING_CUSTOMER: "warning",
  RESOLVED: "success",
  ESCALATED: "danger",
};

export function ConversationStatusBadge({ status }: { status: string }) {
  return <Badge variant={STATUS_VARIANT[status] ?? "default"}>{status.replace("_", " ")}</Badge>;
}

const CUSTOMER_STATUS_VARIANT: Record<string, "default" | "accent" | "danger" | "success" | "warning" | "outline" | "hot"> = {
  NEW: "outline",
  LEAD: "warning",
  QUALIFIED: "accent",
  BOOKED: "success",
  ACTIVE_CUSTOMER: "success",
  VIP: "hot",
  INACTIVE: "default",
  LOST: "danger",
};

export function CustomerStatusBadge({ status }: { status: string }) {
  return <Badge variant={CUSTOMER_STATUS_VARIANT[status] ?? "default"}>{status.replace(/_/g, " ")}</Badge>;
}
