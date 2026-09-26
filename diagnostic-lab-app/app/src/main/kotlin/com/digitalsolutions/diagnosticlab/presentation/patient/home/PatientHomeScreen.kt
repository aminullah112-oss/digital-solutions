package com.digitalsolutions.diagnosticlab.presentation.patient.home

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.R
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.IconChip
import com.digitalsolutions.diagnosticlab.presentation.components.RoundedIconButton
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.patient.bookings.statusLabel
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipAmberContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipBlueContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipMintContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipRoseContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.HealthGreen
import com.digitalsolutions.diagnosticlab.presentation.theme.InfoBlue
import com.digitalsolutions.diagnosticlab.presentation.theme.WarningAmber

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
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    stringResource(
                        R.string.home_greeting,
                        state.primaryPatient?.fullName?.ifBlank { null } ?: stringResource(R.string.home_greeting_fallback)
                    ),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.ExtraBold,
                    modifier = Modifier.weight(1f)
                )
                RoundedIconButton(onClick = onNotifications) {
                    BadgedBox(badge = { if (state.unreadNotifications > 0) Badge { Text(state.unreadNotifications.toString()) } }) {
                        Icon(Icons.Filled.Notifications, contentDescription = "Notifications")
                    }
                }
                Spacer(Modifier.width(10.dp))
                RoundedIconButton(onClick = onSettings) { Icon(Icons.Filled.Person, contentDescription = "Profile") }
            }
        },
        bottomBar = { PatientBottomNav(selected = 0, onMyBookings = onMyBookings, onReports = onReports, onSettings = onSettings) }
    ) { padding ->
        Column(Modifier.padding(padding).padding(horizontal = 20.dp).verticalScroll(rememberScrollState())) {
            state.activeBooking?.let { booking ->
                Card(
                    onClick = { onOpenBooking(booking.id) },
                    shape = MaterialTheme.shapes.large,
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primary),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(Modifier.padding(20.dp)) {
                        Text(
                            stringResource(R.string.active_booking_label).uppercase(),
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.85f)
                        )
                        Spacer(Modifier.height(6.dp))
                        Text(
                            "${statusLabel(booking.status)} · ${booking.scheduledDate} at ${booking.scheduledTimeSlot}",
                            style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onPrimary
                        )
                        if (booking.addressLine.isNotBlank()) {
                            Spacer(Modifier.height(8.dp))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    Icons.Filled.LocationOn, contentDescription = null,
                                    tint = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.85f), modifier = Modifier.size(18.dp)
                                )
                                Spacer(Modifier.width(4.dp))
                                Text(
                                    booking.addressLine, style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.9f)
                                )
                            }
                        }
                        Spacer(Modifier.height(14.dp))
                        Box(
                            Modifier.fillMaxWidth().height(40.dp)
                                .background(MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.18f), RoundedCornerShape(12.dp)),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("View Details", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onPrimary)
                        }
                    }
                }
                Spacer(Modifier.height(18.dp))
            }

            BigPrimaryButton(
                text = stringResource(R.string.book_a_test),
                onClick = onBookTest,
                modifier = Modifier.testTag("patient_home_book_button")
            )
            Spacer(Modifier.height(22.dp))

            Text(stringResource(R.string.quick_actions), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold)
            Spacer(Modifier.height(12.dp))
            HomeActionGrid(onMyBookings, onReports, onFamily, onMedicalHistory, onHelp)
            Spacer(Modifier.height(20.dp))
        }
    }
}

@Composable
private fun PatientBottomNav(selected: Int, onMyBookings: () -> Unit, onReports: () -> Unit, onSettings: () -> Unit) {
    NavigationBar(containerColor = MaterialTheme.colorScheme.surface, tonalElevation = 0.dp) {
        val selectedColors = NavigationBarItemDefaults.colors(
            selectedIconColor = MaterialTheme.colorScheme.primary,
            selectedTextColor = MaterialTheme.colorScheme.primary,
            unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
            unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
            indicatorColor = androidx.compose.ui.graphics.Color.Transparent
        )
        NavigationBarItem(selected = selected == 0, onClick = {}, colors = selectedColors, icon = { Icon(Icons.Filled.Home, null) }, label = { Text(stringResource(R.string.nav_home)) })
        NavigationBarItem(selected = selected == 1, onClick = onMyBookings, colors = selectedColors, icon = { Icon(Icons.Filled.CalendarMonth, null) }, label = { Text(stringResource(R.string.nav_bookings)) })
        NavigationBarItem(selected = selected == 2, onClick = onReports, colors = selectedColors, icon = { Icon(Icons.Filled.Description, null) }, label = { Text(stringResource(R.string.nav_reports)) })
        NavigationBarItem(selected = selected == 3, onClick = onSettings, colors = selectedColors, icon = { Icon(Icons.Filled.Person, null) }, label = { Text(stringResource(R.string.nav_profile)) })
    }
}

private data class QuickAction(val label: String, val icon: ImageVector, val chipColor: androidx.compose.ui.graphics.Color, val iconColor: androidx.compose.ui.graphics.Color, val onClick: () -> Unit)

@Composable
private fun HomeActionGrid(
    onMyBookings: () -> Unit,
    onReports: () -> Unit,
    onFamily: () -> Unit,
    onMedicalHistory: () -> Unit,
    onHelp: () -> Unit
) {
    val actions = listOf(
        QuickAction(stringResource(R.string.action_my_bookings), Icons.Filled.CalendarMonth, ChipBlueContainer, InfoBlue, onMyBookings),
        QuickAction(stringResource(R.string.action_my_reports), Icons.Filled.Description, ChipMintContainer, HealthGreen, onReports),
        QuickAction(stringResource(R.string.action_my_family), Icons.Filled.People, ChipRoseContainer, MaterialTheme.colorScheme.primary, onFamily),
        QuickAction(stringResource(R.string.action_previous_records), Icons.Filled.History, ChipAmberContainer, WarningAmber, onMedicalHistory),
        QuickAction(stringResource(R.string.action_help_support), Icons.Filled.Help, ChipBlueContainer, InfoBlue, onHelp)
    )
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        actions.chunked(2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                row.forEach { action ->
                    SectionCard(modifier = Modifier.weight(1f).clickable(onClick = action.onClick)) {
                        IconChip(icon = action.icon, containerColor = action.chipColor, contentColor = action.iconColor)
                        Spacer(Modifier.height(10.dp))
                        Text(action.label, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, textAlign = TextAlign.Start)
                    }
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}
