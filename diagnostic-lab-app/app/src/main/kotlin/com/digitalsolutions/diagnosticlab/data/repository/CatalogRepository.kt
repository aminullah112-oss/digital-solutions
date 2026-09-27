package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.Investigation
import com.digitalsolutions.diagnosticlab.domain.model.Laboratory
import com.digitalsolutions.diagnosticlab.domain.model.PricedInvestigation
import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FieldPath
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await

class CatalogRepository(private val firestore: FirebaseFirestore) {

    fun observeLaboratories(): Flow<List<Laboratory>> = callbackFlow {
        val registration = firestore.collection("laboratories")
            .whereEqualTo("active", true)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                trySend(snapshot?.documents.orEmpty().mapNotNull { it.toLaboratory() })
            }
        awaitClose { registration.remove() }
    }

    /** Investigations offered by a specific lab, with that lab's pricing. One-shot read + join
     * against the investigations collection rather than a live listener — pricing/catalog data
     * changes rarely enough that a snapshot listener here isn't worth the complexity. */
    fun observePricedInvestigations(laboratoryId: String): Flow<List<PricedInvestigation>> = callbackFlow {
        val registration = firestore.collection("laboratories").document(laboratoryId).collection("pricing")
            .addSnapshotListener { pricingSnapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                val pricingDocs = pricingSnapshot?.documents.orEmpty()
                if (pricingDocs.isEmpty()) {
                    trySend(emptyList())
                    return@addSnapshotListener
                }
                val investigationIds = pricingDocs.map { it.id }
                firestore.collection("investigations").whereIn(FieldPath.documentId(), investigationIds.take(30)).get()
                    .addOnSuccessListener { investigationSnapshot ->
                        val investigationsById = investigationSnapshot.documents.mapNotNull { it.toInvestigation() }.associateBy { it.id }
                        val priced = pricingDocs.mapNotNull { doc ->
                            investigationsById[doc.id]?.let { investigation ->
                                PricedInvestigation(
                                    investigation = investigation,
                                    price = doc.getDouble("price") ?: 0.0,
                                    homeCollectionAvailable = doc.getBoolean("homeCollectionAvailable") ?: false
                                )
                            }
                        }
                        trySend(priced)
                    }
            }
        awaitClose { registration.remove() }
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

private fun DocumentSnapshot.toInvestigation(): Investigation? {
    if (!exists()) return null
    return Investigation(
        id = id,
        name = getString("name").orEmpty(),
        description = getString("description").orEmpty(),
        category = getString("category").orEmpty(),
        sampleType = getString("sampleType").orEmpty(),
        preparationInstructions = getString("preparationInstructions").orEmpty(),
        reportTurnaroundHours = (getLong("reportTurnaroundHours") ?: 0L).toInt()
    )
}
