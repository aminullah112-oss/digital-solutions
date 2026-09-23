package com.digitalsolutions.diagnosticlab.presentation.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Light tints paired with the brand/status colors so containers (selected chips, the bottom
// nav indicator, error banners) read as "this app's palette" instead of Material's default
// purple — same colors as Color.kt, just softened for use as a background behind text/icons.
private val PrimaryContainerLight = Color(0xFFF4DAD8)
private val OnPrimaryContainerLight = BrandRedDark
private val SecondaryContainerLight = Color(0xFFD7EEE1)
private val OnSecondaryContainerLight = Color(0xFF0F4A31)
private val ErrorContainerLight = Color(0xFFF9DEDC)
private val OnErrorContainerLight = Color(0xFF410E0B)
private val SurfaceVariantLight = BrandCreamDeep
private val OnSurfaceVariantLight = TextSecondaryLight

private val LightColors = lightColorScheme(
    primary = BrandRed,
    onPrimary = SurfaceLight,
    primaryContainer = PrimaryContainerLight,
    onPrimaryContainer = OnPrimaryContainerLight,
    secondary = HealthGreen,
    onSecondary = SurfaceLight,
    secondaryContainer = SecondaryContainerLight,
    onSecondaryContainer = OnSecondaryContainerLight,
    error = AlertRed,
    onError = SurfaceLight,
    errorContainer = ErrorContainerLight,
    onErrorContainer = OnErrorContainerLight,
    background = BackgroundLight,
    onBackground = TextPrimaryLight,
    surface = SurfaceLight,
    onSurface = TextPrimaryLight,
    surfaceVariant = SurfaceVariantLight,
    onSurfaceVariant = OnSurfaceVariantLight,
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
