package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.Report
import com.digitalsolutions.diagnosticlab.domain.model.ReportStatus
import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow

class ReportRepository(private val firestore: FirebaseFirestore) {

    private fun collection() = firestore.collection("reports")

    /**
     * Firestore validates a list/listen query against security rules using the query's own
     * filter fields, not the data it happens to return — a query filtered on `patientId` can
     * never satisfy a rule written in terms of `patientAccountOwnerUserId` (a different field),
     * so it's rejected outright with PERMISSION_DENIED regardless of whether every actual match
     * would pass. Query on the field the rule checks instead, then narrow to the specific
     * family member client-side.
     */
    fun observeForPatient(ownerUserId: String, patientId: String): Flow<List<Report>> = callbackFlow {
        val registration = collection().whereEqualTo("patientAccountOwnerUserId", ownerUserId)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                trySend(snapshot?.documents.orEmpty().mapNotNull { it.toReport() }.filter { it.patientId == patientId })
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
