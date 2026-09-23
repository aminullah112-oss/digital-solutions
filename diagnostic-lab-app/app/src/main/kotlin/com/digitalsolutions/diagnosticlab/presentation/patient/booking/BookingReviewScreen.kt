package com.digitalsolutions.diagnosticlab.presentation.patient.booking

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.digitalsolutions.diagnosticlab.domain.model.PaymentMethod
import com.digitalsolutions.diagnosticlab.presentation.components.AddressCard
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookingReviewScreen(
    bookingViewModel: BookingViewModel,
    onConfirmed: (bookingId: String) -> Unit,
    onBack: () -> Unit
) {
    val state by bookingViewModel.state.collectAsState()

    LaunchedEffect(state.createdBookingId) {
        state.createdBookingId?.let { onConfirmed(it) }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Review & pay") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        Column(Modifier.padding(padding).padding(16.dp).verticalScroll(rememberScrollState())) {
            SectionCard("Patient") {
                Text(state.patient?.fullName?.ifBlank { "Myself" } ?: "-", style = MaterialTheme.typography.bodyLarge)
            }
            Spacer(Modifier.height(12.dp))
            SectionCard("Laboratory") {
                Text(state.laboratory?.name ?: "-", style = MaterialTheme.typography.bodyLarge)
            }
            Spacer(Modifier.height(12.dp))
            SectionCard("Tests (${state.selectedCount})") {
                state.availableInvestigations.filter { it.investigation.id in state.selectedInvestigationIds }.forEach {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(it.investigation.name, style = MaterialTheme.typography.bodyMedium)
                        Text("₹${"%.0f".format(it.price)}", style = MaterialTheme.typography.bodyMedium)
                    }
                }
                Divider(Modifier.padding(vertical = 8.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Total", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                    Text("₹${"%.0f".format(state.totalAmount)}", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                }
            }
            Spacer(Modifier.height(12.dp))
            SectionCard("Schedule") {
                Text("${state.scheduledDate} · ${state.scheduledTimeSlot}", style = MaterialTheme.typography.bodyLarge)
            }
            Spacer(Modifier.height(12.dp))
            state.address?.let { address ->
                AddressCard(
                    title = "Collection address",
                    label = address.label,
                    addressLine = address.displayLine,
                    latitude = address.latitude,
                    longitude = address.longitude
                )
                Spacer(Modifier.height(12.dp))
            }
            SectionCard("Payment method") {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier
                        .fillMaxWidth()
                        .selectable(
                            selected = state.paymentMethod == PaymentMethod.ONLINE,
                            onClick = { bookingViewModel.setPaymentMethod(PaymentMethod.ONLINE) }
                        )
                        .padding(vertical = 8.dp)
                ) {
                    RadioButton(selected = state.paymentMethod == PaymentMethod.ONLINE, onClick = null)
                    Text("Pay online now", style = MaterialTheme.typography.bodyLarge)
                }
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier
                        .fillMaxWidth()
                        .selectable(
                            selected = state.paymentMethod == PaymentMethod.CASH,
                            onClick = { bookingViewModel.setPaymentMethod(PaymentMethod.CASH) }
                        )
                        .padding(vertical = 8.dp)
                ) {
                    RadioButton(selected = state.paymentMethod == PaymentMethod.CASH, onClick = null)
                    Text("Cash at collection", style = MaterialTheme.typography.bodyLarge)
                }
            }
            if (state.error != null) {
                Spacer(Modifier.height(12.dp))
                Text(state.error.orEmpty(), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            }
            Spacer(Modifier.height(20.dp))
            BigPrimaryButton(
                text = if (state.paymentMethod == PaymentMethod.ONLINE) "Pay ₹${"%.0f".format(state.totalAmount)} & Confirm" else "Confirm Booking",
                enabled = !state.submitting,
                onClick = { bookingViewModel.submitAndPay() }
            )
            Spacer(Modifier.height(24.dp))
        }
    }
}
