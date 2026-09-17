package com.digitalsolutions.diagnosticlab.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.digitalsolutions.diagnosticlab.data.local.entities.AuditLogEntity
import com.digitalsolutions.diagnosticlab.data.local.entities.ComplaintEntity
import com.digitalsolutions.diagnosticlab.data.local.entities.NotificationEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface NotificationDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(notification: NotificationEntity)

    @Update
    suspend fun update(notification: NotificationEntity)

    @Query("SELECT * FROM notifications WHERE userId = :userId ORDER BY createdAt DESC")
    fun observeForUser(userId: String): Flow<List<NotificationEntity>>

    @Query("SELECT COUNT(*) FROM notifications WHERE userId = :userId AND read = 0")
    fun observeUnreadCount(userId: String): Flow<Int>

    @Query("UPDATE notifications SET read = 1 WHERE id = :id")
    suspend fun markRead(id: String)
}

@Dao
interface ComplaintDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(complaint: ComplaintEntity)

    @Update
    suspend fun update(complaint: ComplaintEntity)

    @Query("SELECT * FROM complaints WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): ComplaintEntity?

    @Query("SELECT * FROM complaints WHERE patientId = :patientId ORDER BY createdAt DESC")
    fun observeForPatient(patientId: String): Flow<List<ComplaintEntity>>

    @Query("SELECT * FROM complaints ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<ComplaintEntity>>

    @Query("SELECT COUNT(*) FROM complaints WHERE status IN ('OPEN','ASSIGNED','IN_PROGRESS')")
    fun observeOpenCount(): Flow<Int>
}

@Dao
interface AuditLogDao {
    @Insert
    suspend fun insert(entry: AuditLogEntity)

    @Query("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT :limit")
    fun observeRecent(limit: Int = 200): Flow<List<AuditLogEntity>>

    @Query("SELECT * FROM audit_logs WHERE entityType = :entityType AND entityId = :entityId ORDER BY timestamp ASC")
    fun observeForEntity(entityType: String, entityId: String): Flow<List<AuditLogEntity>>
}
