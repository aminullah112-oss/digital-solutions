package com.digitalsolutions.diagnosticlab.presentation.patient.investigations

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
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
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Science
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.digitalsolutions.diagnosticlab.domain.model.PricedInvestigation
import com.digitalsolutions.diagnosticlab.domain.model.TestPackage
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
            if (state.availablePackages.isNotEmpty()) {
                Text("Fever panels", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    state.availablePackages.forEach { pkg ->
                        PackageRow(
                            testPackage = pkg,
                            selected = pkg.id == state.selectedPackageId,
                            onToggle = { bookingViewModel.selectPackage(pkg) }
                        )
                    }
                }
                Spacer(Modifier.height(16.dp))
                Text("Or pick individual tests", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
            }
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
                val packageTestIds = state.selectedPackage?.investigationIds?.toSet().orEmpty()
                LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(filtered, key = { it.investigation.id }) { priced ->
                        val includedInPackage = priced.investigation.id in packageTestIds
                        InvestigationRow(
                            priced = priced,
                            selected = priced.investigation.id in state.selectedInvestigationIds,
                            includedInPackage = includedInPackage,
                            // Can't individually untoggle a test the active package already
                            // covers — deselecting that whole panel is the only way to drop it.
                            onToggle = { if (!includedInPackage) bookingViewModel.toggleInvestigation(priced.investigation.id) }
                        )
                    }
                    item { Spacer(Modifier.height(80.dp)) }
                }
            }
        }
    }
}

@Composable
private fun InvestigationRow(
    priced: PricedInvestigation,
    selected: Boolean,
    includedInPackage: Boolean,
    onToggle: () -> Unit
) {
    SectionCard(
        modifier = Modifier.testTag("investigation_row").clickable(enabled = !includedInPackage, onClick = onToggle)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            IconChip(icon = Icons.Filled.Science, containerColor = ChipRoseContainer, contentColor = MaterialTheme.colorScheme.primary, size = 48.dp)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(priced.investigation.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(
                    if (includedInPackage) "Included in selected panel" else "Results in ${priced.investigation.reportTurnaroundHours} hrs · ₹${"%.0f".format(priced.price)}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Spacer(Modifier.width(8.dp))
            if (includedInPackage) {
                Icon(Icons.Filled.Lock, contentDescription = "Included in selected panel", tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(24.dp))
            } else {
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
}

@Composable
private fun PackageRow(testPackage: TestPackage, selected: Boolean, onToggle: () -> Unit) {
    SectionCard(
        modifier = Modifier
            .testTag("package_row")
            .clickable(onClick = onToggle)
            .let { if (selected) it.border(BorderStroke(2.dp, MaterialTheme.colorScheme.primary), MaterialTheme.shapes.medium) else it }
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.weight(1f)) {
                Text(testPackage.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                if (testPackage.description.isNotBlank()) {
                    Text(testPackage.description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.height(4.dp))
                Text("₹${"%.0f".format(testPackage.price)}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            }
            Spacer(Modifier.width(8.dp))
            Icon(
                if (selected) Icons.Filled.CheckCircle else Icons.Filled.AddCircle,
                contentDescription = if (selected) "Remove ${testPackage.name}" else "Add ${testPackage.name}",
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(34.dp)
            )
        }
    }
}
