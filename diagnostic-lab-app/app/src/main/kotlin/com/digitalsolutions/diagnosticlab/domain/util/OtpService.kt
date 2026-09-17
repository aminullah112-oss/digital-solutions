package com.digitalsolutions.diagnosticlab.domain.util

import kotlin.random.Random

/**
 * Simulated OTP authentication. There is no SMS gateway wired up yet (see README), so the
 * generated code is handed back to the caller to display on-screen ("Demo OTP: 4821")
 * instead of being sent anywhere. Swapping in a real SMS provider only means changing
 * [OtpService.send] to call that provider instead of returning the code.
 */
class OtpService {

    private data class Challenge(val code: String, val expiresAtMillis: Long, val attemptsLeft: Int)

    private val challenges = mutableMapOf<String, Challenge>()

    fun send(mobileNumber: String, nowMillis: Long = System.currentTimeMillis()): String {
        val code = Random.nextInt(1000, 9999).toString()
        challenges[mobileNumber] = Challenge(code, nowMillis + OTP_VALIDITY_MS, MAX_ATTEMPTS)
        return code
    }

    sealed class VerifyResult {
        data object Success : VerifyResult()
        data object Expired : VerifyResult()
        data object NoActiveChallenge : VerifyResult()
        data class Incorrect(val attemptsLeft: Int) : VerifyResult()
    }

    fun verify(mobileNumber: String, code: String, nowMillis: Long = System.currentTimeMillis()): VerifyResult {
        val challenge = challenges[mobileNumber] ?: return VerifyResult.NoActiveChallenge
        if (nowMillis > challenge.expiresAtMillis) {
            challenges.remove(mobileNumber)
            return VerifyResult.Expired
        }
        if (challenge.code == code) {
            challenges.remove(mobileNumber)
            return VerifyResult.Success
        }
        val remaining = challenge.attemptsLeft - 1
        if (remaining <= 0) {
            challenges.remove(mobileNumber)
        } else {
            challenges[mobileNumber] = challenge.copy(attemptsLeft = remaining)
        }
        return VerifyResult.Incorrect(remaining)
    }

    companion object {
        private const val OTP_VALIDITY_MS = 5 * 60 * 1000L
        private const val MAX_ATTEMPTS = 3
    }
}
