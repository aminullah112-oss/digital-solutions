package com.digitalsolutions.diagnosticlab.presentation.phlebotomist

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Logout
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
import com.digitalsolutions.diagnosticlab.domain.model.AssignmentStatus
import com.digitalsolutions.diagnosticlab.domain.model.Booking
import com.digitalsolutions.diagnosticlab.presentation.components.AddressCard
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.BigSecondaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.EmptyState
import com.digitalsolutions.diagnosticlab.presentation.components.LoadingState
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.components.StatusChip
import com.digitalsolutions.diagnosticlab.presentation.patient.bookings.statusColor
import com.digitalsolutions.diagnosticlab.presentation.patient.bookings.statusLabel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class PhlebotomistHomeViewModel(bookingRepository: BookingRepository, sessionManager: SessionManager) : ViewModel() {
    val assignments: StateFlow<List<Booking>?> = sessionManager.session
        .filterNotNull()
        .map { it.linkedEntityId }
        .filterNotNull()
        .flatMapLatest { bookingRepository.observeActiveForPhlebotomist(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PhlebotomistHomeScreen(onOpenAssignment: (String) -> Unit, onSignedOut: () -> Unit) {
    val container = LocalAppContainer.current
    val scope = rememberCoroutineScope()
    val viewModel: PhlebotomistHomeViewModel = viewModel(
        factory = viewModelFactory { initializer { PhlebotomistHomeViewModel(container.bookingRepository, container.sessionManager) } }
    )
    val assignments by viewModel.assignments.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Today's Collections") },
                actions = {
                    IconButton(onClick = { scope.launch { container.sessionManager.signOut(); withContext(Dispatchers.Main.immediate) { onSignedOut() } } }) {
                        Icon(Icons.Filled.Logout, contentDescription = "Sign out")
                    }
                }
            )
        }
    ) { padding ->
        when {
            assignments == null -> LoadingState(Modifier.padding(padding))
            assignments!!.isEmpty() -> EmptyState("No collections assigned right now.", Modifier.padding(padding))
            else -> LazyColumn(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(assignments!!, key = { it.id }) { booking ->
                    Card(onClick = { onOpenAssignment(booking.id) }, modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp)) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text(booking.patientName, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                                StatusChip(statusLabel(booking.status), statusColor(booking.status))
                            }
                            Text(booking.addressLine, style = MaterialTheme.typography.bodyMedium)
                            Text("${booking.scheduledDate} · ${booking.scheduledTimeSlot}", style = MaterialTheme.typography.labelMedium)
                        }
                    }
                }
            }
        }
    }
}

class PhlebotomistAssignmentViewModel(
    private val bookingRepository: BookingRepository,
    private val sessionManager: SessionManager,
    private val bookingId: String
) : ViewModel() {
    val booking: StateFlow<Booking?> = bookingRepository.observeBooking(bookingId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)
    val assignment = bookingRepository.observeAssignment(bookingId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    fun respond(accept: Boolean) = viewModelScope.launch { bookingRepository.respondToAssignment(bookingId, accept) }
    fun setTravelStatus(status: AssignmentStatus) = viewModelScope.launch { bookingRepository.updateAssignmentTravelStatus(bookingId, status) }
    fun collectSample(sampleType: String, location: String) = viewModelScope.launch { bookingRepository.recordSampleCollected(bookingId, sampleType, location) }
    fun markInTransit() = viewModelScope.launch { bookingRepository.markSampleInTransit(bookingId) }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PhlebotomistAssignmentScreen(bookingId: String, onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: PhlebotomistAssignmentViewModel = viewModel(
        key = bookingId,
        factory = viewModelFactory { initializer { PhlebotomistAssignmentViewModel(container.bookingRepository, container.sessionManager, bookingId) } }
    )
    val booking by viewModel.booking.collectAsState()
    val assignment by viewModel.assignment.collectAsState()

    Scaffold(
        topBar = { TopAppBar(title = { Text(bookingId) }) }
    ) { padding ->
        val b = booking
        if (b == null) {
            LoadingState(Modifier.padding(padding))
        } else {
            Column(Modifier.padding(padding).padding(16.dp)) {
                SectionCard("Patient") {
                    Text(b.patientName, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("${b.scheduledDate} · ${b.scheduledTimeSlot}", style = MaterialTheme.typography.bodyMedium)
                }
                Spacer(Modifier.height(12.dp))
                AddressCard(
                    title = "Collection address",
                    label = b.addressLabel,
                    addressLine = b.addressLine,
                    latitude = b.addressLatitude,
                    longitude = b.addressLongitude
                )
                Spacer(Modifier.height(12.dp))
                SectionCard("Tests to collect for") {
                    b.items.forEach { Text("• ${it.investigation.name} (${it.investigation.sampleType})", style = MaterialTheme.typography.bodyMedium) }
                }
                Spacer(Modifier.height(20.dp))
                when (assignment?.status) {
                    AssignmentStatus.ASSIGNED -> Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        BigPrimaryButton(text = "Accept", modifier = Modifier.weight(1f), onClick = { viewModel.respond(true) })
                        BigSecondaryButton(text = "Reject", modifier = Modifier.weight(1f), onClick = { viewModel.respond(false) })
                    }
                    AssignmentStatus.ACCEPTED -> BigPrimaryButton(text = "Start traveling", onClick = { viewModel.setTravelStatus(AssignmentStatus.ON_THE_WAY) })
                    AssignmentStatus.ON_THE_WAY -> BigPrimaryButton(text = "Mark arrived", onClick = { viewModel.setTravelStatus(AssignmentStatus.ARRIVED) })
                    AssignmentStatus.ARRIVED -> CollectSampleForm(onCollect = { type, location -> viewModel.collectSample(type, location) })
                    AssignmentStatus.SAMPLE_COLLECTED, AssignmentStatus.COMPLETED ->
                        BigPrimaryButton(text = "Hand over to transit", onClick = { viewModel.markInTransit() })
                    else -> Text("Waiting for allocation...", style = MaterialTheme.typography.bodyLarge)
                }
            }
        }
    }
}

@Composable
private fun CollectSampleForm(onCollect: (String, String) -> Unit) {
    var sampleType by remember { mutableStateOf("Blood") }
    var location by remember { mutableStateOf("Patient's home") }
    Column {
        OutlinedTextField(sampleType, { sampleType = it }, label = { Text("Sample type") }, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(location, { location = it }, label = { Text("Collection location") }, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(12.dp))
        BigPrimaryButton(text = "Confirm sample collected", onClick = { onCollect(sampleType, location) })
    }
}
