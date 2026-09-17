package com.digitalsolutions.diagnosticlab

import android.Manifest
import android.content.Context
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.CompositionLocalProvider
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.locale.LocaleHelper
import com.digitalsolutions.diagnosticlab.presentation.navigation.DiagnosticLabNavGraph
import com.digitalsolutions.diagnosticlab.presentation.theme.DiagnosticLabTheme

class MainActivity : ComponentActivity() {

    private val notificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { /* no-op: app works without it */ }

    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(LocaleHelper.wrap(newBase))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }

        val container = (application as DiagnosticLabApp).container

        setContent {
            CompositionLocalProvider(LocalAppContainer provides container) {
                DiagnosticLabTheme {
                    DiagnosticLabNavGraph()
                }
            }
        }
    }
}
