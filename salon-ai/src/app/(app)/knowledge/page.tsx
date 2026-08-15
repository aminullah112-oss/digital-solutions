import { prisma } from "@/lib/db/prisma";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ServicesTab } from "@/components/knowledge/services-tab";
import { FaqsTab } from "@/components/knowledge/faqs-tab";
import { PoliciesTab } from "@/components/knowledge/policies-tab";
import { PromotionsTab } from "@/components/knowledge/promotions-tab";
import { BusinessTab } from "@/components/knowledge/business-tab";

export default async function KnowledgePage() {
  const [services, faqs, policies, promotions, settings] = await Promise.all([
    prisma.service.findMany({ orderBy: { name: "asc" } }),
    prisma.fAQ.findMany({ orderBy: { createdAt: "desc" } }),
    prisma.policy.findMany({ orderBy: { type: "asc" } }),
    prisma.promotion.findMany({ orderBy: { startDate: "desc" } }),
    prisma.businessSettings.findUnique({ where: { id: "default" } }),
  ]);

  return (
    <div className="mx-auto max-w-[1100px] p-4 md:p-6">
      <div className="mb-5">
        <h1 className="text-lg font-semibold tracking-tight">Knowledge Base</h1>
        <p className="text-xs text-muted">What the AI knows about your salon — services, FAQs, policies, and promotions.</p>
      </div>

      <Tabs defaultValue="services">
        <TabsList className="mb-4 flex-wrap">
          <TabsTrigger value="services">Services</TabsTrigger>
          <TabsTrigger value="faqs">FAQs</TabsTrigger>
          <TabsTrigger value="policies">Policies</TabsTrigger>
          <TabsTrigger value="promotions">Promotions</TabsTrigger>
          <TabsTrigger value="business">Business Info</TabsTrigger>
        </TabsList>

        <TabsContent value="services">
          <ServicesTab initial={JSON.parse(JSON.stringify(services))} />
        </TabsContent>
        <TabsContent value="faqs">
          <FaqsTab initial={JSON.parse(JSON.stringify(faqs))} />
        </TabsContent>
        <TabsContent value="policies">
          <PoliciesTab initial={JSON.parse(JSON.stringify(policies))} />
        </TabsContent>
        <TabsContent value="promotions">
          <PromotionsTab initial={JSON.parse(JSON.stringify(promotions))} />
        </TabsContent>
        <TabsContent value="business">
          {settings && (
            <BusinessTab
              initial={{
                salonName: settings.salonName,
                address: settings.address,
                phone: settings.phone,
                openingHours: settings.openingHours as { sat_thu?: string; fri?: string },
                socials: settings.socials as { instagram?: string; whatsapp?: string },
              }}
            />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
