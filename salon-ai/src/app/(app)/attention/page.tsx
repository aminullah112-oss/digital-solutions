import { listOpenHandoffs } from "@/lib/data/attention";
import { AttentionList } from "@/components/attention/attention-list";

export default async function AttentionPage() {
  const handoffs = await listOpenHandoffs();

  return (
    <div className="mx-auto max-w-[900px] p-4 md:p-6">
      <div className="mb-5">
        <h1 className="text-lg font-semibold tracking-tight">Human Attention Queue</h1>
        <p className="text-xs text-muted">Conversations the AI escalated — complaints, refunds, low-confidence replies, manager requests.</p>
      </div>
      <AttentionList initial={JSON.parse(JSON.stringify(handoffs))} />
    </div>
  );
}
