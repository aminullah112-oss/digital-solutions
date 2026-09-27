package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.Complaint
import com.digitalsolutions.diagnosticlab.domain.model.ComplaintCategory
import com.digitalsolutions.diagnosticlab.domain.model.ComplaintStatus
import com.digitalsolutions.diagnosticlab.domain.model.MedicalRecord
import com.digitalsolutions.diagnosticlab.domain.model.NotificationType
import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await
import java.time.LocalDate

class MedicalRecordRepository(private val firestore: FirebaseFirestore) {

    private fun collection() = firestore.collection("medicalRecords")

    fun observeForPatient(patientId: String): Flow<List<MedicalRecord>> = callbackFlow {
        val registration = collection().whereEqualTo("patientId", patientId)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                trySend(snapshot?.documents.orEmpty().mapNotNull { it.toMedicalRecord() })
            }
        awaitClose { registration.remove() }
    }

    suspend fun addRecord(patientId: String, accountOwnerUserId: String, type: String, title: String, fileUri: String?, date: LocalDate, notes: String?) {
        val ref = collection().document()
        ref.set(
            mapOf(
                "patientId" to patientId,
                "accountOwnerUserId" to accountOwnerUserId,
                "type" to type,
                "title" to title,
                "fileUri" to fileUri,
                "recordDate" to date.toString(),
                "notes" to notes,
                "createdAtMillis" to System.currentTimeMillis()
            )
        ).await()
    }
}

private fun DocumentSnapshot.toMedicalRecord(): MedicalRecord? {
    if (!exists()) return null
    return MedicalRecord(
        id = id,
        type = getString("type").orEmpty(),
        title = getString("title").orEmpty(),
        fileUri = getString("fileUri"),
        date = getString("recordDate")?.let { runCatching { LocalDate.parse(it) }.getOrNull() } ?: LocalDate.now(),
        notes = getString("notes")
    )
}

class ComplaintRepository(
    private val firestore: FirebaseFirestore,
    private val notificationRepository: NotificationRepository
) {
    private fun collection() = firestore.collection("complaints")

    fun observeForPatient(patientId: String): Flow<List<Complaint>> = callbackFlow {
        val registration = collection().whereEqualTo("patientId", patientId)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                trySend(snapshot?.documents.orEmpty().mapNotNull { it.toComplaint() })
            }
        awaitClose { registration.remove() }
    }

    fun observeAll(): Flow<List<Complaint>> = callbackFlow {
        val registration = collection().addSnapshotListener { snapshot, error ->
            if (error != null) {
                close(error)
                return@addSnapshotListener
            }
            trySend(snapshot?.documents.orEmpty().mapNotNull { it.toComplaint() })
        }
        awaitClose { registration.remove() }
    }

    suspend fun submit(patientId: String, accountOwnerUserId: String, bookingId: String?, category: ComplaintCategory, description: String, attachmentUri: String?, notifyUserId: String) {
        collection().document().set(
            mapOf(
                "patientId" to patientId,
                "patientAccountOwnerUserId" to accountOwnerUserId,
                "bookingId" to bookingId,
                "category" to category.name,
                "description" to description,
                "attachmentUri" to attachmentUri,
                "status" to ComplaintStatus.OPEN.name,
                "createdAtMillis" to System.currentTimeMillis()
            )
        ).await()
        notificationRepository.notify(notifyUserId, NotificationType.COMPLAINT_UPDATE, "Complaint received", "We've logged your complaint and will get back to you.")
    }

    suspend fun updateStatus(complaintId: String, status: ComplaintStatus, resolutionNotes: String?, notifyUserId: String?) {
        val updates = mutableMapOf<String, Any>("status" to status.name)
        if (resolutionNotes != null) updates["resolutionNotes"] = resolutionNotes
        if (status == ComplaintStatus.RESOLVED || status == ComplaintStatus.CLOSED) updates["resolvedAtMillis"] = System.currentTimeMillis()
        collection().document(complaintId).update(updates).await()
        if (notifyUserId != null) {
            notificationRepository.notify(notifyUserId, NotificationType.COMPLAINT_UPDATE, "Complaint update", "Your complaint status is now ${status.name.lowercase()}.")
        }
    }
}

private fun DocumentSnapshot.toComplaint(): Complaint? {
    if (!exists()) return null
    return Complaint(
        id = id,
        patientId = getString("patientId").orEmpty(),
        bookingId = getString("bookingId"),
        category = runCatching { ComplaintCategory.valueOf(getString("category") ?: "OTHER") }.getOrDefault(ComplaintCategory.OTHER),
        description = getString("description").orEmpty(),
        status = runCatching { ComplaintStatus.valueOf(getString("status") ?: "OPEN") }.getOrDefault(ComplaintStatus.OPEN),
        createdAtMillis = getLong("createdAtMillis") ?: 0L
    )
}
