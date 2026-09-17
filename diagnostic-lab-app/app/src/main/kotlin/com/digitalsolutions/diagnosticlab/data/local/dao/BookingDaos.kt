package com.digitalsolutions.diagnosticlab.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.digitalsolutions.diagnosticlab.data.local.entities.*
import kotlinx.coroutines.flow.Flow

@Dao
interface BookingDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(booking: BookingEntity)

    @Update
    suspend fun update(booking: BookingEntity)

    @Query("SELECT * FROM bookings WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): BookingEntity?

    @Query("SELECT * FROM bookings WHERE id = :id")
    fun observeById(id: String): Flow<BookingEntity?>

    @Query("SELECT * FROM bookings WHERE bookedByUserId = :ownerUserId ORDER BY createdAt DESC")
    fun observeByOwner(ownerUserId: String): Flow<List<BookingEntity>>

    @Query("SELECT * FROM bookings WHERE patientId = :patientId ORDER BY createdAt DESC")
    fun observeByPatient(patientId: String): Flow<List<BookingEntity>>

    @Query("SELECT * FROM bookings WHERE laboratoryId = :laboratoryId ORDER BY createdAt DESC")
    fun observeByLaboratory(laboratoryId: String): Flow<List<BookingEntity>>

    @Query("SELECT * FROM bookings WHERE phlebotomistId = :phlebotomistId AND status NOT IN ('REPORT_DELIVERED','CANCELLED_BY_PATIENT','CANCELLED_BY_LAB') ORDER BY scheduledDateEpochDay ASC")
    fun observeActiveForPhlebotomist(phlebotomistId: String): Flow<List<BookingEntity>>

    @Query("SELECT * FROM bookings ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<BookingEntity>>

    @Query("SELECT COUNT(*) FROM bookings WHERE createdAt >= :sinceEpochMillis")
    fun observeCountSince(sinceEpochMillis: Long): Flow<Int>

    @Query("SELECT COUNT(*) FROM bookings WHERE status = :status")
    fun observeCountByStatus(status: String): Flow<Int>

    @Query("SELECT id FROM bookings ORDER BY createdAt DESC LIMIT 1")
    suspend fun latestId(): String?

    @Query("SELECT COALESCE(SUM(totalAmount), 0) FROM bookings b JOIN payments p ON p.bookingId = b.id WHERE p.status IN ('SUCCESSFUL')")
    fun observeTotalRevenue(): Flow<Double>
}

@Dao
interface BookingItemDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(items: List<BookingItemEntity>)

    @Query("SELECT * FROM booking_items WHERE bookingId = :bookingId")
    suspend fun forBooking(bookingId: String): List<BookingItemEntity>

    @Query("SELECT * FROM booking_items WHERE bookingId = :bookingId")
    fun observeForBooking(bookingId: String): Flow<List<BookingItemEntity>>
}

@Dao
interface PaymentDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(payment: PaymentEntity)

    @Query("SELECT * FROM payments WHERE bookingId = :bookingId LIMIT 1")
    suspend fun forBooking(bookingId: String): PaymentEntity?

    @Query("SELECT * FROM payments WHERE bookingId = :bookingId")
    fun observeForBooking(bookingId: String): Flow<PaymentEntity?>
}

@Dao
interface PhlebotomistAssignmentDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(assignment: PhlebotomistAssignmentEntity)

    @Query("SELECT * FROM phlebotomist_assignments WHERE bookingId = :bookingId ORDER BY assignedAt DESC LIMIT 1")
    suspend fun latestForBooking(bookingId: String): PhlebotomistAssignmentEntity?

    @Query("SELECT * FROM phlebotomist_assignments WHERE bookingId = :bookingId ORDER BY assignedAt DESC LIMIT 1")
    fun observeLatestForBooking(bookingId: String): Flow<PhlebotomistAssignmentEntity?>

    @Query("SELECT * FROM phlebotomist_assignments WHERE phlebotomistId = :phlebotomistId ORDER BY assignedAt DESC")
    fun observeForPhlebotomist(phlebotomistId: String): Flow<List<PhlebotomistAssignmentEntity>>
}
