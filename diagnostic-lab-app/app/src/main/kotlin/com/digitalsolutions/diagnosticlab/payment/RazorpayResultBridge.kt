package com.digitalsolutions.diagnosticlab.payment

import kotlinx.coroutines.CompletableDeferred

sealed class RazorpayCheckoutResult {
    data class Success(val paymentId: String, val orderId: String, val signature: String) : RazorpayCheckoutResult()
    data class Failure(val message: String) : RazorpayCheckoutResult()
}

/**
 * Razorpay's Checkout SDK reports its result via a callback on whichever Activity called
 * Checkout.open (PaymentResultWithDataListener) — there's no way for a Compose screen or
 * ViewModel to receive that directly. MainActivity implements the listener and forwards here,
 * so the ViewModel can just suspend on [awaitResult] after launching checkout instead of wiring
 * its own callback plumbing through the NavGraph.
 */
object RazorpayResultBridge {
    private var pending: CompletableDeferred<RazorpayCheckoutResult>? = null

    /** Call this BEFORE Checkout.open(), not after — Activity launches are asynchronous in
     * practice, but registering the deferred first rules out any window where a callback could
     * fire before anything is listening for it, rather than relying on that timing. */
    fun beginAwaiting(): CompletableDeferred<RazorpayCheckoutResult> {
        val deferred = CompletableDeferred<RazorpayCheckoutResult>()
        pending = deferred
        return deferred
    }

    fun completeSuccess(paymentId: String, orderId: String, signature: String) {
        pending?.complete(RazorpayCheckoutResult.Success(paymentId, orderId, signature))
        pending = null
    }

    fun completeFailure(message: String) {
        pending?.complete(RazorpayCheckoutResult.Failure(message))
        pending = null
    }
}
