import { prisma } from "@/lib/db/prisma";
import { StaffList } from "@/components/staff/staff-list";

export default async function StaffPage() {
  const staff = await prisma.staff.findMany({
    orderBy: { name: "asc" },
    include: { services: { include: { service: true } } },
  });

  return (
    <div className="mx-auto max-w-[1100px] p-4 md:p-6">
      <div className="mb-5">
        <h1 className="text-lg font-semibold tracking-tight">Staff</h1>
        <p className="text-xs text-muted">Manage staff profiles, availability, and service specialties.</p>
      </div>
      <StaffList initial={JSON.parse(JSON.stringify(staff))} />
    </div>
  );
}
