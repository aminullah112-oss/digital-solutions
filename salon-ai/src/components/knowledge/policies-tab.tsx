"use client";
import { useState } from "react";
import { Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

export interface PolicyRow {
  id: string;
  type: string;
  title: string;
  content: string;
}

function PolicyEditor({ policy }: { policy: PolicyRow }) {
  const [content, setContent] = useState(policy.content);
  const [saving, setSaving] = useState(false);
  const { push } = useToast();

  async function save() {
    setSaving(true);
    const res = await fetch(`/api/policies/${policy.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    setSaving(false);
    if (!res.ok) return push({ kind: "error", title: "Couldn't save policy" });
    push({ kind: "success", title: `${policy.title} updated` });
  }

  return (
    <div className="glass-panel p-3">
      <p className="mb-1.5 text-sm font-medium">{policy.title}</p>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={2}
        className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none focus:border-accent/40"
      />
      <Button size="sm" variant="secondary" className="mt-2" onClick={save} disabled={saving}>
        <Save className="size-3.5" /> {saving ? "Saving…" : "Save"}
      </Button>
    </div>
  );
}

export function PoliciesTab({ initial }: { initial: PolicyRow[] }) {
  return (
    <div className="space-y-2">
      {initial.map((p) => (
        <PolicyEditor key={p.id} policy={p} />
      ))}
    </div>
  );
}
