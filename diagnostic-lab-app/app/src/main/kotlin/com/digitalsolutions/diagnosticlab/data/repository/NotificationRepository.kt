package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.AppNotification
import com.digitalsolutions.diagnosticlab.domain.model.NotificationType
import com.digitalsolutions.diagnosticlab.notification.SystemNotifier
import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.tasks.await

/**
 * The in-app notification center (bell icon). Most entries here are created server-side by
 * the onBookingStatusChange Cloud Function reacting to a booking's status field — this class
 * is mostly read-only from the client's perspective. [notify] still exists for the handful of
 * cases that aren't themselves a booking-status transition (assignment acceptance, sample
 * rejection, complaints) and writes both a Firestore doc (for the bell icon / other devices)
 * and a local Android system notification via [SystemNotifier] for this device.
 */
class NotificationRepository(
    private val firestore: FirebaseFirestore,
    private val systemNotifier: SystemNotifier
) {

    private fun notificationsOf(userId: String) = firestore.collection("users").document(userId).collection("notifications")

    fun observeForUser(userId: String): Flow<List<AppNotification>> = callbackFlow {
        val registration = notificationsOf(userId).orderBy("createdAtMillis", com.google.firebase.firestore.Query.Direction.DESCENDING)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                trySend(snapshot?.documents.orEmpty().mapNotNull { it.toNotification() })
            }
        awaitClose { registration.remove() }
    }

    fun observeUnreadCount(userId: String): Flow<Int> = observeForUser(userId).map { list -> list.count { !it.read } }

    suspend fun markRead(userId: String, id: String) {
        notificationsOf(userId).document(id).update("read", true).await()
    }

    suspend fun notify(userId: String, type: NotificationType, title: String, body: String, relatedEntityId: String? = null) {
        notificationsOf(userId).add(
            mapOf(
                "type" to type.name,
                "title" to title,
                "body" to body,
                "read" to false,
                "relatedEntityId" to relatedEntityId,
                "createdAtMillis" to System.currentTimeMillis()
            )
        ).await()
        systemNotifier.show(title, body)
    }
}

private fun DocumentSnapshot.toNotification(): AppNotification? {
    if (!exists()) return null
    return AppNotification(
        id = id,
        type = runCatching { NotificationType.valueOf(getString("type") ?: "GENERAL") }.getOrDefault(NotificationType.GENERAL),
        title = getString("title").orEmpty(),
        body = getString("body").orEmpty(),
        read = getBoolean("read") ?: false,
        createdAtMillis = getLong("createdAtMillis") ?: 0L
    )
}
