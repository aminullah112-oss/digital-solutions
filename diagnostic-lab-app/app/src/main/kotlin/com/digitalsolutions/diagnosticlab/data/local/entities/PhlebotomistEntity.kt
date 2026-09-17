package com.digitalsolutions.diagnosticlab.data.local.entities

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "phlebotomists")
data class PhlebotomistEntity(
    @PrimaryKey val id: String,
    val userId: String,
    val name: String,
    val photoUri: String? = null,
    val mobileNumber: String,
    val professionalId: String,
    val rating: Float = 0f,
    val active: Boolean = true,
    val currentLatitude: Double? = null,
    val currentLongitude: Double? = null,
    val isDemoData: Boolean = false
)
