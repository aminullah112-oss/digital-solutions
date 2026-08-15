"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Search, LogOut, User as UserIcon } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { initials } from "@/lib/utils";
import { DemoModeToggle } from "@/components/shell/demo-mode-toggle";

export function TopBar({ user, simulationEnabled }: { user: { name: string; role: string }; simulationEnabled: boolean }) {
  const router = useRouter();
  const [q, setQ] = useState("");

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  function onSearch(e: React.FormEvent) {
    e.preventDefault();
    if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
  }

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-white/10 bg-surface/60 px-4">
      <form onSubmit={onSearch} className="relative hidden max-w-sm flex-1 sm:block">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search customers, phone, bookings…"
          className="w-full rounded-md border border-white/10 bg-white/[0.03] py-1.5 pl-8 pr-3 text-xs outline-none focus:border-accent/40"
        />
      </form>

      <div className="flex-1 sm:hidden" />

      <DemoModeToggle initialEnabled={simulationEnabled} />

      <DropdownMenu>
        <DropdownMenuTrigger className="flex items-center gap-2 rounded-md px-1.5 py-1 outline-none hover:bg-white/[0.05]">
          <Avatar className="size-7">
            <AvatarFallback>{initials(user.name)}</AvatarFallback>
          </Avatar>
          <span className="hidden text-xs text-muted sm:inline">{user.name.split(" ")[0]}</span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>
            {user.name}
            <div className="text-[10px] uppercase tracking-wide text-accent">{user.role}</div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => router.push("/settings")}>
            <UserIcon className="size-3.5" /> Settings
          </DropdownMenuItem>
          <DropdownMenuItem onClick={logout}>
            <LogOut className="size-3.5" /> Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
