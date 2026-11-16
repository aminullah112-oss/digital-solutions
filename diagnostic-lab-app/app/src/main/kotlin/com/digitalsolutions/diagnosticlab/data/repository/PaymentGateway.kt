package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.PaymentMethod

/**
 * Cash-at-collection and UPI-direct only now — a real payment gateway (Razorpay) requires its
 * own checkout UI launched from an Activity plus a server-side order-creation/signature-
 * verification round trip, which doesn't fit a plain suspend function; see
 * BookingViewModel.payOnline and functions/src/index.ts (createRazorpayOrder,
 * verifyRazorpayPayment) for that path instead. This interface only remains because cash and
 * UPI-direct still benefit from going through the same success/failure result shape as
 * everything else. Both are equally unverified: neither has a signature check proving money
 * actually moved, so a booking under either method is trusted the same way cash always was
 * (staff reconcile outside the app).
 */
interface PaymentGateway {
    suspend fun charge(amount: Double, method: PaymentMethod): PaymentGatewayResult
}

sealed class PaymentGatewayResult {
    data class Success(val transactionId: String) : PaymentGatewayResult()
    data class Failure(val reason: String) : PaymentGatewayResult()
}

class MockPaymentGateway : PaymentGateway {
    override suspend fun charge(amount: Double, method: PaymentMethod): PaymentGatewayResult =
        PaymentGatewayResult.Success(
            if (method == PaymentMethod.UPI_DIRECT) "UPI_DIRECT_UNVERIFIED" else "CASH_ON_COLLECTION"
        )
}
