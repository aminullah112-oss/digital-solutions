package com.digitalsolutions.diagnosticlab.presentation.auth

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.data.repository.PatientRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.time.LocalDate

class ProfileSetupViewModel(
    private val patientRepository: PatientRepository,
    private val sessionManager: SessionManager
) : ViewModel() {
    var saved by mutableStateOf(false)
        private set

    fun save(fullName: String, ageYears: Int, sex: String) {
        viewModelScope.launch {
            val patientId = sessionManager.activePatientId.first() ?: return@launch
            patientRepository.updateProfile(
                patientId = patientId,
                fullName = fullName,
                dateOfBirth = LocalDate.now().minusYears(ageYears.toLong()),
                sex = sex,
                email = null,
                emergencyContact = null
            )
            saved = true
        }
    }
}

@Composable
fun ProfileSetupScreen(onDone: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: ProfileSetupViewModel = viewModel(
        factory = viewModelFactory { initializer { ProfileSetupViewModel(container.patientRepository, container.sessionManager) } }
    )
    var name by remember { mutableStateOf("") }
    var age by remember { mutableStateOf("") }
    var sex by remember { mutableStateOf("Female") }

    LaunchedEffect(viewModel.saved) { if (viewModel.saved) onDone() }

    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
        Text("Tell us about you", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(name, { name = it }, label = { Text("Full name") }, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(
            age, { if (it.length <= 3) age = it.filter(Char::isDigit) },
            label = { Text("Age") }, modifier = Modifier.fillMaxWidth()
        )
        Spacer(Modifier.height(16.dp))
        Text("Sex", style = MaterialTheme.typography.titleMedium)
        Row {
            listOf("Female", "Male", "Other").forEach { option ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = sex == option, onClick = { sex = option })
                    Text(option, style = MaterialTheme.typography.bodyMedium)
                    Spacer(Modifier.width(12.dp))
                }
            }
        }
        Spacer(Modifier.height(24.dp))
        BigPrimaryButton(
            text = "Continue",
            enabled = name.isNotBlank() && age.toIntOrNull() != null,
            onClick = { viewModel.save(name, age.toInt(), sex) }
        )
    }
}
