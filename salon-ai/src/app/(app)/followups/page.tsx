import { listFollowUps } from "@/lib/data/attention";
import { FollowUpList } from "@/components/followups/followup-list";
import { ScanButton } from "@/components/followups/scan-button";

export default async function FollowUpsPage() {
  const followUps = await listFollowUps();

  return (
    <div className="mx-auto max-w-[900px] p-4 md:p-6">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Follow-ups</h1>
          <p className="text-xs text-muted">Warm leads that went quiet after an AI reply — review and approve a nudge.</p>
        </div>
        <ScanButton />
      </div>
      <FollowUpList initial={JSON.parse(JSON.stringify(followUps))} />
    </div>
  );
}
