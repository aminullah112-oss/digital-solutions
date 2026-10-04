package com.digitalsolutions.diagnosticlab.presentation.lab

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.data.repository.LaboratoryOnboardingRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.UserRole
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.VoiceEnabledTextField
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class RegisterLabViewModel(
    private val laboratoryOnboardingRepository: LaboratoryOnboardingRepository,
    private val sessionManager: SessionManager
) : ViewModel() {
    var isSubmitting by mutableStateOf(false)
        private set
    var errorMessage by mutableStateOf<String?>(null)
        private set

    fun register(
        name: String,
        address: String,
        city: String,
        phone: String,
        openTime: String,
        closeTime: String,
        homeCollectionAvailable: Boolean,
        licenseNumber: String?,
        onRegistered: () -> Unit
    ) {
        if (isSubmitting) return
        viewModelScope.launch {
            isSubmitting = true
            errorMessage = null
            try {
                val labId = laboratoryOnboardingRepository.registerLaboratory(
                    name, address, city, phone, openTime, closeTime, homeCollectionAvailable, licenseNumber
                )
                // The Cloud Function already flipped users/{uid}.role in Firestore — this just
                // refreshes the locally cached session (SessionManager/DataStore) to match, so
                // navigation routes to LAB_HOME on the very next recomposition instead of only
                // after the next sign-in.
                val session = sessionManager.session.first()
                if (session != null) {
                    sessionManager.signIn(session.userId, UserRole.LABORATORY, session.mobileNumber, labId)
                }
                onRegistered()
            } catch (e: Exception) {
                errorMessage = e.message ?: "Registration failed. Please try again."
            } finally {
                isSubmitting = false
            }
        }
    }
}

/**
 * Self-service lab onboarding: any signed-in account (defaults to PATIENT on first sign-in, per
 * AuthRepository's "no separate signup form" design) can register their own lab here. Submitting
 * flips this account's role to LABORATORY and creates a laboratories doc that stays invisible to
 * patients (active: false) until an admin approves it — see registerLaboratory in
 * functions/src/index.ts and the "Pending approvals" section on AdminHomeScreen.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RegisterLabScreen(onRegistered: () -> Unit, onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: RegisterLabViewModel = viewModel(
        factory = viewModelFactory { initializer { RegisterLabViewModel(container.laboratoryOnboardingRepository, container.sessionManager) } }
    )

    var name by remember { mutableStateOf("") }
    var address by remember { mutableStateOf("") }
    var city by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var openTime by remember { mutableStateOf("07:00") }
    var closeTime by remember { mutableStateOf("20:00") }
    var homeCollectionAvailable by remember { mutableStateOf(true) }
    var licenseNumber by remember { mutableStateOf("") }

    val canSubmit = name.isNotBlank() && address.isNotBlank() && city.isNotBlank() &&
        phone.isNotBlank() && openTime.isNotBlank() && closeTime.isNotBlank()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Register Your Lab") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        Column(
            Modifier.padding(padding).padding(16.dp).verticalScroll(rememberScrollState())
        ) {
            Text(
                "Tell us about your lab. An admin reviews every new registration before it appears to patients.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(16.dp))
            VoiceEnabledTextField(name, { name = it }, label = "Lab name", singleLine = true)
            Spacer(Modifier.height(10.dp))
            VoiceEnabledTextField(address, { address = it }, label = "Full address", singleLine = false)
            Spacer(Modifier.height(10.dp))
            VoiceEnabledTextField(city, { city = it }, label = "City", singleLine = true)
            Spacer(Modifier.height(10.dp))
            VoiceEnabledTextField(phone, { phone = it }, label = "Contact phone", singleLine = true)
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                VoiceEnabledTextField(openTime, { openTime = it }, label = "Opens (HH:mm)", singleLine = true, modifier = Modifier.weight(1f))
                VoiceEnabledTextField(closeTime, { closeTime = it }, label = "Closes (HH:mm)", singleLine = true, modifier = Modifier.weight(1f))
            }
            Spacer(Modifier.height(10.dp))
            VoiceEnabledTextField(licenseNumber, { licenseNumber = it }, label = "Lab license / NABL number (optional)", singleLine = true)
            Spacer(Modifier.height(10.dp))
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Home sample collection available", style = MaterialTheme.typography.bodyLarge)
                Switch(checked = homeCollectionAvailable, onCheckedChange = { homeCollectionAvailable = it })
            }
            Spacer(Modifier.height(20.dp))
            viewModel.errorMessage?.let {
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(10.dp))
            }
            BigPrimaryButton(
                text = if (viewModel.isSubmitting) "Submitting..." else "Submit for review",
                enabled = canSubmit && !viewModel.isSubmitting,
                onClick = {
                    viewModel.register(
                        name.trim(), address.trim(), city.trim(), phone.trim(),
                        openTime.trim(), closeTime.trim(), homeCollectionAvailable,
                        licenseNumber.trim().ifBlank { null },
                        onRegistered
                    )
                }
            )
        }
    }
}
