package com.digitalsolutions.diagnosticlab.presentation.lab

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import com.digitalsolutions.diagnosticlab.data.repository.BookingRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.Booking
import com.digitalsolutions.diagnosticlab.domain.model.BookingStatus
import com.digitalsolutions.diagnosticlab.domain.model.SampleRejectionReason
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.BigSecondaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.EmptyState
import com.digitalsolutions.diagnosticlab.presentation.components.LoadingState
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.components.StatusChip
import com.digitalsolutions.diagnosticlab.presentation.patient.bookings.statusColor
import com.digitalsolutions.diagnosticlab.presentation.patient.bookings.statusLabel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

private val LAB_RELEVANT_STATUSES = setOf(
    BookingStatus.PHLEBOTOMIST_ASSIGNED, BookingStatus.PHLEBOTOMIST_ON_THE_WAY, BookingStatus.ARRIVED,
    BookingStatus.SAMPLE_COLLECTED, BookingStatus.SAMPLE_IN_TRANSIT, BookingStatus.RECEIVED_AT_LAB,
    BookingStatus.PROCESSING, BookingStatus.REPORT_READY, BookingStatus.REJECTED_RECOLLECTION_NEEDED
)

class LabHomeViewModel(bookingRepository: BookingRepository, sessionManager: SessionManager) : ViewModel() {
    val orders: StateFlow<List<Booking>?> = sessionManager.session
        .filterNotNull()
        .map { it.linkedEntityId }
        .filterNotNull()
        .flatMapLatest { bookingRepository.observeBookingsForLab(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LabHomeScreen(onOpenOrder: (String) -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: LabHomeViewModel = viewModel(factory = viewModelFactory { initializer { LabHomeViewModel(container.bookingRepository, container.sessionManager) } })
    val orders by viewModel.orders.collectAsState()
    val relevant = orders?.filter { it.status in LAB_RELEVANT_STATUSES || it.status == BookingStatus.REPORT_DELIVERED }

    Scaffold(topBar = { TopAppBar(title = { Text("Incoming Orders") }) }) { padding ->
        when {
            orders == null -> LoadingState(Modifier.padding(padding))
            relevant.isNullOrEmpty() -> EmptyState("No orders yet.", Modifier.padding(padding))
            else -> LazyColumn(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(relevant, key = { it.id }) { booking ->
                    Card(onClick = { onOpenOrder(booking.id) }, modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp)) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text(booking.id, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                                StatusChip(statusLabel(booking.status), statusColor(booking.status))
                            }
                            Text("${booking.patientName} · ${booking.items.size} test(s)", style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
        }
    }
}

class LabOrderViewModel(
    private val bookingRepository: BookingRepository,
    bookingId: String
) : ViewModel() {
    val booking: StateFlow<Booking?> = bookingRepository.observeBooking(bookingId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    fun receiveSample(bookingId: String, userId: String) = viewModelScope.launch { bookingRepository.labReceiveSample(bookingId, userId) }
    fun rejectSample(bookingId: String, reason: SampleRejectionReason, notes: String?, userId: String) =
        viewModelScope.launch { bookingRepository.rejectSample(bookingId, reason, notes, userId) }
    fun startProcessing(bookingId: String, userId: String) = viewModelScope.launch { bookingRepository.startProcessing(bookingId, userId) }
    fun uploadReport(bookingId: String, fileUri: String, userId: String) = viewModelScope.launch { bookingRepository.uploadReport(bookingId, fileUri, userId) }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LabOrderDetailScreen(bookingId: String, onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: LabOrderViewModel = viewModel(
        key = bookingId,
        factory = viewModelFactory { initializer { LabOrderViewModel(container.bookingRepository, bookingId) } }
    )
    val booking by viewModel.booking.collectAsState()
    val session by container.sessionManager.session.collectAsState(initial = null)
    var showRejectDialog by remember { mutableStateOf(false) }
    val userId = session?.userId ?: return

    val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) viewModel.uploadReport(bookingId, uri.toString(), userId)
    }

    Scaffold(topBar = { TopAppBar(title = { Text(bookingId) }) }) { padding ->
        val b = booking
        if (b == null) {
            LoadingState(Modifier.padding(padding))
        } else {
            Column(Modifier.padding(padding).padding(16.dp)) {
                SectionCard("Order") {
                    Text(b.patientName, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    b.items.forEach { Text("• ${it.investigation.name}", style = MaterialTheme.typography.bodyMedium) }
                }
                Spacer(Modifier.height(20.dp))
                when (b.status) {
                    BookingStatus.SAMPLE_IN_TRANSIT -> BigPrimaryButton(text = "Mark sample received", onClick = { viewModel.receiveSample(bookingId, userId) })
                    BookingStatus.RECEIVED_AT_LAB -> Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        BigPrimaryButton(text = "Start processing", modifier = Modifier.weight(1f), onClick = { viewModel.startProcessing(bookingId, userId) })
                        BigSecondaryButton(text = "Reject sample", modifier = Modifier.weight(1f), onClick = { showRejectDialog = true })
                    }
                    BookingStatus.PROCESSING -> BigPrimaryButton(text = "Upload report (PDF)", onClick = { filePicker.launch(arrayOf("application/pdf")) })
                    BookingStatus.REPORT_READY, BookingStatus.REPORT_DELIVERED -> Text("Report uploaded.", style = MaterialTheme.typography.bodyLarge)
                    else -> Text("Waiting for sample to arrive...", style = MaterialTheme.typography.bodyLarge)
                }
            }
        }
    }

    if (showRejectDialog) {
        var reason by remember { mutableStateOf(SampleRejectionReason.INSUFFICIENT_SAMPLE) }
        AlertDialog(
            onDismissRequest = { showRejectDialog = false },
            title = { Text("Reject sample") },
            text = {
                Column {
                    SampleRejectionReason.values().forEach { option ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(selected = reason == option, onClick = { reason = option })
                            Text(option.name.lowercase().replace('_', ' ').replaceFirstChar(Char::uppercase))
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { viewModel.rejectSample(bookingId, reason, null, userId); showRejectDialog = false }) { Text("Reject") }
            },
            dismissButton = { TextButton(onClick = { showRejectDialog = false }) { Text("Cancel") } }
        )
    }
}
