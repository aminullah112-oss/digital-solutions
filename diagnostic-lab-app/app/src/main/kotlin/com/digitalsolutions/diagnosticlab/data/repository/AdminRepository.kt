package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.DashboardStats
import com.digitalsolutions.diagnosticlab.domain.model.Laboratory
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.functions.FirebaseFunctions
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await

/** Backs the admin/owner dashboard. [observeDashboard] just reads the stats/dashboard doc the
 * recalcDashboardStats Cloud Function keeps up to date — no client-side aggregation needed. */
class AdminRepository(
    private val firestore: FirebaseFirestore,
    private val functions: FirebaseFunctions
) {

    fun observeDashboard(): Flow<DashboardStats> = callbackFlow {
        val registration = firestore.collection("stats").document("dashboard").addSnapshotListener { snapshot, error ->
            if (error != null) {
                close(error)
                return@addSnapshotListener
            }
            trySend(
                DashboardStats(
                    totalPatients = (snapshot?.getLong("totalPatients") ?: 0L).toInt(),
                    newPatientsLast7Days = (snapshot?.getLong("newPatientsLast7Days") ?: 0L).toInt(),
                    totalBookings = (snapshot?.getLong("totalBookings") ?: 0L).toInt(),
                    todaysBookings = (snapshot?.getLong("todaysBookings") ?: 0L).toInt(),
                    pendingCollections = (snapshot?.getLong("pendingCollections") ?: 0L).toInt(),
                    samplesInTransit = (snapshot?.getLong("samplesInTransit") ?: 0L).toInt(),
                    reportsPending = (snapshot?.getLong("reportsPending") ?: 0L).toInt(),
                    reportsCompleted = (snapshot?.getLong("reportsCompleted") ?: 0L).toInt(),
                    totalRevenue = snapshot?.getDouble("totalRevenue") ?: 0.0,
                    openComplaints = (snapshot?.getLong("openComplaints") ?: 0L).toInt(),
                    activeLabs = (snapshot?.getLong("activeLabs") ?: 0L).toInt()
                )
            )
        }
        awaitClose { registration.remove() }
    }

    fun observeAllLaboratories(): Flow<List<Laboratory>> = callbackFlow {
        val registration = firestore.collection("laboratories").addSnapshotListener { snapshot, error ->
            if (error != null) {
                close(error)
                return@addSnapshotListener
            }
            trySend(snapshot?.documents.orEmpty().mapNotNull { it.toLaboratory() })
        }
        awaitClose { registration.remove() }
    }

    suspend fun setLabActive(id: String, active: Boolean) {
        firestore.collection("laboratories").document(id).update("active", active).await()
    }

    /** Approve/reject a self-registered lab (laboratories.onboardingStatus ==
     * PENDING_APPROVAL) — the only path that flips active/onboardingStatus for one of those,
     * since the admin app's own direct [setLabActive] write only touches `active` and would
     * leave onboardingStatus stuck at PENDING_APPROVAL forever. Pre-existing admin-seeded labs
     * (no onboardingStatus field at all) keep using [setLabActive] via the UI's plain toggle. */
    suspend fun reviewLabOnboarding(labId: String, approve: Boolean, reason: String? = null) {
        functions.getHttpsCallable("reviewLaboratoryOnboarding").call(
            mapOf(
                "labId" to labId,
                "decision" to if (approve) "APPROVE" else "REJECT",
                "reason" to reason
            )
        ).await()
    }
}
