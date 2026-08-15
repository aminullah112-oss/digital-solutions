# Salon AI Command Center

A production-shaped, omnichannel AI lead-management and customer-service platform for a salon business — WhatsApp, Instagram, Facebook, and website chat all flow through one AI pipeline that classifies intent, scores leads, drafts replies, and escalates to staff when it should.

Built on Next.js 16 (App Router) + TypeScript + Tailwind CSS v4 + PostgreSQL/Prisma, styled as a dark "AI mission control" ops dashboard.

## Demo Mode (no external credentials required)

The app is fully usable out of the box:

- A **rule-based AI engine** (intent detection, lead scoring, sentiment, service matching, reply generation) runs entirely offline — no LLM API key needed. Swap in a real model later by implementing `AnthropicProvider` in `src/lib/ai/provider.ts` and setting `AI_PROVIDER=anthropic`.
- A **live simulator** (toggle in the top bar, "Demo simulation") generates a realistic inbound message across a random channel every 10–20s and runs it through the exact same pipeline real webhooks use — watch the Command Center's Live AI Activity feed update without touching anything.
- `prisma/seed.ts` seeds 50+ customers, 100+ messages, 40 real AI-processed conversations (bookings, hot leads, complaints, follow-ups), services, staff, FAQs, policies, and promotions — by literally running them through `processInboundMessage()`, not hand-authored fake rows.

## Quick start

```bash
npm install
cp .env.example .env          # fill in DATABASE_URL at minimum
npx prisma migrate dev
npm run db:seed
npm run dev
```

Visit `http://localhost:3000/login`. Demo accounts (all password `salon123`):

| Email | Role |
|---|---|
| admin@lumiere.sa | Admin |
| manager@lumiere.sa | Manager |
| staff@lumiere.sa | Staff |

## Install on your phone (PWA)

The app is a Progressive Web App — once it's hosted somewhere with a real URL (it can't be installed straight out of a local `npm run dev`/temporary session), open that URL on your phone and:

- **Android (Chrome)**: tap the **⋮** menu → **Add to Home screen** / **Install app**.
- **iOS (Safari)**: tap the **Share** icon → **Add to Home Screen**.

Either way you get a real home-screen icon that opens full-screen with no browser bar, like a native app. This only affects presentation — it's still the same web app underneath, so it needs to be deployed (Vercel, Docker on any host, etc.) rather than "installed" as a package.

## Docker

```bash
docker compose up --build
```

Runs Postgres + the app together; migrations apply automatically on container start. Run `npm run db:seed` once against the container's `DATABASE_URL` to populate demo data.

## Architecture

```
Inbound message (webhook or simulator)
  → Channel Adapter        src/lib/channels/adapters.ts   (normalizes provider payload)
  → ingestChannelMessage    src/lib/ai/ingest.ts            (customer + conversation identification)
  → processInboundMessage   src/lib/ai/pipeline.ts          (the whole AI pipeline, one call)
      → NLP                 src/lib/ai/nlp.ts               (language, intent, service, sentiment, entities)
      → Scoring              src/lib/ai/scoring.ts + scoring-config.ts (transparent, configurable weights)
      → Handoff rules         src/lib/ai/handoff.ts          (when the AI must NOT respond)
      → Response engine        src/lib/ai/provider.ts + templates.ts (swappable AI provider)
      → Follow-up detection      src/lib/ai/followup.ts       (stale-conversation sweep)
  → Persisted via Prisma (PostgreSQL) → surfaces on every screen via Server Components + short-poll hooks
```

Every screen in the app (Inbox, CRM, Analytics, Decision Center, AI Advisor) reads from this same data — nothing is mocked in the UI layer.

### Channel integration

- `src/lib/channels/adapters.ts` — `WhatsAppAdapter`, `InstagramAdapter`, `FacebookAdapter`, `WebsiteChatAdapter`, all producing a common `NormalizedInboundMessage`.
- `src/app/api/webhooks/{whatsapp,instagram,facebook,website}/route.ts` — signed webhook endpoints (Meta `X-Hub-Signature-256` verification for the three Meta channels, bearer token for the website widget). Signature checks are skipped only when `DEMO_MODE=true`.
- Add a new channel by writing one adapter + one route; the pipeline needs no changes.

### Data model

See `prisma/schema.prisma` — `Customer`, `Conversation`, `Message`, `Lead`, `LeadScore` (transparent scoring breakdown), `Booking`, `Service`, `Staff`, `Promotion`, `FAQ`, `Policy`, `BusinessSettings`, `FollowUp`, `HumanHandoff`, `AiEvent` (live feed), `AnalyticsEvent`, `Campaign`, `User`/`AuditLog` (auth).

### AI transparency

Every lead score is backed by `LeadScore` rows recorded at the moment they're earned (`src/lib/ai/scoring.ts`) — the "Why this score?" panel in the conversation view reads them directly, no black box.

## Connecting real channels

1. Set `DEMO_MODE=false`.
2. Fill in `META_APP_SECRET`, `WHATSAPP_*`, `INSTAGRAM_VERIFY_TOKEN`, `FACEBOOK_*`, `WEBSITE_CHAT_TOKEN` in `.env` (see `.env.example`).
3. Register the webhook URLs with Meta's Cloud API / Messenger Platform, pointing at `/api/webhooks/{whatsapp,instagram,facebook}`.
4. Point your website's chat widget at `/api/webhooks/website` with an `Authorization: Bearer <WEBSITE_CHAT_TOKEN>` header.

Nothing else changes — the same pipeline, scoring, and UI already work against real traffic. Outbound replies (AI and staff) are delivered back to the customer automatically via `src/lib/channels/senders.ts` once the matching access token (`INSTAGRAM_ACCESS_TOKEN`, `WHATSAPP_ACCESS_TOKEN`, `FACEBOOK_PAGE_ACCESS_TOKEN`) is set.

For a full walkthrough of connecting a real Instagram account — Meta app setup, webhook subscription, tokens, and how to test with multiple accounts — see [`docs/INSTAGRAM_SETUP.md`](docs/INSTAGRAM_SETUP.md).

## Roles & permissions

`ADMIN` / `MANAGER` / `STAFF`, enforced both in `src/proxy.ts` (page access) and per-route in API handlers that mutate data. Admins manage users under Settings → Users.
