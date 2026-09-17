package com.digitalsolutions.diagnosticlab.presentation.patient.settings

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.digitalsolutions.diagnosticlab.R
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.AppLanguage
import com.digitalsolutions.diagnosticlab.presentation.components.BigSecondaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(onSignedOut: () -> Unit, onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val currentLanguage by container.sessionManager.language.collectAsState(initial = AppLanguage.ENGLISH.tag)

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.settings_title)) },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        Column(Modifier.padding(padding).padding(16.dp)) {
            SectionCard(stringResource(R.string.language_label)) {
                AppLanguage.values().forEach { lang ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(
                            selected = currentLanguage == lang.tag,
                            onClick = {
                                scope.launch {
                                    container.sessionManager.setLanguage(lang.tag)
                                    (context as? ComponentActivity)?.recreate()
                                }
                            }
                        )
                        Text(if (lang == AppLanguage.ENGLISH) "English" else "தமிழ்", style = MaterialTheme.typography.bodyLarge)
                    }
                }
            }
            Spacer(Modifier.height(24.dp))
            BigSecondaryButton(text = stringResource(R.string.sign_out)) {
                scope.launch {
                    container.sessionManager.signOut()
                    onSignedOut()
                }
            }
        }
    }
}
