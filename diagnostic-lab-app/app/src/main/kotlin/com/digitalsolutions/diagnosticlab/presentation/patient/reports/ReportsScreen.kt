package com.digitalsolutions.diagnosticlab.presentation.patient.reports

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Description
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.data.repository.ReportRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.Report
import com.digitalsolutions.diagnosticlab.domain.model.ReportStatus
import com.digitalsolutions.diagnosticlab.presentation.components.EmptyState
import com.digitalsolutions.diagnosticlab.presentation.components.IconChip
import com.digitalsolutions.diagnosticlab.presentation.components.LoadingState
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.components.StatusChip
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipMintContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.HealthGreen
import com.digitalsolutions.diagnosticlab.presentation.theme.WarningAmber
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn

class ReportsViewModel(reportRepository: ReportRepository, sessionManager: SessionManager) : ViewModel() {
    val reports: StateFlow<List<Report>?> = sessionManager.activePatientId
        .filterNotNull()
        .flatMapLatest { reportRepository.observeForPatient(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReportsScreen(onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: ReportsViewModel = viewModel(
        factory = viewModelFactory { initializer { ReportsViewModel(container.reportRepository, container.sessionManager) } }
    )
    val reports by viewModel.reports.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("My Reports") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        when {
            reports == null -> LoadingState(Modifier.padding(padding))
            reports!!.isEmpty() -> EmptyState("No reports yet. They'll appear here once ready.", Modifier.padding(padding))
            else -> LazyColumn(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(reports!!, key = { it.id }) { report -> ReportRow(report) }
            }
        }
    }
}

@Composable
private fun ReportRow(report: Report) {
    val ready = report.status == ReportStatus.READY || report.status == ReportStatus.DELIVERED
    SectionCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconChip(
                icon = Icons.Filled.Description,
                containerColor = if (ready) ChipMintContainer else MaterialTheme.colorScheme.surfaceVariant,
                contentColor = if (ready) HealthGreen else WarningAmber
            )
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(report.investigationNames.joinToString(", "), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(report.laboratoryName, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.width(8.dp))
            StatusChip(if (ready) "READY" else "PENDING", if (ready) HealthGreen else WarningAmber)
            if (ready) {
                TextButton(onClick = { /* Opening the actual PDF needs a real file provider — see README "Reports". */ }) {
                    Text("View")
                }
            }
        }
    }
}
