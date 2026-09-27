package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.DashboardStats
import com.digitalsolutions.diagnosticlab.domain.model.Laboratory
import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await

/** Backs the admin/owner dashboard. [observeDashboard] just reads the stats/dashboard doc the
 * recalcDashboardStats Cloud Function keeps up to date — no client-side aggregation needed. */
class AdminRepository(private val firestore: FirebaseFirestore) {

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
}

private fun DocumentSnapshot.toLaboratory(): Laboratory? {
    if (!exists()) return null
    return Laboratory(
        id = id,
        name = getString("name").orEmpty(),
        city = getString("city").orEmpty(),
        address = getString("address").orEmpty(),
        phone = getString("phone").orEmpty(),
        openTime = getString("openTime").orEmpty(),
        closeTime = getString("closeTime").orEmpty(),
        homeCollectionAvailable = getBoolean("homeCollectionAvailable") ?: false,
        estimatedReportHours = (getLong("estimatedReportHours") ?: 0L).toInt(),
        rating = (getDouble("rating") ?: 0.0).toFloat(),
        active = getBoolean("active") ?: true
    )
}
