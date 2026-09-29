# ARR Lead Engine V11

Single-file CRM (`index.html`, no build step) for finding local businesses and working them through
WhatsApp / call outreach to a sale. Data stays in your browser unless you turn on Supabase sync.

## What changed from V10 and why

| Problem in V10 | V11 |
|---|---|
| Nothing told you *who to contact today*; you had to browse lists | **Today** queue: replies waiting → deals to move → follow-ups due → best-fit new businesses, with a daily first-message target |
| One generic pitch for every business, same 3-day follow-up forever | **Cadence**: intro → follow-up → call → proof → soft close, auto-scheduled, stops on reply, then rests in Nurture and re-engages after 60 days. Every step/template/wait is editable |
| Score was hard-coded per lead | Score is computed and explained (no website, mobile number, review volume, industry fit, audit gaps) |
| Pitch ignored what was actually wrong with the business | Messages open with a **specific hook** (“12 reviews at 4.9★ but no website”, “no WhatsApp button on your site”) |
| Landline numbers got WhatsApp buttons | Indian landlines detected: call-only |
| Replies were logged but not acted on | Reply classes (interested / meeting / price / later / no / wrong number) set the next action and date; “no” = do-not-contact |
| No way to see which message works | Reply rate per template, per touch number, per industry, per source |
| No proposals | Package-based proposal builder → WhatsApp; proposal chase reminders; Won schedules a referral/review ask |
| Website-form leads (Code.gs sheet) lived elsewhere | Import the sheet as CSV; “inbound” leads go straight to the reply-first group |
| Broken code: `openWhatsApp` defined twice, phone regex `\\D`, CSV export with literal `\\n`, `/api/leads/sync` didn't exist | Rewritten as one coherent script; covered by tests |
| Cloud pull overwrote local data; Supabase policies were `using (true)` | Newer-wins merge by `updated`; per-user RLS; anon key can read nothing |
| Backend open to the internet, SSRF in `/api/audit`, single-threaded | Threaded, loopback by default, token auth, CORS allowlist, SSRF guard incl. redirects, Places pagination (up to 60) |

Kept from V10: the rule that **opening WhatsApp is not the same as sending**. A message is only logged after you tap
“✓ Sent” (a banner asks when you come back).

## Daily use

1. **Discover**: Google Places search (needs backend), paste/CSV, or add manually. Duplicates are detected by phone, Place ID, name+area.
2. **Today**: work top to bottom. Tap WhatsApp → send in WhatsApp → come back → ✓ Sent. The next touch is scheduled for you.
3. Reply arrives → **💬 Replied** → classify → the CRM sets the next action.
4. Interested → **Proposal** → WhatsApp → chase reminders → **Won** (or **Lost** with a reason).
5. **Insights** weekly: where the funnel leaks, which template and segment work.

## Setup

Open `index.html` (or host the folder anywhere static). Then Settings:

- Set your name, brand, **portfolio link**, and **real package prices** (defaults are placeholders).
- Tamil intro template is included; have a native speaker review it before using it.

### Backend (optional: Places search + website audit)

```bash
export GOOGLE_PLACES_API_KEY=...        # Places API (New) enabled
export ARR_API_TOKEN=$(openssl rand -hex 16)   # required if HOST is not loopback
python3 backend/server.py                # http://127.0.0.1:8787
```
Put the URL (and token) in Settings → Backend. Optional: `AUTOMATION_WEBHOOK`, `ARR_ALLOWED_ORIGINS`, `HOST`, `PORT`.
An `https://` CRM page cannot call a plain `http://` backend (mixed content); run both locally or put the backend behind HTTPS.

### Cloud sync (optional)

Run `supabase/schema.sql`, create your user in Supabase Auth, **disable public sign-ups**, then sign in from Settings.
Sync is last-write-wins per lead. Settings/templates are **not** synced yet; use the JSON backup to move them.

### Migrating V8/V9/V10 data

Automatic if the old app ran at the same address (V8 key). Otherwise Discover → “Import old data”.

## Tests

```bash
python3 -m unittest tests.test_server
NODE_PATH=$(npm root -g) node tests/ui.test.js     # needs playwright + chromium
```

## Known limits

- Local mode = browser storage. Clearing site data erases it; use Settings → Download backup weekly.
- Supabase sync is tested against a mocked REST API, not a live project.
- No official WhatsApp Business API: sending is manual by design, so it's bounded by how fast you tap. Keep cold volume to ~20–30 new chats/day per number.
- Stage probabilities in the weighted pipeline are guesses until you have 20+ closed deals.
- Website audit is heuristic HTML inspection, good for a hook, not a client deliverable.
