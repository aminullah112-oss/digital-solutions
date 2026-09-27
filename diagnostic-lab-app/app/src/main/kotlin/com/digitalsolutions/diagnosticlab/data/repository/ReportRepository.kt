package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.Report
import com.digitalsolutions.diagnosticlab.domain.model.ReportStatus
import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow

/** Access control note: every query here is scoped by patientId — a patient can only ever
 * observe their own reports because the ViewModel always supplies the signed-in patient's id,
 * never an arbitrary one from user input. Firestore security rules additionally check
 * patientAccountOwnerUserId on read. */
class ReportRepository(private val firestore: FirebaseFirestore) {

    private fun collection() = firestore.collection("reports")

    fun observeForPatient(patientId: String): Flow<List<Report>> = callbackFlow {
        val registration = collection().whereEqualTo("patientId", patientId).addSnapshotListener { snapshot, error ->
            if (error != null) {
                close(error)
                return@addSnapshotListener
            }
            trySend(snapshot?.documents.orEmpty().mapNotNull { it.toReport() })
        }
        awaitClose { registration.remove() }
    }

    fun observePendingForLab(laboratoryId: String): Flow<List<Report>> = callbackFlow {
        val registration = collection()
            .whereEqualTo("laboratoryId", laboratoryId)
            .whereEqualTo("status", ReportStatus.PENDING.name)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                trySend(snapshot?.documents.orEmpty().mapNotNull { it.toReport() })
            }
        awaitClose { registration.remove() }
    }
}

private fun DocumentSnapshot.toReport(): Report? {
    if (!exists()) return null
    @Suppress("UNCHECKED_CAST")
    val names = get("investigationNames") as? List<String> ?: emptyList()
    return Report(
        id = id,
        bookingId = getString("bookingId").orEmpty(),
        patientId = getString("patientId").orEmpty(),
        laboratoryName = getString("laboratoryName") ?: "Laboratory",
        investigationNames = names,
        fileUri = getString("fileUri"),
        status = runCatching { ReportStatus.valueOf(getString("status") ?: "PENDING") }.getOrDefault(ReportStatus.PENDING),
        generatedAtMillis = getLong("generatedAtMillis")
    )
}
