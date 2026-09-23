package com.digitalsolutions.diagnosticlab.presentation.patient.booking

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.format.TextStyle
import java.util.Locale

private val timeSlots = listOf("07:00-08:00", "08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00", "16:00-17:00", "17:00-18:00")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookingDateTimeScreen(
    bookingViewModel: BookingViewModel,
    onContinue: () -> Unit,
    onBack: () -> Unit
) {
    val state by bookingViewModel.state.collectAsState()
    var selectedDate by remember { mutableStateOf(state.scheduledDate ?: LocalDate.now().plusDays(1)) }
    var selectedSlot by remember { mutableStateOf(state.scheduledTimeSlot) }
    val nextDays = remember { (0..6).map { LocalDate.now().plusDays(it.toLong()) } }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pick a date & time") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        Column(Modifier.padding(padding).padding(16.dp)) {
            Text("Select date", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(12.dp))
            LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                itemsIndexed(nextDays) { index, date ->
                    val label = date.dayOfWeek.getDisplayName(TextStyle.SHORT, Locale.getDefault())
                    FilterChip(
                        selected = date == selectedDate,
                        onClick = { selectedDate = date },
                        label = { Text("$label ${date.format(DateTimeFormatter.ofPattern("d MMM"))}") },
                        modifier = Modifier.testTag("date_chip_$index")
                    )
                }
            }
            Spacer(Modifier.height(24.dp))
            Text("Select time slot", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(12.dp))
            FlowRowSimple {
                timeSlots.forEachIndexed { index, slot ->
                    FilterChip(
                        selected = slot == selectedSlot,
                        onClick = { selectedSlot = slot },
                        label = { Text(slot) },
                        modifier = Modifier.testTag("time_chip_$index")
                    )
                }
            }
            Spacer(Modifier.weight(1f))
            BigPrimaryButton(
                text = "Continue",
                enabled = selectedSlot != null,
                onClick = {
                    bookingViewModel.setSchedule(selectedDate, selectedSlot!!)
                    onContinue()
                }
            )
        }
    }
}

/** Tiny wrap-layout so time slot chips flow onto multiple lines without pulling in the full accompanist FlowRow dependency. */
@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun FlowRowSimple(content: @Composable () -> Unit) {
    androidx.compose.foundation.layout.FlowRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) { content() }
}
