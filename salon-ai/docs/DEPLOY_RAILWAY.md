# Deploying to Railway

Railway runs the `Dockerfile` already in this repo as-is — a real persistent server, so the live demo simulator (the background timer that generates a new inbound message every 10–20s) works exactly like it does locally. No code changes needed.

## 1. Create the project

1. [railway.app](https://railway.app) → sign in with GitHub → **New Project**.
2. **Deploy from GitHub repo** → select `salon-ai-command-center` (or `digital-solutions` if deploying from there — see note at the bottom).
3. Railway detects the `Dockerfile` automatically and starts a build. It'll fail on the first attempt because there's no database yet — that's expected, continue to step 2.

## 2. Add Postgres

1. In the same project, **New** → **Database** → **Add PostgreSQL**.
2. Railway provisions it and exposes a `DATABASE_URL` variable automatically on the Postgres service.
3. Go to your app service → **Variables** → **New Variable** → click the **⚡ reference** option and select the Postgres service's `DATABASE_URL` (this wires them together — you don't type a connection string by hand, and it updates automatically if Railway ever rotates it).

## 3. Set the app's environment variables

On the app service → **Variables**, add:

```bash
AUTH_SECRET=<run: openssl rand -base64 32>
DEMO_MODE=true
AI_PROVIDER=rule-based
SIMULATION_MIN_INTERVAL_MS=10000
SIMULATION_MAX_INTERVAL_MS=20000
```

(`DATABASE_URL` is already wired from step 2. Leave the Meta/Instagram vars unset until you're ready to connect real channels — see `docs/INSTAGRAM_SETUP.md`.)

Railway injects `PORT` automatically; `next start` already reads it, so nothing to configure there.

## 4. Deploy and seed

1. Trigger a redeploy (Railway → **Deployments** → **Redeploy**, now that `DATABASE_URL` is set). The Dockerfile's `CMD` runs `prisma migrate deploy` automatically on every start, so the schema is created on this deploy.
2. Seed demo data **once**, using the Railway CLI from your own machine:
   ```bash
   npm install -g @railway/cli
   railway login
   railway link            # pick this project
   railway run npm run db:seed
   ```
   Do **not** run this repeatedly — the seed script wipes and re-creates all demo data every time (`prisma/seed.ts` starts with `deleteMany` on every table), which is fine for a fresh demo environment but would destroy any real data if you'd started using it for real conversations.
3. Railway gives you a public URL (Settings → Networking → **Generate Domain**). Open it — you should hit `/login`.

## 5. Log in

Same demo accounts as local dev (all password `salon123`): `admin@lumiere.sa`, `manager@lumiere.sa`, `staff@lumiere.sa`. Change these before giving anyone else access — see Settings → Users in the app, or update directly via Prisma.

## Installing it on your phone

Once the public URL is live, open it in your phone's browser and use **Add to Home Screen** (see the main README's PWA section) — the app is fully installable once it has a real address.

## Alternative: Render

Render works the same way — **New** → **Web Service** → connect the repo → it detects the Dockerfile → add a **Postgres** instance from Render's dashboard and wire `DATABASE_URL` the same way. The one difference: Render's **free** tier spins the service down after 15 minutes of inactivity and wakes it on the next request (~30s cold start), which pauses the live simulator while asleep. Railway doesn't have that behavior on its standard plan, which is why it's the default recommendation here.

## Note if deploying from `digital-solutions` instead of the standalone repo

If you point Railway at the monorepo (`aminullah112-oss/digital-solutions`) rather than the standalone `salon-ai-command-center` repo, set the service's **Root Directory** to `salon-ai` in Railway's settings — otherwise it'll try to build the static portfolio site at the repo root instead.
