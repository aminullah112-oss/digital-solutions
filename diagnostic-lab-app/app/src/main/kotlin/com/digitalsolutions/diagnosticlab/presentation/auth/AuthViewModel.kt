package com.digitalsolutions.diagnosticlab.presentation.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.digitalsolutions.diagnosticlab.data.repository.AuthRepository
import com.digitalsolutions.diagnosticlab.domain.model.UserRole
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class AuthViewModel(private val authRepository: AuthRepository) : ViewModel() {

    data class UiState(
        val demoOtp: String? = null,
        val attemptsLeft: Int = 3,
        val error: String? = null,
        val isNewAccount: Boolean = false,
        val signedInRole: UserRole? = null,
        val loading: Boolean = false
    )

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    fun sendOtp(mobileNumber: String) {
        val otp = authRepository.requestOtp(mobileNumber)
        _state.value = UiState(demoOtp = otp)
    }

    fun verifyOtp(mobileNumber: String, code: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            when (val outcome = authRepository.verifyOtpAndSignIn(mobileNumber, code)) {
                is AuthRepository.OtpOutcome.SignedIn -> {
                    _state.value = _state.value.copy(loading = false, isNewAccount = outcome.isNewAccount, signedInRole = outcome.role)
                }
                is AuthRepository.OtpOutcome.Incorrect -> {
                    _state.value = _state.value.copy(loading = false, error = "Incorrect code. ${outcome.attemptsLeft} attempts left.", attemptsLeft = outcome.attemptsLeft)
                }
                AuthRepository.OtpOutcome.Expired -> {
                    _state.value = _state.value.copy(loading = false, error = "This code expired. Please request a new one.")
                }
            }
        }
    }

    fun resetError() {
        _state.value = _state.value.copy(error = null)
    }
}
