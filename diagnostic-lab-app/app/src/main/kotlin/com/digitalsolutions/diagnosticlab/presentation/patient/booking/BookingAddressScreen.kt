package com.digitalsolutions.diagnosticlab.presentation.patient.booking

import android.Manifest
import android.content.pm.PackageManager
import android.location.LocationManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.data.repository.PatientRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.Address
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.LoadingState
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class AddressBookViewModel(
    private val patientRepository: PatientRepository,
    private val sessionManager: SessionManager
) : ViewModel() {
    // null means "haven't heard from the Room Flow yet" — distinct from a genuinely empty
    // list, so the screen can tell "still loading" apart from "no saved addresses" instead
    // of guessing from a placeholder empty list and picking the wrong initial screen.
    val addresses: StateFlow<List<Address>?> = sessionManager.session
        .filterNotNull()
        .flatMapLatest { patientRepository.observeAddresses(it.userId) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    fun saveAddress(
        label: String, line1: String, city: String, state: String, pincode: String,
        latitude: Double?, longitude: Double?, onSaved: (Address) -> Unit
    ) {
        viewModelScope.launch {
            val ownerUserId = sessionManager.session.first()?.userId ?: return@launch
            val saved = patientRepository.saveAddress(
                ownerUserId = ownerUserId, existingId = null, label = label, line1 = line1, line2 = null,
                city = city, state = state, pincode = pincode, latitude = latitude, longitude = longitude,
                makeDefault = addresses.value.isNullOrEmpty()
            )
            onSaved(saved)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookingAddressScreen(
    bookingViewModel: BookingViewModel,
    onContinue: () -> Unit,
    onBack: () -> Unit
) {
    val container = LocalAppContainer.current
    val viewModel: AddressBookViewModel = viewModel(
        factory = viewModelFactory { initializer { AddressBookViewModel(container.patientRepository, container.sessionManager) } }
    )
    val addresses by viewModel.addresses.collectAsState()
    // null (still loading) is handled separately from an override the user makes explicitly
    // by tapping "+ Add a new address" or cancelling out of the form — once addresses
    // resolves, the derived default (form only when there's truly nothing saved) takes over
    // unless the user has already made an explicit choice this screen visit.
    var userOverride by remember { mutableStateOf<Boolean?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Collection address") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        val resolvedAddresses = addresses
        if (resolvedAddresses == null) {
            LoadingState(Modifier.padding(padding))
        } else {
            val showAddForm = userOverride ?: resolvedAddresses.isEmpty()
            Column(Modifier.padding(padding).padding(16.dp)) {
                if (!showAddForm) {
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.weight(1f)) {
                        items(resolvedAddresses) { address ->
                            Card(
                                onClick = { bookingViewModel.setAddress(address); onContinue() },
                                modifier = Modifier.fillMaxWidth().testTag("address_row")
                            ) {
                                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Icon(Icons.Filled.LocationOn, contentDescription = null)
                                    Spacer(Modifier.width(12.dp))
                                    Column {
                                        Text(address.label, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                                        Text(address.displayLine, style = MaterialTheme.typography.bodyMedium)
                                    }
                                }
                            }
                        }
                    }
                    Spacer(Modifier.height(12.dp))
                    TextButton(onClick = { userOverride = true }) { Text("+ Add a new address") }
                } else {
                    AddAddressForm(
                        onSaved = { address -> bookingViewModel.setAddress(address); onContinue() },
                        viewModel = viewModel,
                        onCancel = { if (resolvedAddresses.isNotEmpty()) userOverride = false }
                    )
                }
            }
        }
    }
}

@Composable
private fun AddAddressForm(viewModel: AddressBookViewModel, onSaved: (Address) -> Unit, onCancel: () -> Unit) {
    val context = LocalContext.current
    var label by remember { mutableStateOf("Home") }
    var line1 by remember { mutableStateOf("") }
    var city by remember { mutableStateOf("") }
    var state by remember { mutableStateOf("") }
    var pincode by remember { mutableStateOf("") }
    var capturedLocation by remember { mutableStateOf<Pair<Double, Double>?>(null) }
    var locationMessage by remember { mutableStateOf<String?>(null) }

    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            capturedLocation = readLastKnownLocation(context)
            locationMessage = if (capturedLocation != null) "Location captured ✓" else "Couldn't get your location. You can still enter the address manually."
        } else {
            locationMessage = "Location permission denied. You can still enter the address manually."
        }
    }

    Column {
        Text("Where should we collect the sample?", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(label, { label = it }, label = { Text("Label (Home, Office...)") }, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(line1, { line1 = it }, label = { Text("House / Street") }, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(city, { city = it }, label = { Text("City") }, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(state, { state = it }, label = { Text("State") }, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(pincode, { if (it.length <= 6) pincode = it.filter(Char::isDigit) }, label = { Text("PIN code") }, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(12.dp))
        TextButton(onClick = {
            val granted = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
            if (granted) {
                capturedLocation = readLastKnownLocation(context)
                locationMessage = if (capturedLocation != null) "Location captured ✓" else "Couldn't get your location. You can still enter the address manually."
            } else {
                permissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
            }
        }) {
            Icon(Icons.Filled.LocationOn, contentDescription = null)
            Spacer(Modifier.width(6.dp))
            Text("Use my current location")
        }
        locationMessage?.let { Text(it, style = MaterialTheme.typography.labelMedium) }
        Spacer(Modifier.height(16.dp))
        BigPrimaryButton(
            text = "Save & continue",
            enabled = line1.isNotBlank() && city.isNotBlank() && pincode.length == 6,
            onClick = {
                viewModel.saveAddress(label, line1, city, state, pincode, capturedLocation?.first, capturedLocation?.second, onSaved)
            }
        )
        Spacer(Modifier.height(8.dp))
        TextButton(onClick = onCancel) { Text("Use a saved address instead") }
    }
}

private fun readLastKnownLocation(context: android.content.Context): Pair<Double, Double>? {
    return try {
        val hasPermission = ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (!hasPermission) return null
        val manager = context.getSystemService(android.content.Context.LOCATION_SERVICE) as LocationManager
        val providers = manager.getProviders(true)
        for (provider in providers) {
            val location = manager.getLastKnownLocation(provider)
            if (location != null) return location.latitude to location.longitude
        }
        null
    } catch (e: SecurityException) {
        null
    }
}
