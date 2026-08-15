"use client";
import { useMemo, useState } from "react";
import { ChannelBadge } from "@/components/shared/channel-badge";
import { cn, formatCurrency } from "@/lib/utils";
import { useToast } from "@/components/ui/toast";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

export interface BookingRow {
  id: string;
  date: string;
  durationMin: number;
  status: string;
  source: string;
  price: number;
  notes: string | null;
  customer: { id: string; name: string };
  service: { name: string };
  staff: { name: string } | null;
}

const STATUS_FILTERS = ["All", "PENDING", "CONFIRMED", "COMPLETED", "CANCELLED", "NO_SHOW", "RESCHEDULED"];

export function BookingTable({ initial }: { initial: BookingRow[] }) {
  const [items, setItems] = useState(initial);
  const [filter, setFilter] = useState("All");
  const { push } = useToast();

  const filtered = useMemo(() => (filter === "All" ? items : items.filter((b) => b.status === filter)), [items, filter]);

  async function updateStatus(id: string, status: string) {
    setItems((prev) => prev.map((b) => (b.id === id ? { ...b, status } : b)));
    try {
      const res = await fetch(`/api/bookings/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error();
      push({ kind: "success", title: `Booking marked ${status.toLowerCase().replace("_", " ")}` });
    } catch {
      push({ kind: "error", title: "Couldn't update booking" });
    }
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-1">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={cn(
              "rounded-full border px-2.5 py-1 text-[11px] transition-colors",
              filter === s ? "border-accent/40 bg-accent/12 text-accent" : "border-white/10 text-muted hover:text-foreground"
            )}
          >
            {s.replace("_", " ")}
          </button>
        ))}
      </div>

      <div className="glass-panel overflow-x-auto">
        <table className="w-full min-w-[820px] text-left text-xs">
          <thead>
            <tr className="border-b border-white/10 text-[10px] uppercase tracking-wide text-muted">
              <th className="px-4 py-2.5 font-medium">Customer</th>
              <th className="px-4 py-2.5 font-medium">Service</th>
              <th className="px-4 py-2.5 font-medium">Staff</th>
              <th className="px-4 py-2.5 font-medium">Date &amp; Time</th>
              <th className="px-4 py-2.5 font-medium">Source</th>
              <th className="px-4 py-2.5 font-medium">Price</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((b) => (
              <tr key={b.id} className="border-b border-white/5 last:border-0 hover:bg-white/[0.03]">
                <td className="px-4 py-2.5 font-medium">{b.customer.name}</td>
                <td className="px-4 py-2.5">{b.service.name}</td>
                <td className="px-4 py-2.5 text-muted">{b.staff?.name ?? "Unassigned"}</td>
                <td className="px-4 py-2.5 text-muted">{new Date(b.date).toLocaleString()}</td>
                <td className="px-4 py-2.5">
                  <ChannelBadge channel={b.source} />
                </td>
                <td className="px-4 py-2.5 text-revenue">{formatCurrency(b.price)}</td>
                <td className="px-4 py-2.5">
                  <Select value={b.status} onValueChange={(v) => updateStatus(b.id, v)}>
                    <SelectTrigger className="h-7 w-[130px] text-[11px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_FILTERS.filter((s) => s !== "All").map((s) => (
                        <SelectItem key={s} value={s}>
                          {s.replace("_", " ")}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && <p className="p-6 text-center text-xs text-muted">No bookings in this status.</p>}
      </div>
    </div>
  );
}
