package com.digitalsolutions.diagnosticlab.presentation.patient.booking

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton

@Composable
fun BookingConfirmationScreen(bookingId: String, onDone: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Filled.CheckCircle, contentDescription = null,
            tint = MaterialTheme.colorScheme.secondary, modifier = Modifier.size(96.dp)
        )
        Spacer(Modifier.height(16.dp))
        Text("Booking confirmed!", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))
        Text("Booking ID: $bookingId", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        Text(
            "We'll assign a lab assistant and notify you before they arrive.",
            style = MaterialTheme.typography.bodyLarge,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center
        )
        Spacer(Modifier.height(32.dp))
        BigPrimaryButton(text = "Back to Home", onClick = onDone)
    }
}
