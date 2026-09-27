package com.digitalsolutions.diagnosticlab.data.repository

import android.app.Activity
import com.digitalsolutions.diagnosticlab.domain.model.Relation
import com.digitalsolutions.diagnosticlab.domain.model.UserRole
import com.google.firebase.FirebaseException
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.PhoneAuthCredential
import com.google.firebase.auth.PhoneAuthOptions
import com.google.firebase.auth.PhoneAuthProvider
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await
import java.util.concurrent.TimeUnit

/**
 * Real Firebase Phone Auth, replacing the old on-device OtpService simulation. A brand-new
 * phone number always self-provisions as PATIENT on first sign-in (matching the app's
 * "no separate signup form" design) — staff accounts (phlebotomist/lab/admin) are created by
 * editing the users/{uid} doc's role field in the Firebase console after that person's first
 * sign-in, since only a human should be able to grant those roles (see firestore.rules).
 */
class AuthRepository(
    private val auth: FirebaseAuth,
    private val firestore: FirebaseFirestore,
    private val sessionManager: SessionManager
) {

    sealed class OtpRequestOutcome {
        data class CodeSent(val verificationId: String) : OtpRequestOutcome()
        data class AutoVerified(val credential: PhoneAuthCredential) : OtpRequestOutcome()
        data class Failed(val message: String) : OtpRequestOutcome()
    }

    sealed class OtpOutcome {
        data class SignedIn(val isNewAccount: Boolean, val role: UserRole, val newUserId: String? = null) : OtpOutcome()
        data class Failed(val message: String) : OtpOutcome()
    }

    /** [mobileNumber] must already be in E.164 form (e.g. "+919000000001", no spaces). */
    fun requestOtp(activity: Activity, mobileNumber: String): Flow<OtpRequestOutcome> = callbackFlow {
        val callbacks = object : PhoneAuthProvider.OnVerificationStateChangedCallbacks() {
            override fun onVerificationCompleted(credential: PhoneAuthCredential) {
                trySend(OtpRequestOutcome.AutoVerified(credential))
            }

            override fun onVerificationFailed(e: FirebaseException) {
                trySend(OtpRequestOutcome.Failed(e.message ?: "Verification failed"))
                close()
            }

            override fun onCodeSent(verificationId: String, token: PhoneAuthProvider.ForceResendingToken) {
                trySend(OtpRequestOutcome.CodeSent(verificationId))
            }
        }
        val options = PhoneAuthOptions.newBuilder(auth)
            .setPhoneNumber(mobileNumber)
            .setTimeout(60L, TimeUnit.SECONDS)
            .setActivity(activity)
            .setCallbacks(callbacks)
            .build()
        PhoneAuthProvider.verifyPhoneNumber(options)
        awaitClose { }
    }

    suspend fun verifyOtpAndSignIn(verificationId: String, code: String): OtpOutcome =
        signInWithCredential(PhoneAuthProvider.getCredential(verificationId, code))

    suspend fun signInWithCredential(credential: PhoneAuthCredential): OtpOutcome {
        return try {
            val user = auth.signInWithCredential(credential).await().user
                ?: return OtpOutcome.Failed("Sign-in failed")
            finishSignIn(user.uid, user.phoneNumber.orEmpty())
        } catch (e: Exception) {
            OtpOutcome.Failed(e.message ?: "Incorrect code")
        }
    }

    private suspend fun finishSignIn(uid: String, mobileNumber: String): OtpOutcome {
        val userDocRef = firestore.collection("users").document(uid)
        val snapshot = userDocRef.get().await()
        if (snapshot.exists()) {
            val role = runCatching { UserRole.valueOf(snapshot.getString("role") ?: "PATIENT") }.getOrDefault(UserRole.PATIENT)
            val linkedEntityId = snapshot.getString("linkedEntityId")
            sessionManager.signIn(uid, role, mobileNumber, linkedEntityId)
            if (role == UserRole.PATIENT) activatePrimaryPatient(uid)
            return OtpOutcome.SignedIn(isNewAccount = false, role = role)
        }

        userDocRef.set(mapOf("role" to UserRole.PATIENT.name, "mobileNumber" to mobileNumber)).await()
        val patientRef = firestore.collection("patients").document()
        patientRef.set(
            mapOf(
                "id" to patientRef.id,
                "accountOwnerUserId" to uid,
                "relation" to Relation.MYSELF.name,
                "isPrimary" to true,
                "fullName" to "",
                "dateOfBirth" to null,
                "sex" to "",
                "mobileNumber" to mobileNumber,
                "email" to null,
                "createdAtMillis" to System.currentTimeMillis()
            )
        ).await()
        sessionManager.signIn(uid, UserRole.PATIENT, mobileNumber, null)
        sessionManager.setActivePatient(patientRef.id)
        return OtpOutcome.SignedIn(isNewAccount = true, newUserId = uid, role = UserRole.PATIENT)
    }

    private suspend fun activatePrimaryPatient(uid: String) {
        val results = firestore.collection("patients")
            .whereEqualTo("accountOwnerUserId", uid)
            .whereEqualTo("isPrimary", true)
            .limit(1)
            .get().await()
        results.documents.firstOrNull()?.let { sessionManager.setActivePatient(it.id) }
    }

    suspend fun signOut() {
        auth.signOut()
        sessionManager.signOut()
    }
}
