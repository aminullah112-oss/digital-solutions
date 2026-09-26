package com.digitalsolutions.diagnosticlab.presentation.components

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.digitalsolutions.diagnosticlab.presentation.theme.MinTouchTargetDp
import java.util.Locale

/** Full-width, large-type primary action button — the default button everywhere patients tap. */
@Composable
fun BigPrimaryButton(
    text: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    onClick: () -> Unit
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.fillMaxWidth().height(MinTouchTargetDp.dp + 8.dp),
        shape = MaterialTheme.shapes.medium
    ) {
        Text(text, style = MaterialTheme.typography.titleMedium)
    }
}

@Composable
fun BigSecondaryButton(
    text: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    onClick: () -> Unit
) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.fillMaxWidth().height(MinTouchTargetDp.dp),
        shape = MaterialTheme.shapes.medium
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
fun SectionCard(title: String? = null, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(Modifier.padding(20.dp)) {
            if (title != null) {
                Text(title, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(12.dp))
            }
            content()
        }
    }
}

@Composable
fun LoadingState(modifier: Modifier = Modifier) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator()
    }
}

@Composable
fun EmptyState(message: String, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
        Text(message, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun ErrorState(message: String, modifier: Modifier = Modifier, onRetry: (() -> Unit)? = null) {
    Column(
        modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(message, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.error)
        if (onRetry != null) {
            Spacer(Modifier.height(16.dp))
            BigSecondaryButton("Try again", onClick = onRetry)
        }
    }
}

/**
 * A visual, step-by-step booking/sample timeline (spec section 29). [completedSteps] are shown
 * with a check, [currentStep] gets the highlighted dot, everything after is greyed out.
 */
@Composable
fun StatusTimeline(steps: List<String>, currentIndex: Int, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth()) {
        steps.forEachIndexed { index, label ->
            val done = index < currentIndex
            val current = index == currentIndex
            val isLast = index == steps.lastIndex
            Row(verticalAlignment = Alignment.Top) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Box(contentAlignment = Alignment.Center) {
                        if (current) {
                            Box(
                                Modifier.size(32.dp)
                                    .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.15f), androidx.compose.foundation.shape.CircleShape)
                            )
                        }
                        Box(
                            Modifier.size(if (current) 20.dp else 24.dp)
                                .background(
                                    when {
                                        done -> MaterialTheme.colorScheme.primary
                                        current -> MaterialTheme.colorScheme.primary
                                        else -> MaterialTheme.colorScheme.surfaceVariant
                                    },
                                    androidx.compose.foundation.shape.CircleShape
                                ),
                            contentAlignment = Alignment.Center
                        ) {
                            if (done) {
                                Icon(
                                    Icons.Filled.Check, contentDescription = null,
                                    tint = MaterialTheme.colorScheme.onPrimary, modifier = Modifier.size(14.dp)
                                )
                            } else if (current) {
                                Box(Modifier.size(8.dp).background(MaterialTheme.colorScheme.onPrimary, androidx.compose.foundation.shape.CircleShape))
                            }
                        }
                    }
                    if (!isLast) {
                        Box(
                            Modifier.width(2.dp).height(34.dp)
                                .background(if (done) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant)
                        )
                    }
                }
                Spacer(Modifier.width(14.dp))
                Column(Modifier.padding(bottom = if (isLast) 0.dp else 18.dp)) {
                    Text(
                        label,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = if (current) FontWeight.Bold else FontWeight.SemiBold,
                        color = if (done || current) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

/**
 * A text field with an optional voice-input mic button using Android's built-in speech
 * recognizer — no cloud API key required. Always usable without voice too (spec section 30:
 * "Do not make voice mandatory").
 */
@Composable
fun VoiceEnabledTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    singleLine: Boolean = true
) {
    val context = LocalContext.current
    var voiceError by remember { mutableStateOf<String?>(null) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val text = result.data
            ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            ?.firstOrNull()
        if (text != null) onValueChange(if (singleLine) text else (value + " " + text).trim())
    }
    Column(modifier) {
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            label = { Text(label) },
            singleLine = singleLine,
            modifier = Modifier.fillMaxWidth(),
            trailingIcon = {
                IconButton(onClick = {
                    val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                        putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                        putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak now")
                    }
                    try {
                        launcher.launch(intent)
                        voiceError = null
                    } catch (e: ActivityNotFoundException) {
                        voiceError = "Voice input isn't available on this device."
                    }
                }) {
                    Icon(Icons.Filled.Mic, contentDescription = "Speak instead of typing")
                }
            }
        )
        if (voiceError != null) {
            Text(voiceError.orEmpty(), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelMedium)
        }
    }
}

@Composable
fun StatusChip(text: String, color: Color, modifier: Modifier = Modifier) {
    Box(
        modifier
            .background(color.copy(alpha = 0.15f), RoundedCornerShape(20.dp))
            .padding(horizontal = 14.dp, vertical = 6.dp)
    ) {
        Text(text, color = color, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
    }
}

/**
 * Shows the sample-collection address as a real visual element — a pin icon, the label and
 * full address, and a "View on map" action — wherever a booking's address matters (review,
 * confirmation, tracking, the home-screen active-booking banner). Requested directly by a
 * customer: the address needs to be visible, not just implied, at every step of booking.
 *
 * There's no embedded map (no Maps API key provisioned for this project), so "View on map"
 * hands off to whatever maps app is installed on the device via a plain geo: intent —
 * zero extra dependencies, works everywhere, degrades silently if no maps app exists.
 */
@Composable
fun AddressCard(
    label: String,
    addressLine: String,
    modifier: Modifier = Modifier,
    latitude: Double? = null,
    longitude: Double? = null,
    title: String? = null
) {
    val context = LocalContext.current
    SectionCard(title = title, modifier = modifier) {
        Row(verticalAlignment = Alignment.Top) {
            Icon(
                Icons.Filled.LocationOn,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(28.dp)
            )
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                if (label.isNotBlank()) {
                    Text(label, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(2.dp))
                }
                Text(addressLine, style = MaterialTheme.typography.bodyMedium)
            }
        }
        Spacer(Modifier.height(12.dp))
        OutlinedButton(
            onClick = {
                val geoUri = if (latitude != null && longitude != null) {
                    "geo:$latitude,$longitude?q=$latitude,$longitude(${Uri.encode(label.ifBlank { "Collection address" })})"
                } else {
                    "geo:0,0?q=${Uri.encode(addressLine)}"
                }
                try {
                    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(geoUri)))
                } catch (e: ActivityNotFoundException) {
                    // No maps app installed — nothing sensible to fall back to, so this is a silent no-op.
                }
            },
            modifier = Modifier.fillMaxWidth().height(MinTouchTargetDp.dp),
            shape = MaterialTheme.shapes.medium
        ) {
            Icon(Icons.Filled.Map, contentDescription = null, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(8.dp))
            Text("View on map", style = MaterialTheme.typography.labelLarge)
        }
    }
}

/** A small rounded-square colored icon container — the "icon chip" used for quick actions,
 * catalog rows, and list leading icons throughout the app. */
@Composable
fun IconChip(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    containerColor: Color,
    contentColor: Color,
    modifier: Modifier = Modifier,
    size: androidx.compose.ui.unit.Dp = 44.dp,
    iconSize: androidx.compose.ui.unit.Dp = 20.dp
) {
    Box(
        modifier
            .size(size)
            .background(containerColor, RoundedCornerShape(size / 3)),
        contentAlignment = Alignment.Center
    ) {
        Icon(icon, contentDescription = null, tint = contentColor, modifier = Modifier.size(iconSize))
    }
}

/** A white, elevated, rounded-square icon button — used for the home-screen notification
 * bell and similar "floating" icon actions instead of a plain flat IconButton. */
@Composable
fun RoundedIconButton(onClick: () -> Unit, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Box(
        modifier
            .size(MinTouchTargetDp.dp - 12.dp)
            .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(14.dp))
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center
    ) {
        content()
    }
}

/** A circular avatar showing initials on a solid brand-colored background, for profile /
 * chat-style headers where there's no real photo to show. */
@Composable
fun InitialsAvatar(initials: String, modifier: Modifier = Modifier, size: androidx.compose.ui.unit.Dp = 44.dp) {
    Box(
        modifier
            .size(size)
            .background(MaterialTheme.colorScheme.primary, androidx.compose.foundation.shape.CircleShape),
        contentAlignment = Alignment.Center
    ) {
        Text(
            initials.take(2).uppercase(),
            color = MaterialTheme.colorScheme.onPrimary,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold
        )
    }
}

/** A pill-shaped filter chip (category filters, etc.) — Material3's own FilterChip works fine
 * functionally but reads visually "componenty"; this matches the softer pill look used
 * everywhere else in this redesign. */
@Composable
fun PillFilterChip(text: String, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val containerColor = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface
    val contentColor = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface
    Box(
        modifier
            .height(38.dp)
            .background(containerColor, RoundedCornerShape(100))
            .clickable(onClick = onClick)
            .padding(horizontal = 18.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(text, color = contentColor, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
    }
}
