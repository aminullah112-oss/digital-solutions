import Link from "next/link";
import { prisma } from "@/lib/db/prisma";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { CustomerStatusBadge } from "@/components/shared/badges";
import { ChannelBadge } from "@/components/shared/channel-badge";
import { formatCurrency, initials } from "@/lib/utils";

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q } = await searchParams;
  const query = (q ?? "").trim();

  const [customers, bookings] = query
    ? await Promise.all([
        prisma.customer.findMany({
          where: {
            OR: [
              { name: { contains: query, mode: "insensitive" } },
              { phone: { contains: query, mode: "insensitive" } },
              { email: { contains: query, mode: "insensitive" } },
            ],
          },
          take: 20,
        }),
        prisma.booking.findMany({
          where: { customer: { name: { contains: query, mode: "insensitive" } } },
          include: { customer: true, service: true },
          take: 20,
        }),
      ])
    : [[], []];

  return (
    <div className="mx-auto max-w-[900px] p-4 md:p-6">
      <h1 className="mb-1 text-lg font-semibold tracking-tight">Search</h1>
      <p className="mb-5 text-xs text-muted">{query ? `Results for "${query}"` : "Type in the search box above to find customers, phone numbers, or bookings."}</p>

      {query && (
        <div className="space-y-5">
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">Customers ({customers.length})</p>
            <div className="glass-panel divide-y divide-white/5">
              {customers.map((c) => (
                <Link key={c.id} href={`/customers/${c.id}`} className="flex items-center gap-2.5 p-3 hover:bg-white/[0.03]">
                  <Avatar>
                    <AvatarFallback>{initials(c.name)}</AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{c.name}</p>
                    <p className="text-xs text-muted">{c.phone ?? c.email ?? "—"}</p>
                  </div>
                  <ChannelBadge channel={c.source} />
                  <CustomerStatusBadge status={c.status} />
                </Link>
              ))}
              {customers.length === 0 && <p className="p-4 text-center text-xs text-muted">No customers found.</p>}
            </div>
          </div>

          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">Bookings ({bookings.length})</p>
            <div className="glass-panel divide-y divide-white/5">
              {bookings.map((b) => (
                <Link key={b.id} href={`/customers/${b.customerId}`} className="flex items-center justify-between p-3 hover:bg-white/[0.03]">
                  <div>
                    <p className="text-sm font-medium">
                      {b.customer.name} — {b.service.name}
                    </p>
                    <p className="text-xs text-muted">{new Date(b.date).toLocaleString()}</p>
                  </div>
                  <span className="text-xs text-revenue">{formatCurrency(b.price)}</span>
                </Link>
              ))}
              {bookings.length === 0 && <p className="p-4 text-center text-xs text-muted">No bookings found.</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
