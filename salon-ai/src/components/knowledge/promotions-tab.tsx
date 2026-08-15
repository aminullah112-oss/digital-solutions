"use client";
import { useState } from "react";
import { Plus, Power } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";

export interface PromotionRow {
  id: string;
  name: string;
  description: string;
  discountPct: number;
  startDate: string;
  endDate: string;
  active: boolean;
}

const EMPTY = { name: "", description: "", discountPct: "", startDate: "", endDate: "" };

export function PromotionsTab({ initial }: { initial: PromotionRow[] }) {
  const [items, setItems] = useState(initial);
  const [form, setForm] = useState(EMPTY);
  const [showForm, setShowForm] = useState(false);
  const { push } = useToast();

  async function add() {
    if (!form.name || !form.description || !form.startDate || !form.endDate) {
      push({ kind: "error", title: "Fill in all required fields" });
      return;
    }
    const res = await fetch("/api/promotions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    if (!res.ok) return push({ kind: "error", title: "Couldn't add promotion" });
    const { promotion } = await res.json();
    setItems((prev) => [promotion, ...prev]);
    setForm(EMPTY);
    setShowForm(false);
  }

  async function toggle(id: string, active: boolean) {
    setItems((prev) => prev.map((p) => (p.id === id ? { ...p, active } : p)));
    await fetch(`/api/promotions/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ active }) });
  }

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button size="sm" onClick={() => setShowForm((s) => !s)}>
          <Plus className="size-3.5" /> Add Promotion
        </Button>
      </div>
      {showForm && (
        <div className="glass-panel mb-3 grid grid-cols-2 gap-2 p-3">
          <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="col-span-2 rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <input placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="col-span-2 rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <input placeholder="Discount %" type="number" value={form.discountPct} onChange={(e) => setForm({ ...form, discountPct: e.target.value })} className="rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <div />
          <input placeholder="Start date" type="date" value={form.startDate} onChange={(e) => setForm({ ...form, startDate: e.target.value })} className="rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <input placeholder="End date" type="date" value={form.endDate} onChange={(e) => setForm({ ...form, endDate: e.target.value })} className="rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <Button size="sm" className="col-span-2" onClick={add}>Save Promotion</Button>
        </div>
      )}
      <div className="space-y-2">
        {items.map((p) => (
          <div key={p.id} className="glass-panel flex items-center justify-between gap-3 p-3">
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium">{p.name}</p>
                <Badge variant="accent">{p.discountPct}% off</Badge>
                <Badge variant={p.active ? "success" : "outline"}>{p.active ? "Active" : "Inactive"}</Badge>
              </div>
              <p className="mt-0.5 text-xs text-muted">{p.description}</p>
              <p className="mt-0.5 text-[10px] text-muted-2">
                {new Date(p.startDate).toLocaleDateString()} – {new Date(p.endDate).toLocaleDateString()}
              </p>
            </div>
            <button onClick={() => toggle(p.id, !p.active)} className="shrink-0 text-muted hover:text-accent">
              <Power className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
