package com.digitalsolutions.diagnosticlab.presentation.patient.booking

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.presentation.components.AddressCard
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.patient.bookings.BookingDetailViewModel

@Composable
fun BookingConfirmationScreen(bookingId: String, onDone: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: BookingDetailViewModel = viewModel(
        key = bookingId,
        factory = viewModelFactory { initializer { BookingDetailViewModel(container.bookingRepository, container.sessionManager, bookingId) } }
    )
    val booking = viewModel.detail.collectAsState().value?.booking

    Column(
        Modifier.fillMaxSize().padding(24.dp).verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(Modifier.height(24.dp))
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
            textAlign = TextAlign.Center
        )
        booking?.let {
            Spacer(Modifier.height(24.dp))
            AddressCard(
                title = "Sample will be collected at",
                label = it.addressLabel,
                addressLine = it.addressLine,
                latitude = it.addressLatitude,
                longitude = it.addressLongitude,
                modifier = Modifier.fillMaxWidth()
            )
        }
        Spacer(Modifier.height(32.dp))
        BigPrimaryButton(text = "Back to Home", onClick = onDone)
        Spacer(Modifier.height(16.dp))
    }
}
