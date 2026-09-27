package com.digitalsolutions.diagnosticlab.data.repository

import android.app.Activity
import android.util.Log
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
 *
 * Requires Firebase Console > Authentication > Settings > SMS Region Policy to explicitly
 * allow the country codes any real or test phone number will use (e.g. India/+91) — it
 * defaults to blocking every region, and that block applies even to numbers registered under
 * "Phone numbers for testing", surfacing as FirebaseAuth error 17006 ("SMS unable to be sent
 * until this region enabled by the app developer") with no other visible symptom.
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
                Log.e("AuthDebug", "onVerificationFailed for $mobileNumber", e)
                trySend(OtpRequestOutcome.Failed(e.message ?: "Verification failed"))
                close()
            }

            override fun onCodeSent(verificationId: String, token: PhoneAuthProvider.ForceResendingToken) {
                Log.d("AuthDebug", "onCodeSent for $mobileNumber, verificationId=$verificationId")
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

    suspend fun verifyOtpAndSignIn(verificationId: String, code: String): OtpOutcome {
        Log.d("AuthDebug", "verifyOtpAndSignIn: verificationId=$verificationId, code=$code")
        return signInWithCredential(PhoneAuthProvider.getCredential(verificationId, code))
    }

    suspend fun signInWithCredential(credential: PhoneAuthCredential): OtpOutcome {
        return try {
            Log.d("AuthDebug", "signInWithCredential: calling auth.signInWithCredential")
            val user = auth.signInWithCredential(credential).await().user
                ?: return OtpOutcome.Failed("Sign-in failed").also { Log.d("AuthDebug", "signInWithCredential: user null") }
            Log.d("AuthDebug", "signInWithCredential: signed in uid=${user.uid}, calling finishSignIn")
            finishSignIn(user.uid, user.phoneNumber.orEmpty())
        } catch (e: Exception) {
            Log.e("AuthDebug", "signInWithCredential: threw", e)
            OtpOutcome.Failed(e.message ?: "Incorrect code")
        }
    }

    private suspend fun finishSignIn(uid: String, mobileNumber: String): OtpOutcome {
        Log.d("AuthDebug", "finishSignIn: start uid=$uid")
        val userDocRef = firestore.collection("users").document(uid)
        val snapshot = userDocRef.get().await()
        Log.d("AuthDebug", "finishSignIn: users/$uid exists=${snapshot.exists()}")
        if (snapshot.exists()) {
            val role = runCatching { UserRole.valueOf(snapshot.getString("role") ?: "PATIENT") }.getOrDefault(UserRole.PATIENT)
            val linkedEntityId = snapshot.getString("linkedEntityId")
            sessionManager.signIn(uid, role, mobileNumber, linkedEntityId)
            if (role == UserRole.PATIENT) activatePrimaryPatient(uid)
            return OtpOutcome.SignedIn(isNewAccount = false, role = role)
        }

        userDocRef.set(mapOf("role" to UserRole.PATIENT.name, "mobileNumber" to mobileNumber)).await()
        Log.d("AuthDebug", "finishSignIn: users/$uid created, writing patients doc")
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
        Log.d("AuthDebug", "finishSignIn: done for uid=$uid, returning SignedIn(isNewAccount=true)")
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
