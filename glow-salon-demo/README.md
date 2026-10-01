# Glow Salon — WhatsApp booking demo

A working demo of the **WhatsApp Enquiry & Booking** offer from ARR Digital, for a fictional salon.
Live at `/glow-salon-demo/` once merged to `master` (GitHub Pages).

## What it shows
- **Customer view:** pick a service → pick a day/time (taken slots are blocked) → name + WhatsApp number → confirmation message and a "send on WhatsApp" button.
- **Owner view:** dashboard of bookings, expected revenue, one-tap "Message customer" and "Cancel". Booking a slot blocks it for the next customer.
- Demo bookings live in the visitor's own browser (`localStorage`). Nothing is sent to a server unless `SHEET_ENDPOINT` is set.

## Configure
Edit the CONFIG block at the top of the script in `index.html`:
- `SALON_WA`: the WhatsApp number that receives booking messages (currently ARR Digital's).
- `SHEET_ENDPOINT`: optional Google Apps Script web-app URL (see `apps-script/Code.gs`) to also log each booking to a Google Sheet and email the owner.

## Turning this into a real client build
1. Replace the services, prices, hours and branding for the client.
2. Deploy `apps-script/Code.gs` on a Sheet the client owns; set `SHEET_ENDPOINT`.
3. For **automatic** WhatsApp confirmations and reminders, connect an official WhatsApp Business API provider (e.g. through n8n). Approved message templates and per-conversation fees apply — quote these to the client up front.
4. Slot availability across all visitors needs the Sheet-backed `doGet()` (already in `Code.gs`) wired into the page.
