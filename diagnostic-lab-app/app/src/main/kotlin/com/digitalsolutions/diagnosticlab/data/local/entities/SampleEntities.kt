package com.digitalsolutions.diagnosticlab.data.local.entities

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.digitalsolutions.diagnosticlab.domain.model.SampleRejectionReason
import com.digitalsolutions.diagnosticlab.domain.model.SampleStatus

@Entity(tableName = "samples")
data class SampleEntity(
    @PrimaryKey val id: String,
    val bookingId: String,
    val patientId: String,
    val collectorId: String,
    val collectionTime: Long,
    val collectionLocation: String,
    val sampleType: String,
    val numberOfSamples: Int = 1,
    val status: SampleStatus,
    val rejectionReason: SampleRejectionReason? = null,
    val rejectionNotes: String? = null
)

/** One row per chain-of-custody transition (section 16) — the audit trail patients and staff see. */
@Entity(tableName = "sample_tracking_events")
data class SampleTrackingEventEntity(
    @PrimaryKey val id: String,
    val bookingId: String,
    val sampleId: String? = null,
    val status: String,
    val timestamp: Long,
    val actorId: String,
    val actorRole: String,
    val location: String? = null,
    val notes: String? = null
)
