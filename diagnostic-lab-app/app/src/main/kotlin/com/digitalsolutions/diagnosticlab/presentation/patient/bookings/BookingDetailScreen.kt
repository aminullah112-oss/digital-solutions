package com.digitalsolutions.diagnosticlab.presentation.patient.bookings

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import com.digitalsolutions.diagnosticlab.data.repository.BookingRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.Assignment
import com.digitalsolutions.diagnosticlab.domain.model.Booking
import com.digitalsolutions.diagnosticlab.domain.model.TrackingEvent
import com.digitalsolutions.diagnosticlab.domain.util.BookingStatusMachine
import com.digitalsolutions.diagnosticlab.presentation.components.AddressCard
import com.digitalsolutions.diagnosticlab.presentation.components.BigSecondaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.LoadingState
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.components.StatusTimeline
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class BookingDetailViewModel(private val bookingRepository: BookingRepository, private val sessionManager: SessionManager, bookingId: String) : ViewModel() {
    data class DetailState(val booking: Booking?, val events: List<TrackingEvent>, val assignment: Assignment?)

    val detail: StateFlow<DetailState?> = combine(
        bookingRepository.observeBooking(bookingId),
        bookingRepository.observeTrackingEvents(bookingId),
        bookingRepository.observeAssignment(bookingId)
    ) { booking, events, assignment -> DetailState(booking, events, assignment) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    fun cancel(bookingId: String, reason: String) {
        viewModelScope.launch {
            val userId = sessionManager.session.first()?.userId ?: return@launch
            bookingRepository.cancelBooking(bookingId, reason, userId, byLab = false)
        }
    }
}

private val timelineLabels = listOf(
    "Booking confirmed", "Lab assistant assigned", "Lab assistant on the way", "Arrived",
    "Sample collected", "Sample in transit", "Received at lab", "Processing", "Report ready", "Report delivered"
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookingDetailScreen(bookingId: String, onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: BookingDetailViewModel = viewModel(
        key = bookingId,
        factory = viewModelFactory { initializer { BookingDetailViewModel(container.bookingRepository, container.sessionManager, bookingId) } }
    )
    val detail by viewModel.detail.collectAsState()
    var showCancelDialog by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(bookingId) },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        val booking = detail?.booking
        if (booking == null) {
            LoadingState(Modifier.padding(padding))
        } else {
            Column(Modifier.padding(padding).padding(16.dp).verticalScroll(rememberScrollState())) {
                SectionCard("Status") {
                    // BookingStatusMachine.timelineSteps() gives the canonical forward order used to
                    // compute how far along the visual timeline (spec section 29) should be filled in.
                    val forwardSteps = BookingStatusMachine.timelineSteps()
                    val currentIndex = forwardSteps.indexOf(booking.status).let { if (it < 0) forwardSteps.size else it }
                    StatusTimeline(timelineLabels, currentIndex)
                }
                Spacer(Modifier.height(12.dp))
                detail?.assignment?.let { assignment ->
                    SectionCard("Lab assistant") {
                        Text(assignment.phlebotomist.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text("Rating ${assignment.phlebotomist.rating}", style = MaterialTheme.typography.bodyMedium)
                    }
                    Spacer(Modifier.height(12.dp))
                }
                SectionCard("Tests") {
                    booking.items.forEach { Text("• ${it.investigation.name}", style = MaterialTheme.typography.bodyMedium) }
                }
                Spacer(Modifier.height(12.dp))
                SectionCard("Schedule") {
                    Text("${booking.scheduledDate} · ${booking.scheduledTimeSlot}", style = MaterialTheme.typography.bodyMedium)
                }
                Spacer(Modifier.height(12.dp))
                AddressCard(
                    title = "Collection address",
                    label = booking.addressLabel,
                    addressLine = booking.addressLine,
                    latitude = booking.addressLatitude,
                    longitude = booking.addressLongitude
                )
                if (BookingStatusMachine.canCancel(booking.status)) {
                    Spacer(Modifier.height(20.dp))
                    BigSecondaryButton(text = "Cancel booking", onClick = { showCancelDialog = true })
                }
                Spacer(Modifier.height(24.dp))
            }
        }
    }

    if (showCancelDialog) {
        AlertDialog(
            onDismissRequest = { showCancelDialog = false },
            title = { Text("Cancel this booking?") },
            text = { Text("The lab assistant, if already assigned, will be notified.") },
            confirmButton = {
                TextButton(onClick = { viewModel.cancel(bookingId, "Cancelled by patient"); showCancelDialog = false }) { Text("Yes, cancel") }
            },
            dismissButton = { TextButton(onClick = { showCancelDialog = false }) { Text("No") } }
        )
    }
}
