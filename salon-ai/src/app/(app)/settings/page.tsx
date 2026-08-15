import { prisma } from "@/lib/db/prisma";
import { getSession, roleAtLeast } from "@/lib/auth/session";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { AiModeTab } from "@/components/settings/ai-mode-tab";
import { ChannelsTab } from "@/components/settings/channels-tab";
import { NotificationsTab } from "@/components/settings/notifications-tab";
import { UsersTab } from "@/components/settings/users-tab";

export default async function SettingsPage() {
  const [settings, users, session] = await Promise.all([
    prisma.businessSettings.findUnique({ where: { id: "default" } }),
    prisma.user.findMany({ orderBy: { createdAt: "asc" }, select: { id: true, name: true, email: true, role: true, active: true } }),
    getSession(),
  ]);

  if (!settings) return null;

  return (
    <div className="mx-auto max-w-[1100px] p-4 md:p-6">
      <div className="mb-5">
        <h1 className="text-lg font-semibold tracking-tight">Settings</h1>
        <p className="text-xs text-muted">Configure how the AI responds, which channels are active, and who has access.</p>
      </div>

      <Tabs defaultValue="ai">
        <TabsList className="mb-4 flex-wrap">
          <TabsTrigger value="ai">AI</TabsTrigger>
          <TabsTrigger value="channels">Channels</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
        </TabsList>

        <TabsContent value="ai">
          <AiModeTab initial={settings.aiMode} />
        </TabsContent>
        <TabsContent value="channels">
          <ChannelsTab initial={settings.channelsEnabled as Record<string, boolean>} />
        </TabsContent>
        <TabsContent value="notifications">
          <NotificationsTab
            initial={{
              notifyHotLead: settings.notifyHotLead,
              notifyComplaint: settings.notifyComplaint,
              notifyBooking: settings.notifyBooking,
              notifyHandoff: settings.notifyHandoff,
            }}
          />
        </TabsContent>
        <TabsContent value="users">
          <UsersTab initial={JSON.parse(JSON.stringify(users))} canManage={!!session && roleAtLeast(session.role, "ADMIN")} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
