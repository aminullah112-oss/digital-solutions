package com.digitalsolutions.diagnosticlab

import android.app.Application
import com.digitalsolutions.diagnosticlab.di.AppContainer
import kotlinx.coroutines.runBlocking

class DiagnosticLabApp : Application() {

    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        // Blocking is deliberate: this only ever touches an empty database on a brand-new
        // install (seedIfEmpty short-circuits instantly on every later launch), and doing it
        // here — before MainActivity/Compose ever runs — means the very first screen the user
        // sees always has real data behind it, instead of a race where login can run before
        // seeding finishes and silently create a blank account instead of recognizing a demo one.
        runBlocking {
            container.demoDataSeeder.seedIfEmpty()
        }
    }
}
