# Diagnostic Lab — Home Sample Collection Marketplace (Android)

A Kotlin + Jetpack Compose Android app for a multi-laboratory diagnostic marketplace with
home sample collection — patients book tests from any onboarded lab, a phlebotomist
collects the sample at home, the lab processes it, and the patient gets a report. Built for
40+ and elderly users: large type, high contrast, minimal typing, voice input where it helps.

This lives at `diagnostic-lab-app/` inside the `digital-solutions` repo, alongside the
unrelated portfolio site and sheet-metal pipeline project — see the root README for how
this repo is organized.

## Scope and honesty check

The original spec asked for a complete production platform: four full role-based apps,
live GPS tracking, a real payment gateway, SMS/WhatsApp notifications, LIMS integration,
and a hardened multi-tenant backend. That is genuinely months of work for a team, not
something to claim as "done" after one build pass. What's actually here:

- **Built and functional**: the full patient journey end-to-end (register → OTP → profile
  → book for self/family → pick lab → pick tests → schedule → address → pay → track →
  view report), plus working phlebotomist, laboratory, and admin flows — all backed by a
  real local database, not static mockups.
- **Simulated, by design, because there's no backend yet**: OTP is generated in-app and
  shown on screen instead of sent by SMS; payment goes through a mock gateway behind a
  real `PaymentGateway` interface; push notifications fire locally instead of via FCM;
  phlebotomist/sample location is captured via device GPS but there's no live map or
  routing (no Maps API key provisioned).
- **Not done**: only the most visible screens (Home, bottom nav, Login/OTP, Settings) have
  their strings extracted into `strings.xml`/`values-ta`; the rest of the app's English UI
  text is still inline. The `LocaleHelper` + per-app-language plumbing is real and wired
  up end-to-end, so extending it to the remaining screens is a matter of swapping
  `Text("...")` for `Text(stringResource(R.string...))`, not new architecture.
- **Not run**: this was built in a sandboxed environment with no Android SDK and no
  network access to Google's/Maven's dependency repositories, so `./gradlew build` could
  not actually be executed here. The code was written carefully and cross-checked by hand
  (every DAO call, repository constructor, and screen reference was grep-verified against
  its declaration), but it has not been compiled or run on a device/emulator. Please build
  it in Android Studio (or CI with network access) before treating it as verified, and file
  issues for whatever the compiler catches that this review didn't.

## Getting it running

1. Open `diagnostic-lab-app/` in Android Studio (Koala/2024.1 or newer recommended).
2. Let Gradle sync — it will generate `gradle/wrapper/gradle-wrapper.jar` for you. If you
   prefer the command line, run `gradle wrapper --gradle-version 8.7` once from this
   directory with a local Gradle 8.x install, then use `./gradlew` as normal.
3. Run the `app` configuration on an emulator or device with API 26+.
4. On first launch the app seeds itself with demo data (see below) — no backend, no
   account, no API key needed to explore every screen.

### Signing in

There's no real SMS gateway, so OTP is simulated: enter any mobile number, and the OTP
screen shows the code directly ("Demo OTP: 4821"). Use one of these to see a specific
role, or any new number to create a fresh patient account:

| Role | Mobile number |
|---|---|
| Patient (seeded, with bookings/reports) | `+91 9000000001` through `+91 9000000010` |
| Phlebotomist | `+91 98400 10001` through `...10005` |
| Laboratory | `+91 98500 20001` through `...20005` |
| Admin | `+91 90001 00000` |

## Architecture

Clean-ish layering in a single Gradle module (kept as one module deliberately — see
"Why no Hilt / one module" below):

```
domain/       Pure Kotlin: enums, status state machines, ID generation, OTP simulation,
              UI-facing data classes. No Android imports.
data/local/   Room: entities, DAOs, AppDatabase. This is the only "backend" today.
data/repository/  One repository per bounded area (Auth, Patient, Catalog, Booking,
              Report, MedicalRecord, Complaint, Phlebotomist, Admin, Notification).
              BookingRepository is the orchestrator for the whole booking → collection →
              lab → report chain-of-custody (spec section 16) — every status change goes
              through it so the status-machine rules in domain/util can't be bypassed.
data/seed/    DemoDataSeeder — realistic fake data, clearly marked isDemoData = true.
di/           AppContainer: a hand-wired dependency graph (see below), plus
              LocalAppContainer, a CompositionLocal that hands it to Compose screens.
notification/ Local Android notifications (no push server yet) + per-app locale plumbing.
presentation/ Compose UI by feature (patient/*, phlebotomist/, lab/, admin/, auth/),
              plus shared components (theme, StatusTimeline, VoiceEnabledTextField, etc.)
              and the single NavGraph that switches role-based start destinations based
              on the signed-in user's role.
```

**Why no Hilt/Dagger, no nested navigation graphs, no server-backed Retrofit calls**: this
was built in a sandbox with no network access to Google's/Maven's repositories, so an
annotation-processor-heavy dependency graph (Hilt) couldn't be pulled down or even verified
to compile here. Room's KSP compiler is unavoidable (Room requires it) and is the one place
this still depends on a working Maven Central connection at build time — everything else
was kept deliberately low on build-tool surface area so the risk of an un-verifiable build
error is concentrated in as few places as possible. `AppContainer` is a plain constructor
graph; swapping it for Hilt later is mechanical (add `@Inject` constructors, delete the
container). Retrofit is declared as a dependency and the repository interfaces are already
shaped for a remote implementation, but no `LocalXRepository` has a real HTTP counterpart
yet — that's the actual next step toward a production backend.

### Database

20 Room entities covering every table the spec calls for: `users`, `patients` (family
members are just additional patient rows linked via `accountOwnerUserId` + `relation`),
`addresses`, `laboratories`, `investigations`, `laboratory_investigations` (per-lab
pricing), `phlebotomists`, `bookings`, `booking_items`, `payments`,
`phlebotomist_assignments`, `samples`, `sample_tracking_events` (the chain-of-custody
audit trail), `reports`, `medical_records`, `fever_records`, `notifications`,
`complaints`, `audit_logs`.

### Status machines

`BookingStatusMachine` and `AssignmentStatusMachine` (in `domain/util`) are the single
source of truth for which status transitions are legal. `BookingRepository` calls into
them before writing any status change, so nothing in the UI layer can push a booking from
`CONFIRMED` straight to `REPORT_READY`. These are the parts with unit test coverage — see
below.

### Payments

`PaymentGateway` is an interface; `MockPaymentGateway` simulates a ~92%-success online
charge and an always-succeeding cash selection. Swapping in Razorpay/Stripe/PayU means
implementing that interface and changing one line in `AppContainer` — nothing else in the
app talks to a payment SDK directly.

### Notifications

`SystemNotifier` wraps `NotificationManager` for real on-device notifications; there is no
FCM/SMS/WhatsApp backend to push from yet since there's no server. `NotificationRepository`
mirrors every event into the in-app notification center (the bell icon) and calls
`SystemNotifier` at the same time — a future FCM integration would call the same `notify()`
method from a push-received handler instead of from the repository directly.

### Location & voice

- GPS: `BookingAddressScreen` requests `ACCESS_FINE_LOCATION` and reads
  `LocationManager.getLastKnownLocation` — coordinates are stored with the address but
  there's no live map/route rendering (that needs a Maps API key and billing account this
  environment can't provision).
- Voice: `VoiceEnabledTextField` uses Android's built-in `RecognizerIntent` speech-to-text
  (no cloud API key needed) for investigation search, complaint text, and medical-history
  notes. Every voice-enabled field has a normal keyboard as the default input — voice is
  never mandatory, per spec.

## Demo data

`DemoDataSeeder` runs once on first launch (skips if data already exists) and creates:
5 laboratories, 20 investigations (CBC, CRP, Dengue NS1, LFT/KFT, HbA1c, Thyroid Profile,
Vitamin D/B12, COVID-19 RT-PCR, etc.), per-lab pricing links, 5 phlebotomists, 10 patient
accounts + 5 linked family members, and 20 bookings spread across every status in the
chain-of-custody (including delivered reports) with their tracking-event history. Lab
names are invented (Sunrise Diagnostics, Apex Pathlabs, ...) rather than real companies.
Entities that support it carry `isDemoData = true`; delete rows with that flag (or drop
the database) before shipping to production.

## Tests

`app/src/test/` has JVM unit tests (no Robolectric/Room needed) for the parts of the app
where a silent logic bug would be worst: `IdGeneratorTest`, `BookingStatusMachineTest`,
`AssignmentStatusMachineTest`, `OtpServiceTest`, `PaymentGatewayTest`. Repository- and
ViewModel-level tests would be the natural next addition — the repositories take DAO
interfaces as constructor parameters specifically so they can be swapped for
Robolectric's in-memory Room database or hand-written fakes in a test.

## Known gaps / next steps, in priority order

1. Run an actual `./gradlew build` / instrumented run and fix whatever the compiler and a
   real device catch that this review didn't (see "Not run" above).
2. Extract the remaining screens' strings into `strings.xml` + `values-ta` (Home, Login,
   OTP, and Settings are already done as the reference pattern).
3. Wire a real backend: turn the repository interfaces' local implementations into
   Retrofit-backed ones, keep Room as an offline cache.
4. Real payment gateway integration behind `PaymentGateway`.
5. FCM for real push notifications; SMS/WhatsApp for OTP and status updates.
6. Maps SDK for live phlebotomist tracking (needs an API key + billing).
7. Repository/ViewModel test coverage beyond the status-machine/util layer.
