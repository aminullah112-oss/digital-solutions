"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { NAV_ITEMS } from "./nav-config";
import { cn } from "@/lib/utils";

export function MobileNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const priority = NAV_ITEMS.filter((i) => i.mobilePriority);
  const rest = NAV_ITEMS.filter((i) => !i.mobilePriority);

  return (
    <>
      <nav className="fixed inset-x-0 bottom-0 z-40 flex border-t border-white/10 bg-surface/95 backdrop-blur lg:hidden">
        {priority.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[10px]",
                active ? "text-accent" : "text-muted"
              )}
            >
              <Icon className="size-5" />
              {item.label.split(" ")[0]}
            </Link>
          );
        })}
        <button
          onClick={() => setOpen(true)}
          className="flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[10px] text-muted"
        >
          <Menu className="size-5" />
          More
        </button>
      </nav>

      {open && (
        <div className="fixed inset-0 z-50 flex flex-col justify-end bg-black/60 lg:hidden" onClick={() => setOpen(false)}>
          <div
            className="glass-panel event-enter max-h-[70vh] overflow-y-auto rounded-b-none bg-surface p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-semibold">All sections</p>
              <button onClick={() => setOpen(false)} className="text-muted">
                <X className="size-4" />
              </button>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {[...priority, ...rest].map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className="flex flex-col items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2 py-3 text-center text-[11px] text-muted hover:text-foreground"
                  >
                    <Icon className="size-5" />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
