package com.digitalsolutions.diagnosticlab.presentation.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.R
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.UserRole
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton

@Composable
fun rememberAuthViewModel(): AuthViewModel {
    val container = LocalAppContainer.current
    return viewModel(factory = viewModelFactory { initializer { AuthViewModel(container.authRepository) } })
}

@Composable
fun LoginScreen(onOtpRequested: (String) -> Unit) {
    var mobile by remember { mutableStateOf("") }
    val viewModel = rememberAuthViewModel()

    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center
    ) {
        Text(stringResource(R.string.app_name), style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))
        Text(stringResource(R.string.app_tagline), style = MaterialTheme.typography.bodyLarge)
        Spacer(Modifier.height(40.dp))
        Text(stringResource(R.string.enter_mobile_number), style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = mobile,
            onValueChange = { if (it.length <= 10) mobile = it.filter(Char::isDigit) },
            placeholder = { Text(stringResource(R.string.mobile_number_hint)) },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            modifier = Modifier.fillMaxWidth(),
            textStyle = MaterialTheme.typography.titleMedium
        )
        Spacer(Modifier.height(24.dp))
        BigPrimaryButton(
            text = stringResource(R.string.send_otp),
            enabled = mobile.length == 10,
            onClick = {
                viewModel.sendOtp("+91 $mobile")
                onOtpRequested("+91 $mobile")
            }
        )
    }
}

@Composable
fun OtpScreen(mobile: String, onVerified: (UserRole, isNewAccount: Boolean) -> Unit) {
    var code by remember { mutableStateOf("") }
    val viewModel = rememberAuthViewModel()
    val state by viewModel.state.collectAsState()

    LaunchedEffect(mobile) { viewModel.sendOtp(mobile) }

    LaunchedEffect(state.signedInRole) {
        state.signedInRole?.let { onVerified(it, state.isNewAccount) }
    }

    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
        Text(stringResource(R.string.verify_number), style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))
        Text(stringResource(R.string.otp_sent_to, mobile), style = MaterialTheme.typography.bodyLarge)
        state.demoOtp?.let {
            Spacer(Modifier.height(8.dp))
            Text(
                "Demo OTP: $it  (no SMS gateway configured — see README)",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary
            )
        }
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(
            value = code,
            onValueChange = { if (it.length <= 4) code = it.filter(Char::isDigit) },
            placeholder = { Text(stringResource(R.string.otp_code_hint)) },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
            modifier = Modifier.fillMaxWidth(),
            textStyle = MaterialTheme.typography.titleMedium
        )
        if (state.error != null) {
            Spacer(Modifier.height(8.dp))
            Text(state.error.orEmpty(), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
        }
        Spacer(Modifier.height(24.dp))
        BigPrimaryButton(
            text = stringResource(R.string.verify_and_continue),
            enabled = code.length == 4 && !state.loading,
            onClick = { viewModel.verifyOtp(mobile, code) }
        )
        Spacer(Modifier.height(12.dp))
        TextButton(onClick = { viewModel.sendOtp(mobile) }, modifier = Modifier.align(Alignment.CenterHorizontally)) {
            Text(stringResource(R.string.resend_code))
        }
    }
}
