package com.digitalsolutions.diagnosticlab.presentation.patient.investigations

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddCircle
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Science
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.digitalsolutions.diagnosticlab.domain.model.PricedInvestigation
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.EmptyState
import com.digitalsolutions.diagnosticlab.presentation.components.IconChip
import com.digitalsolutions.diagnosticlab.presentation.components.PillFilterChip
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.components.VoiceEnabledTextField
import com.digitalsolutions.diagnosticlab.presentation.patient.booking.BookingViewModel
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipRoseContainer

private const val ALL_CATEGORIES = "All"

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InvestigationCatalogScreen(
    bookingViewModel: BookingViewModel,
    onContinue: (labId: String) -> Unit,
    onBack: () -> Unit
) {
    val state by bookingViewModel.state.collectAsState()
    var query by remember { mutableStateOf("") }
    var selectedCategory by remember { mutableStateOf(ALL_CATEGORIES) }
    val categories = remember(state.availableInvestigations) {
        listOf(ALL_CATEGORIES) + state.availableInvestigations.map { it.investigation.category }.distinct()
    }
    val filtered = state.availableInvestigations.filter {
        (query.isBlank() || it.investigation.name.contains(query, ignoreCase = true) || it.investigation.category.contains(query, ignoreCase = true)) &&
            (selectedCategory == ALL_CATEGORIES || it.investigation.category == selectedCategory)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(state.laboratory?.name ?: "Select tests") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        },
        bottomBar = {
            Surface(shadowElevation = 8.dp) {
                Column(Modifier.padding(16.dp)) {
                    Text("${state.selectedCount} selected · ₹${"%.0f".format(state.totalAmount)}", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(8.dp))
                    BigPrimaryButton(
                        text = "Continue",
                        enabled = state.selectedCount > 0,
                        onClick = { state.laboratory?.let { onContinue(it.id) } }
                    )
                }
            }
        }
    ) { padding ->
        Column(Modifier.padding(padding).padding(horizontal = 16.dp)) {
            Spacer(Modifier.height(8.dp))
            VoiceEnabledTextField(value = query, onValueChange = { query = it }, label = "Search tests (e.g. CBC, Diabetes)")
            Spacer(Modifier.height(12.dp))
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                categories.forEach { category ->
                    PillFilterChip(text = category, selected = category == selectedCategory, onClick = { selectedCategory = category })
                }
            }
            Spacer(Modifier.height(12.dp))
            if (filtered.isEmpty()) {
                EmptyState("No tests match your search.")
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(filtered, key = { it.investigation.id }) { priced ->
                        InvestigationRow(
                            priced = priced,
                            selected = priced.investigation.id in state.selectedInvestigationIds,
                            onToggle = { bookingViewModel.toggleInvestigation(priced.investigation.id) }
                        )
                    }
                    item { Spacer(Modifier.height(80.dp)) }
                }
            }
        }
    }
}

@Composable
private fun InvestigationRow(priced: PricedInvestigation, selected: Boolean, onToggle: () -> Unit) {
    SectionCard(modifier = Modifier.testTag("investigation_row").clickable(onClick = onToggle)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            IconChip(icon = Icons.Filled.Science, containerColor = ChipRoseContainer, contentColor = MaterialTheme.colorScheme.primary, size = 48.dp)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(priced.investigation.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(
                    "Results in ${priced.investigation.reportTurnaroundHours} hrs · ₹${"%.0f".format(priced.price)}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Spacer(Modifier.width(8.dp))
            IconButton(onClick = onToggle) {
                Icon(
                    if (selected) Icons.Filled.CheckCircle else Icons.Filled.AddCircle,
                    contentDescription = if (selected) "Remove ${priced.investigation.name}" else "Add ${priced.investigation.name}",
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(34.dp)
                )
            }
        }
    }
}
