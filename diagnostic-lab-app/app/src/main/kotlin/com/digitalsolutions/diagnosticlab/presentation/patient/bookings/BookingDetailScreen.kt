package com.digitalsolutions.diagnosticlab.presentation.patient.bookings

import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
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
import com.digitalsolutions.diagnosticlab.domain.model.AssignmentStatus
import com.digitalsolutions.diagnosticlab.domain.model.Booking
import com.digitalsolutions.diagnosticlab.domain.model.TrackingEvent
import com.digitalsolutions.diagnosticlab.domain.util.BookingStatusMachine
import com.digitalsolutions.diagnosticlab.presentation.components.AddressCard
import com.digitalsolutions.diagnosticlab.presentation.patient.booking.AddressPickerScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.booking.timeSlots
import com.digitalsolutions.diagnosticlab.presentation.components.BigSecondaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.LiveTrackingMap
import com.digitalsolutions.diagnosticlab.presentation.components.LoadingState
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.components.StatusTimeline
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

class BookingDetailViewModel(private val bookingRepository: BookingRepository, private val sessionManager: SessionManager, bookingId: String) : ViewModel() {
    data class DetailState(val booking: Booking?, val events: List<TrackingEvent>, val assignment: Assignment?)

    val detail: StateFlow<DetailState?> = combine(
        bookingRepository.observeBooking(bookingId),
        bookingRepository.observeTrackingEvents(bookingId),
        bookingRepository.observeAssignment(bookingId)
    ) { booking, events, assignment -> DetailState(booking, events, assignment) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    var notice by mutableStateOf<String?>(null)
        private set

    fun reschedule(bookingId: String, date: LocalDate, slot: String) {
        viewModelScope.launch {
            try {
                val userId = sessionManager.session.first()?.userId ?: return@launch
                bookingRepository.updateSchedule(bookingId, date, slot, userId)
                notice = "Time updated to $date, $slot."
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: Exception) {
                notice = e.message ?: "Couldn't change the time. Please try again."
            }
        }
    }

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
fun BookingDetailScreen(bookingId: String, onChangeAddress: () -> Unit, onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: BookingDetailViewModel = viewModel(
        key = bookingId,
        factory = viewModelFactory { initializer { BookingDetailViewModel(container.bookingRepository, container.sessionManager, bookingId) } }
    )
    val detail by viewModel.detail.collectAsState()
    var showCancelDialog by remember { mutableStateOf(false) }
    var showRescheduleDialog by remember { mutableStateOf(false) }

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
                    // Only while actually en route, and only once they've reported a real fix —
                    // avoids a map centered on (0,0) or a stale pin from a much earlier leg.
                    val patientLat = booking.addressLatitude
                    val patientLng = booking.addressLongitude
                    if (assignment.status == AssignmentStatus.ON_THE_WAY &&
                        assignment.phlebotomistLatitude != null && assignment.phlebotomistLongitude != null &&
                        patientLat != null && patientLng != null
                    ) {
                        LiveTrackingMap(
                            patientLatitude = patientLat,
                            patientLongitude = patientLng,
                            phlebotomistLatitude = assignment.phlebotomistLatitude,
                            phlebotomistLongitude = assignment.phlebotomistLongitude
                        )
                        Spacer(Modifier.height(12.dp))
                    }
                }
                SectionCard("Tests") {
                    booking.items.forEach { Text("• ${it.investigation.name}", style = MaterialTheme.typography.bodyMedium) }
                }
                Spacer(Modifier.height(12.dp))
                val canModify = BookingStatusMachine.canModifyVisit(booking.status)
                SectionCard("Schedule") {
                    Text("${booking.scheduledDate} · ${booking.scheduledTimeSlot}", style = MaterialTheme.typography.bodyMedium)
                    if (canModify) {
                        TextButton(onClick = { showRescheduleDialog = true }) { Text("Change date & time") }
                    }
                }
                Spacer(Modifier.height(12.dp))
                AddressCard(
                    title = "Collection address",
                    label = booking.addressLabel,
                    addressLine = booking.addressLine,
                    latitude = booking.addressLatitude,
                    longitude = booking.addressLongitude
                )
                if (canModify) {
                    TextButton(onClick = onChangeAddress) { Text("Change address") }
                } else if (BookingStatusMachine.canCancel(booking.status)) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "The lab assistant is on the way, so the time and address can't be changed here. Contact support from the Help & Support page.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                viewModel.notice?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary)
                }
                if (BookingStatusMachine.canCancel(booking.status)) {
                    Spacer(Modifier.height(20.dp))
                    BigSecondaryButton(text = "Cancel booking", onClick = { showCancelDialog = true })
                }
                Spacer(Modifier.height(24.dp))
            }
        }
    }

    if (showRescheduleDialog) {
        detail?.booking?.let { current ->
            RescheduleDialog(
                current = current,
                onDismiss = { showRescheduleDialog = false },
                onConfirm = { date, slot ->
                    viewModel.reschedule(bookingId, date, slot)
                    showRescheduleDialog = false
                }
            )
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

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun RescheduleDialog(current: Booking, onDismiss: () -> Unit, onConfirm: (LocalDate, String) -> Unit) {
    val today = remember { LocalDate.now() }
    val days = remember { (0..6).map { today.plusDays(it.toLong()) } }
    var date by remember { mutableStateOf(current.scheduledDate.takeIf { !it.isBefore(today) } ?: today) }
    var slot by remember { mutableStateOf<String?>(null) }
    // Today only offers slots that haven't started yet.
    val nowHour = remember { java.time.LocalTime.now().hour }
    val slots = timeSlots.filter { date != today || (it.substringBefore(":").toIntOrNull() ?: 0) > nowHour }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Change date & time") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Text("Date", fontWeight = FontWeight.Bold)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    days.forEach { day ->
                        FilterChip(
                            selected = day == date,
                            onClick = { date = day; slot = null },
                            label = { Text(day.format(DateTimeFormatter.ofPattern("EEE d MMM", Locale.getDefault()))) }
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
                Text("Time", fontWeight = FontWeight.Bold)
                if (slots.isEmpty()) {
                    Text("No more slots today. Pick another day.", style = MaterialTheme.typography.bodySmall)
                }
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    slots.forEach { s ->
                        FilterChip(selected = s == slot, onClick = { slot = s }, label = { Text(s.substringBefore("-")) })
                    }
                }
            }
        },
        confirmButton = {
            TextButton(enabled = slot != null, onClick = { onConfirm(date, slot!!) }) { Text("Save") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Close") } }
    )
}

/** Pick another saved address (or add one) for an existing booking. */
@Composable
fun ChangeAddressScreen(bookingId: String, onDone: () -> Unit) {
    val container = LocalAppContainer.current
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var saving by remember { mutableStateOf(false) }
    AddressPickerScreen(
        title = "Change address",
        onPicked = { address ->
            if (!saving) {
                saving = true
                scope.launch {
                    try {
                        val userId = container.sessionManager.session.first()?.userId
                            ?: throw IllegalStateException("Please sign in again.")
                        container.bookingRepository.updateAddress(bookingId, userId, address.id, userId)
                        Toast.makeText(context, "Address updated.", Toast.LENGTH_SHORT).show()
                        onDone()
                    } catch (e: kotlinx.coroutines.CancellationException) {
                        throw e
                    } catch (e: Exception) {
                        Toast.makeText(context, e.message ?: "Couldn't change the address.", Toast.LENGTH_LONG).show()
                        saving = false
                    }
                }
            }
        },
        onBack = onDone
    )
}
