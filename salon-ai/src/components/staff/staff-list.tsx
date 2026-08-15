"use client";
import { useState } from "react";
import { Plus, Power } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { initials } from "@/lib/utils";
import { useToast } from "@/components/ui/toast";

export interface StaffRow {
  id: string;
  name: string;
  role: string;
  workingHours: string | null;
  active: boolean;
  services: { service: { name: string } }[];
}

export function StaffList({ initial }: { initial: StaffRow[] }) {
  const [items, setItems] = useState(initial);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", role: "", workingHours: "" });
  const { push } = useToast();

  async function add() {
    if (!form.name || !form.role) {
      push({ kind: "error", title: "Name and role are required" });
      return;
    }
    const res = await fetch("/api/staff", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    if (!res.ok) return push({ kind: "error", title: "Couldn't add staff member" });
    const { staff } = await res.json();
    setItems((prev) => [...prev, { ...staff, services: [] }]);
    setForm({ name: "", role: "", workingHours: "" });
    setShowForm(false);
  }

  async function toggleActive(id: string, active: boolean) {
    setItems((prev) => prev.map((s) => (s.id === id ? { ...s, active } : s)));
    await fetch(`/api/staff/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ active }) });
  }

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button size="sm" onClick={() => setShowForm((s) => !s)}>
          <Plus className="size-3.5" /> Add Staff
        </Button>
      </div>
      {showForm && (
        <div className="glass-panel mb-3 grid grid-cols-3 gap-2 p-3">
          <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <input placeholder="Role (e.g. Colorist)" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className="rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <input placeholder="Working hours" value={form.workingHours} onChange={(e) => setForm({ ...form, workingHours: e.target.value })} className="rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <Button size="sm" className="col-span-3" onClick={add}>Save Staff Member</Button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((s) => (
          <div key={s.id} className="glass-panel p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Avatar>
                  <AvatarFallback>{initials(s.name)}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="text-sm font-medium">{s.name}</p>
                  <p className="text-xs text-muted">{s.role}</p>
                </div>
              </div>
              <button onClick={() => toggleActive(s.id, !s.active)} className={s.active ? "text-success" : "text-muted"}>
                <Power className="size-4" />
              </button>
            </div>
            {s.workingHours && <p className="mt-2 text-[11px] text-muted-2">{s.workingHours}</p>}
            <div className="mt-2 flex flex-wrap gap-1">
              {s.services.slice(0, 4).map((sv, i) => (
                <Badge key={i} variant="outline">
                  {sv.service.name}
                </Badge>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
