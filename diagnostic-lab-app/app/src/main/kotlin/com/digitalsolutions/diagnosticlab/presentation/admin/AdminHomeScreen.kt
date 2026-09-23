package com.digitalsolutions.diagnosticlab.presentation.admin

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Logout
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
import com.digitalsolutions.diagnosticlab.data.repository.AdminRepository
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.DashboardStats
import com.digitalsolutions.diagnosticlab.domain.model.Laboratory
import com.digitalsolutions.diagnosticlab.presentation.components.LoadingState
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class AdminHomeViewModel(private val adminRepository: AdminRepository) : ViewModel() {
    val stats: StateFlow<DashboardStats?> = adminRepository.observeDashboard()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    val laboratories: StateFlow<List<Laboratory>> = adminRepository.observeAllLaboratories()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    fun toggleLab(id: String, active: Boolean) = viewModelScope.launch { adminRepository.setLabActive(id, active) }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdminHomeScreen(onSignedOut: () -> Unit) {
    val container = LocalAppContainer.current
    val scope = rememberCoroutineScope()
    val viewModel: AdminHomeViewModel = viewModel(factory = viewModelFactory { initializer { AdminHomeViewModel(container.adminRepository) } })
    val stats by viewModel.stats.collectAsState()
    val labs by viewModel.laboratories.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Admin Dashboard") },
                actions = {
                    IconButton(onClick = { scope.launch { container.sessionManager.signOut(); withContext(Dispatchers.Main.immediate) { onSignedOut() } } }) {
                        Icon(Icons.Filled.Logout, contentDescription = "Sign out")
                    }
                }
            )
        }
    ) { padding ->
        val s = stats
        if (s == null) {
            LoadingState(Modifier.padding(padding))
        } else {
            LazyColumn(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                item {
                    StatGrid(s)
                }
                item {
                    Text("Laboratories", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                }
                items(labs, key = { it.id }) { lab ->
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Column {
                                Text(lab.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                                Text(lab.city, style = MaterialTheme.typography.bodyMedium)
                            }
                            Switch(checked = lab.active, onCheckedChange = { viewModel.toggleLab(lab.id, it) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StatGrid(stats: DashboardStats) {
    val items = listOf(
        "Total patients" to stats.totalPatients.toString(),
        "New (7 days)" to stats.newPatientsLast7Days.toString(),
        "Total bookings" to stats.totalBookings.toString(),
        "Today's bookings" to stats.todaysBookings.toString(),
        "Pending collections" to stats.pendingCollections.toString(),
        "Samples in transit" to stats.samplesInTransit.toString(),
        "Reports pending" to stats.reportsPending.toString(),
        "Reports completed" to stats.reportsCompleted.toString(),
        "Revenue" to "₹${"%.0f".format(stats.totalRevenue)}",
        "Open complaints" to stats.openComplaints.toString(),
        "Active labs" to stats.activeLabs.toString()
    )
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        items.chunked(2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                row.forEach { (label, value) ->
                    SectionCard(modifier = Modifier.weight(1f)) {
                        Text(value, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                        Text(label, style = MaterialTheme.typography.labelMedium)
                    }
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}
