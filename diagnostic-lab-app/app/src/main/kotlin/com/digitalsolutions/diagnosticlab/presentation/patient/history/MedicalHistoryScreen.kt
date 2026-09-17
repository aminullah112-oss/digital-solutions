package com.digitalsolutions.diagnosticlab.presentation.patient.history

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.data.repository.MedicalRecordRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.MedicalRecord
import com.digitalsolutions.diagnosticlab.presentation.components.EmptyState
import com.digitalsolutions.diagnosticlab.presentation.components.VoiceEnabledTextField
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.time.LocalDate

class MedicalHistoryViewModel(
    private val medicalRecordRepository: MedicalRecordRepository,
    private val sessionManager: SessionManager
) : ViewModel() {
    val records: StateFlow<List<MedicalRecord>> = sessionManager.activePatientId
        .filterNotNull()
        .flatMapLatest { medicalRecordRepository.observeForPatient(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    fun addNote(title: String, notes: String) {
        viewModelScope.launch {
            val patientId = sessionManager.activePatientId.first() ?: return@launch
            medicalRecordRepository.addRecord(patientId, "NOTE", title, null, LocalDate.now(), notes)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MedicalHistoryScreen(onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: MedicalHistoryViewModel = viewModel(
        factory = viewModelFactory { initializer { MedicalHistoryViewModel(container.medicalRecordRepository, container.sessionManager) } }
    )
    val records by viewModel.records.collectAsState()
    var showAddDialog by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Medical History") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(onClick = { showAddDialog = true }, text = { Text("Add note") }, icon = {})
        }
    ) { padding ->
        if (records.isEmpty()) {
            EmptyState("Your past investigations and reports will show up here as a timeline.", Modifier.padding(padding))
        } else {
            LazyColumn(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(records, key = { it.id }) { record ->
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp)) {
                            Text(record.date.toString(), style = MaterialTheme.typography.labelMedium)
                            Text(record.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                            record.notes?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                        }
                    }
                }
            }
        }
    }

    if (showAddDialog) {
        var title by remember { mutableStateOf("") }
        var notes by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { showAddDialog = false },
            title = { Text("Add a note to your history") },
            text = {
                Column {
                    OutlinedTextField(title, { title = it }, label = { Text("Title (e.g. Fever episode)") }, modifier = Modifier.fillMaxWidth())
                    Spacer(Modifier.height(8.dp))
                    VoiceEnabledTextField(notes, { notes = it }, label = "Notes", singleLine = false)
                }
            },
            confirmButton = {
                TextButton(enabled = title.isNotBlank(), onClick = { viewModel.addNote(title, notes); showAddDialog = false }) { Text("Save") }
            },
            dismissButton = { TextButton(onClick = { showAddDialog = false }) { Text("Cancel") } }
        )
    }
}
