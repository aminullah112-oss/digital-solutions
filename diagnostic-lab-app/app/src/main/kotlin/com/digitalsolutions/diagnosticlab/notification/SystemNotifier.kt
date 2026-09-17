package com.digitalsolutions.diagnosticlab.notification

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import com.digitalsolutions.diagnosticlab.R
import java.util.concurrent.atomic.AtomicInteger

/**
 * Thin wrapper over Android's NotificationManager. This is the "push notification" channel
 * called out in the spec (section 21) — there is no FCM/SMS/WhatsApp backend behind it yet,
 * everything fires locally from inside the app because there is no server to push from.
 * Swapping in FCM later means calling this same [show] from a push-received handler instead
 * of from the repository layer directly.
 */
class SystemNotifier(private val context: Context) {

    private val nextId = AtomicInteger(1000)

    init {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(CHANNEL_ID, "Booking updates", NotificationManager.IMPORTANCE_DEFAULT)
            channel.description = "Booking, collection, and report status updates"
            val manager = context.getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
        }
    }

    fun show(title: String, body: String) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ActivityCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED
            if (!granted) return
        }
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .build()
        androidx.core.app.NotificationManagerCompat.from(context).notify(nextId.incrementAndGet(), notification)
    }

    companion object {
        private const val CHANNEL_ID = "booking_updates"
    }
}
