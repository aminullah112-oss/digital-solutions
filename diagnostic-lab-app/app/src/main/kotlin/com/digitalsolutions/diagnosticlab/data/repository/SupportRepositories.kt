package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.data.local.dao.ComplaintDao
import com.digitalsolutions.diagnosticlab.data.local.dao.FeverRecordDao
import com.digitalsolutions.diagnosticlab.data.local.dao.MedicalRecordDao
import com.digitalsolutions.diagnosticlab.data.local.entities.ComplaintEntity
import com.digitalsolutions.diagnosticlab.data.local.entities.FeverRecordEntity
import com.digitalsolutions.diagnosticlab.data.local.entities.MedicalRecordEntity
import com.digitalsolutions.diagnosticlab.domain.model.Complaint
import com.digitalsolutions.diagnosticlab.domain.model.ComplaintCategory
import com.digitalsolutions.diagnosticlab.domain.model.ComplaintStatus
import com.digitalsolutions.diagnosticlab.domain.model.MedicalRecord
import com.digitalsolutions.diagnosticlab.domain.model.NotificationType
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.LocalDate

class MedicalRecordRepository(
    private val medicalRecordDao: MedicalRecordDao,
    private val feverRecordDao: FeverRecordDao
) {
    fun observeForPatient(patientId: String): Flow<List<MedicalRecord>> =
        medicalRecordDao.observeForPatient(patientId).map { list -> list.map { it.toDomain() } }

    suspend fun addRecord(patientId: String, type: String, title: String, fileUri: String?, date: LocalDate, notes: String?) {
        medicalRecordDao.upsert(
            MedicalRecordEntity(
                id = "MREC-${System.currentTimeMillis()}", patientId = patientId, type = type,
                title = title, fileUri = fileUri, recordDateEpochDay = date.toEpochDay(),
                notes = notes, createdAt = System.currentTimeMillis()
            )
        )
    }

    fun observeFeverRecords(patientId: String) = feverRecordDao.observeForPatient(patientId)

    suspend fun addFeverRecord(
        patientId: String, date: LocalDate, durationDays: Int?, temperatureCelsius: Double?,
        symptoms: String?, medicationTaken: String?, previousEpisodes: String?, relevantHistory: String?
    ) {
        feverRecordDao.upsert(
            FeverRecordEntity(
                id = "FEV-${System.currentTimeMillis()}", patientId = patientId, recordDateEpochDay = date.toEpochDay(),
                durationDays = durationDays, temperatureCelsius = temperatureCelsius, symptoms = symptoms,
                medicationTaken = medicationTaken, previousEpisodes = previousEpisodes,
                relevantHistory = relevantHistory, createdAt = System.currentTimeMillis()
            )
        )
    }
}

private fun MedicalRecordEntity.toDomain() = MedicalRecord(id, type, title, fileUri, LocalDate.ofEpochDay(recordDateEpochDay), notes)

class ComplaintRepository(
    private val complaintDao: ComplaintDao,
    private val notificationRepository: NotificationRepository
) {
    fun observeForPatient(patientId: String): Flow<List<Complaint>> =
        complaintDao.observeForPatient(patientId).map { list -> list.map { it.toDomain() } }

    fun observeAll(): Flow<List<Complaint>> = complaintDao.observeAll().map { list -> list.map { it.toDomain() } }

    suspend fun submit(patientId: String, bookingId: String?, category: ComplaintCategory, description: String, attachmentUri: String?, notifyUserId: String) {
        complaintDao.upsert(
            ComplaintEntity(
                id = "CMP-${System.currentTimeMillis()}", patientId = patientId, bookingId = bookingId,
                category = category, description = description, attachmentUri = attachmentUri,
                createdAt = System.currentTimeMillis()
            )
        )
        notificationRepository.notify(notifyUserId, NotificationType.COMPLAINT_UPDATE, "Complaint received", "We've logged your complaint and will get back to you.")
    }

    suspend fun updateStatus(complaintId: String, status: ComplaintStatus, resolutionNotes: String?, notifyUserId: String?) {
        val existing = complaintDao.findById(complaintId) ?: return
        complaintDao.update(
            existing.copy(
                status = status,
                resolutionNotes = resolutionNotes ?: existing.resolutionNotes,
                resolvedAt = if (status == ComplaintStatus.RESOLVED || status == ComplaintStatus.CLOSED) System.currentTimeMillis() else existing.resolvedAt
            )
        )
        if (notifyUserId != null) {
            notificationRepository.notify(notifyUserId, NotificationType.COMPLAINT_UPDATE, "Complaint update", "Your complaint status is now ${status.name.lowercase()}.")
        }
    }
}

private fun ComplaintEntity.toDomain() = Complaint(id, patientId, bookingId, category, description, status, createdAt)
