package com.digitalsolutions.diagnosticlab.domain.model

import java.time.LocalDate

/**
 * UI/ViewModel-facing models. Screens and ViewModels only ever see these, never the Room
 * @Entity classes — that keeps the persistence layer swappable for a real REST backend
 * later without touching a single Composable (see README "Architecture").
 */

data class Session(
    val userId: String,
    val role: UserRole,
    val mobileNumber: String,
    val linkedEntityId: String? = null
)

data class Patient(
    val id: String,
    val accountOwnerUserId: String,
    val relation: Relation,
    val isPrimary: Boolean,
    val fullName: String,
    val dateOfBirth: LocalDate?,
    val sex: String,
    val mobileNumber: String,
    val email: String?
) {
    val age: Int?
        get() = dateOfBirth?.let { LocalDate.now().year - it.year }
}

data class Address(
    val id: String,
    val label: String,
    val line1: String,
    val line2: String?,
    val city: String,
    val state: String,
    val pincode: String,
    val latitude: Double?,
    val longitude: Double?,
    val isDefault: Boolean
) {
    val displayLine: String get() = listOfNotNull(line1, line2, city, state, pincode).joinToString(", ")
}

data class Laboratory(
    val id: String,
    val name: String,
    val city: String,
    val address: String,
    val phone: String,
    val openTime: String,
    val closeTime: String,
    val homeCollectionAvailable: Boolean,
    val estimatedReportHours: Int,
    val rating: Float,
    val active: Boolean = true
)

data class Investigation(
    val id: String,
    val name: String,
    val description: String,
    val category: String,
    val sampleType: String,
    val preparationInstructions: String,
    val reportTurnaroundHours: Int
)

data class PricedInvestigation(
    val investigation: Investigation,
    val price: Double,
    val homeCollectionAvailable: Boolean
)

data class BookingItem(val investigation: Investigation, val price: Double)

data class Booking(
    val id: String,
    val patientId: String,
    val patientName: String,
    val laboratoryId: String,
    val laboratoryName: String,
    val addressLine: String,
    val scheduledDate: LocalDate,
    val scheduledTimeSlot: String,
    val status: BookingStatus,
    val items: List<BookingItem>,
    val totalAmount: Double,
    val phlebotomistId: String?,
    val createdAtMillis: Long
)

data class PhlebotomistProfile(
    val id: String,
    val name: String,
    val mobileNumber: String,
    val professionalId: String,
    val rating: Float
)

data class Assignment(
    val id: String,
    val bookingId: String,
    val phlebotomist: PhlebotomistProfile,
    val status: AssignmentStatus
)

data class TrackingEvent(
    val status: String,
    val timestampMillis: Long,
    val actorRole: String,
    val notes: String?
)

data class Sample(
    val id: String,
    val bookingId: String,
    val collectionTimeMillis: Long,
    val sampleType: String,
    val status: SampleStatus,
    val rejectionReason: SampleRejectionReason?
)

data class Report(
    val id: String,
    val bookingId: String,
    val patientId: String,
    val laboratoryName: String,
    val investigationNames: List<String>,
    val fileUri: String?,
    val status: ReportStatus,
    val generatedAtMillis: Long?
)

data class MedicalRecord(
    val id: String,
    val type: String,
    val title: String,
    val fileUri: String?,
    val date: LocalDate,
    val notes: String?
)

data class Complaint(
    val id: String,
    val patientId: String,
    val bookingId: String?,
    val category: ComplaintCategory,
    val description: String,
    val status: ComplaintStatus,
    val createdAtMillis: Long
)

data class AppNotification(
    val id: String,
    val type: NotificationType,
    val title: String,
    val body: String,
    val read: Boolean,
    val createdAtMillis: Long
)

data class DashboardStats(
    val totalPatients: Int,
    val newPatientsLast7Days: Int,
    val totalBookings: Int,
    val todaysBookings: Int,
    val pendingCollections: Int,
    val samplesInTransit: Int,
    val reportsPending: Int,
    val reportsCompleted: Int,
    val totalRevenue: Double,
    val openComplaints: Int,
    val activeLabs: Int
)

sealed class Result<out T> {
    data class Success<T>(val data: T) : Result<T>()
    data class Failure(val message: String) : Result<Nothing>()
}
