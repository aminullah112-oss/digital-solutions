"use client";
import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";

export interface UserRow {
  id: string;
  name: string;
  email: string;
  role: "ADMIN" | "MANAGER" | "STAFF";
  active: boolean;
}

export function UsersTab({ initial, canManage }: { initial: UserRow[]; canManage: boolean }) {
  const [users, setUsers] = useState(initial);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "STAFF" });
  const { push } = useToast();

  async function addUser() {
    if (!form.name || !form.email || !form.password) {
      push({ kind: "error", title: "Name, email, and password are required" });
      return;
    }
    const res = await fetch("/api/users", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      return push({ kind: "error", title: data.error ?? "Couldn't create user" });
    }
    const { user } = await res.json();
    setUsers((prev) => [...prev, { ...user, active: true }]);
    setForm({ name: "", email: "", password: "", role: "STAFF" });
    setShowForm(false);
    push({ kind: "success", title: `${user.name} added` });
  }

  async function toggleActive(id: string, active: boolean) {
    setUsers((prev) => prev.map((u) => (u.id === id ? { ...u, active } : u)));
    await fetch(`/api/users/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ active }) });
  }

  return (
    <div className="max-w-xl">
      {canManage && (
        <div className="mb-3 flex justify-end">
          <Button size="sm" onClick={() => setShowForm((s) => !s)}>
            <Plus className="size-3.5" /> Add User
          </Button>
        </div>
      )}
      {showForm && (
        <div className="glass-panel mb-3 space-y-2 p-3">
          <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <input placeholder="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <input placeholder="Password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="STAFF">Staff</SelectItem>
              <SelectItem value="MANAGER">Manager</SelectItem>
              <SelectItem value="ADMIN">Admin</SelectItem>
            </SelectContent>
          </Select>
          <Button size="sm" onClick={addUser}>Create User</Button>
        </div>
      )}
      <div className="space-y-2">
        {users.map((u) => (
          <div key={u.id} className="glass-panel flex items-center justify-between p-3">
            <div>
              <p className="text-sm font-medium">{u.name}</p>
              <p className="text-xs text-muted">{u.email}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="accent">{u.role}</Badge>
              <Switch checked={u.active} disabled={!canManage} onCheckedChange={(v) => toggleActive(u.id, v)} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
