# Running PowerTrace AI on your own hardware

Short answer: **a laptop, mini PC or Raspberry Pi works well, and is the correct
shape for anything touching real controllers. A phone does not, for reasons that
are about the operating system rather than the hardware.**

---

## Why local is the right answer here, not a compromise

The backend opens TCP connections to controllers on the plant network. A cloud
host has no route to a panel in a switchroom, so a cloud deployment needs a VPN
or a tunnel back to the site anyway. Running on a machine that is already on that
network removes the problem instead of solving it.

You also do not need a database server. SQLite is the default for exactly this
reason — one panel's configuration, measurements, alarms and diagnostic sessions
fit it comfortably. The data that would actually stress a database is the trend
buffers, and those live in memory by design.

---

## A laptop or mini PC

```bash
cd powertrace-ai
export POWERTRACE_SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')
export POWERTRACE_ADMIN_PASSWORD='something you actually chose'
docker compose -f docker-compose.local.yml up -d --build
```

* `http://localhost:8080` on that machine.
* `http://<machine-ip>:8080` from anything else on the same network — a phone, a
  tablet in front of the panel, a colleague's laptop. This is usually all that is
  needed: a technician wants it on the tablet they are already holding.
* Everything persists in `./data` — the SQLite database and the uploaded
  drawings. Back up that one directory and you have backed up the installation.

**What to watch:** the machine has to stay awake. A laptop that sleeps stops
polling, and the UI will correctly show the controllers as offline rather than
showing stale numbers. On Linux, `sudo systemctl mask sleep.target suspend.target`;
on Windows, set the power plan to never sleep; on macOS, `caffeinate`.

## A Raspberry Pi

A Pi 4 or 5 with 2 GB is comfortable — the whole stack is light, and the images
are multi-architecture so the same compose file builds on arm64. A Pi is arguably
the best fit: cheap, silent, low power, and it can sit permanently on the panel
network rather than leaving with whoever owns the laptop.

Use an SSD or a good-quality A2 card. The SQLite pragmas are set for this
(`synchronous=NORMAL` with WAL), but cheap SD cards still die under sustained
writes.

## Sharing a link from a local machine

Your home or office connection almost certainly cannot accept inbound
connections — most ISPs now use CGNAT, so port forwarding is not available even
if you configure the router. A tunnel solves this without opening anything:

* **Cloudflare Tunnel** (`cloudflared`) — free, no inbound firewall rules, gives
  you HTTPS on a real hostname, and supports WebSockets, which this app needs for
  live values. Best option.
* **Tailscale** — puts the machine on a private network with the people you
  invite. Better than a public URL if the audience is a few named people.
* **ngrok** — fine for a ten-minute demo; the free URL changes each restart.

```bash
cloudflared tunnel --url http://localhost:8080
```

**Before you expose it to the internet, read the next section.**

---

## Where this should sit on a network

This matters more than the hosting choice.

* Modbus TCP has **no authentication of its own**. Anything that can reach port
  502 can read the controller, and on many devices write to it. PowerTrace AI
  never writes — no adapter implements one — but it should not be the reason
  that port becomes reachable from somewhere it was not before.
* A public tunnel to a machine that also has a route to the panel network is a
  path from the internet to that network. For a demo with simulated controllers
  that is fine. For a machine wired to real equipment, put it behind Tailscale or
  your site's existing remote access, not a public URL.
* **Demo mode is the safe thing to share.** Simulated controllers, every value
  tagged SIMULATED, a permanent banner, and nothing connected to real equipment.
  That is what a public link should point at.

---

## Can a phone be the server?

**Android: technically yes, practically no.**

Termux runs Python 3, FastAPI, uvicorn and SQLite, and the dependencies this
project needs are either pure Python (pypdf, pymodbus) or have wheels. You can
genuinely get it running.

What defeats it is the operating system, not the CPU:

* Android suspends background processes aggressively. Doze and the per-app
  battery optimiser will stop a 1 Hz polling loop. You can fight it with
  `termux-wake-lock` and by exempting Termux from battery optimisation, but you
  are working against the platform, and a polling loop that silently stops is
  the worst failure mode this tool has.
* Mobile data is CGNAT'd, so nothing can connect inbound without a tunnel.
* Sustained polling plus a web server means constant wakeups. Expect meaningful
  battery drain and thermal throttling.

So: fine as a party trick or a demo you keep in the foreground. Not something to
leave running.

**iOS: no.** There is no supported way to keep a background network server alive.
a-Shell and iSH exist, but iOS terminates background execution, and iSH is an x86
emulator that would be painfully slow for this anyway.

**What a phone is genuinely good for:** being the *client*. Run the backend on a
Pi or laptop on the panel network and open `http://<ip>:8080` in the phone's
browser. The UI is desktop-first but works on a tablet, and that is the realistic
field setup — the technician holds the screen, the server sits in the cabinet.

---

## Which to choose

| You want | Use |
|---|---|
| A link to show people, no real equipment | Local machine or Pi in demo mode, Cloudflare Tunnel |
| To troubleshoot a real panel | Pi or laptop on the panel network, no public tunnel |
| Several sites, shared server, someone else doing backups | The Postgres stack in `docker-compose.yml` |
| Nothing exposed at all | `docker compose -f docker-compose.local.yml up` and use it on the LAN |
