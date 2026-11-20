package com.digitalsolutions.diagnosticlab.data.repository

import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.tasks.await

/** Switches for features that can be turned on or off without a new release, read from
 * Firestore config/features. Every flag defaults to off when the document or field is missing
 * or can't be read. */
class FeatureFlagRepository(private val firestore: FirebaseFirestore) {

    /** Fever Check suggests tests from a symptom questionnaire. It stays hidden until a doctor has
     * reviewed its rules and config/features.feverCheckEnabled is set to true. */
    suspend fun feverCheckEnabled(): Boolean = try {
        firestore.collection("config").document("features").get().await().getBoolean("feverCheckEnabled") ?: false
    } catch (e: Exception) {
        false
    }
}
