package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.PaymentConfig
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.tasks.await

/**
 * Reads the business's UPI payment details from Firestore (config/payment) instead of compiling
 * them into the app: a wrong UPI ID sends real customer money to the wrong place, so it has to be
 * fixable instantly without a Play release, and the UPI option must not exist at all until real
 * values have been entered. Returns null — and the checkout screen then offers cash only — when
 * the document is missing, switched off (upiEnabled = false), or doesn't look like a valid UPI ID.
 *
 * Expected document: { upiId: "name@bank", payeeName: "Medwyn Labs", upiEnabled: true }
 */
class PaymentConfigRepository(private val firestore: FirebaseFirestore) {

    suspend fun load(): PaymentConfig? {
        val doc = firestore.collection("config").document("payment").get().await()
        if (!doc.exists()) return null
        if (doc.getBoolean("upiEnabled") == false) return null
        val upiId = doc.getString("upiId")?.trim().orEmpty()
        val payeeName = doc.getString("payeeName")?.trim().orEmpty()
        if (!UPI_ID_PATTERN.matches(upiId) || payeeName.isEmpty()) return null
        return PaymentConfig(upiId = upiId, payeeName = payeeName)
    }

    private companion object {
        val UPI_ID_PATTERN = Regex("^[A-Za-z0-9._-]{2,256}@[A-Za-z][A-Za-z0-9]{1,63}$")
    }
}
