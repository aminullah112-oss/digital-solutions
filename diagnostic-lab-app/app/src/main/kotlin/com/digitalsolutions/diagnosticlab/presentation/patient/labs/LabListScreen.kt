package com.digitalsolutions.diagnosticlab.presentation.patient.labs

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.clickable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.LocalHospital
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.data.repository.CatalogRepository
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.Laboratory
import com.digitalsolutions.diagnosticlab.presentation.components.EmptyState
import com.digitalsolutions.diagnosticlab.presentation.components.IconChip
import com.digitalsolutions.diagnosticlab.presentation.components.LoadingState
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipMintContainer
import com.digitalsolutions.diagnosticlab.presentation.theme.HealthGreen
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn

class LabListViewModel(catalogRepository: CatalogRepository) : ViewModel() {
    val laboratories: StateFlow<List<Laboratory>?> = catalogRepository.observeLaboratories()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LabListScreen(onLabSelected: (Laboratory) -> Unit, onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: LabListViewModel = viewModel(factory = viewModelFactory { initializer { LabListViewModel(container.catalogRepository) } })
    val labs by viewModel.laboratories.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Choose a laboratory") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        when {
            labs == null -> LoadingState(Modifier.padding(padding))
            labs!!.isEmpty() -> EmptyState("No laboratories available right now.", Modifier.padding(padding))
            else -> LazyColumn(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(labs!!) { lab -> LabRow(lab, onClick = { onLabSelected(lab) }) }
            }
        }
    }
}

@Composable
private fun LabRow(lab: Laboratory, onClick: () -> Unit) {
    SectionCard(modifier = Modifier.testTag("lab_row").clickable(onClick = onClick)) {
        Row(verticalAlignment = Alignment.Top, modifier = Modifier.fillMaxWidth()) {
            IconChip(icon = Icons.Filled.LocalHospital, containerColor = ChipMintContainer, contentColor = HealthGreen, size = 48.dp)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                    Text(lab.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.Star, contentDescription = null, tint = MaterialTheme.colorScheme.secondary, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(4.dp))
                        Text(lab.rating.toString(), style = MaterialTheme.typography.bodyMedium)
                    }
                }
                Spacer(Modifier.height(4.dp))
                Text("${lab.address}, ${lab.city}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(2.dp))
                Text("Open ${lab.openTime}–${lab.closeTime} · Reports in ~${lab.estimatedReportHours}h", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (lab.homeCollectionAvailable) {
                    Spacer(Modifier.height(4.dp))
                    Text("Home collection available", style = MaterialTheme.typography.labelMedium, color = HealthGreen, fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}
