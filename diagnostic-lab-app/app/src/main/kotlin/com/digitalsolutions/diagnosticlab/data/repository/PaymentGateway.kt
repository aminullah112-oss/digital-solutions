package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.PaymentMethod
import kotlinx.coroutines.delay
import kotlin.random.Random

/**
 * Abstraction over "however we actually take money". Nothing else in the app talks to a
 * payment SDK directly — swap [MockPaymentGateway] for a Razorpay/Stripe/etc. adapter that
 * implements this same interface to go live, no other code changes.
 */
interface PaymentGateway {
    suspend fun charge(amount: Double, method: PaymentMethod): PaymentGatewayResult
}

sealed class PaymentGatewayResult {
    data class Success(val transactionId: String) : PaymentGatewayResult()
    data class Failure(val reason: String) : PaymentGatewayResult()
}

/** Simulates a real gateway round-trip with a delay and an occasional decline, purely for demo purposes. */
class MockPaymentGateway : PaymentGateway {
    override suspend fun charge(amount: Double, method: PaymentMethod): PaymentGatewayResult {
        if (method == PaymentMethod.CASH) return PaymentGatewayResult.Success("CASH_ON_COLLECTION")
        delay(700)
        return if (Random.nextInt(100) < 92) {
            PaymentGatewayResult.Success("TXN-${System.currentTimeMillis()}")
        } else {
            PaymentGatewayResult.Failure("Payment was declined by your bank. Please try again or choose cash.")
        }
    }
}
