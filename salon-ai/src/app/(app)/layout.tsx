import { requireUser } from "@/lib/auth/current-user";
import { prisma } from "@/lib/db/prisma";
import { Sidebar } from "@/components/shell/sidebar";
import { TopBar } from "@/components/shell/top-bar";
import { MobileNav } from "@/components/shell/mobile-nav";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await requireUser();
  const settings = await prisma.businessSettings.findUnique({ where: { id: "default" } });

  return (
    <div className="flex h-dvh overflow-hidden">
      <Sidebar salonName={settings?.salonName ?? "Salon AI"} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar user={{ name: user.name, role: user.role }} simulationEnabled={settings?.demoMode ?? false} />
        <main className="flex-1 overflow-y-auto pb-16 lg:pb-0">{children}</main>
      </div>
      <MobileNav />
    </div>
  );
}
