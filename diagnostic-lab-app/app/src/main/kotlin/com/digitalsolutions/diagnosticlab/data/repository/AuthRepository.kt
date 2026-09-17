package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.data.local.dao.PatientDao
import com.digitalsolutions.diagnosticlab.data.local.dao.UserDao
import com.digitalsolutions.diagnosticlab.data.local.entities.PatientEntity
import com.digitalsolutions.diagnosticlab.data.local.entities.UserEntity
import com.digitalsolutions.diagnosticlab.domain.model.AppLanguage
import com.digitalsolutions.diagnosticlab.domain.model.Relation
import com.digitalsolutions.diagnosticlab.domain.model.UserRole
import com.digitalsolutions.diagnosticlab.domain.util.IdGenerator
import com.digitalsolutions.diagnosticlab.domain.util.OtpService

class AuthRepository(
    private val userDao: UserDao,
    private val patientDao: PatientDao,
    private val otpService: OtpService,
    private val sessionManager: SessionManager
) {

    /** Returns the demo OTP so the UI can display "Demo OTP: 4821" — see OtpService kdoc. */
    fun requestOtp(mobileNumber: String): String = otpService.send(mobileNumber)

    suspend fun verifyOtpAndSignIn(mobileNumber: String, code: String): OtpOutcome {
        return when (val result = otpService.verify(mobileNumber, code)) {
            is OtpService.VerifyResult.Success -> {
                val existingUser = userDao.findByMobile(mobileNumber)
                if (existingUser != null) {
                    sessionManager.signIn(existingUser.id, existingUser.role, mobileNumber, existingUser.linkedEntityId)
                    if (existingUser.role == UserRole.PATIENT) {
                        patientDao.findPrimaryForOwner(existingUser.id)?.let { sessionManager.setActivePatient(it.id) }
                    }
                    OtpOutcome.SignedIn(isNewAccount = false, role = existingUser.role)
                } else {
                    val newUser = createPatientAccount(mobileNumber)
                    OtpOutcome.SignedIn(isNewAccount = true, newUserId = newUser.id, role = UserRole.PATIENT)
                }
            }
            is OtpService.VerifyResult.Incorrect -> OtpOutcome.Incorrect(result.attemptsLeft)
            OtpService.VerifyResult.Expired -> OtpOutcome.Expired
            OtpService.VerifyResult.NoActiveChallenge -> OtpOutcome.Expired
        }
    }

    private suspend fun createPatientAccount(mobileNumber: String): UserEntity {
        val now = System.currentTimeMillis()
        val userId = "USR-PAT-${System.currentTimeMillis()}"
        val user = UserEntity(userId, mobileNumber, null, UserRole.PATIENT, null, AppLanguage.ENGLISH.tag, true, now)
        userDao.upsert(user)
        val latestPatientId = patientDao.latestId()
        val seedSeq = latestPatientId?.let { IdGenerator.sequenceOf(it) } ?: 0
        val patientId = IdGenerator.next("PAT", seedFrom = seedSeq)
        patientDao.upsert(
            PatientEntity(
                id = patientId,
                accountOwnerUserId = userId,
                relation = Relation.MYSELF,
                isPrimary = true,
                fullName = "",
                dateOfBirthEpochDay = null,
                sex = "",
                mobileNumber = mobileNumber,
                createdAt = now
            )
        )
        sessionManager.signIn(userId, UserRole.PATIENT, mobileNumber, null)
        sessionManager.setActivePatient(patientId)
        return user
    }

    suspend fun signOut() = sessionManager.signOut()

    sealed class OtpOutcome {
        data class SignedIn(val isNewAccount: Boolean, val role: UserRole, val newUserId: String? = null) : OtpOutcome()
        data class Incorrect(val attemptsLeft: Int) : OtpOutcome()
        data object Expired : OtpOutcome()
    }
}
