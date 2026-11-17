package com.digitalsolutions.diagnosticlab.presentation.patient.booking

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.digitalsolutions.diagnosticlab.domain.model.PaymentConfig
import com.digitalsolutions.diagnosticlab.domain.model.PaymentMethod
import com.digitalsolutions.diagnosticlab.presentation.components.AddressCard
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookingReviewScreen(
    bookingViewModel: BookingViewModel,
    onConfirmed: (bookingId: String) -> Unit,
    onBack: () -> Unit
) {
    val state by bookingViewModel.state.collectAsState()
    val upiConfig by bookingViewModel.upiConfig.collectAsState()
    val activity = LocalContext.current as Activity

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
                state.selectedPackage?.let { pkg ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Column(Modifier.weight(1f)) {
                            Text(pkg.name, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                            if (pkg.description.isNotBlank()) {
                                Text(pkg.description, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        Text("₹${"%.0f".format(pkg.price)}", style = MaterialTheme.typography.bodyMedium)
                    }
                    Spacer(Modifier.height(6.dp))
                }
                state.availableInvestigations.filter { it.investigation.id in state.adHocInvestigationIds }.forEach {
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
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    // Only offered once the business's real UPI details exist in Firestore
                    // (config/payment) — never a hardcoded or placeholder ID.
                    upiConfig?.let { upi ->
                        PaymentOptionRow(
                            label = "Pay via UPI / GPay",
                            selected = state.paymentMethod == PaymentMethod.UPI_DIRECT,
                            onClick = { bookingViewModel.setPaymentMethod(PaymentMethod.UPI_DIRECT) }
                        )
                        if (state.paymentMethod == PaymentMethod.UPI_DIRECT) {
                            UpiPaymentDetails(upi, state.totalAmount, activity)
                        }
                    }
                    PaymentOptionRow(
                        label = "Cash at collection",
                        selected = state.paymentMethod == PaymentMethod.CASH,
                        onClick = { bookingViewModel.setPaymentMethod(PaymentMethod.CASH) }
                    )
                }
            }
            if (state.error != null) {
                Spacer(Modifier.height(12.dp))
                Text(state.error.orEmpty(), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            }
            Spacer(Modifier.height(20.dp))
            BigPrimaryButton(
                text = if (state.paymentMethod == PaymentMethod.CASH) "Confirm Booking" else "I've Paid — Confirm Booking",
                enabled = !state.submitting,
                onClick = { bookingViewModel.submitAndPay(activity) }
            )
            Spacer(Modifier.height(24.dp))
        }
    }
}

/** Shows who to pay and opens the patient's UPI app with the amount pre-filled. The UPI ID stays
 * visible and selectable regardless, because some UPI apps decline pre-filled intents to certain
 * accounts — paying by hand to the ID is always a working fallback. */
@Composable
private fun UpiPaymentDetails(config: PaymentConfig, amount: Double, activity: Activity) {
    var notice by remember { mutableStateOf<String?>(null) }
    Column(Modifier.padding(horizontal = 4.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(
            "Pay ₹${"%.0f".format(amount)} to ${config.payeeName}",
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold
        )
        SelectionContainer { Text(config.upiId, style = MaterialTheme.typography.bodyLarge) }
        OutlinedButton(onClick = {
            val uri = Uri.Builder().scheme("upi").authority("pay")
                .appendQueryParameter("pa", config.upiId)
                .appendQueryParameter("pn", config.payeeName)
                .appendQueryParameter("am", String.format(Locale.US, "%.2f", amount))
                .appendQueryParameter("cu", "INR")
                .appendQueryParameter("tn", "Medwyn Labs booking")
                .build()
            try {
                activity.startActivity(Intent(Intent.ACTION_VIEW, uri))
                notice = null
            } catch (e: ActivityNotFoundException) {
                notice = "No UPI app found. Pay to the UPI ID above from any UPI app."
            }
        }) { Text("Open UPI app to pay") }
        notice?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        Text(
            "After paying, tap the button below. Keep your payment confirmation handy — our team may ask to see it at sample collection.",
            style = MaterialTheme.typography.bodySmall
        )
    }
}

@Composable
private fun PaymentOptionRow(label: String, selected: Boolean, onClick: () -> Unit) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .background(
                if (selected) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.35f) else MaterialTheme.colorScheme.surface,
                RoundedCornerShape(14.dp)
            )
            .border(
                BorderStroke(if (selected) 2.dp else 1.dp, if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline.copy(alpha = 0.4f)),
                RoundedCornerShape(14.dp)
            )
            .selectable(selected = selected, onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 10.dp)
    ) {
        RadioButton(selected = selected, onClick = null)
        Spacer(Modifier.width(4.dp))
        Text(label, style = MaterialTheme.typography.bodyLarge)
    }
}
