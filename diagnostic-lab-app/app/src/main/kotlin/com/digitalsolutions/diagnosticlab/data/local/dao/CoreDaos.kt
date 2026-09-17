package com.digitalsolutions.diagnosticlab.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.digitalsolutions.diagnosticlab.data.local.entities.AddressEntity
import com.digitalsolutions.diagnosticlab.data.local.entities.PatientEntity
import com.digitalsolutions.diagnosticlab.data.local.entities.UserEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface UserDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(user: UserEntity)

    @Query("SELECT * FROM users WHERE mobileNumber = :mobileNumber LIMIT 1")
    suspend fun findByMobile(mobileNumber: String): UserEntity?

    @Query("SELECT * FROM users WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): UserEntity?

    @Query("SELECT * FROM users WHERE role = :role")
    fun observeByRole(role: String): Flow<List<UserEntity>>

    @Query("SELECT COUNT(*) FROM users WHERE role = 'PATIENT'")
    fun observeTotalPatientAccounts(): Flow<Int>
}

@Dao
interface PatientDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(patient: PatientEntity)

    @Update
    suspend fun update(patient: PatientEntity)

    @Query("SELECT * FROM patients WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): PatientEntity?

    @Query("SELECT * FROM patients WHERE accountOwnerUserId = :ownerUserId ORDER BY isPrimary DESC, fullName ASC")
    fun observeByOwner(ownerUserId: String): Flow<List<PatientEntity>>

    @Query("SELECT * FROM patients WHERE accountOwnerUserId = :ownerUserId AND isPrimary = 1 LIMIT 1")
    suspend fun findPrimaryForOwner(ownerUserId: String): PatientEntity?

    @Query("SELECT id FROM patients ORDER BY createdAt DESC LIMIT 1")
    suspend fun latestId(): String?

    @Query("SELECT COUNT(*) FROM patients")
    fun observeTotalCount(): Flow<Int>

    @Query("SELECT COUNT(*) FROM patients WHERE createdAt >= :sinceEpochMillis")
    fun observeNewSince(sinceEpochMillis: Long): Flow<Int>
}

@Dao
interface AddressDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(address: AddressEntity)

    @Query("SELECT * FROM addresses WHERE ownerUserId = :ownerUserId ORDER BY isDefault DESC, createdAt DESC")
    fun observeByOwner(ownerUserId: String): Flow<List<AddressEntity>>

    @Query("SELECT * FROM addresses WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): AddressEntity?

    @Query("UPDATE addresses SET isDefault = 0 WHERE ownerUserId = :ownerUserId")
    suspend fun clearDefault(ownerUserId: String)
}
