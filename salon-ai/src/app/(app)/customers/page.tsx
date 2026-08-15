import { listCustomers } from "@/lib/data/customers";
import { CustomerTable } from "@/components/customers/customer-table";

export default async function CustomersPage() {
  const customers = await listCustomers();

  return (
    <div className="mx-auto max-w-[1400px] p-4 md:p-6">
      <div className="mb-5">
        <h1 className="text-lg font-semibold tracking-tight">Customer CRM</h1>
        <p className="text-xs text-muted">{customers.length} customers across every channel.</p>
      </div>
      <CustomerTable customers={JSON.parse(JSON.stringify(customers))} />
    </div>
  );
}
