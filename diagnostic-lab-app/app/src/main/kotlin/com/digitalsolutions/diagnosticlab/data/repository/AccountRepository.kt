package com.digitalsolutions.diagnosticlab.data.repository

import com.google.firebase.functions.FirebaseFunctions
import com.google.firebase.functions.FirebaseFunctionsException
import kotlinx.coroutines.tasks.await

/** In-app account deletion. The work happens server-side (deleteMyAccount Cloud Function); this
 * signs the device out afterwards. */
class AccountRepository(
    private val functions: FirebaseFunctions,
    private val authRepository: AuthRepository
) {
    /** Throws IllegalStateException with a user-readable message if deletion didn't happen. */
    suspend fun deleteMyAccount() {
        try {
            functions.getHttpsCallable("deleteMyAccount").call().await()
        } catch (e: FirebaseFunctionsException) {
            throw IllegalStateException(
                when (e.code) {
                    FirebaseFunctionsException.Code.FAILED_PRECONDITION -> e.message ?: "This account can't be deleted from the app."
                    FirebaseFunctionsException.Code.UNAUTHENTICATED -> "Please sign in again, then try once more."
                    else -> "Couldn't delete the account right now. Check your connection and try again."
                }
            )
        }
        authRepository.signOut()
    }
}
