"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { CustomerStatusBadge } from "@/components/shared/badges";
import { ChannelBadge } from "@/components/shared/channel-badge";
import { formatCurrency, formatRelativeTime, initials, cn } from "@/lib/utils";

export interface CustomerRow {
  id: string;
  name: string;
  phone: string | null;
  email: string | null;
  source: string;
  status: string;
  leadScore: number;
  totalBookings: number;
  totalSpend: number;
  lastContactAt: string;
}

const STATUS_FILTERS = ["All", "NEW", "LEAD", "QUALIFIED", "BOOKED", "ACTIVE_CUSTOMER", "VIP", "INACTIVE", "LOST"];

export function CustomerTable({ customers }: { customers: CustomerRow[] }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("All");

  const filtered = useMemo(() => {
    let result = customers;
    if (status !== "All") result = result.filter((c) => c.status === status);
    if (query.trim()) {
      const q = query.toLowerCase();
      result = result.filter((c) => c.name.toLowerCase().includes(q) || c.phone?.toLowerCase().includes(q) || c.email?.toLowerCase().includes(q));
    }
    return result;
  }, [customers, query, status]);

  return (
    <div>
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative max-w-xs flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name, phone, email…"
            className="w-full rounded-md border border-white/10 bg-white/[0.03] py-1.5 pl-8 pr-3 text-xs outline-none focus:border-accent/40"
          />
        </div>
        <div className="flex flex-wrap gap-1">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={cn(
                "rounded-full border px-2 py-0.5 text-[10px] transition-colors",
                status === s ? "border-accent/40 bg-accent/12 text-accent" : "border-white/10 text-muted hover:text-foreground"
              )}
            >
              {s.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      </div>

      <div className="glass-panel overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-xs">
          <thead>
            <tr className="border-b border-white/10 text-[10px] uppercase tracking-wide text-muted">
              <th className="px-4 py-2.5 font-medium">Customer</th>
              <th className="px-4 py-2.5 font-medium">Source</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Score</th>
              <th className="px-4 py-2.5 font-medium">Bookings</th>
              <th className="px-4 py-2.5 font-medium">Spend</th>
              <th className="px-4 py-2.5 font-medium">Last Contact</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <tr key={c.id} className="border-b border-white/5 last:border-0 hover:bg-white/[0.03]">
                <td className="px-4 py-2.5">
                  <Link href={`/customers/${c.id}`} className="flex items-center gap-2">
                    <Avatar className="size-7">
                      <AvatarFallback>{initials(c.name)}</AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="font-medium text-foreground">{c.name}</p>
                      <p className="text-[10px] text-muted-2">{c.phone ?? c.email ?? "—"}</p>
                    </div>
                  </Link>
                </td>
                <td className="px-4 py-2.5">
                  <ChannelBadge channel={c.source} />
                </td>
                <td className="px-4 py-2.5">
                  <CustomerStatusBadge status={c.status} />
                </td>
                <td className="mono-num px-4 py-2.5 font-medium">{c.leadScore}</td>
                <td className="px-4 py-2.5">{c.totalBookings}</td>
                <td className="px-4 py-2.5">{formatCurrency(c.totalSpend)}</td>
                <td className="px-4 py-2.5 text-muted">{formatRelativeTime(c.lastContactAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && <p className="p-6 text-center text-xs text-muted">No customers match this filter.</p>}
      </div>
    </div>
  );
}
