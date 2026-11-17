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
 * Expected document: { upiId: "name@bank", payeeName: "Medwyn Labs", upiEnabled: true }
 * plus these optional fields:
 *  - upiQrPayload:   the bank's UPI QR text ("upi://pay?pa=name@bank&..."). Checkout shows it as a
 *                    QR for the patient to screenshot and scan from their UPI app's gallery option.
 *                    For accounts that refuse payment links and typed IDs.
 *  - upiLinkEnabled: whether to show the "Open UPI app to pay" button. Defaults to true when there
 *                    is no upiQrPayload and false when there is; set it true to show both.
 *  - upiLinkTemplate: the exact link the button opens, with "{amount}" standing for the amount
 *                    (e.g. "upi://pay?pa=name@bank&pn=NAME&am={amount}&cu=INR"). Lets us match
 *                    whatever form a given bank accepts without an app release.
 * Both links must pay the same upiId — a mismatch means the document is wrong, and UPI is
 * switched off rather than risk sending money to the wrong place.
 */
class PaymentConfigRepository(private val firestore: FirebaseFirestore) {

    suspend fun load(): PaymentConfig? {
        val doc = firestore.collection("config").document("payment").get().await()
        if (!doc.exists()) return null
        if (doc.getBoolean("upiEnabled") == false) return null
        val upiId = doc.getString("upiId")?.trim().orEmpty()
        val payeeName = doc.getString("payeeName")?.trim().orEmpty()
        if (!UPI_ID_PATTERN.matches(upiId) || payeeName.isEmpty()) return null

        val qrPayload = doc.getString("upiQrPayload")?.trim()?.takeIf { it.isNotEmpty() }
        if (qrPayload != null && !paysTo(qrPayload, upiId)) return null

        val linkTemplate = doc.getString("upiLinkTemplate")?.trim()?.takeIf { it.isNotEmpty() }
        if (linkTemplate != null && !paysTo(linkTemplate.replace("{amount}", "1.00"), upiId)) return null

        // With a QR on file the pay button is off unless explicitly switched on: accounts that need
        // a QR are the ones that refuse links, so showing a button that fails would be worse than
        // none. Neither a button nor a QR means there is nothing to offer, so UPI stays hidden.
        val linkEnabled = doc.getBoolean("upiLinkEnabled") ?: (qrPayload == null)
        if (!linkEnabled && qrPayload == null) return null

        return PaymentConfig(
            upiId = upiId,
            payeeName = payeeName,
            qrPayload = qrPayload,
            linkEnabled = linkEnabled,
            linkTemplate = linkTemplate
        )
    }

    /** True only for a plain-ASCII upi:// link that pays [upiId] — anything else means the document
     * is wrong, and UPI is switched off rather than risk sending money to the wrong place. (ASCII
     * only because the QR is drawn without a character-set header, see QrCode.kt; UPI links
     * percent-encode everything else anyway.) */
    private fun paysTo(link: String, upiId: String): Boolean {
        val uri = Uri.parse(link)
        return link.length <= MAX_LINK_LENGTH && link.all { it.code in 32..126 } && uri.scheme == "upi" &&
            uri.getQueryParameter("pa").equals(upiId, ignoreCase = true)
    }

    private companion object {
        const val MAX_LINK_LENGTH = 1000
        val UPI_ID_PATTERN = Regex("^[A-Za-z0-9._-]{2,256}@[A-Za-z][A-Za-z0-9]{1,63}$")
    }
}
