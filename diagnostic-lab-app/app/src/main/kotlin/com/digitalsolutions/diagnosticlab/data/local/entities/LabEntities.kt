package com.digitalsolutions.diagnosticlab.data.local.entities

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "laboratories")
data class LaboratoryEntity(
    @PrimaryKey val id: String,
    val name: String,
    val logoUri: String? = null,
    val city: String,
    val address: String,
    val latitude: Double,
    val longitude: Double,
    val phone: String,
    val openTime: String,
    val closeTime: String,
    val homeCollectionAvailable: Boolean = true,
    val estimatedReportHours: Int = 24,
    val rating: Float = 0f,
    val active: Boolean = true,
    /** Demo data can be told apart from anything created later through the admin app. */
    val isDemoData: Boolean = false
)

@Entity(tableName = "investigations")
data class InvestigationEntity(
    @PrimaryKey val id: String,
    val name: String,
    val description: String,
    val category: String,
    val sampleType: String,
    val preparationInstructions: String,
    val reportTurnaroundHours: Int,
    val active: Boolean = true,
    val isDemoData: Boolean = false
)

/** Price and availability of one investigation at one laboratory — labs can price the same test differently. */
@Entity(tableName = "laboratory_investigations", primaryKeys = ["laboratoryId", "investigationId"])
data class LaboratoryInvestigationEntity(
    val laboratoryId: String,
    val investigationId: String,
    val price: Double,
    val homeCollectionAvailable: Boolean = true,
    val active: Boolean = true
)
