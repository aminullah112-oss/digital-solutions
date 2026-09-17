package com.digitalsolutions.diagnosticlab.data.local.entities

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.digitalsolutions.diagnosticlab.domain.model.ComplaintCategory
import com.digitalsolutions.diagnosticlab.domain.model.ComplaintStatus
import com.digitalsolutions.diagnosticlab.domain.model.NotificationType

@Entity(tableName = "notifications")
data class NotificationEntity(
    @PrimaryKey val id: String,
    val userId: String,
    val type: NotificationType,
    val title: String,
    val body: String,
    val relatedEntityId: String? = null,
    val read: Boolean = false,
    val createdAt: Long
)

@Entity(tableName = "complaints")
data class ComplaintEntity(
    @PrimaryKey val id: String,
    val patientId: String,
    val bookingId: String? = null,
    val category: ComplaintCategory,
    val description: String,
    val attachmentUri: String? = null,
    val status: ComplaintStatus = ComplaintStatus.OPEN,
    val createdAt: Long,
    val resolvedAt: Long? = null,
    val resolutionNotes: String? = null
)

@Entity(tableName = "audit_logs")
data class AuditLogEntity(
    @PrimaryKey val id: String,
    val actorId: String,
    val actorRole: String,
    val action: String,
    val entityType: String,
    val entityId: String,
    val timestamp: Long,
    val details: String? = null
)
