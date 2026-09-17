package com.digitalsolutions.diagnosticlab.di

import androidx.compose.runtime.staticCompositionLocalOf

val LocalAppContainer = staticCompositionLocalOf<AppContainer> {
    error("AppContainer not provided — wrap the app in CompositionLocalProvider(LocalAppContainer provides ...)")
}
