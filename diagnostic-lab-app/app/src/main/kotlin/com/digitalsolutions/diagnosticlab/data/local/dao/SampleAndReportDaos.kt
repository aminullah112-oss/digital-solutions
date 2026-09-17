package com.digitalsolutions.diagnosticlab.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.digitalsolutions.diagnosticlab.data.local.entities.*
import kotlinx.coroutines.flow.Flow

@Dao
interface SampleDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(sample: SampleEntity)

    @Update
    suspend fun update(sample: SampleEntity)

    @Query("SELECT * FROM samples WHERE bookingId = :bookingId LIMIT 1")
    suspend fun findByBooking(bookingId: String): SampleEntity?

    @Query("SELECT * FROM samples WHERE bookingId = :bookingId")
    fun observeByBooking(bookingId: String): Flow<SampleEntity?>

    @Query("SELECT * FROM samples WHERE status IN ('IN_TRANSIT','HANDED_OVER') ORDER BY collectionTime DESC")
    fun observeInTransit(): Flow<List<SampleEntity>>
}

@Dao
interface SampleTrackingEventDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(event: SampleTrackingEventEntity)

    @Query("SELECT * FROM sample_tracking_events WHERE bookingId = :bookingId ORDER BY timestamp ASC")
    fun observeForBooking(bookingId: String): Flow<List<SampleTrackingEventEntity>>
}

@Dao
interface ReportDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(report: ReportEntity)

    @Update
    suspend fun update(report: ReportEntity)

    @Query("SELECT * FROM reports WHERE bookingId = :bookingId LIMIT 1")
    suspend fun findByBooking(bookingId: String): ReportEntity?

    @Query("SELECT * FROM reports WHERE bookingId = :bookingId")
    fun observeByBooking(bookingId: String): Flow<ReportEntity?>

    @Query("SELECT * FROM reports WHERE patientId = :patientId ORDER BY generatedAt DESC")
    fun observeForPatient(patientId: String): Flow<List<ReportEntity>>

    @Query("SELECT * FROM reports WHERE laboratoryId = :laboratoryId AND status = 'PENDING'")
    fun observePendingForLab(laboratoryId: String): Flow<List<ReportEntity>>

    @Query("SELECT COUNT(*) FROM reports WHERE status IN ('READY','VERIFIED','DELIVERED')")
    fun observeCompletedCount(): Flow<Int>

    @Query("SELECT COUNT(*) FROM reports WHERE status = 'PENDING'")
    fun observePendingCount(): Flow<Int>
}

@Dao
interface MedicalRecordDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(record: MedicalRecordEntity)

    @Query("SELECT * FROM medical_records WHERE patientId = :patientId ORDER BY recordDateEpochDay DESC")
    fun observeForPatient(patientId: String): Flow<List<MedicalRecordEntity>>
}

@Dao
interface FeverRecordDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(record: FeverRecordEntity)

    @Query("SELECT * FROM fever_records WHERE patientId = :patientId ORDER BY recordDateEpochDay DESC")
    fun observeForPatient(patientId: String): Flow<List<FeverRecordEntity>>
}
