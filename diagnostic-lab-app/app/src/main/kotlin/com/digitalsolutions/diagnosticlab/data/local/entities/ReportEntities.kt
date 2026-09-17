package com.digitalsolutions.diagnosticlab.data.local.entities

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.digitalsolutions.diagnosticlab.domain.model.ReportStatus

@Entity(tableName = "reports")
data class ReportEntity(
    @PrimaryKey val id: String,
    val bookingId: String,
    val patientId: String,
    val laboratoryId: String,
    val investigationIds: List<String>,
    val fileUri: String? = null,
    val status: ReportStatus,
    val generatedAt: Long? = null,
    val verifiedByUserId: String? = null,
    val deliveredAt: Long? = null
)

/** Free-form medical history entry: an uploaded prior report/prescription, or a note. */
@Entity(tableName = "medical_records")
data class MedicalRecordEntity(
    @PrimaryKey val id: String,
    val patientId: String,
    val type: String,
    val title: String,
    val fileUri: String? = null,
    val recordDateEpochDay: Long,
    val notes: String? = null,
    val createdAt: Long
)

/**
 * Fever questionnaire. Fields are intentionally free-text/nullable rather than driving any
 * diagnosis logic — per the spec this is clinician-defined content the app only stores.
 */
@Entity(tableName = "fever_records")
data class FeverRecordEntity(
    @PrimaryKey val id: String,
    val patientId: String,
    val recordDateEpochDay: Long,
    val durationDays: Int? = null,
    val temperatureCelsius: Double? = null,
    val symptoms: String? = null,
    val medicationTaken: String? = null,
    val previousEpisodes: String? = null,
    val relevantHistory: String? = null,
    val doctorNotes: String? = null,
    val createdAt: Long
)
