package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.data.local.dao.AddressDao
import com.digitalsolutions.diagnosticlab.data.local.dao.PatientDao
import com.digitalsolutions.diagnosticlab.data.local.entities.AddressEntity
import com.digitalsolutions.diagnosticlab.data.local.entities.PatientEntity
import com.digitalsolutions.diagnosticlab.domain.model.Address
import com.digitalsolutions.diagnosticlab.domain.model.Patient
import com.digitalsolutions.diagnosticlab.domain.model.Relation
import com.digitalsolutions.diagnosticlab.domain.util.IdGenerator
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.LocalDate

class PatientRepository(
    private val patientDao: PatientDao,
    private val addressDao: AddressDao
) {

    fun observeFamily(ownerUserId: String): Flow<List<Patient>> =
        patientDao.observeByOwner(ownerUserId).map { list -> list.map { it.toDomain() } }

    suspend fun getPatient(patientId: String): Patient? = patientDao.findById(patientId)?.toDomain()

    suspend fun updateProfile(
        patientId: String,
        fullName: String,
        dateOfBirth: LocalDate?,
        sex: String,
        email: String?,
        emergencyContact: String?
    ) {
        val existing = patientDao.findById(patientId) ?: return
        patientDao.update(
            existing.copy(
                fullName = fullName,
                dateOfBirthEpochDay = dateOfBirth?.toEpochDay(),
                sex = sex,
                email = email,
                emergencyContact = emergencyContact
            )
        )
    }

    suspend fun addFamilyMember(
        ownerUserId: String,
        fullName: String,
        dateOfBirth: LocalDate?,
        sex: String,
        relation: Relation,
        mobileNumber: String
    ): Patient {
        val latest = patientDao.latestId()
        val seedSeq = latest?.let { IdGenerator.sequenceOf(it) } ?: 0
        val id = IdGenerator.next("PAT", seedFrom = seedSeq)
        val entity = PatientEntity(
            id = id,
            accountOwnerUserId = ownerUserId,
            relation = relation,
            isPrimary = false,
            fullName = fullName,
            dateOfBirthEpochDay = dateOfBirth?.toEpochDay(),
            sex = sex,
            mobileNumber = mobileNumber,
            createdAt = System.currentTimeMillis()
        )
        patientDao.upsert(entity)
        return entity.toDomain()
    }

    fun observeAddresses(ownerUserId: String): Flow<List<Address>> =
        addressDao.observeByOwner(ownerUserId).map { list -> list.map { it.toDomain() } }

    suspend fun saveAddress(
        ownerUserId: String,
        existingId: String?,
        label: String,
        line1: String,
        line2: String?,
        city: String,
        state: String,
        pincode: String,
        latitude: Double?,
        longitude: Double?,
        makeDefault: Boolean
    ): Address {
        if (makeDefault) addressDao.clearDefault(ownerUserId)
        val id = existingId ?: "ADDR-${System.currentTimeMillis()}"
        val entity = AddressEntity(
            id = id,
            ownerUserId = ownerUserId,
            label = label,
            line1 = line1,
            line2 = line2,
            city = city,
            state = state,
            pincode = pincode,
            latitude = latitude,
            longitude = longitude,
            isDefault = makeDefault,
            createdAt = System.currentTimeMillis()
        )
        addressDao.upsert(entity)
        return entity.toDomain()
    }
}

private fun PatientEntity.toDomain() = Patient(
    id = id,
    accountOwnerUserId = accountOwnerUserId,
    relation = relation,
    isPrimary = isPrimary,
    fullName = fullName,
    dateOfBirth = dateOfBirthEpochDay?.let { LocalDate.ofEpochDay(it) },
    sex = sex,
    mobileNumber = mobileNumber,
    email = email
)

private fun AddressEntity.toDomain() = Address(
    id = id, label = label, line1 = line1, line2 = line2, city = city, state = state,
    pincode = pincode, latitude = latitude, longitude = longitude, isDefault = isDefault
)
