package com.digitalsolutions.diagnosticlab.data.local.entities

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.digitalsolutions.diagnosticlab.domain.model.AppLanguage
import com.digitalsolutions.diagnosticlab.domain.model.Relation
import com.digitalsolutions.diagnosticlab.domain.model.UserRole

@Entity(tableName = "users")
data class UserEntity(
    @PrimaryKey val id: String,
    val mobileNumber: String,
    val email: String? = null,
    val role: UserRole,
    /** For PHLEBOTOMIST -> phlebotomists.id, for LABORATORY -> laboratories.id. Unused otherwise. */
    val linkedEntityId: String? = null,
    val preferredLanguage: String = AppLanguage.ENGLISH.tag,
    val active: Boolean = true,
    val createdAt: Long
)

/**
 * A patient record. Every booked-for person, whether the account owner or a family
 * member, gets one of these — [accountOwnerUserId] links a family member's record back
 * to the login that manages it, while [relation] describes who they are to that owner.
 */
@Entity(tableName = "patients")
data class PatientEntity(
    @PrimaryKey val id: String,
    val accountOwnerUserId: String,
    val relation: Relation,
    val isPrimary: Boolean,
    val fullName: String,
    val dateOfBirthEpochDay: Long?,
    val sex: String,
    val mobileNumber: String,
    val email: String? = null,
    val preferredLanguage: String = AppLanguage.ENGLISH.tag,
    val emergencyContact: String? = null,
    val photoUri: String? = null,
    val createdAt: Long
)
