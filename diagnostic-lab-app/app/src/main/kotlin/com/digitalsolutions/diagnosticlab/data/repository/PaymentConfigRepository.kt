package com.digitalsolutions.diagnosticlab.data.repository

import android.net.Uri
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
 * Expected document: { upiId: "name@bank", payeeName: "Medwyn Labs", upiEnabled: true,
 *                      upiQrPayload: "upi://pay?pa=name@bank&..." (optional) }
 *
 * upiQrPayload is for accounts that only accept scanned QR payments (some bank merchant accounts
 * refuse payment links and typed IDs): when present, checkout shows that QR for the patient to
 * scan from a screenshot instead of a pay button. It must pay the same upiId — a mismatch means
 * the document is wrong, and UPI is switched off rather than risk sending money to the wrong place.
 */
class PaymentConfigRepository(private val firestore: FirebaseFirestore) {

    suspend fun load(): PaymentConfig? {
        val doc = firestore.collection("config").document("payment").get().await()
        if (!doc.exists()) return null
        if (doc.getBoolean("upiEnabled") == false) return null
        val upiId = doc.getString("upiId")?.trim().orEmpty()
        val payeeName = doc.getString("payeeName")?.trim().orEmpty()
        if (!UPI_ID_PATTERN.matches(upiId) || payeeName.isEmpty()) return null

        val rawQr = doc.getString("upiQrPayload")?.trim()
        val qrPayload = if (rawQr.isNullOrEmpty()) {
            null
        } else {
            val uri = Uri.parse(rawQr)
            val validQr = rawQr.length <= MAX_QR_LENGTH && uri.scheme == "upi" &&
                uri.getQueryParameter("pa").equals(upiId, ignoreCase = true)
            if (!validQr) return null
            rawQr
        }
        return PaymentConfig(upiId = upiId, payeeName = payeeName, qrPayload = qrPayload)
    }

    private companion object {
        const val MAX_QR_LENGTH = 1000
        val UPI_ID_PATTERN = Regex("^[A-Za-z0-9._-]{2,256}@[A-Za-z][A-Za-z0-9]{1,63}$")
    }
}
