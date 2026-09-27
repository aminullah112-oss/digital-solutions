package com.digitalsolutions.diagnosticlab.notification

import android.util.Log
import com.digitalsolutions.diagnosticlab.DiagnosticLabApp
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Real FCM delivery — the notification-type message onBookingStatusChange sends (functions/
 * src/index.ts) is auto-displayed by the system when the app isn't in the foreground, so
 * [onMessageReceived] only needs to show it manually for the case Android/FCM never auto-shows:
 * the app being open and in the foreground when the push arrives.
 */
class FcmService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        Log.d("FcmService", "onNewToken")
        val container = (application as DiagnosticLabApp).container
        CoroutineScope(Dispatchers.IO).launch {
            val userId = container.sessionManager.session.filterNotNull().first().userId
            container.notificationRepository.updateFcmToken(userId, token)
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val notification = message.notification ?: return
        SystemNotifier(applicationContext).show(notification.title.orEmpty(), notification.body.orEmpty())
    }
}
