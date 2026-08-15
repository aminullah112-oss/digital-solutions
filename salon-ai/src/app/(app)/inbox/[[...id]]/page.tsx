import { MessageSquareText } from "lucide-react";
import { listConversations, getConversationDetail, listStaff } from "@/lib/data/inbox";
import { ConversationList } from "@/components/inbox/conversation-list";
import { ConversationView } from "@/components/inbox/conversation-view";
import { IntelligencePanel } from "@/components/inbox/intelligence-panel";

export default async function InboxPage({ params }: { params: Promise<{ id?: string[] }> }) {
  const { id } = await params;
  const selectedId = id?.[0];

  const [list, staff, detail] = await Promise.all([
    listConversations(),
    listStaff(),
    selectedId ? getConversationDetail(selectedId) : Promise.resolve(null),
  ]);

  return (
    <div className="flex h-full">
      <div className={selectedId ? "hidden h-full lg:flex" : "flex h-full w-full lg:w-auto"}>
        <ConversationList initial={JSON.parse(JSON.stringify(list))} selectedId={selectedId} />
      </div>

      {!detail && (
        <div className="hidden flex-1 flex-col items-center justify-center gap-2 text-center text-muted lg:flex">
          <MessageSquareText className="size-8 text-muted-2" />
          <p className="text-sm">Select a conversation to view the AI intelligence panel</p>
        </div>
      )}

      {detail && (
        <div className="flex h-full flex-1">
          <ConversationView initial={JSON.parse(JSON.stringify(detail))} />
          <IntelligencePanel
            data={{
              customer: {
                name: detail.customer.name,
                phone: detail.customer.phone,
                firstContactAt: detail.customer.firstContactAt.toISOString(),
                lastContactAt: detail.customer.lastContactAt.toISOString(),
              },
              channel: detail.channel,
              previousConversations: detail.previousConversations,
              lead: detail.lead
                ? {
                    intent: detail.lead.intent,
                    sentiment: detail.lead.sentiment,
                    temperature: detail.lead.temperature,
                    score: detail.lead.score,
                    estimatedValue: detail.lead.estimatedValue,
                    bookingProbability: detail.lead.bookingProbability,
                    serviceName: detail.lead.service?.name ?? null,
                    preferredDate: detail.lead.preferredDate,
                    preferredTime: detail.lead.preferredTime,
                    scoreEvents: detail.lead.scoreEvents.map((e) => ({ reason: e.reason, points: e.points })),
                  }
                : null,
              openHandoffReason: detail.handoffs.find((h) => !h.resolved)?.reason ?? null,
              assignedStaffId: detail.assignedStaffId,
              staffOptions: staff.map((s) => ({ id: s.id, name: s.name })),
              conversationId: detail.id,
            }}
          />
        </div>
      )}
    </div>
  );
}
