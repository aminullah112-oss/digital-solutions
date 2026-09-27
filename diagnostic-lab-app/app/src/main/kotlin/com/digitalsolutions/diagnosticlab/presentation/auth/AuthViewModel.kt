package com.digitalsolutions.diagnosticlab.presentation.auth

import android.app.Activity
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
        requestOtpJob?.cancel()
        _state.value = _state.value.copy(loading = true, error = null, codeSent = false)
        requestOtpJob = viewModelScope.launch {
            authRepository.requestOtp(activity, mobileNumber).collect { outcome ->
                when (outcome) {
                    is AuthRepository.OtpRequestOutcome.CodeSent -> {
                        verificationId = outcome.verificationId
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
            _state.value = _state.value.copy(error = "Request a code first.")
            return
        }
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            applyOutcome(authRepository.verifyOtpAndSignIn(id, code))
        }
    }

    private fun applyOutcome(outcome: AuthRepository.OtpOutcome) {
        _state.value = when (outcome) {
            is AuthRepository.OtpOutcome.SignedIn ->
                _state.value.copy(loading = false, isNewAccount = outcome.isNewAccount, signedInRole = outcome.role)
            is AuthRepository.OtpOutcome.Failed ->
                _state.value.copy(loading = false, error = outcome.message)
        }
    }

    fun resetError() {
        _state.value = _state.value.copy(error = null)
    }
}
