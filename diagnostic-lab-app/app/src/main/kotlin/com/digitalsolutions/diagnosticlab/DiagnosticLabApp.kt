package com.digitalsolutions.diagnosticlab

import android.app.Application
import com.digitalsolutions.diagnosticlab.di.AppContainer

class DiagnosticLabApp : Application() {

    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
