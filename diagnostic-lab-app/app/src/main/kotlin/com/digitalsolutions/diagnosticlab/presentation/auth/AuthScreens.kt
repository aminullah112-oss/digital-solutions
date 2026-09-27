package com.digitalsolutions.diagnosticlab.presentation.auth

import android.app.Activity
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.VerifiedUser
import androidx.compose.material.icons.filled.Description
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.R
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.UserRole
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.BigSecondaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.IconChip
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipBlueContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipMintContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipRoseContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.HealthGreen
import com.digitalsolutions.diagnosticlab.presentation.theme.InfoBlue

@Composable
fun rememberAuthViewModel(): AuthViewModel {
    val container = LocalAppContainer.current
    return viewModel(factory = viewModelFactory { initializer { AuthViewModel(container.authRepository) } })
}

/** First screen a signed-out user sees — introduces the app before asking for a mobile
 * number. Both buttons lead to the same login flow: this app has no separate sign-up form,
 * a new account is created transparently on first OTP verification. */
@Composable
fun WelcomeScreen(onContinue: () -> Unit) {
    val background = Brush.verticalGradient(
        listOf(MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f), MaterialTheme.colorScheme.background)
    )
    Column(Modifier.fillMaxSize().background(background).padding(28.dp)) {
        Column(
            Modifier.weight(1f).fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Box(
                Modifier.size(168.dp).background(Color.White, CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Image(
                    painter = painterResource(R.drawable.logo_mark),
                    contentDescription = stringResource(R.string.app_name),
                    modifier = Modifier.size(120.dp)
                )
            }
            Spacer(Modifier.height(24.dp))
            Text(
                stringResource(R.string.app_name),
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center
            )
            Spacer(Modifier.height(10.dp))
            Text(
                stringResource(R.string.app_tagline),
                style = MaterialTheme.typography.bodyLarge,
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(36.dp))
            WelcomePerkRow(Icons.Filled.Home, ChipRoseContainer, MaterialTheme.colorScheme.primary, stringResource(R.string.welcome_perk_home_collection))
            Spacer(Modifier.height(16.dp))
            WelcomePerkRow(Icons.Filled.VerifiedUser, ChipMintContainer, HealthGreen, stringResource(R.string.welcome_perk_certified_labs))
            Spacer(Modifier.height(16.dp))
            WelcomePerkRow(Icons.Filled.Description, ChipBlueContainer, InfoBlue, stringResource(R.string.welcome_perk_fast_reports))
        }
        BigPrimaryButton(text = stringResource(R.string.get_started), onClick = onContinue)
        Spacer(Modifier.height(12.dp))
        BigSecondaryButton(text = stringResource(R.string.already_have_account), onClick = onContinue)
    }
}

@Composable
private fun WelcomePerkRow(icon: androidx.compose.ui.graphics.vector.ImageVector, chipColor: Color, iconColor: Color, label: String) {
    Row(Modifier.fillMaxWidth(0.85f), verticalAlignment = Alignment.CenterVertically) {
        IconChip(icon = icon, containerColor = chipColor, contentColor = iconColor, size = 36.dp, iconSize = 18.dp)
        Spacer(Modifier.width(14.dp))
        Text(label, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
    }
}

@Composable
fun LoginScreen(onOtpRequested: (String) -> Unit) {
    var mobile by remember { mutableStateOf("") }
    val activity = LocalContext.current as Activity
    val viewModel = rememberAuthViewModel()

    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center
    ) {
        Image(
            painter = painterResource(R.drawable.logo_mark),
            contentDescription = stringResource(R.string.app_name),
            modifier = Modifier.size(88.dp).align(Alignment.CenterHorizontally)
        )
        Spacer(Modifier.height(32.dp))
        Text(stringResource(R.string.enter_mobile_number), style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = mobile,
            onValueChange = { if (it.length <= 10) mobile = it.filter(Char::isDigit) },
            placeholder = { Text(stringResource(R.string.mobile_number_hint)) },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            modifier = Modifier.fillMaxWidth().testTag("login_mobile_field"),
            textStyle = MaterialTheme.typography.titleMedium
        )
        Spacer(Modifier.height(24.dp))
        BigPrimaryButton(
            text = stringResource(R.string.send_otp),
            enabled = mobile.length == 10,
            onClick = {
                // E.164 format required by Firebase Phone Auth — no space after the country code.
                val e164 = "+91$mobile"
                viewModel.sendOtp(activity, e164)
                onOtpRequested(e164)
            }
        )
    }
}

@Composable
fun OtpScreen(mobile: String, onVerified: (UserRole, isNewAccount: Boolean) -> Unit) {
    var code by remember { mutableStateOf("") }
    val activity = LocalContext.current as Activity
    val viewModel = rememberAuthViewModel()
    val state by viewModel.state.collectAsState()

    // The code was already requested by LoginScreen's "Send OTP" click — this screen just
    // displays the entry field and lets the user retry via "Resend code" if needed. Sending
    // again here on entry would fire a second real SMS for the same number.

    LaunchedEffect(state.signedInRole) {
        state.signedInRole?.let { onVerified(it, state.isNewAccount) }
    }

    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
        Text(stringResource(R.string.verify_number), style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))
        Text(stringResource(R.string.otp_sent_to, mobile), style = MaterialTheme.typography.bodyLarge)
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(
            value = code,
            onValueChange = { if (it.length <= 6) code = it.filter(Char::isDigit) },
            placeholder = { Text(stringResource(R.string.otp_code_hint)) },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
            modifier = Modifier.fillMaxWidth().testTag("otp_field"),
            textStyle = MaterialTheme.typography.titleMedium
        )
        if (state.error != null) {
            Spacer(Modifier.height(8.dp))
            Text(state.error.orEmpty(), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
        }
        Spacer(Modifier.height(24.dp))
        BigPrimaryButton(
            text = stringResource(R.string.verify_and_continue),
            enabled = code.length == 6 && !state.loading,
            onClick = { viewModel.verifyOtp(code) }
        )
        Spacer(Modifier.height(12.dp))
        TextButton(onClick = { viewModel.sendOtp(activity, mobile) }, modifier = Modifier.align(Alignment.CenterHorizontally)) {
            Text(stringResource(R.string.resend_code))
        }
    }
}
