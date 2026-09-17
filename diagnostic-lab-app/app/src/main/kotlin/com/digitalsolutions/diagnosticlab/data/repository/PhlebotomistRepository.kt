package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.data.local.dao.PhlebotomistDao
import com.digitalsolutions.diagnosticlab.data.local.entities.PhlebotomistEntity
import com.digitalsolutions.diagnosticlab.domain.model.PhlebotomistProfile
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

class PhlebotomistRepository(private val phlebotomistDao: PhlebotomistDao) {

    suspend fun getByUserId(userId: String): PhlebotomistProfile? = phlebotomistDao.findByUserId(userId)?.toDomain()

    fun observeActive(): Flow<List<PhlebotomistProfile>> =
        phlebotomistDao.observeActive().map { list -> list.map { it.toDomain() } }

    suspend fun setActive(id: String, active: Boolean) {
        val existing = phlebotomistDao.findById(id) ?: return
        phlebotomistDao.update(existing.copy(active = active))
    }

    suspend fun updateLocation(id: String, latitude: Double, longitude: Double) {
        val existing = phlebotomistDao.findById(id) ?: return
        phlebotomistDao.update(existing.copy(currentLatitude = latitude, currentLongitude = longitude))
    }
}

private fun PhlebotomistEntity.toDomain() = PhlebotomistProfile(id, name, mobileNumber, professionalId, rating)
