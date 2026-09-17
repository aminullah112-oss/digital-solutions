package com.digitalsolutions.diagnosticlab.presentation.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = TrustBlue,
    onPrimary = SurfaceLight,
    primaryContainer = TrustBlueDark,
    secondary = HealthGreen,
    error = AlertRed,
    background = BackgroundLight,
    surface = SurfaceLight,
    onBackground = TextPrimaryLight,
    onSurface = TextPrimaryLight,
    outline = OutlineLight
)

@Composable
fun DiagnosticLabTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColors,
        typography = ElderlyFriendlyTypography,
        content = content
    )
}

/** Minimum recommended touch target for elderly users — bigger than Material's 48dp default. */
const val MinTouchTargetDp = 56
