package com.digitalsolutions.diagnosticlab.presentation.patient.notifications

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.DirectionsCar
import androidx.compose.material.icons.filled.Help
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Science
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.data.repository.NotificationRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.AppNotification
import com.digitalsolutions.diagnosticlab.domain.model.NotificationType
import com.digitalsolutions.diagnosticlab.presentation.components.EmptyState
import com.digitalsolutions.diagnosticlab.presentation.components.IconChip
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipBlueContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipMintContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipRoseContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.HealthGreen
import com.digitalsolutions.diagnosticlab.presentation.theme.InfoBlue
import com.digitalsolutions.diagnosticlab.presentation.theme.WarningAmber
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.util.concurrent.TimeUnit

class NotificationsViewModel(
    private val notificationRepository: NotificationRepository,
    sessionManager: SessionManager
) : ViewModel() {
    val notifications: StateFlow<List<AppNotification>> = sessionManager.session
        .filterNotNull()
        .flatMapLatest { notificationRepository.observeForUser(it.userId) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    fun markRead(id: String) {
        viewModelScope.launch { notificationRepository.markRead(id) }
    }
}

private fun iconFor(type: NotificationType): ImageVector = when (type) {
    NotificationType.BOOKING_CONFIRMED, NotificationType.PAYMENT_CONFIRMED, NotificationType.REPORT_READY, NotificationType.REPORT_DELIVERED -> Icons.Filled.CheckCircle
    NotificationType.PHLEBOTOMIST_ASSIGNED, NotificationType.PHLEBOTOMIST_ACCEPTED, NotificationType.PHLEBOTOMIST_ON_THE_WAY, NotificationType.PHLEBOTOMIST_ARRIVED -> Icons.Filled.DirectionsCar
    NotificationType.SAMPLE_COLLECTED, NotificationType.SAMPLE_RECEIVED_AT_LAB, NotificationType.SAMPLE_PROCESSING -> Icons.Filled.Science
    NotificationType.COMPLAINT_UPDATE -> Icons.Filled.Help
    NotificationType.GENERAL -> Icons.Filled.Notifications
}

private fun chipColorFor(type: NotificationType) = when (type) {
    NotificationType.BOOKING_CONFIRMED, NotificationType.PAYMENT_CONFIRMED, NotificationType.REPORT_READY, NotificationType.REPORT_DELIVERED -> ChipMintContainer to HealthGreen
    NotificationType.PHLEBOTOMIST_ASSIGNED, NotificationType.PHLEBOTOMIST_ACCEPTED, NotificationType.PHLEBOTOMIST_ON_THE_WAY, NotificationType.PHLEBOTOMIST_ARRIVED -> ChipRoseContainer to WarningAmber
    NotificationType.SAMPLE_COLLECTED, NotificationType.SAMPLE_RECEIVED_AT_LAB, NotificationType.SAMPLE_PROCESSING -> ChipRoseContainer to WarningAmber
    NotificationType.COMPLAINT_UPDATE -> ChipBlueContainer to InfoBlue
    NotificationType.GENERAL -> ChipBlueContainer to InfoBlue
}

private fun relativeTime(createdAtMillis: Long): String {
    val diff = System.currentTimeMillis() - createdAtMillis
    val hours = TimeUnit.MILLISECONDS.toHours(diff)
    return when {
        hours < 1 -> "now"
        hours < 24 -> "${hours}h"
        else -> "${TimeUnit.MILLISECONDS.toDays(diff)}d"
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationsScreen(onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: NotificationsViewModel = viewModel(
        factory = viewModelFactory { initializer { NotificationsViewModel(container.notificationRepository, container.sessionManager) } }
    )
    val notifications by viewModel.notifications.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Notifications") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        if (notifications.isEmpty()) {
            EmptyState("You're all caught up.", Modifier.padding(padding))
        } else {
            val oneDayAgo = System.currentTimeMillis() - TimeUnit.DAYS.toMillis(1)
            val (today, earlier) = notifications.partition { it.createdAtMillis >= oneDayAgo }
            LazyColumn(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (today.isNotEmpty()) {
                    item { Text("TODAY", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    items(today, key = { it.id }) { NotificationRow(it, onClick = { viewModel.markRead(it.id) }) }
                }
                if (earlier.isNotEmpty()) {
                    item { Text("EARLIER", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    items(earlier, key = { it.id }) { NotificationRow(it, onClick = { viewModel.markRead(it.id) }) }
                }
            }
        }
    }
}

@Composable
private fun NotificationRow(notification: AppNotification, onClick: () -> Unit) {
    val (chipBg, chipTint) = chipColorFor(notification.type)
    SectionCard(modifier = Modifier.clickable(onClick = onClick)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconChip(icon = iconFor(notification.type), containerColor = chipBg, contentColor = chipTint, size = 40.dp, iconSize = 18.dp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(notification.title, style = MaterialTheme.typography.bodyLarge, fontWeight = if (notification.read) FontWeight.Normal else FontWeight.Bold)
                Text(notification.body, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.width(8.dp))
            Text(relativeTime(notification.createdAtMillis), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
