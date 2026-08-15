"use client";
import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { formatCurrency } from "@/lib/utils";

export interface ServiceRow {
  id: string;
  name: string;
  nameAr: string | null;
  description: string;
  price: number;
  durationMin: number;
  category: string;
  active: boolean;
}

const EMPTY = { name: "", nameAr: "", description: "", price: "", durationMin: "", category: "" };

export function ServicesTab({ initial }: { initial: ServiceRow[] }) {
  const [items, setItems] = useState(initial);
  const [form, setForm] = useState(EMPTY);
  const [showForm, setShowForm] = useState(false);
  const { push } = useToast();

  async function addService() {
    if (!form.name || !form.description || !form.price || !form.durationMin || !form.category) {
      push({ kind: "error", title: "Fill in all required fields" });
      return;
    }
    const res = await fetch("/api/services", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(form),
    });
    if (!res.ok) {
      push({ kind: "error", title: "Couldn't add service" });
      return;
    }
    const { service } = await res.json();
    setItems((prev) => [...prev, service]);
    setForm(EMPTY);
    setShowForm(false);
    push({ kind: "success", title: `${service.name} added` });
  }

  async function toggleActive(id: string, active: boolean) {
    setItems((prev) => prev.map((s) => (s.id === id ? { ...s, active } : s)));
    await fetch(`/api/services/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active }),
    });
  }

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button size="sm" onClick={() => setShowForm((s) => !s)}>
          <Plus className="size-3.5" /> Add Service
        </Button>
      </div>

      {showForm && (
        <div className="glass-panel mb-3 grid grid-cols-2 gap-2 p-3">
          <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <input placeholder="Arabic name (optional)" value={form.nameAr} onChange={(e) => setForm({ ...form, nameAr: e.target.value })} className="rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <input placeholder="Category" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <input placeholder="Price (SAR)" type="number" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} className="rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <input placeholder="Duration (min)" type="number" value={form.durationMin} onChange={(e) => setForm({ ...form, durationMin: e.target.value })} className="rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <input placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="col-span-2 rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <Button size="sm" className="col-span-2" onClick={addService}>Save Service</Button>
        </div>
      )}

      <div className="glass-panel overflow-x-auto">
        <table className="w-full min-w-[700px] text-left text-xs">
          <thead>
            <tr className="border-b border-white/10 text-[10px] uppercase tracking-wide text-muted">
              <th className="px-4 py-2.5 font-medium">Service</th>
              <th className="px-4 py-2.5 font-medium">Category</th>
              <th className="px-4 py-2.5 font-medium">Price</th>
              <th className="px-4 py-2.5 font-medium">Duration</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.id} className="border-b border-white/5 last:border-0 hover:bg-white/[0.03]">
                <td className="px-4 py-2.5 font-medium">{s.name}</td>
                <td className="px-4 py-2.5 text-muted">{s.category}</td>
                <td className="px-4 py-2.5 text-revenue">{formatCurrency(s.price)}</td>
                <td className="px-4 py-2.5 text-muted">{s.durationMin} min</td>
                <td className="px-4 py-2.5">
                  <Badge variant={s.active ? "success" : "outline"}>{s.active ? "Active" : "Inactive"}</Badge>
                </td>
                <td className="px-4 py-2.5">
                  <button onClick={() => toggleActive(s.id, !s.active)} className="text-muted hover:text-danger">
                    <Trash2 className="size-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
