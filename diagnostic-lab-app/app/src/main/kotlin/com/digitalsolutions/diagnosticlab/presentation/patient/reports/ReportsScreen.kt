package com.digitalsolutions.diagnosticlab.presentation.patient.reports

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
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
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.io.File

class ReportsViewModel(
    private val reportRepository: ReportRepository,
    sessionManager: SessionManager
) : ViewModel() {
    // All reports on the account, not just the active family member's.
    val reports: StateFlow<List<Report>?> = sessionManager.session.filterNotNull()
        .flatMapLatest { reportRepository.observeForOwner(it.userId) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    private val _openingReportId = MutableStateFlow<String?>(null)
    val openingReportId: StateFlow<String?> = _openingReportId
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message

    /** Downloads the report PDF, then hands the file to [onReady] (which launches the viewer). */
    fun openReport(report: Report, cacheDir: File, onReady: (File) -> Unit) {
        if (_openingReportId.value != null) return
        viewModelScope.launch {
            _openingReportId.value = report.id
            try {
                onReady(reportRepository.downloadReport(report, cacheDir))
            } catch (e: CancellationException) {
                throw e
            } catch (e: IllegalStateException) {
                _message.value = e.message
            } catch (e: Exception) {
                _message.value = "Couldn't open this report. Check your connection and try again."
            } finally {
                _openingReportId.value = null
            }
        }
    }

    fun showMessage(text: String) { _message.value = text }
    fun messageShown() { _message.value = null }
}

/** Returns false if the device has no app that can open PDFs. */
private fun openPdf(context: Context, file: File): Boolean {
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    val intent = Intent(Intent.ACTION_VIEW).apply {
        setDataAndType(uri, "application/pdf")
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    return try {
        context.startActivity(intent)
        true
    } catch (e: ActivityNotFoundException) {
        false
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReportsScreen(onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: ReportsViewModel = viewModel(
        factory = viewModelFactory { initializer { ReportsViewModel(container.reportRepository, container.sessionManager) } }
    )
    val reports by viewModel.reports.collectAsState()
    val openingReportId by viewModel.openingReportId.collectAsState()
    val message by viewModel.message.collectAsState()
    val context = LocalContext.current
    val snackbarHostState = remember { SnackbarHostState() }
    LaunchedEffect(message) {
        message?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.messageShown()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
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
                items(reports!!, key = { it.id }) { report ->
                    ReportRow(
                        report = report,
                        opening = openingReportId == report.id,
                        onView = {
                            viewModel.openReport(report, context.cacheDir) { file ->
                                if (!openPdf(context, file)) {
                                    viewModel.showMessage("No app found to open PDF files. Please install a PDF viewer.")
                                }
                            }
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun ReportRow(report: Report, opening: Boolean, onView: () -> Unit) {
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
                Text(
                    listOfNotNull(report.patientName, report.laboratoryName).joinToString(" · "),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Spacer(Modifier.width(8.dp))
            StatusChip(if (ready) "READY" else "PENDING", if (ready) HealthGreen else WarningAmber)
            if (ready) {
                TextButton(onClick = onView, enabled = !opening) {
                    Text(if (opening) "Opening…" else "View")
                }
            }
        }
    }
}
