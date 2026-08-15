# Connecting a Real Instagram Account

This walks through wiring a real Instagram Business/Creator account into the app so DMs actually flow through the AI pipeline — both receiving them (already built) and sending AI/staff replies back out (now built, see "What changed" below).

## What changed to make this testable

Before this guide, the app could *receive* Instagram webhook messages but had no way to *send* a reply back to Instagram — the AI's reply only ever showed up inside the app's own Inbox UI. Testing with a real account would have meant sending a DM and never seeing anything come back. Two things were fixed to close that loop:

1. **`Customer.externalId`** — the Instagram/Facebook sender id (PSID) is now saved on the customer record, so the app has somewhere to send a reply back *to*, and so the same person messaging twice reuses one customer/conversation instead of creating a duplicate each time.
2. **`src/lib/channels/senders.ts`** — calls the Graph API's `/me/messages` endpoint to actually deliver AI and staff replies. It's wired into the three places a reply gets created: the AI pipeline's auto-response, a staff typing a manual reply, and approving a queued/follow-up message. It's a safe no-op (does nothing, no error) whenever the relevant access token isn't set — so Demo Mode is unaffected.

## Two ways to connect Instagram

**Recommended for testing: "Instagram API with Instagram Login"** — a professional Instagram account (Business or Creator) logs into your Meta app directly. No Facebook Page required. This is the simplest path when you want to test with several different client accounts, since each one just logs in independently.

**Alternative: classic Messenger Platform path** — the Instagram account must be linked to a Facebook Page, and you get a Page Access Token instead. Use this if you're already managing the salon's Facebook Page anyway, or if Instagram Login isn't available for a given account type.

Both paths land in the same place: an access token (for sending) and a webhook subscription (for receiving), which is all this app needs.

## Step by step

### 1. Prerequisites

- The Instagram account must be a **Business** or **Creator** account (not personal). Convert it in the Instagram app: Settings → Account type and tools → Switch to professional account.
- You'll need a Meta Developer account at [developers.facebook.com](https://developers.facebook.com).

### 2. Create a Meta App

1. [developers.facebook.com/apps](https://developers.facebook.com/apps) → **Create App** → choose **"Other"** → **"Business"** as the app type.
2. Once created, go to **App Settings → Basic**. Copy the **App Secret** — this becomes `META_APP_SECRET` in `.env`. It's what verifies the `X-Hub-Signature-256` header on every incoming webhook, so the app can trust that requests really came from Meta.

### 3. Add Instagram messaging

1. From the app dashboard, **Add Product** → **Instagram** → set up **"Instagram API with Instagram Login"**.
2. Follow Meta's prompt to have the Instagram Business/Creator account log in and authorize the app. This grants the app permission to read and send messages for that account.
3. Under the Instagram product's settings, generate a **User Access Token** (or set up a long-lived token — Meta's UI walks through exchanging a short-lived token for a long-lived one, which lasts ~60 days and can be refreshed). This value goes into `INSTAGRAM_ACCESS_TOKEN`.

### 4. Subscribe the webhook

1. Still in the Instagram product settings, find **Webhooks** and click **Subscribe**.
2. **Callback URL**: `https://<your-domain>/api/webhooks/instagram`
   - Testing locally? You need a public HTTPS URL pointing at your `npm run dev` server. Use a tunnel:
     ```bash
     npx localtunnel --port 3000
     # or
     cloudflared tunnel --url http://localhost:3000
     ```
     Use the `https://…` URL it prints as your callback URL.
3. **Verify Token**: any string you choose — put the same value in `INSTAGRAM_VERIFY_TOKEN` in `.env`. Meta calls your callback URL once with this token to confirm you control it; the route at `src/app/api/webhooks/instagram/route.ts` already handles that handshake.
4. **Subscribed fields**: check **`messages`** (this is the one the app's webhook parser reads).

### 5. Configure the app

In `.env`:

```bash
DEMO_MODE="false"                    # enforce real signature verification
META_APP_SECRET="<app secret from step 2>"
INSTAGRAM_VERIFY_TOKEN="<the string you chose in step 4>"
INSTAGRAM_ACCESS_TOKEN="<token from step 3>"
```

Restart the app (`npm run dev` or redeploy) so the new env vars load.

### 6. Test it

1. From a **different** Instagram account (your phone, a friend's account — anything that isn't the connected business account), send a DM to the connected account: *"Hi, how much is a haircut?"*
2. Within a few seconds it should appear in **Inbox** in the app, already processed — intent classified, lead scored, and (in `ASSISTED`/`FULL_AUTO` AI mode) a reply sent back to you on Instagram automatically.
3. If nothing arrives: check the server logs first — Meta's webhook call will show up there, or an error will if signature verification is failing (double check `META_APP_SECRET` matches exactly what's in App Settings → Basic).

## Testing with multiple "client" accounts

Two different meanings worth separating, because they need different setups:

**A. Several different people DMing the same salon account** (most common for testing — you play the customer from a few different Instagram accounts to see how the AI handles different conversations). This needs **no extra setup** — every sender gets their own `Customer`/`Conversation` record automatically (that's exactly what the `externalId` fix above enables). Just message the one connected business account from as many other accounts as you like.

**B. Actually onboarding a different client's salon Instagram account** as the business this app represents. Right now this app is **single-tenant** — one `BusinessSettings` row, one services/FAQ/promotions knowledge base, one set of Meta credentials in `.env`. To test a second real client's Instagram this way you'd currently need to either:
   - point this same deployment's env vars at the new client's token/verify-token and re-seed the knowledge base for their salon, or
   - run a second deployment (Docker makes this cheap — `docker compose up` again with a different `.env` and database).

  If you want to test several client businesses *simultaneously* from one running instance, that needs multi-tenancy (a `Business` model that `Service`/`Staff`/`Customer`/etc. all scope to, keyed off which Instagram account a webhook came from) — a real but scoped extension of the current schema, not something this guide covers. Ask if you want that built.

## Going live with real (non-tester) customers

While your Meta app is in **Development mode**, Instagram messaging only works for accounts added as **testers** under **App Roles → Roles** in the dashboard — fine for your own testing, not for real customers. To message with anyone, submit the app for **App Review** and request the `instagram_business_manage_messages` permission (naming varies slightly as Meta iterates the API — check the current requirement in your app's Permissions tab). Review typically asks for a screencast showing the exact flow this app already implements: a DM comes in, gets processed, and a reply goes out.

## The same pattern applies to WhatsApp and Facebook Messenger

`src/lib/channels/senders.ts` also has `sendWhatsAppMessage` and `sendFacebookMessage`, wired into the same three places. Fill in `WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID` (from the WhatsApp Cloud API product) or `FACEBOOK_PAGE_ACCESS_TOKEN` (from a Facebook Page linked to the Messenger product) the same way, and those channels start delivering real outbound replies too — no code changes needed.
