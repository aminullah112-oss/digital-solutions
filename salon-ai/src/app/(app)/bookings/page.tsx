import { listBookings, listBookingFormOptions } from "@/lib/data/bookings";
import { BookingTable } from "@/components/bookings/booking-table";
import { NewBookingDialog } from "@/components/bookings/new-booking-dialog";

export default async function BookingsPage() {
  const [bookings, options] = await Promise.all([listBookings(), listBookingFormOptions()]);

  return (
    <div className="mx-auto max-w-[1300px] p-4 md:p-6">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Bookings</h1>
          <p className="text-xs text-muted">{bookings.length} bookings across all channels and services.</p>
        </div>
        <NewBookingDialog customers={options.customers} services={options.services} staff={options.staff} />
      </div>
      <BookingTable initial={JSON.parse(JSON.stringify(bookings))} />
    </div>
  );
}
