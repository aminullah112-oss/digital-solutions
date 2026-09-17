package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.data.local.dao.NotificationDao
import com.digitalsolutions.diagnosticlab.data.local.entities.NotificationEntity
import com.digitalsolutions.diagnosticlab.domain.model.AppNotification
import com.digitalsolutions.diagnosticlab.domain.model.NotificationType
import com.digitalsolutions.diagnosticlab.notification.SystemNotifier
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/**
 * The in-app notification center (bell icon). Every entry here is also mirrored to a real
 * Android system notification via [SystemNotifier] — see README for how this maps onto
 * FCM/SMS/WhatsApp once a backend exists.
 */
class NotificationRepository(
    private val notificationDao: NotificationDao,
    private val systemNotifier: SystemNotifier
) {

    fun observeForUser(userId: String): Flow<List<AppNotification>> =
        notificationDao.observeForUser(userId).map { list -> list.map { it.toDomain() } }

    fun observeUnreadCount(userId: String): Flow<Int> = notificationDao.observeUnreadCount(userId)

    suspend fun markRead(id: String) = notificationDao.markRead(id)

    suspend fun notify(userId: String, type: NotificationType, title: String, body: String, relatedEntityId: String? = null) {
        val entity = NotificationEntity(
            id = "NOTIF-${System.currentTimeMillis()}-$userId",
            userId = userId,
            type = type,
            title = title,
            body = body,
            relatedEntityId = relatedEntityId,
            createdAt = System.currentTimeMillis()
        )
        notificationDao.insert(entity)
        systemNotifier.show(title, body)
    }
}

private fun NotificationEntity.toDomain() = AppNotification(
    id = id, type = type, title = title, body = body, read = read, createdAtMillis = createdAt
)
