package com.digitalsolutions.diagnosticlab.data.local.entities

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.digitalsolutions.diagnosticlab.domain.model.AssignmentStatus
import com.digitalsolutions.diagnosticlab.domain.model.BookingStatus
import com.digitalsolutions.diagnosticlab.domain.model.PaymentMethod
import com.digitalsolutions.diagnosticlab.domain.model.PaymentStatus

@Entity(tableName = "bookings")
data class BookingEntity(
    @PrimaryKey val id: String,
    val patientId: String,
    val bookedByUserId: String,
    val laboratoryId: String,
    val addressId: String,
    val scheduledDateEpochDay: Long,
    val scheduledTimeSlot: String,
    val status: BookingStatus,
    val phlebotomistId: String? = null,
    val totalAmount: Double,
    val createdAt: Long,
    val updatedAt: Long,
    val cancellationReason: String? = null
)

@Entity(tableName = "booking_items")
data class BookingItemEntity(
    @PrimaryKey val id: String,
    val bookingId: String,
    val investigationId: String,
    val priceAtBooking: Double
)

@Entity(tableName = "payments")
data class PaymentEntity(
    @PrimaryKey val id: String,
    val bookingId: String,
    val amount: Double,
    val method: PaymentMethod,
    val status: PaymentStatus,
    val transactionId: String? = null,
    val timestamp: Long
)

@Entity(tableName = "phlebotomist_assignments")
data class PhlebotomistAssignmentEntity(
    @PrimaryKey val id: String,
    val bookingId: String,
    val phlebotomistId: String,
    val status: AssignmentStatus,
    val assignedAt: Long,
    val respondedAt: Long? = null,
    val arrivedAt: Long? = null,
    val completedAt: Long? = null
)
