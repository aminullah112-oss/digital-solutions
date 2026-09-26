package com.digitalsolutions.diagnosticlab.presentation.patient.support

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Call
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.data.repository.ComplaintRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.Complaint
import com.digitalsolutions.diagnosticlab.domain.model.ComplaintCategory
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.EmptyState
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.components.StatusChip
import com.digitalsolutions.diagnosticlab.presentation.components.VoiceEnabledTextField
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class ComplaintViewModel(
    private val complaintRepository: ComplaintRepository,
    private val sessionManager: SessionManager
) : ViewModel() {
    val complaints: StateFlow<List<Complaint>> = sessionManager.activePatientId
        .filterNotNull()
        .flatMapLatest { complaintRepository.observeForPatient(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    fun submit(category: ComplaintCategory, description: String, onDone: () -> Unit) {
        viewModelScope.launch {
            val patientId = sessionManager.activePatientId.first() ?: return@launch
            val userId = sessionManager.session.first()?.userId ?: return@launch
            complaintRepository.submit(patientId, null, category, description, null, userId)
            onDone()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HelpSupportScreen(onRaiseComplaint: () -> Unit, onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: ComplaintViewModel = viewModel(
        factory = viewModelFactory { initializer { ComplaintViewModel(container.complaintRepository, container.sessionManager) } }
    )
    val complaints by viewModel.complaints.collectAsState()
    val context = LocalContext.current

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Help & Support") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        LazyColumn(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            item {
                SectionCard("Call us") {
                    Text("Our support line is open 7am–9pm every day.", style = MaterialTheme.typography.bodyLarge)
                    Spacer(Modifier.height(12.dp))
                    BigPrimaryButton(text = "Call +91 44 2000 1000") {
                        context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:+914420001000")))
                    }
                }
            }
            item {
                SectionCard("Raise a complaint") {
                    Text("Tell us what went wrong and we'll follow up.", style = MaterialTheme.typography.bodyLarge)
                    Spacer(Modifier.height(12.dp))
                    BigPrimaryButton(text = "Raise a complaint", onClick = onRaiseComplaint)
                }
            }
            if (complaints.isNotEmpty()) {
                item { Text("Your complaints", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
                items(complaints, key = { it.id }) { complaint ->
                    SectionCard {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(complaint.category.name.lowercase().replace('_', ' ').replaceFirstChar(Char::uppercase), fontWeight = FontWeight.Bold)
                            StatusChip(complaint.status.name, MaterialTheme.colorScheme.primary)
                        }
                        Spacer(Modifier.height(4.dp))
                        Text(complaint.description, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ComplaintScreen(onDone: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: ComplaintViewModel = viewModel(
        factory = viewModelFactory { initializer { ComplaintViewModel(container.complaintRepository, container.sessionManager) } }
    )
    var category by remember { mutableStateOf(ComplaintCategory.BOOKING_ISSUE) }
    var description by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Raise a complaint") },
                navigationIcon = { IconButton(onClick = onDone) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        Column(Modifier.padding(padding).padding(16.dp)) {
            Text("What's this about?", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            ComplaintCategory.values().forEach { option ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = category == option, onClick = { category = option })
                    Text(option.name.lowercase().replace('_', ' ').replaceFirstChar(Char::uppercase), style = MaterialTheme.typography.bodyMedium)
                }
            }
            Spacer(Modifier.height(12.dp))
            VoiceEnabledTextField(description, { description = it }, label = "Describe the issue", singleLine = false)
            Spacer(Modifier.height(20.dp))
            BigPrimaryButton(text = "Submit", enabled = description.isNotBlank(), onClick = { viewModel.submit(category, description, onDone) })
        }
    }
}
