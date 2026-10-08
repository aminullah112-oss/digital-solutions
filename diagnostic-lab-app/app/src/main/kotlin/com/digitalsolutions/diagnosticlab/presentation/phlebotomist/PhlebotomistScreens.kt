package com.digitalsolutions.diagnosticlab.presentation.phlebotomist

import android.Manifest
import android.content.pm.PackageManager
import android.os.Looper
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
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
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
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
    fun reportLocation(latitude: Double, longitude: Double) =
        viewModelScope.launch { bookingRepository.updatePhlebotomistLocation(bookingId, latitude, longitude) }
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
    val context = LocalContext.current

    var hasLocationPermission by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED)
    }
    val locationPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        hasLocationPermission = granted
    }
    // Ask only once actually needed (travel starts), not up front at screen open — the manifest
    // already declares the permission, but requesting it before there's a reason to confuses
    // a user who hasn't even accepted the assignment yet.
    LaunchedEffect(assignment?.status) {
        if (assignment?.status == AssignmentStatus.ON_THE_WAY && !hasLocationPermission) {
            locationPermissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
        }
    }
    // Live tracking (#42) is foreground-only by design: it runs while this screen is open and
    // the assignment is ON_THE_WAY, and stops the moment either stops being true (screen closed,
    // status moves to ARRIVED, permission revoked). A background service that keeps reporting
    // location after the app is backgrounded is real additional scope — a foreground-service
    // notification, Android's stricter background-location review for Play Store — deliberately
    // not built here; this covers the common case (phlebotomist has the app open while driving)
    // without that cost.
    DisposableEffect(assignment?.status, hasLocationPermission) {
        if (assignment?.status == AssignmentStatus.ON_THE_WAY &&
            hasLocationPermission &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        ) {
            val client = LocationServices.getFusedLocationProviderClient(context)
            val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 15_000L).build()
            val callback = object : LocationCallback() {
                override fun onLocationResult(result: LocationResult) {
                    result.lastLocation?.let { viewModel.reportLocation(it.latitude, it.longitude) }
                }
            }
            client.requestLocationUpdates(request, callback, Looper.getMainLooper())
            onDispose { client.removeLocationUpdates(callback) }
        } else {
            onDispose { }
        }
    }

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
