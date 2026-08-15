import Link from "next/link";
import { notFound } from "next/navigation";
import { Phone, Mail, Calendar, Wallet, MessageSquare, CalendarCheck } from "lucide-react";
import { getCustomerProfile } from "@/lib/data/customers";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { CustomerStatusBadge, TemperatureBadge, IntentBadge } from "@/components/shared/badges";
import { ChannelBadge } from "@/components/shared/channel-badge";
import { formatCurrency, formatRelativeTime, initials } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export default async function CustomerProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const customer = await getCustomerProfile(id);
  if (!customer) notFound();

  return (
    <div className="mx-auto max-w-[1100px] p-4 md:p-6">
      <div className="glass-panel mb-4 flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Avatar className="size-12">
            <AvatarFallback className="text-base">{initials(customer.name)}</AvatarFallback>
          </Avatar>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-semibold">{customer.name}</h1>
              <CustomerStatusBadge status={customer.status} />
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted">
              {customer.phone && (
                <span className="flex items-center gap-1">
                  <Phone className="size-3" /> {customer.phone}
                </span>
              )}
              {customer.email && (
                <span className="flex items-center gap-1">
                  <Mail className="size-3" /> {customer.email}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Calendar className="size-3" /> First contact {formatRelativeTime(customer.firstContactAt)}
              </span>
            </div>
          </div>
        </div>
        <ChannelBadge channel={customer.source} />
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="glass-panel p-3">
          <p className="text-[10px] uppercase tracking-wide text-muted">Lead Score</p>
          <p className="mono-num mt-1 text-xl font-semibold">{customer.leadScore}</p>
        </div>
        <div className="glass-panel p-3">
          <p className="text-[10px] uppercase tracking-wide text-muted">Conversations</p>
          <p className="mono-num mt-1 text-xl font-semibold">{customer.totalConversations}</p>
        </div>
        <div className="glass-panel p-3">
          <p className="text-[10px] uppercase tracking-wide text-muted">Bookings</p>
          <p className="mono-num mt-1 text-xl font-semibold">{customer.totalBookings}</p>
        </div>
        <div className="glass-panel p-3">
          <p className="text-[10px] uppercase tracking-wide text-muted">Total Spend</p>
          <p className="mono-num mt-1 text-xl font-semibold text-revenue">{formatCurrency(customer.totalSpend)}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="glass-panel p-4">
          <p className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-muted">
            <MessageSquare className="size-3.5" /> CONVERSATION HISTORY
          </p>
          <div className="space-y-1.5">
            {customer.conversations.length === 0 && <p className="text-xs text-muted">No conversations yet.</p>}
            {customer.conversations.map((c) => (
              <Link
                key={c.id}
                href={`/inbox/${c.id}`}
                className="flex items-center justify-between rounded-md px-2 py-2 text-xs hover:bg-white/[0.04]"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <ChannelBadge channel={c.channel} compact />
                    <span className="truncate font-medium">{c.messages[0]?.text?.slice(0, 50) ?? "No messages"}</span>
                  </div>
                  {c.lead && (
                    <div className="mt-1 flex items-center gap-1.5">
                      <IntentBadge intent={c.lead.intent} />
                      <TemperatureBadge temperature={c.lead.temperature} />
                    </div>
                  )}
                </div>
                <span className="shrink-0 text-[10px] text-muted-2">{formatRelativeTime(c.lastMessageAt)}</span>
              </Link>
            ))}
          </div>
        </div>

        <div className="glass-panel p-4">
          <p className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-muted">
            <CalendarCheck className="size-3.5" /> BOOKINGS
          </p>
          <div className="space-y-1.5">
            {customer.bookings.length === 0 && <p className="text-xs text-muted">No bookings yet.</p>}
            {customer.bookings.map((b) => (
              <div key={b.id} className="flex items-center justify-between rounded-md px-2 py-2 text-xs">
                <div>
                  <p className="font-medium">{b.service.name}</p>
                  <p className="text-[10px] text-muted-2">
                    {new Date(b.date).toLocaleDateString()} · {b.staff?.name ?? "Unassigned"}
                  </p>
                </div>
                <div className="text-right">
                  <Badge variant={b.status === "COMPLETED" ? "success" : b.status === "CANCELLED" ? "danger" : "accent"}>
                    {b.status}
                  </Badge>
                  <p className="mt-1 flex items-center justify-end gap-1 text-[10px] text-revenue">
                    <Wallet className="size-3" /> {formatCurrency(b.price)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
