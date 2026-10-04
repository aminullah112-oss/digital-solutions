package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.LabOnboardingStatus
import com.digitalsolutions.diagnosticlab.domain.model.Laboratory
import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.functions.FirebaseFunctions
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await

/**
 * The self-service side of lab onboarding: a signed-in account (any role-less/PATIENT account,
 * per registerLaboratory's own check) registering a new laboratory and managing its profile
 * afterward. The privileged parts — creating the laboratories doc and flipping the caller's
 * own role to LABORATORY — happen server-side in registerLaboratory (functions/src/index.ts),
 * since firestore.rules otherwise permanently blocks a client from granting itself a staff
 * role. See AdminRepository for the admin-side approve/reject half of this flow.
 */
class LaboratoryOnboardingRepository(
    private val firestore: FirebaseFirestore,
    private val functions: FirebaseFunctions
) {

    /** Returns the new lab's ID. The caller still needs to refresh its own cached session
     * (SessionManager.signIn) afterward — this only changes Firestore, not local state. */
    suspend fun registerLaboratory(
        name: String,
        address: String,
        city: String,
        phone: String,
        openTime: String,
        closeTime: String,
        homeCollectionAvailable: Boolean,
        licenseNumber: String?
    ): String {
        val result = functions.getHttpsCallable("registerLaboratory").call(
            mapOf(
                "name" to name,
                "address" to address,
                "city" to city,
                "phone" to phone,
                "openTime" to openTime,
                "closeTime" to closeTime,
                "homeCollectionAvailable" to homeCollectionAvailable,
                "licenseNumber" to licenseNumber
            )
        ).await()
        @Suppress("UNCHECKED_CAST")
        val data = result.data as Map<String, Any>
        return data["labId"] as String
    }

    suspend fun updateProfile(
        labId: String,
        name: String,
        address: String,
        city: String,
        phone: String,
        openTime: String,
        closeTime: String,
        homeCollectionAvailable: Boolean,
        licenseNumber: String?
    ) {
        functions.getHttpsCallable("updateLaboratoryProfile").call(
            mapOf(
                "labId" to labId,
                "name" to name,
                "address" to address,
                "city" to city,
                "phone" to phone,
                "openTime" to openTime,
                "closeTime" to closeTime,
                "homeCollectionAvailable" to homeCollectionAvailable,
                "licenseNumber" to licenseNumber
            )
        ).await()
    }

    /** Backs the lab's own home screen — used to gate it behind a "pending approval" state
     * until laboratories.active flips true. Unlike CatalogRepository.observeLaboratories, this
     * is a single-doc read by ID, so it works regardless of active/onboardingStatus (the owner
     * can always see their own lab, per firestore.rules). */
    fun observeLaboratory(labId: String): Flow<Laboratory?> = callbackFlow {
        val registration = firestore.collection("laboratories").document(labId)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                trySend(snapshot?.toLaboratory())
            }
        awaitClose { registration.remove() }
    }
}

internal fun DocumentSnapshot.toLaboratory(): Laboratory? {
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
        active = getBoolean("active") ?: true,
        onboardingStatus = runCatching { LabOnboardingStatus.valueOf(getString("onboardingStatus") ?: "ACTIVE") }
            .getOrDefault(LabOnboardingStatus.ACTIVE),
        ownerUserId = getString("ownerUserId"),
        licenseNumber = getString("licenseNumber")
    )
}
