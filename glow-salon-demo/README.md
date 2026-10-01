# Glow Salon — WhatsApp booking demo

A working demo of the **WhatsApp Enquiry & Booking** offer from ARR Digital, for a fictional salon.
Live at `/glow-salon-demo/` (GitHub Pages).

## What it shows
- **Customer view:** service → stylist (only people who offer that service, or "Any available") → day/time (taken slots blocked, per stylist) → name + WhatsApp number → confirmation and a "send on WhatsApp" button.
- **Owner view:** dashboard of bookings, expected revenue, filter by stylist, one-tap "Message customer" and "Cancel". A booked slot is blocked for that stylist.
- Without `SHEET_ENDPOINT`, bookings live in the visitor's own browser (`localStorage`). With it set, each booking is also written to a Google Sheet and taken slots are shared across all visitors.

## Configure (top of the script in `index.html`)
- `SALON_WA`: WhatsApp number that receives booking messages (currently ARR Digital's).
- `SHEET_ENDPOINT`: Apps Script web-app URL (see below).
- `SERVICES` and `STAFF`: services, prices, stylists and which services each stylist offers (`skills`).

## Deploy the Google Sheets logger (about 5 minutes)
1. Open the booking Sheet. Row 1 must be, in this order:
   `Timestamp | Name | Phone | Service | Stylist | Price | Date | Time | Status`
2. **Extensions → Apps Script.** Delete the sample code, paste `apps-script/Code.gs`, set `NOTIFY_EMAIL`, save.
3. **Deploy → New deployment → ⚙ → Web app.** Description: `booking v1`. *Execute as:* **Me**. *Who has access:* **Anyone**. Click Deploy.
4. Click **Authorize access**, choose your Google account, *Advanced → Go to project (unsafe)* → Allow. (It is your own script; Google shows this for any unverified script.)
5. Copy the **Web app URL** (ends in `/exec`) and paste it into `SHEET_ENDPOINT` in `index.html`. Commit and push.
6. Test: make a booking on the demo page. A row should appear in the Sheet within a few seconds, and you get an email.
7. After editing the script later: **Deploy → Manage deployments → ✏ → Version: New version → Deploy.** The URL stays the same.

Notes: the page sends bookings with `mode:'no-cors'`, so it cannot read the server's reply. If two people pick the same stylist and slot at the same moment, the script rejects the second row (it is never written); the page already hides slots that have been logged.

## Turning this into a real client build
1. Replace services, prices, hours, stylists and branding.
2. Deploy `Code.gs` on a Sheet the client owns.
3. For **automatic** WhatsApp confirmations and reminders, connect an official WhatsApp Business API provider (e.g. through n8n). Approved message templates and per-conversation fees apply — quote these up front.
