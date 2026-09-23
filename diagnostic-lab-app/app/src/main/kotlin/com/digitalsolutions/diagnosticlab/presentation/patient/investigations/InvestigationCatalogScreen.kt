package com.digitalsolutions.diagnosticlab.presentation.patient.investigations

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
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
import com.digitalsolutions.diagnosticlab.presentation.components.VoiceEnabledTextField
import com.digitalsolutions.diagnosticlab.presentation.patient.booking.BookingViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InvestigationCatalogScreen(
    bookingViewModel: BookingViewModel,
    onContinue: (labId: String) -> Unit,
    onBack: () -> Unit
) {
    val state by bookingViewModel.state.collectAsState()
    var query by remember { mutableStateOf("") }
    val filtered = state.availableInvestigations.filter {
        query.isBlank() || it.investigation.name.contains(query, ignoreCase = true) || it.investigation.category.contains(query, ignoreCase = true)
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
            Spacer(Modifier.height(8.dp))
            if (filtered.isEmpty()) {
                EmptyState("No tests match your search.")
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
    Card(onClick = onToggle, modifier = Modifier.fillMaxWidth().testTag("investigation_row")) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = selected, onCheckedChange = { onToggle() })
            Spacer(Modifier.width(8.dp))
            Column(Modifier.weight(1f)) {
                Text(priced.investigation.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(priced.investigation.preparationInstructions, style = MaterialTheme.typography.labelMedium)
            }
            Text("₹${"%.0f".format(priced.price)}", style = MaterialTheme.typography.titleMedium)
        }
    }
}
