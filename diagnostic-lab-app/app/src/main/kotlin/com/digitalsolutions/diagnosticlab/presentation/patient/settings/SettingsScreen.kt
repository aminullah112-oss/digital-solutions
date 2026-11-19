package com.digitalsolutions.diagnosticlab.presentation.patient.settings

import androidx.activity.ComponentActivity
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.MedicalServices
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.R
import com.digitalsolutions.diagnosticlab.data.repository.PatientRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.AppLanguage
import com.digitalsolutions.diagnosticlab.presentation.components.BigSecondaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.InitialsAvatar
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class ProfileHeaderViewModel(patientRepository: PatientRepository, sessionManager: SessionManager) : ViewModel() {
    data class Header(val name: String, val mobile: String)

    val header: StateFlow<Header?> = sessionManager.session
        .filterNotNull()
        .flatMapLatest { session ->
            patientRepository.observeFamily(session.userId).map { family ->
                Header(family.firstOrNull { it.isPrimary }?.fullName?.ifBlank { null } ?: "Patient", session.mobileNumber)
            }
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onSignedOut: () -> Unit,
    onBack: () -> Unit,
    onReports: () -> Unit = {},
    onMedicalHistory: () -> Unit = {},
    onRegisterLab: () -> Unit = {}
) {
    val container = LocalAppContainer.current
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val currentLanguage by container.sessionManager.language.collectAsState(initial = AppLanguage.ENGLISH.tag)
    val headerViewModel: ProfileHeaderViewModel = viewModel(
        factory = viewModelFactory { initializer { ProfileHeaderViewModel(container.patientRepository, container.sessionManager) } }
    )
    val header by headerViewModel.header.collectAsState()
    var showDeleteDialog by remember { mutableStateOf(false) }
    var deleteConfirmText by remember { mutableStateOf("") }
    var deleting by remember { mutableStateOf(false) }
    var deleteError by remember { mutableStateOf<String?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.settings_title)) },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        Column(Modifier.padding(padding).padding(16.dp).verticalScroll(rememberScrollState())) {
            header?.let { h ->
                Column(Modifier.fillMaxWidth().padding(vertical = 12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    val initials = h.name.trim().split(" ").filter { it.isNotBlank() }.take(2).mapNotNull { it.firstOrNull() }.joinToString("")
                    InitialsAvatar(initials = initials.ifBlank { "?" }, size = 76.dp)
                    Spacer(Modifier.height(10.dp))
                    Text(h.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
                    Text(h.mobile, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.height(20.dp))
            }

            Text("HEALTH RECORDS", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            SectionCard {
                ProfileListRow(Icons.Filled.MedicalServices, "Medical History", onMedicalHistory)
                Divider()
                ProfileListRow(Icons.Filled.Description, "My Reports", onReports)
            }
            Spacer(Modifier.height(20.dp))

            Text("PARTNER WITH US", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            SectionCard {
                ProfileListRow(Icons.Filled.MedicalServices, "Register Your Lab", onRegisterLab)
            }
            Spacer(Modifier.height(20.dp))

            Text("ACCOUNT", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            SectionCard(stringResource(R.string.language_label)) {
                AppLanguage.values().forEach { lang ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(
                            selected = currentLanguage == lang.tag,
                            onClick = {
                                scope.launch {
                                    container.sessionManager.setLanguage(lang.tag)
                                    withContext(Dispatchers.Main.immediate) {
                                        (context as? ComponentActivity)?.recreate()
                                    }
                                }
                            }
                        )
                        Text(if (lang == AppLanguage.ENGLISH) "English" else "தமிழ்", style = MaterialTheme.typography.bodyLarge)
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            TextButton(onClick = { showDeleteDialog = true }) {
                Text("Delete my account", color = MaterialTheme.colorScheme.error)
            }
            Spacer(Modifier.height(12.dp))
            BigSecondaryButton(text = stringResource(R.string.sign_out)) {
                scope.launch {
                    container.sessionManager.signOut()
                    withContext(Dispatchers.Main.immediate) { onSignedOut() }
                }
            }
        }
    }

    if (showDeleteDialog) {
        DeleteAccountDialog(
            confirmText = deleteConfirmText,
            onConfirmTextChange = { deleteConfirmText = it },
            deleting = deleting,
            error = deleteError,
            onDelete = {
                deleting = true
                deleteError = null
                scope.launch {
                    try {
                        container.accountRepository.deleteMyAccount()
                        withContext(Dispatchers.Main.immediate) { onSignedOut() }
                    } catch (e: kotlinx.coroutines.CancellationException) {
                        throw e
                    } catch (e: Exception) {
                        deleteError = e.message ?: "Couldn't delete the account. Please try again."
                    } finally {
                        deleting = false
                    }
                }
            },
            onDismiss = { showDeleteDialog = false; deleteConfirmText = ""; deleteError = null }
        )
    }
}

@Composable
private fun DeleteAccountDialog(
    confirmText: String,
    onConfirmTextChange: (String) -> Unit,
    deleting: Boolean,
    error: String?,
    onDelete: () -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = { if (!deleting) onDismiss() },
        title = { Text("Delete your account?") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Text("This can't be undone.", fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                Text("Deleted now: your profile, saved addresses, family profiles, notifications, medical history notes, and any prescriptions or reports you stored in My Documents.")
                Spacer(Modifier.height(8.dp))
                Text("Kept for legal reasons: booking and lab test records (up to 7 years) and payment records (up to 8 years). They are no longer linked to your profile.")
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = confirmText,
                    onValueChange = onConfirmTextChange,
                    label = { Text("Type DELETE to confirm") },
                    singleLine = true,
                    enabled = !deleting,
                    modifier = Modifier.fillMaxWidth()
                )
                if (deleting) {
                    Spacer(Modifier.height(8.dp))
                    LinearProgressIndicator(Modifier.fillMaxWidth())
                }
                error?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDelete, enabled = !deleting && confirmText.trim() == "DELETE") {
                Text("Delete permanently", color = MaterialTheme.colorScheme.error)
            }
        },
        dismissButton = { TextButton(onClick = onDismiss, enabled = !deleting) { Text("Cancel") } }
    )
}

@Composable
private fun ProfileListRow(icon: ImageVector, label: String, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(14.dp))
        Text(label, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
        Icon(Icons.Filled.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
