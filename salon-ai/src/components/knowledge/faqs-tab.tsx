"use client";
import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

export interface FaqRow {
  id: string;
  question: string;
  answer: string;
  category: string;
}

export function FaqsTab({ initial }: { initial: FaqRow[] }) {
  const [items, setItems] = useState(initial);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ question: "", answer: "", category: "general" });
  const { push } = useToast();

  async function add() {
    if (!form.question || !form.answer) {
      push({ kind: "error", title: "Question and answer are required" });
      return;
    }
    const res = await fetch("/api/faqs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    if (!res.ok) return push({ kind: "error", title: "Couldn't add FAQ" });
    const { faq } = await res.json();
    setItems((prev) => [faq, ...prev]);
    setForm({ question: "", answer: "", category: "general" });
    setShowForm(false);
  }

  async function remove(id: string) {
    setItems((prev) => prev.filter((f) => f.id !== id));
    await fetch(`/api/faqs/${id}`, { method: "DELETE" });
  }

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button size="sm" onClick={() => setShowForm((s) => !s)}>
          <Plus className="size-3.5" /> Add FAQ
        </Button>
      </div>
      {showForm && (
        <div className="glass-panel mb-3 space-y-2 p-3">
          <input placeholder="Question" value={form.question} onChange={(e) => setForm({ ...form, question: e.target.value })} className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <textarea placeholder="Answer" value={form.answer} onChange={(e) => setForm({ ...form, answer: e.target.value })} rows={2} className="w-full rounded-md border border-white/15 bg-white/[0.03] px-2.5 py-1.5 text-xs outline-none" />
          <Button size="sm" onClick={add}>Save FAQ</Button>
        </div>
      )}
      <div className="space-y-2">
        {items.map((f) => (
          <div key={f.id} className="glass-panel flex items-start justify-between gap-3 p-3">
            <div>
              <p className="text-sm font-medium">{f.question}</p>
              <p className="mt-0.5 text-xs text-muted">{f.answer}</p>
            </div>
            <button onClick={() => remove(f.id)} className="shrink-0 text-muted hover:text-danger">
              <Trash2 className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
