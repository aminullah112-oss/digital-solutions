package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.PaymentMethod
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertTrue
import org.junit.Test

class PaymentGatewayTest {

    @Test
    fun `cash payments always succeed without a card-network round trip`() = runBlocking {
        val gateway: PaymentGateway = MockPaymentGateway()
        val result = gateway.charge(500.0, PaymentMethod.CASH)
        assertTrue(result is PaymentGatewayResult.Success)
        assertTrue((result as PaymentGatewayResult.Success).transactionId.isNotBlank())
    }

    @Test
    fun `online payments resolve to a well-formed outcome either way`() = runBlocking {
        val gateway: PaymentGateway = MockPaymentGateway()
        // Run enough attempts to exercise both branches of the simulated ~92% success rate.
        repeat(30) {
            when (val result = gateway.charge(500.0, PaymentMethod.ONLINE)) {
                is PaymentGatewayResult.Success -> assertTrue(result.transactionId.isNotBlank())
                is PaymentGatewayResult.Failure -> assertTrue(result.reason.isNotBlank())
            }
        }
    }
}
