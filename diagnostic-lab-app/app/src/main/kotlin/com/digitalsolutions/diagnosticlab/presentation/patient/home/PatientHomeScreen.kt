package com.digitalsolutions.diagnosticlab.presentation.patient.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.R
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.patient.bookings.statusLabel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PatientHomeScreen(
    onBookTest: () -> Unit,
    onMyBookings: () -> Unit,
    onReports: () -> Unit,
    onFamily: () -> Unit,
    onHelp: () -> Unit,
    onNotifications: () -> Unit,
    onSettings: () -> Unit,
    onMedicalHistory: () -> Unit,
    onOpenBooking: (String) -> Unit
) {
    val container = LocalAppContainer.current
    val viewModel: PatientHomeViewModel = viewModel(
        factory = viewModelFactory {
            initializer {
                PatientHomeViewModel(container.patientRepository, container.bookingRepository, container.notificationRepository, container.sessionManager)
            }
        }
    )
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        stringResource(
                            R.string.home_greeting,
                            state.primaryPatient?.fullName?.ifBlank { null } ?: stringResource(R.string.home_greeting_fallback)
                        )
                    )
                },
                actions = {
                    IconButton(onClick = onNotifications) {
                        BadgedBox(badge = { if (state.unreadNotifications > 0) Badge { Text(state.unreadNotifications.toString()) } }) {
                            Icon(Icons.Filled.Notifications, contentDescription = "Notifications")
                        }
                    }
                    IconButton(onClick = onSettings) { Icon(Icons.Filled.Person, contentDescription = "Profile") }
                }
            )
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(selected = true, onClick = {}, icon = { Icon(Icons.Filled.Home, null) }, label = { Text(stringResource(R.string.nav_home)) })
                NavigationBarItem(selected = false, onClick = onMyBookings, icon = { Icon(Icons.Filled.CalendarMonth, null) }, label = { Text(stringResource(R.string.nav_bookings)) })
                NavigationBarItem(selected = false, onClick = onReports, icon = { Icon(Icons.Filled.Description, null) }, label = { Text(stringResource(R.string.nav_reports)) })
                NavigationBarItem(selected = false, onClick = onSettings, icon = { Icon(Icons.Filled.Person, null) }, label = { Text(stringResource(R.string.nav_profile)) })
            }
        }
    ) { padding ->
        Column(Modifier.padding(padding).padding(16.dp).verticalScroll(rememberScrollState())) {
            state.activeBooking?.let { booking ->
                Card(
                    onClick = { onOpenBooking(booking.id) },
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(Modifier.padding(16.dp)) {
                        Text(stringResource(R.string.active_booking_label), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.height(4.dp))
                        Text(
                            "${statusLabel(booking.status)} · ${booking.scheduledDate} at ${booking.scheduledTimeSlot}",
                            style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold
                        )
                        if (booking.addressLine.isNotBlank()) {
                            Spacer(Modifier.height(6.dp))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    Icons.Filled.LocationOn, contentDescription = null,
                                    tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(18.dp)
                                )
                                Spacer(Modifier.width(4.dp))
                                Text(booking.addressLine, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
                Spacer(Modifier.height(16.dp))
            }

            BigPrimaryButton(text = stringResource(R.string.book_a_test), onClick = onBookTest)
            Spacer(Modifier.height(20.dp))

            Text(stringResource(R.string.quick_actions), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(12.dp))
            HomeActionGrid(onMyBookings, onReports, onFamily, onMedicalHistory, onHelp)
        }
    }
}

@Composable
private fun HomeActionGrid(
    onMyBookings: () -> Unit,
    onReports: () -> Unit,
    onFamily: () -> Unit,
    onMedicalHistory: () -> Unit,
    onHelp: () -> Unit
) {
    val actions = listOf(
        Triple(stringResource(R.string.action_my_bookings), Icons.Filled.CalendarMonth, onMyBookings),
        Triple(stringResource(R.string.action_my_reports), Icons.Filled.Description, onReports),
        Triple(stringResource(R.string.action_my_family), Icons.Filled.People, onFamily),
        Triple(stringResource(R.string.action_previous_records), Icons.Filled.History, onMedicalHistory),
        Triple(stringResource(R.string.action_help_support), Icons.Filled.Help, onHelp)
    )
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        actions.chunked(2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                row.forEach { (label, icon, action) ->
                    SectionCard(modifier = Modifier.weight(1f)) {
                        Column(
                            modifier = Modifier.fillMaxWidth().clickableCard(action),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(32.dp))
                            Spacer(Modifier.height(8.dp))
                            Text(label, style = MaterialTheme.typography.labelLarge, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                        }
                    }
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

private fun Modifier.clickableCard(onClick: () -> Unit): Modifier = this.clickable(onClick = onClick)
