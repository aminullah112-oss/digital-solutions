package com.digitalsolutions.diagnosticlab.presentation.patient.family

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.Patient
import com.digitalsolutions.diagnosticlab.domain.model.Relation
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.EmptyState
import com.digitalsolutions.diagnosticlab.presentation.components.IconChip
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.theme.ChipRoseContainer

@Composable
fun rememberFamilyViewModel(): FamilyViewModel {
    val container = LocalAppContainer.current
    return viewModel(factory = viewModelFactory { initializer { FamilyViewModel(container.patientRepository, container.sessionManager) } })
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FamilyScreen(onBack: () -> Unit) {
    val viewModel = rememberFamilyViewModel()
    val family by viewModel.family.collectAsState()
    var showAddDialog by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("My Family") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(onClick = { showAddDialog = true }, text = { Text("Add family member") }, icon = {})
        }
    ) { padding ->
        if (family.isEmpty()) {
            EmptyState("No family members added yet.", Modifier.padding(padding))
        } else {
            LazyColumn(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(family) { person -> FamilyMemberRow(person) }
            }
        }
    }

    if (showAddDialog) {
        AddFamilyMemberDialog(
            onDismiss = { showAddDialog = false },
            onSave = { name, age, sex, relation, mobile ->
                viewModel.addFamilyMember(name, age, sex, relation, mobile)
                showAddDialog = false
            }
        )
    }
}

@Composable
private fun FamilyMemberRow(person: Patient) {
    SectionCard(modifier = Modifier.testTag("family_member_row")) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconChip(icon = Icons.Filled.Person, containerColor = ChipRoseContainer, contentColor = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.width(14.dp))
            Column {
                Text(person.fullName.ifBlank { "(name not set)" }, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(
                    "${person.relation.name.lowercase().replaceFirstChar(Char::uppercase)} · ${person.age?.let { "$it yrs" } ?: "age not set"} · ${person.sex}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun AddFamilyMemberDialog(
    onDismiss: () -> Unit,
    onSave: (String, Int, String, Relation, String) -> Unit
) {
    var name by remember { mutableStateOf("") }
    var age by remember { mutableStateOf("") }
    var sex by remember { mutableStateOf("Female") }
    var relation by remember { mutableStateOf(Relation.SPOUSE) }
    var mobile by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Add family member") },
        text = {
            Column {
                OutlinedTextField(name, { name = it }, label = { Text("Full name") }, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(age, { if (it.length <= 3) age = it.filter(Char::isDigit) }, label = { Text("Age") }, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(mobile, { if (it.length <= 10) mobile = it.filter(Char::isDigit) }, label = { Text("Mobile number") }, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                ExposedRelationDropdown(relation) { relation = it }
            }
        },
        confirmButton = {
            TextButton(
                enabled = name.isNotBlank() && age.toIntOrNull() != null,
                onClick = { onSave(name, age.toIntOrNull() ?: 0, sex, relation, "+91 $mobile") }
            ) { Text("Save") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ExposedRelationDropdown(selected: Relation, onSelected: (Relation) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            readOnly = true,
            value = selected.name.lowercase().replaceFirstChar(Char::uppercase),
            onValueChange = {},
            label = { Text("Relation") },
            modifier = Modifier.menuAnchor().fillMaxWidth()
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            Relation.values().filter { it != Relation.MYSELF }.forEach { option ->
                DropdownMenuItem(text = { Text(option.name.lowercase().replaceFirstChar(Char::uppercase)) }, onClick = { onSelected(option); expanded = false })
            }
        }
    }
}

/** Step 1 of the booking flow (spec's primary journey): pick who this booking is for. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookingPatientSelectScreen(onPatientSelected: (Patient) -> Unit, onBack: () -> Unit) {
    val viewModel = rememberFamilyViewModel()
    val family by viewModel.family.collectAsState()
    var showAddDialog by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Who is this test for?") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        LazyColumn(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            items(family) { person ->
                SectionCard(modifier = Modifier.testTag("patient_row").clickable { onPatientSelected(person) }) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        IconChip(icon = Icons.Filled.Person, containerColor = ChipRoseContainer, contentColor = MaterialTheme.colorScheme.primary)
                        Spacer(Modifier.width(14.dp))
                        Column {
                            Text(person.fullName.ifBlank { "Myself" }, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                            Text(person.relation.name.lowercase().replaceFirstChar(Char::uppercase), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
            item {
                Row(
                    Modifier.fillMaxWidth().clickable { showAddDialog = true }.padding(vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("+ Add someone else", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
                }
            }
        }
    }

    if (showAddDialog) {
        AddFamilyMemberDialog(
            onDismiss = { showAddDialog = false },
            onSave = { name, age, sex, relation, mobile ->
                viewModel.addFamilyMember(name, age, sex, relation, mobile)
                showAddDialog = false
            }
        )
    }
}
