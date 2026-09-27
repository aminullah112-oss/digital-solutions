package com.digitalsolutions.diagnosticlab.di

import android.content.Context
import android.content.pm.ApplicationInfo
import android.os.Build
import com.digitalsolutions.diagnosticlab.BuildConfig
import com.digitalsolutions.diagnosticlab.data.repository.*
import com.digitalsolutions.diagnosticlab.notification.SystemNotifier
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.functions.FirebaseFunctions

/**
 * Hand-rolled dependency container. The app is intentionally kept off Hilt/Dagger: with no
 * network access in CI/dev sandboxes to fetch the annotation processor, a plain constructor
 * graph is both simpler to reason about and safer to build for a one-module MVP this size.
 * A single instance lives on [com.digitalsolutions.diagnosticlab.DiagnosticLabApp].
 *
 * Everything here is backed by Firestore now, not the local Room database — see
 * data/local/AppDatabase.kt and data/seed/DemoDataSeeder.kt, which still exist but are no
 * longer wired into any repository (kept for now rather than deleted outright, since ripping
 * out ~15 files is its own separate, carefully-reviewed change).
 */
class AppContainer(context: Context) {

    private val appContext = context.applicationContext
    val sessionManager = SessionManager(appContext)
    private val systemNotifier = SystemNotifier(appContext)
    private val paymentGateway: PaymentGateway = MockPaymentGateway()
    private val firebaseAuth = FirebaseAuth.getInstance().apply {
        // Registering a number under Firebase Console > Phone > "testing" only picks which
        // OTP code the backend accepts later — it does NOT stop the SDK launching
        // RecaptchaActivity/Play Integrity first. On a bare CI/dev emulator with no Play
        // Store that detour hands focus away long enough for AndroidX Test's ActivityScenario
        // to lose track of MainActivity and tear it down (surfaced as "No compose hierarchies
        // found" a few seconds into the walkthrough test).
        //
        // This used to be gated on debuggable alone, on the assumption that disabling
        // verification only skips device attestation and a real number still gets a real SMS.
        // That's wrong: confirmed on a real device running this same debug build, a genuine
        // (non-test) number failed with "missing a valid app identifier" — disabling
        // verification removes Play Integrity entirely, and a real device with no matching
        // disabled-testing exemption has nothing left to authenticate the request with.
        //
        // Tried gating on a Build.* device-fingerprint "looks like an emulator" heuristic next —
        // that also turned out wrong: GitHub's own google_apis emulator image didn't match any
        // of its checks (likely reports a Build.MODEL this heuristic didn't anticipate),
        // silently re-enabling Play Integrity there and bringing back the very
        // RecaptchaActivity-steals-focus bug this whole bypass exists to avoid. BuildConfig.IS_CI
        // is deterministic instead — the CI workflow sets it explicitly (-Pci=true), nothing to
        // guess — with the fingerprint heuristic kept only as a bonus for a developer's own
        // local emulator testing, which isn't relied on for anything.
        if ((appContext.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0 &&
            (BuildConfig.IS_CI || isLikelyEmulator())
        ) {
            firebaseAuthSettings.setAppVerificationDisabledForTesting(true)
        }
    }
    private val firestore = FirebaseFirestore.getInstance()
    // No region argument on either side: createRazorpayOrder/verifyRazorpayPayment (functions/
    // src/index.ts) don't set an explicit region either, so both default to us-central1 and
    // match automatically. The Firestore-triggered functions default to a different region
    // (matching the Firestore database's own location) — that's a 2nd-gen quirk specific to
    // Firestore triggers and doesn't apply to plain callables like these.
    private val functions = FirebaseFunctions.getInstance()

    val notificationRepository = NotificationRepository(firestore, systemNotifier)

    val authRepository = AuthRepository(firebaseAuth, firestore, sessionManager)

    val patientRepository = PatientRepository(firestore)

    val catalogRepository = CatalogRepository(firestore)

    val bookingRepository = BookingRepository(firestore, notificationRepository, paymentGateway, functions)

    val reportRepository = ReportRepository(firestore)

    val medicalRecordRepository = MedicalRecordRepository(firestore)

    val complaintRepository = ComplaintRepository(firestore, notificationRepository)

    val adminRepository = AdminRepository(firestore)
}

/** Best-effort only — not relied on for CI (see BuildConfig.IS_CI above), just a convenience
 * for a developer's own local emulator testing. There's no official "is this an emulator" API,
 * and no fixed set of Build.* values covers every emulator image (confirmed: this alone missed
 * GitHub's own google_apis image), so this is deliberately broad rather than exact. */
private fun isLikelyEmulator(): Boolean =
    Build.FINGERPRINT.startsWith("generic") ||
        Build.FINGERPRINT.startsWith("unknown") ||
        Build.MODEL.contains("google_sdk") ||
        Build.MODEL.contains("sdk_gphone") ||
        Build.MODEL.contains("Emulator") ||
        Build.MODEL.contains("Android SDK built for x86") ||
        Build.MANUFACTURER.contains("Genymotion") ||
        Build.HARDWARE.contains("goldfish") ||
        Build.HARDWARE.contains("ranchu") ||
        (Build.BRAND.startsWith("generic") && Build.DEVICE.startsWith("generic")) ||
        Build.PRODUCT == "google_sdk"
