package com.digitalsolutions.diagnosticlab.data.local.entities

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "addresses")
data class AddressEntity(
    @PrimaryKey val id: String,
    val ownerUserId: String,
    val label: String,
    val line1: String,
    val line2: String? = null,
    val city: String,
    val state: String,
    val pincode: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val isDefault: Boolean = false,
    val createdAt: Long
)
