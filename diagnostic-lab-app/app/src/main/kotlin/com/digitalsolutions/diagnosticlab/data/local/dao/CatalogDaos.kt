package com.digitalsolutions.diagnosticlab.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.digitalsolutions.diagnosticlab.data.local.entities.InvestigationEntity
import com.digitalsolutions.diagnosticlab.data.local.entities.LaboratoryEntity
import com.digitalsolutions.diagnosticlab.data.local.entities.LaboratoryInvestigationEntity
import com.digitalsolutions.diagnosticlab.data.local.entities.PhlebotomistEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface LaboratoryDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(lab: LaboratoryEntity)

    @Update
    suspend fun update(lab: LaboratoryEntity)

    @Query("SELECT * FROM laboratories WHERE active = 1 ORDER BY rating DESC")
    fun observeActive(): Flow<List<LaboratoryEntity>>

    @Query("SELECT * FROM laboratories ORDER BY name ASC")
    fun observeAll(): Flow<List<LaboratoryEntity>>

    @Query("SELECT * FROM laboratories WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): LaboratoryEntity?

    @Query("SELECT COUNT(*) FROM laboratories WHERE active = 1")
    fun observeActiveCount(): Flow<Int>
}

@Dao
interface InvestigationDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(investigation: InvestigationEntity)

    @Query("SELECT * FROM investigations WHERE active = 1 ORDER BY name ASC")
    fun observeActive(): Flow<List<InvestigationEntity>>

    @Query(
        "SELECT * FROM investigations WHERE active = 1 AND (name LIKE '%' || :query || '%' " +
            "OR category LIKE '%' || :query || '%') ORDER BY name ASC"
    )
    fun search(query: String): Flow<List<InvestigationEntity>>

    @Query("SELECT * FROM investigations WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): InvestigationEntity?

    @Query("SELECT * FROM investigations WHERE id IN (:ids)")
    suspend fun findByIds(ids: List<String>): List<InvestigationEntity>
}

@Dao
interface LaboratoryInvestigationDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(link: LaboratoryInvestigationEntity)

    @Query("SELECT * FROM laboratory_investigations WHERE laboratoryId = :laboratoryId AND active = 1")
    fun observeForLab(laboratoryId: String): Flow<List<LaboratoryInvestigationEntity>>

    @Query(
        "SELECT * FROM laboratory_investigations WHERE laboratoryId = :laboratoryId AND investigationId = :investigationId LIMIT 1"
    )
    suspend fun find(laboratoryId: String, investigationId: String): LaboratoryInvestigationEntity?

    @Query("SELECT DISTINCT laboratoryId FROM laboratory_investigations WHERE investigationId = :investigationId AND active = 1")
    suspend fun labsOffering(investigationId: String): List<String>
}

@Dao
interface PhlebotomistDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(phlebotomist: PhlebotomistEntity)

    @Update
    suspend fun update(phlebotomist: PhlebotomistEntity)

    @Query("SELECT * FROM phlebotomists WHERE active = 1 ORDER BY rating DESC")
    fun observeActive(): Flow<List<PhlebotomistEntity>>

    @Query("SELECT * FROM phlebotomists WHERE userId = :userId LIMIT 1")
    suspend fun findByUserId(userId: String): PhlebotomistEntity?

    @Query("SELECT * FROM phlebotomists WHERE id = :id LIMIT 1")
    suspend fun findById(id: String): PhlebotomistEntity?

    /** Simple round-robin availability pick for the MVP allocator (see BookingRepository). */
    @Query("SELECT * FROM phlebotomists WHERE active = 1 ORDER BY RANDOM() LIMIT 1")
    suspend fun pickAvailable(): PhlebotomistEntity?
}
