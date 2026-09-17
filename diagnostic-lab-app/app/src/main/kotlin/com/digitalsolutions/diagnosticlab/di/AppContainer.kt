package com.digitalsolutions.diagnosticlab.di

import android.content.Context
import com.digitalsolutions.diagnosticlab.data.local.AppDatabase
import com.digitalsolutions.diagnosticlab.data.repository.*
import com.digitalsolutions.diagnosticlab.data.seed.DemoDataSeeder
import com.digitalsolutions.diagnosticlab.domain.util.OtpService
import com.digitalsolutions.diagnosticlab.notification.SystemNotifier

/**
 * Hand-rolled dependency container. The app is intentionally kept off Hilt/Dagger: with no
 * network access in CI/dev sandboxes to fetch the annotation processor, a plain constructor
 * graph is both simpler to reason about and safer to build for a one-module MVP this size.
 * A single instance lives on [com.digitalsolutions.diagnosticlab.DiagnosticLabApp].
 */
class AppContainer(context: Context) {

    private val appContext = context.applicationContext
    val database: AppDatabase = AppDatabase.getInstance(appContext)
    val sessionManager = SessionManager(appContext)
    private val systemNotifier = SystemNotifier(appContext)
    private val otpService = OtpService()
    private val paymentGateway: PaymentGateway = MockPaymentGateway()

    val notificationRepository = NotificationRepository(database.notificationDao(), systemNotifier)

    val authRepository = AuthRepository(database.userDao(), database.patientDao(), otpService, sessionManager)

    val patientRepository = PatientRepository(database.patientDao(), database.addressDao())

    val catalogRepository = CatalogRepository(
        database.laboratoryDao(), database.investigationDao(), database.laboratoryInvestigationDao()
    )

    val bookingRepository = BookingRepository(
        bookingDao = database.bookingDao(),
        bookingItemDao = database.bookingItemDao(),
        paymentDao = database.paymentDao(),
        assignmentDao = database.phlebotomistAssignmentDao(),
        phlebotomistDao = database.phlebotomistDao(),
        sampleDao = database.sampleDao(),
        trackingEventDao = database.sampleTrackingEventDao(),
        reportDao = database.reportDao(),
        patientDao = database.patientDao(),
        laboratoryDao = database.laboratoryDao(),
        addressDao = database.addressDao(),
        investigationDao = database.investigationDao(),
        auditLogDao = database.auditLogDao(),
        notificationRepository = notificationRepository,
        paymentGateway = paymentGateway
    )

    val reportRepository = ReportRepository(database.reportDao(), database.laboratoryDao(), database.investigationDao())

    val medicalRecordRepository = MedicalRecordRepository(database.medicalRecordDao(), database.feverRecordDao())

    val complaintRepository = ComplaintRepository(database.complaintDao(), notificationRepository)

    val phlebotomistRepository = PhlebotomistRepository(database.phlebotomistDao())

    val adminRepository = AdminRepository(
        database.patientDao(), database.bookingDao(), database.reportDao(),
        database.complaintDao(), database.laboratoryDao(), database.sampleDao()
    )

    val demoDataSeeder = DemoDataSeeder(database)
}
