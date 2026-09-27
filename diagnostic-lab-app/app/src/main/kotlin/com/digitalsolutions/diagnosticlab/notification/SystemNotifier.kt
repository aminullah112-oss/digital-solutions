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
 * Thin wrapper over Android's NotificationManager. Two callers: [NotificationRepository.notify]
 * fires this directly for the couple of cases that write a notification without going through
 * a real push (see its own kdoc), and [FcmService] calls it for an incoming push that arrived
 * while the app was already in the foreground — Android only auto-displays a push's
 * notification payload when the app is backgrounded or not running.
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
