package com.digitalsolutions.diagnosticlab.domain.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class OtpServiceTest {

    @Test
    fun `correct code succeeds`() {
        val service = OtpService()
        val mobile = "+91 9000000001"
        val code = service.send(mobile)
        val result = service.verify(mobile, code)
        assertEquals(OtpService.VerifyResult.Success, result)
    }

    @Test
    fun `wrong code is rejected and counts down attempts`() {
        val service = OtpService()
        val mobile = "+91 9000000002"
        service.send(mobile)
        val result = service.verify(mobile, "0000") as OtpService.VerifyResult.Incorrect
        assertEquals(2, result.attemptsLeft)
    }

    @Test
    fun `three wrong attempts locks out the challenge entirely`() {
        val service = OtpService()
        val mobile = "+91 9000000003"
        service.send(mobile)
        service.verify(mobile, "0000")
        service.verify(mobile, "0000")
        service.verify(mobile, "0000")
        val afterLockout = service.verify(mobile, "0000")
        assertEquals(OtpService.VerifyResult.NoActiveChallenge, afterLockout)
    }

    @Test
    fun `an expired code is rejected even if correct`() {
        val service = OtpService()
        val mobile = "+91 9000000004"
        val now = 1_000_000L
        val code = service.send(mobile, nowMillis = now)
        val result = service.verify(mobile, code, nowMillis = now + 6 * 60 * 1000L)
        assertEquals(OtpService.VerifyResult.Expired, result)
    }

    @Test
    fun `verifying without ever requesting a code is rejected`() {
        val service = OtpService()
        val result = service.verify("+91 9000000005", "1234")
        assertEquals(OtpService.VerifyResult.NoActiveChallenge, result)
    }

    @Test
    fun `a successful verification consumes the challenge so it cannot be replayed`() {
        val service = OtpService()
        val mobile = "+91 9000000006"
        val code = service.send(mobile)
        assertEquals(OtpService.VerifyResult.Success, service.verify(mobile, code))
        assertEquals(OtpService.VerifyResult.NoActiveChallenge, service.verify(mobile, code))
    }
}
