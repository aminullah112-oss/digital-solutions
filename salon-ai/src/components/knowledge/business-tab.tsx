"use client";
import { useState } from "react";
import { Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

export interface BusinessInfo {
  salonName: string;
  address: string;
  phone: string;
  openingHours: { sat_thu?: string; fri?: string };
  socials: { instagram?: string; whatsapp?: string };
}

export function BusinessTab({ initial }: { initial: BusinessInfo }) {
  const [form, setForm] = useState(initial);
  const [saving, setSaving] = useState(false);
  const { push } = useToast();

  async function save() {
    setSaving(true);
    const res = await fetch("/api/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    setSaving(false);
    if (!res.ok) return push({ kind: "error", title: "Couldn't save business info" });
    push({ kind: "success", title: "Business info updated" });
  }

  return (
    <div className="glass-panel max-w-lg space-y-3 p-4">
      <div>
        <label className="mb-1 block text-xs text-muted">Salon Name</label>
        <input value={form.salonName} onChange={(e) => setForm({ ...form, salonName: e.target.value })} className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-sm outline-none" />
      </div>
      <div>
        <label className="mb-1 block text-xs text-muted">Address</label>
        <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-sm outline-none" />
      </div>
      <div>
        <label className="mb-1 block text-xs text-muted">Phone</label>
        <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-sm outline-none" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="mb-1 block text-xs text-muted">Hours (Sat–Thu)</label>
          <input
            value={form.openingHours.sat_thu ?? ""}
            onChange={(e) => setForm({ ...form, openingHours: { ...form.openingHours, sat_thu: e.target.value } })}
            className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-sm outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted">Hours (Friday)</label>
          <input
            value={form.openingHours.fri ?? ""}
            onChange={(e) => setForm({ ...form, openingHours: { ...form.openingHours, fri: e.target.value } })}
            className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-sm outline-none"
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="mb-1 block text-xs text-muted">Instagram</label>
          <input
            value={form.socials.instagram ?? ""}
            onChange={(e) => setForm({ ...form, socials: { ...form.socials, instagram: e.target.value } })}
            className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-sm outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted">WhatsApp</label>
          <input
            value={form.socials.whatsapp ?? ""}
            onChange={(e) => setForm({ ...form, socials: { ...form.socials, whatsapp: e.target.value } })}
            className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-sm outline-none"
          />
        </div>
      </div>
      <Button size="sm" onClick={save} disabled={saving}>
        <Save className="size-3.5" /> {saving ? "Saving…" : "Save Business Info"}
      </Button>
    </div>
  );
}
