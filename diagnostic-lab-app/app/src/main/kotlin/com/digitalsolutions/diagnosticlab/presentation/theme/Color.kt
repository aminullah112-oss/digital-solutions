package com.digitalsolutions.diagnosticlab.presentation.theme

import androidx.compose.ui.graphics.Color

// Brand palette sampled directly from the client's logo (cream circle, deep red cross,
// white mark) — see presentation/theme/Theme.kt for how these compose into the scheme.
val BrandRed = Color(0xFF9B0909)
val BrandRedDark = Color(0xFF6B0606)
val BrandCream = Color(0xFFF5F6E8)
val BrandCreamDeep = Color(0xFFEAE6CF)

// Status/semantic accents, kept distinct from BrandRed so an error or a cancellation
// doesn't read as "the brand color" — see statusColor()/StatusChip usage.
val InfoBlue = Color(0xFF0B5FA5)
val HealthGreen = Color(0xFF1E8A5F)
val AlertRed = Color(0xFFC62828)
val WarningAmber = Color(0xFFB5670A)

val SurfaceLight = Color(0xFFFFFFFF)
val BackgroundLight = BrandCream
val TextPrimaryLight = Color(0xFF16202A)
val TextSecondaryLight = Color(0xFF44515C)
val OutlineLight = Color(0xFFD8D2C0)
