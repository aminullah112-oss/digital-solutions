# Deploying the build API

This is the piece that makes the [UI](../ui/) actually generate parts
instead of just validating them. It's a small Flask/gunicorn service
wrapping `bracket_model.build_bracket()` — the exact same function
`run_batch.py` uses — behind an HTTP API, running inside the same
FreeCAD conda environment Stage 1 built (see `Dockerfile`, which mirrors
`../setup_env.sh`'s steps).

Tested locally in this repo's dev environment (gunicorn + 2 sync workers,
concurrent requests, all four failure paths — bad JSON, missing fields,
unknown material, a manufacturability violation) before writing this
doc; not tested inside an actual Docker build or on real Oracle hardware,
since this development session's own network policy blocks Docker Hub
image pulls entirely (confirmed: pulls to `production.cloudfront.docker.com`
and `pkg-containers.githubusercontent.com` both return 403 here). The
Dockerfile and compose setup follow the same install steps already proven
to work outside a container; a normal VM with unrestricted internet access
shouldn't hit that wall.

## Why this needs a real server, and why HTTPS isn't optional

FreeCAD's Python bindings need its own ~1.5GB conda environment and do
real native (OCCT) geometry computation per request — nothing a static
host or serverless function can run. And because the UI is served from
GitHub Pages over **HTTPS**, browsers block `fetch()` calls from an HTTPS
page to a plain **HTTP** endpoint by default (mixed-content blocking, on
in Chrome and Firefox out of the box) — "Generate real part" would fail
silently against a bare-HTTP backend, not from a bug, from the browser
refusing the request outright. So this setup includes Caddy as a reverse
proxy purely to get automatic, real HTTPS in front of the API.

## 1. Create the VM (Oracle Cloud "Always Free")

1. Sign up at [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) if you don't already have an account.
2. Console → **Compute → Instances → Create Instance**.
3. **Image and shape**: change shape to **Ampere (ARM), VM.Standard.A1.Flex** — this is the Always Free-eligible shape. 2 OCPUs / 12GB RAM is comfortably more than this API needs and still well inside the free allowance (up to 4 OCPUs / 24GB total, across however many A1 instances you run).
4. Image: **Canonical Ubuntu** (24.04, or 22.04 if that's what's offered — either works).
5. Under **Networking**, let it create a new VCN with internet access, and make sure **"Assign a public IPv4 address"** is checked.
6. Add your SSH public key (or have it generate a key pair for you and download the private key).
7. Create the instance, note its **public IP** once it's running.

## 2. Open the firewall for ports 80 and 443

Oracle's default Security List only allows inbound SSH (port 22). Add rules for HTTP/HTTPS:

1. Console → your instance → the VCN link under "Primary VNIC" → the subnet → **Security Lists** → the default list.
2. **Add Ingress Rules** twice: Source CIDR `0.0.0.0/0`, IP Protocol TCP, Destination Port Range `80`, then again for `443`.

(Ubuntu's own `iptables`/`ufw` on the instance defaults to allowing everything outbound and most things inbound already, but if you find ports still blocked once Docker is running, also check `sudo iptables -L` / `sudo ufw status` on the VM itself — Oracle's Ubuntu images sometimes ship with restrictive `iptables` rules on top of the cloud-level Security List.)

## 3. Install Docker on the VM

SSH in (`ssh ubuntu@<public-ip>`), then:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker   # or log out and back in
docker compose version   # confirm the compose plugin is present
```

## 4. Get the code onto the VM

```bash
git clone https://github.com/aminullah112-oss/digital-solutions.git
cd digital-solutions/sheetmetal-pipeline/backend
```

## 5. Pick your HTTPS hostname

If you own a domain, point an A record at the VM's public IP and use that
as `DOMAIN` below. If not, use **sslip.io** — no signup, no DNS setup,
resolves automatically:

```
IP 203.0.113.10  ->  DOMAIN=203-0-113-10.sslip.io
```

(replace the dots in your actual IP with dashes)

## 6. Run it

```bash
export DOMAIN=203-0-113-10.sslip.io          # your actual IP, dashed, .sslip.io
export ALLOWED_ORIGINS=https://aminullah112-oss.github.io
docker compose up -d --build
```

First build takes a while (~5-10 min) — it's installing Miniconda and the
whole FreeCAD conda environment inside the image, same as
`setup_env.sh` does outside one. Watch progress with:

```bash
docker compose logs -f
```

Caddy requests its Let's Encrypt certificate automatically on first
request to your domain over port 443 — this needs ports 80 and 443
actually reachable from the internet (step 2), since Let's Encrypt
validates domain ownership by connecting back to your server.

## 7. Verify

```bash
curl https://203-0-113-10.sslip.io/health
# {"status":"ok","freecad_version":"1.0.0"}
```

If that hangs or fails: check `docker compose ps` (both containers should
show "Up"), `docker compose logs caddy` (certificate issuance errors show
up here first), and that ports 80/443 are actually open both in Oracle's
Security List and the VM's own firewall (step 2's note).

## 8. Point the UI at it

Open the [UI](https://aminullah112-oss.github.io/digital-solutions/sheetmetal-pipeline/ui/),
paste `https://203-0-113-10.sslip.io` into **Backend URL**, click **Check
connection**. Once it shows "Connected", a validated part's **Generate
real part** button downloads a real STEP + DXF pair. The URL is saved in
your browser's local storage so you only have to enter it once per
browser.

## Maintenance

```bash
# View logs
docker compose logs -f api

# After a git pull with backend/scripts/config changes, rebuild:
docker compose up -d --build

# Stop everything
docker compose down
```

The API has no persistent state (each request builds in a temp directory,
zips the result, cleans up) — restarting or rebuilding the containers
never loses anything.

## Security notes (small demo tool, not hardened for production)

- `ALLOWED_ORIGINS` restricts CORS to the origins you list (comma-separated)
  — set it to your actual GitHub Pages origin, not `*`, once you've confirmed
  things work, so random sites can't drive your server from a visitor's browser.
- There's no authentication, no rate limiting, and no per-request resource
  cap beyond gunicorn's request timeout. Fine for a personal tool behind a
  URL only you know; not something to put a link to on a public page without
  adding at least a shared-secret header check in `app.py` first.
- `app.config["MAX_CONTENT_LENGTH"]` caps request bodies at 1MB — plenty for
  this API's small JSON payloads, and a basic guard against abuse.
