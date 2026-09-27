package com.digitalsolutions.diagnosticlab.presentation.auth

import android.app.Activity
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.digitalsolutions.diagnosticlab.data.repository.AuthRepository
import com.digitalsolutions.diagnosticlab.domain.model.UserRole
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class AuthViewModel(private val authRepository: AuthRepository) : ViewModel() {

    data class UiState(
        val codeSent: Boolean = false,
        val error: String? = null,
        val isNewAccount: Boolean = false,
        val signedInRole: UserRole? = null,
        val loading: Boolean = false
    )

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    private var verificationId: String? = null
    private var requestOtpJob: Job? = null

    fun sendOtp(activity: Activity, mobileNumber: String) {
        Log.d("AuthDebug", "sendOtp: $mobileNumber, this instance=$this")
        requestOtpJob?.cancel()
        // This ViewModel is a single instance hoisted at the NavGraph level (needed so the
        // OTP screen's enabled-state survives Compose Navigation's per-destination recreation —
        // see the class kdoc history), which means its state otherwise survives a sign-out.
        // A stale non-null signedInRole from a PREVIOUS session made OtpScreen's
        // LaunchedEffect(state.signedInRole) fire immediately on the next login attempt,
        // navigating away before the OTP screen ever rendered — signing out and back in as a
        // different number silently reused the old session's role. A fresh OTP request starts
        // a genuinely new auth attempt, so it gets a genuinely fresh state.
        _state.value = UiState(loading = true)
        requestOtpJob = viewModelScope.launch {
            authRepository.requestOtp(activity, mobileNumber).collect { outcome ->
                when (outcome) {
                    is AuthRepository.OtpRequestOutcome.CodeSent -> {
                        verificationId = outcome.verificationId
                        Log.d("AuthDebug", "sendOtp: captured verificationId=$verificationId, this instance=$this")
                        _state.value = _state.value.copy(loading = false, codeSent = true)
                    }
                    is AuthRepository.OtpRequestOutcome.AutoVerified -> {
                        applyOutcome(authRepository.signInWithCredential(outcome.credential))
                    }
                    is AuthRepository.OtpRequestOutcome.Failed -> {
                        _state.value = _state.value.copy(loading = false, error = outcome.message)
                    }
                }
            }
        }
    }

    fun verifyOtp(code: String) {
        val id = verificationId ?: run {
            Log.d("AuthDebug", "verifyOtp: no verificationId captured, this instance=$this")
            _state.value = _state.value.copy(error = "Request a code first.")
            return
        }
        Log.d("AuthDebug", "verifyOtp: launching with verificationId=$id, this instance=$this")
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            val outcome = authRepository.verifyOtpAndSignIn(id, code)
            Log.d("AuthDebug", "verifyOtp: got outcome=$outcome")
            applyOutcome(outcome)
        }
    }

    private fun applyOutcome(outcome: AuthRepository.OtpOutcome) {
        _state.value = when (outcome) {
            is AuthRepository.OtpOutcome.SignedIn ->
                _state.value.copy(loading = false, isNewAccount = outcome.isNewAccount, signedInRole = outcome.role)
            is AuthRepository.OtpOutcome.Failed ->
                _state.value.copy(loading = false, error = outcome.message)
        }
        Log.d("AuthDebug", "applyOutcome: new state=${_state.value}")
    }

    fun resetError() {
        _state.value = _state.value.copy(error = null)
    }
}
