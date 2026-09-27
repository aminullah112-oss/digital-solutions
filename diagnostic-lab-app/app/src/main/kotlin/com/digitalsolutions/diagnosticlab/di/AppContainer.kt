package com.digitalsolutions.diagnosticlab.di

import android.content.Context
import com.digitalsolutions.diagnosticlab.data.repository.*
import com.digitalsolutions.diagnosticlab.notification.SystemNotifier
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore

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
    private val firebaseAuth = FirebaseAuth.getInstance()
    private val firestore = FirebaseFirestore.getInstance()

    val notificationRepository = NotificationRepository(firestore, systemNotifier)

    val authRepository = AuthRepository(firebaseAuth, firestore, sessionManager)

    val patientRepository = PatientRepository(firestore)

    val catalogRepository = CatalogRepository(firestore)

    val bookingRepository = BookingRepository(firestore, notificationRepository, paymentGateway)

    val reportRepository = ReportRepository(firestore)

    val medicalRecordRepository = MedicalRecordRepository(firestore)

    val complaintRepository = ComplaintRepository(firestore, notificationRepository)

    val adminRepository = AdminRepository(firestore)
}
