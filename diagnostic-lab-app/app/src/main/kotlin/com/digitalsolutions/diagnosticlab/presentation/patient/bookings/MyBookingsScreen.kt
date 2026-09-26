package com.digitalsolutions.diagnosticlab.presentation.patient.bookings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Science
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
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
import com.digitalsolutions.diagnosticlab.presentation.components.EmptyState
import com.digitalsolutions.diagnosticlab.presentation.components.IconChip
import com.digitalsolutions.diagnosticlab.presentation.components.LoadingState
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.components.StatusChip
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipRoseContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.AlertRed
import com.digitalsolutions.diagnosticlab.presentation.theme.HealthGreen
import com.digitalsolutions.diagnosticlab.presentation.theme.InfoBlue
import com.digitalsolutions.diagnosticlab.presentation.theme.WarningAmber
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn

class MyBookingsViewModel(bookingRepository: BookingRepository, sessionManager: SessionManager) : ViewModel() {
    val bookings: StateFlow<List<Booking>?> = sessionManager.session
        .filterNotNull()
        .flatMapLatest { bookingRepository.observeBookingsForOwner(it.userId) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)
}

fun statusColor(status: BookingStatus): Color = when (status) {
    BookingStatus.REPORT_DELIVERED -> HealthGreen
    BookingStatus.CANCELLED_BY_PATIENT, BookingStatus.CANCELLED_BY_LAB -> AlertRed
    BookingStatus.REJECTED_RECOLLECTION_NEEDED -> WarningAmber
    else -> InfoBlue
}

fun statusLabel(status: BookingStatus): String = status.name.split('_').joinToString(" ") { it.lowercase().replaceFirstChar(Char::uppercase) }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MyBookingsScreen(onOpenBooking: (String) -> Unit, onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: MyBookingsViewModel = viewModel(
        factory = viewModelFactory { initializer { MyBookingsViewModel(container.bookingRepository, container.sessionManager) } }
    )
    val bookings by viewModel.bookings.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("My Bookings") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        when {
            bookings == null -> LoadingState(Modifier.padding(padding))
            bookings!!.isEmpty() -> EmptyState("You haven't booked any tests yet.", Modifier.padding(padding))
            else -> LazyColumn(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(bookings!!, key = { it.id }) { booking ->
                    SectionCard(modifier = Modifier.testTag("booking_row").clickable(onClick = { onOpenBooking(booking.id) })) {
                        Row(verticalAlignment = Alignment.Top) {
                            IconChip(icon = Icons.Filled.Science, containerColor = ChipRoseContainer, contentColor = MaterialTheme.colorScheme.primary, size = 48.dp)
                            Spacer(Modifier.width(14.dp))
                            Column(Modifier.weight(1f)) {
                                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                                    Text(booking.laboratoryName, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                                    StatusChip(statusLabel(booking.status), statusColor(booking.status))
                                }
                                Spacer(Modifier.height(4.dp))
                                Text("For ${booking.patientName} · ${booking.items.size} test(s)", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Text("${booking.scheduledDate} · ${booking.scheduledTimeSlot}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
    }
}
