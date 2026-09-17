# PowerTrace AI

Industrial electrical troubleshooting and diagnostic platform for generator control
panels, engine/genset controllers, PPU systems and their associated control circuits.

It combines live controller data, a circuit graph derived from schematics, physical
measurements and a deterministic diagnostic engine to help a technician find where a
control circuit is broken.

---

## Read this before anything else

**PowerTrace AI is not a safety-rated protection system.** It is a diagnostic aid.

* It issues **no control commands**. It does not start or stop engines, open or close
  breakers, synchronise, or change controller or protection configuration. No protocol
  adapter implements a write; `write()` on the adapter base class raises
  `ControlNotPermitted`, and only Modbus read function codes (1, 2, 3, 4) are supported.
* **It never tells you a circuit is safe to touch.** Nothing it displays establishes
  absence of voltage. A controller reporting an output as de-energized is not a
  measurement.
* For medium-voltage systems it displays, on every relevant screen and in every report:
  *VERIFY WITH APPROPRIATELY RATED TEST EQUIPMENT AND FOLLOW SITE SAFETY PROCEDURES.*
* **Never connect ordinary computer or DAQ inputs to medium voltage.** Use rated,
  isolated instrument transformers or transducers. The application refuses a measurement
  channel configuration that implies a direct connection above 60 V — but that check is
  on the configuration, not on what is actually wired in the field.
* It will not recommend bypassing an interlock or defeating a protection function.

---

## The idea the whole application is built around

A number is useless to a technician unless they know where it came from. So no value is
passed around as a bare float. Every value carries:

```json
{
  "value": 24.1,
  "unit": "V",
  "timestamp": "2026-09-16T14:32:02Z",
  "quality": "GOOD",
  "source": "MEASURED",
  "source_detail": "DAQ-01 AI-04"
}
```

`source` is one of:

| Source | Means |
|---|---|
| `MEASURED` | A physical measurement taken with an instrument |
| `CONTROLLER` | Reported by a controller over a protocol |
| `SCHEMATIC` | Derived from a drawing or connectivity model |
| `EXPECTATION` | An engineering expectation — design intent |
| `INFERENCE` | Produced by the rule engine or the AI layer |
| `SIMULATED` | Demo mode |
| `UNKNOWN` | Nothing is known about this point |

`quality` is `GOOD`, `BAD`, `STALE`, `TIMEOUT`, `UNKNOWN` or `SIMULATED`.

These are set at the point of production and are never rewritten downstream. The
consequences are enforced in code, not left to discipline:

* The comparison engine **refuses** to evaluate a `CONTROLLER` value against a voltage
  expectation. A controller saying DO-07 is ON can never render as "24 V present at the
  terminal".
* A point with no physical measurement is `NOT_MEASURED` — a distinct outcome, not a
  pass — and its overlay is gray with the text "NOT MEASURED".
* `CONFIRMED_BY_MEASUREMENT` is reachable only when physical measurements are actually
  in a finding's evidence. The rule evaluator downgrades any rule that claims it
  without them.

---

## Architecture

```
            ┌──────────────────────────┐
            │  React / TypeScript UI   │
            └────────────┬─────────────┘
                REST + WebSocket
            ┌────────────▼─────────────┐
            │      FastAPI backend     │
            └────────────┬─────────────┘
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌───────────────┐ ┌──────────────┐ ┌───────────────┐
│  Controller   │ │  Schematic   │ │  Diagnostic   │
│  integration  │ │  engine      │ │  engine       │
└───────┬───────┘ └──────┬───────┘ └───────┬───────┘
        ▼                ▼                 ▼
  Protocol adapter   Circuit graph     Rule engine
        │                │                 │
        └────────────────┼─────────────────┘
                         ▼
                   AI layer (last, optional)
                         ▼
                  Troubleshooting procedure
```

### Protocol abstraction

```
Controller -> Protocol Adapter -> Data Normalization -> Application
EMCP 4.4   -> Modbus TCP       -> Normalized genset   -> Dashboard
```

| Protocol | State |
|---|---|
| Modbus TCP | Implemented (reads only) |
| Simulator | Implemented (demo mode) |
| Modbus RTU | Interface defined, not implemented — fails with a clear message |
| CAN / J1939 | Interface defined, not implemented |
| OPC UA | Interface defined, not implemented |
| MQTT | Interface defined, not implemented |

The unimplemented adapters are real classes that the registry resolves and that report
honestly, rather than placeholders that produce a stack trace or, worse, empty data that
looks like a healthy zero.

### Register maps: nothing ships with the product

**PowerTrace AI contains no vendor register addresses.** Not Caterpillar's, not anyone
else's. A register map must be imported (CSV or JSON), and:

* It records `source_document` — the document and revision the addresses came from.
* It cannot be marked `verified` without one.
* Re-importing clears `verified`: the content changed and nobody has checked it.
* An unverified map is flagged on the controller list and on every live-data screen.

A wrong register map does not fail loudly. It decodes into plausible, wrong engineering
values — which is the most dangerous failure mode this tool has. Check several readings
against the controller's own display before trusting a map.

The one map that ships is `SIMULATOR DEMO MAP`, flagged `is_simulator_only`, whose
addresses are meaningless placeholders consumed by the built-in simulator. It cannot be
marked verified.

---

## Diagnostics

Deterministic work happens first and stands on its own.

**1. Evidence assembly** — live controller values, active alarms, per-node terminal
status (expected / controller / measured kept separate) and the circuit graph, all
provenance-tagged.

**2. Rule evaluation** — rules are JSON, stored in the database, so a site rule can be
added without a release. Every finding names the rule that produced it and the specific
evidence items that matched.

**3. Discontinuity localization** — the most useful output. Given two *measured* points
on a traced path, one with voltage and one without, the break is bounded between them.
It is stated as a segment and the devices inside it, never as a named failed part.

```
Voltage is present at CTRL_BUS and absent at K12_CONTACT. Both values are physical
measurements, so the discontinuity lies in the segment between these two points,
including the device and terminations in it.
```

**4. Procedure generation** — steps are built from the actual circuit graph, so they
name this panel's components rather than reciting a generic checklist. Each step shows
expected, actual, status, evidence and the next action.

**5. Fault tree** — each branch is `SUSPECT`, `RULED_OUT`, `NOT_MEASURED` or
`UNVERIFIED`. Nothing is ruled out on inference alone.

**6. AI layer (optional, last)** — receives the finished evidence package. Three guard
rails are enforced in code, not requested in the prompt:

* The evidence section of the output is **replaced** with the deterministic evidence
  after the model responds. The model cannot add an observation.
* Numeric values in the model's prose that do not trace to the evidence package are
  listed and the response is downgraded to `UNVERIFIED`.
* The AI can never reach `CONFIRMED_BY_MEASUREMENT`.

With no provider configured the AI section reports `UNAVAILABLE` and says so plainly —
the deterministic findings do not depend on it.

---

## Uploading real schematics

Schematics exported from AutoCAD Electrical, EPLAN, SEE Electrical and similar tools are
**vector** PDFs: the wires are real line segments with coordinates, and the tags are real
text with coordinates. That is the difference between guessing at a drawing and reading
it, and it is what the importer works on.

| Stage | Status |
|---|---|
| Page detection | Implemented |
| Positioned text extraction | Implemented — every text run with its position on the page |
| Line geometry extraction | Implemented — stroked segments, via a PDF content-stream interpreter |
| Device / terminal outline detection | Implemented — closed outlines, split by size |
| Junction dot detection | Implemented — small filled blobs |
| Conductor (net) tracing | Implemented |
| Designator / terminal / wire tag reading | Implemented, confidence-scored |
| OCR of scanned pages | Optional (requires pytesseract + Tesseract) |
| Symbol classification by shape | **Not implemented** — a device's kind comes from its designator (K, F, CB…) |
| Cross-sheet off-page references | **Not implemented** |

### The rules it traces by

These are the drawing conventions, not convenient approximations:

* Two segments sharing an endpoint are the same conductor.
* An endpoint landing on another segment's interior is a T-junction, and is the same
  conductor.
* **Two conductors whose interiors cross are NOT connected.** Wires cross on schematics
  constantly without being joined. Joining them manufactures continuity that does not
  exist, which in a fault-finding tool sends a technician to the wrong side of a panel.
* A crossing is joined only where a junction dot is drawn — which is exactly what the
  dot means.
* **A closed symbol outline is a device, not a length of wire.** A coil, a fuse or a
  controller block breaks the conductor, so it stays a component between two wires
  instead of dissolving into one. Tracing straight through a component would hide the
  very break someone is looking for.
* A wire number binds to a conductor only when it sits alongside that conductor's body.
  A tag that merely happens to be near a crossing line is not claimed by it.

### Review

Everything the importer produces is a *proposal* with a confidence band (HIGH ≥ 85%,
MEDIUM ≥ 60%, LOW below) and the evidence that produced it:

```
CONDUCTOR  W-105  (also numbered W-106, W-200)   MEDIUM 68%
  lands on: TB23-14  TB23-20  DO-07  K12
  traced conductor: 11 segment(s), 502 pt, labelled W-105; 1 junction dot(s);
  lands on TB23-14, TB23-20, DO-07, K12. NOTE: this conductor carries more than
  one wire number (W-105, W-106, W-200) — confirm it is really one conductor.
```

Nothing enters the circuit model until a reviewer accepts it. Only HIGH-confidence items
are pre-selected, and anything the tracer itself flagged as ambiguous is never
pre-selected. Accepted nodes are laid out at their position on the drawing, so the
interactive circuit reads like the page it came from. The original file is always
preserved and viewable alongside it.

A **scanned** drawing is raster: no text, no geometry, nothing to trace. With OCR
installed the tags can still be read, but connectivity cannot be recovered from a scan
at all, and the importer reports that rather than proposing something.

### Trying it

`tools/make_sample_schematic.py` generates a vector ladder diagram of the same breaker
close circuit the demo project builds by hand — including a conductor that crosses two
rungs, joined to one by a junction dot and merely crossing the other:

```bash
python tools/make_sample_schematic.py /tmp/E-4412.pdf
```

Upload it under Schematics. It should trace five conductors, keep the close command and
the close coil on separate nets, and flag the conductors carrying more than one wire
number. `tests/test_schematic_import.py` asserts exactly that.

---

## Running it

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set POWERTRACE_SECRET_KEY outside development
./run.sh                      # http://localhost:8000, docs at /docs
```

SQLite is the default so it runs on a laptop in a plant with no database server. Point
`POWERTRACE_DATABASE_URL` at PostgreSQL for a real installation.

The first start creates an administrator from `POWERTRACE_ADMIN_EMAIL` /
`POWERTRACE_ADMIN_PASSWORD` (default `admin@example.com` / `powertrace`). Change it.

### Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173, proxies /api and /ws
```

### Demo mode

No hardware needed. Sign in, go to **Settings → Seed demo project**. You get:

* Two simulated controllers (`EMCP DEMO 01`, `EMCP DEMO 02`)
* A generator breaker close circuit as a circuit graph
* A simulated measurement gateway with measurements on that circuit
* A permanent DEMO MODE banner, and every value tagged `SIMULATED`

Inject faults from Settings: low/high voltage, overcurrent, reverse reactive power,
abnormal frequency, breaker fail to close/open, sensor failure, communication loss,
control voltage loss.

The pre-loaded demo scenario is a breaker that will not close: the controller commands
the close, the K12 coil measures 24.1 V, and 0.2 V is measured downstream of its
contact. The engine localizes the discontinuity to that segment and generates the
procedure. Walk it through Diagnostics → Troubleshooting → Reports.

---

## Deploying it

**This is not a static site.** It needs a running Python process, a database, WebSockets
and disk for uploaded drawings. Static hosting — GitHub Pages, S3, Netlify's free tier —
can serve the frontend, but the frontend on its own is a login screen that can never
authenticate.

### Where it should sit on the network

The backend opens TCP connections to controllers on the plant network. That makes its
placement a security decision before it is a hosting decision:

* Run it **on the plant network**, or on a host with a route to it. A cloud deployment
  needs a VPN or a tunnel back to the panel; do not forward Modbus in from the internet.
* Put the UI behind whatever the site already uses for remote access. Modbus TCP has no
  authentication of its own — anything that can reach port 502 can read the controller,
  and on many devices write to it. PowerTrace AI never writes, but it should not be the
  reason that port becomes reachable.
* One backend process per site. The polling workers and the live value cache are
  per-process state, so a second worker polls the same controllers again and answers with
  different numbers depending on which one you hit. Scale with a proxy in front of one
  process, not with more workers.

### On your own machine (laptop, mini PC, Raspberry Pi)

This is the right shape for anything touching real controllers, and it needs no
database server — SQLite is the default for exactly this reason:

```bash
export POWERTRACE_SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')
export POWERTRACE_ADMIN_PASSWORD='something you actually chose'
docker compose -f docker-compose.local.yml up -d --build
```

Then `http://localhost:8080`, or `http://<machine-ip>:8080` from a tablet on the same
network. Everything persists in `./data` — the database and the uploaded drawings.

To share a link without opening a port, use a Cloudflare Tunnel. Read
[`docs/self-hosting.md`](docs/self-hosting.md) first — it covers what to expose, what
not to, and why a phone makes a poor server but a good client.

### Docker Compose with Postgres

```bash
cd powertrace-ai
export POWERTRACE_SECRET_KEY=$(python -c 'import secrets;print(secrets.token_urlsafe(48))')
export POWERTRACE_ADMIN_PASSWORD='something you actually chose'
docker compose up -d --build
```

Frontend on `http://localhost:8080`, API docs at `/api/docs`. The stack is Postgres,
the backend, and nginx serving the built frontend while proxying `/api` and `/ws` to it —
one origin, so no CORS, one certificate, and a WebSocket that inherits the page's TLS.

The backend **refuses to start** outside development with the default secret key or with
no administrator password set. That check runs before the database is touched, so a
refused start leaves nothing behind.

Two volumes matter: `pgdata` and `schematics`. Losing the second loses the original
drawings the circuit model was reviewed against.

### Split hosting

If the frontend has to live on a static host and the backend elsewhere, build with
`VITE_API_BASE=https://api.example.com` and set `POWERTRACE_CORS_ORIGINS` on the backend
to name the frontend's origin. It works, but prefer the single-origin shape — splitting
adds CORS, a second certificate and a cross-origin WebSocket, which is three more things
to be wrong at 03:00.

### Running it without containers

`backend/run.sh` for development. For anything else, the container is the supported path;
the Dockerfile shows the exact command and the non-root user it runs as.

## Tests

```bash
cd backend && python -m pytest tests/ -q
```

35 tests. `test_safety_invariants.py` pins the rules that make the tool trustworthy —
if any of them fail, the application is telling a technician something it cannot
support. `test_end_to_end.py` walks the demo panel from seeding to report export.

---

## Project layout

```
backend/
  app/
    domain.py              Provenance model, enums, the MV safety notice
    config.py              Environment-driven settings
    models/                SQLAlchemy: 25 tables
    protocols/             base.py, modbus_tcp.py, simulator.py, future.py, registry.py
    services/
      normalization.py     Registers -> normalized signals
      poller.py            Per-controller polling workers
      value_store.py       In-memory live cache + trend ring buffers
      circuit_graph.py     Graph build, direction-aware trace, highlight, path
      expected_actual.py   Deterministic comparison engine
      terminal_status.py   Expected / controller / measured, kept separate
      rules.py             Declarative rule language
      builtin_rules.py     Vendor-neutral diagnostic rules
      diagnostics.py       Evidence, evaluation, discontinuity, procedure
      fault_tree.py        Live-status fault tree
      correlation.py       Cross-source event timeline
      measurement_safety.py  Input rating / isolation validation
      pdf_geometry.py      Vector PDF reader: positioned text, stroked segments,
                           device outlines, junction dots
      net_builder.py       Conductor tracing, junction rules, label binding
      schematic_import.py  Import pipeline over the above, with a text-only fallback
      ai.py                AI layer with response validation
      reports.py           JSON / CSV / HTML / PDF
      demo.py              Demo panel seeding and fault injection
    api/routes/            REST + WebSocket
  tools/
    make_sample_schematic.py   Generates a vector test drawing
  tests/
docker-compose.yml       Postgres + backend + nginx, one command
frontend/
  Dockerfile, nginx.conf   Build and serve, proxying /api and /ws to the backend
  src/
    lib/                   api, config (API origin), types, formatting, hooks
    components/            ui primitives, layout, circuit canvas, fault tree
    pages/                 14 screens
```

---

## Known limits

Worth stating plainly rather than discovering in a plant:

* **Trend buffers are in memory.** They do not survive a server restart, and the
  historian that would decimate samples into PostgreSQL is not written yet. For a
  permanent trend record you need that piece.
* **The measurement gateway is an abstraction with a simulated implementation.** The
  device model, channel safety validation and measurement recording are real; a driver
  that reads a specific physical DAQ over Modbus is not written. Manual measurement
  entry works today.
* **Symbols are located but not classified.** A device outline is found and positioned,
  but what kind of device it is comes from its reference designator, so a panel using
  its own naming scheme needs the component proposals corrected by hand at review.
* **Off-page cross-references are not followed.** Each sheet is traced on its own; a
  conductor continuing on sheet 13 is not joined to its continuation automatically.
* **Curves are reduced to their endpoints.** Wires in a schematic are straight, so this
  is safe for conductors, but a line-hop arc drawn over a crossing wire may split a
  conductor into two nets. Those show up as separate nets at review.
* **PDF report rendering needs ReportLab.** Without it the API says so and returns
  print-ready HTML rather than a broken file.
* **Clock skew between sources is reported, not corrected.** Sub-second ordering between
  a controller and a gateway is not reliable unless the devices are time-synchronised.
* **Authentication is single-tenant with a local user table.** No SSO, no per-project
  ACLs — roles are global.
