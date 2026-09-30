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

### Free map search (OpenStreetMap)

Discover → “Free map search” needs no key and no card. It geocodes the area with Nominatim, then pulls named businesses within
5–20 km from Overpass, by category. Coverage of small Indian towns is patchy and phone tags are sparse; every result set shows
how many have a phone so you can judge the source quickly. Data © OpenStreetMap contributors (ODbL).

### Landing pages for businesses without a website

On a lead with no website (or only a Facebook/Instagram page), **🌐 Create landing page** builds a sample site from the
business's details (name, phone, WhatsApp, area, Google rating, map), commits it to its own branch (`lp-<name>-<id>`) at
`prospects/<slug>/index.html`, and shows a review link. **Publish live** merges it into `master` (live at
`https://aminullah112-oss.github.io/digital-solutions/prospects/<slug>/` after a minute or two). **Draft proposal message**
writes the WhatsApp message with the live link and your packages; sending it (after you confirm) advances the follow-up cadence,
and the next reminder asks whether they saw the sample.

- Needs a fine-grained GitHub token limited to this repo with *Contents: Read and write* (Settings → Landing pages). It is stored
  on the device only and left out of backups.
- Pages are marked as a sample, `noindex`, and use only real facts (name, phone, address, Google rating). Section text is
  placeholder and says so. Don't publish a page for a business that objects.
- The template is deterministic, not AI-written per business. For a fully custom design, **Copy brief for Claude Code** puts the
  business facts and build instructions on your clipboard.
- Design sample for a fictional business: `arr-lead-engine/sample/index.html`.
- The preview link uses the third-party rawcdn.githack.com host. Publishing to GitHub Pages is the reliable link to send.

### WhatsApp chatbot upsell

Every WhatsApp-able lead gets an **upsell** line in its opportunity list: a WhatsApp chatbot (answers common questions, shares
the catalogue or prices, captures enquiries 24/7) worded for the industry: appointments for clinics, menu and orders for food,
catalogue and bulk enquiries for manufacturers. It is marked *cannot be checked remotely*, because a website audit cannot see
whether a business already runs a bot, so ask before you pitch. It rises in priority when the audit finds no WhatsApp button.
The lead screen has **Send chatbot pitch** (a personalised message with opt-out). The package **WhatsApp Chatbot (add-on)**
is added to Settings → Packages once for existing users, with a placeholder price of ₹10,000; set your real price. The CRM does
not name any specific chatbot vendor. Decide separately which platform you deliver it on.

### Discovery only shows new businesses

Search results hide every business already in the CRM: contacted, lost, not-interested, still-new **and deleted** ones. They
are matched by phone number (last 10 digits), Google place ID, or name + area, so a differently spelled Google listing of a
business you already hold is still caught by its phone. A note says how many were hidden, with a “Show them” toggle. Google
Text Search only returns about 60 results per query, so when a search runs dry, **Search wider for more new businesses**
scans four ~8 km squares around the area centre, then further out each time you press it (about 8 Google requests each; the
ring you reached is remembered per search). Google's free allowance is per request, so widening costs quota, not much money.

### Website check and ARR opportunity

Every business with a website shows the real link, a badge (free builder, social page only, not secure) and a “💡 opportunity”
line in Discover, Leads and the lead screen. With a Google key that also has **PageSpeed Insights API** enabled (free, add it
to the key's API restrictions), “Audit website” runs a real mobile Lighthouse test: speed, SEO, https, mobile-friendliness and
a screenshot. Findings become a “what is missing → what ARR can sell” list with a suggested package, feed the fit score, and
open your outreach message (“your website is slow on mobile phones…”). Tick “Audit their websites after adding” to do it in bulk.
PageSpeed cannot see whether a site has a WhatsApp button or enquiry form. That check needs the optional backend.

### Google Places search without a server

Settings → Google Places: paste a Google Cloud API key (Places API (New) enabled). It's called from the browser, so restrict
the key to your site's referrer and to Places API only, and set a budget alert. The key stays on that device and is not
included in backups. Website audit still needs the backend (browsers can't fetch other sites' HTML).

### Backend (optional: website audit, or Places behind a token)

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
