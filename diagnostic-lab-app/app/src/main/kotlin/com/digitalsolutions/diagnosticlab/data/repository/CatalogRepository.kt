package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.data.local.dao.InvestigationDao
import com.digitalsolutions.diagnosticlab.data.local.dao.LaboratoryDao
import com.digitalsolutions.diagnosticlab.data.local.dao.LaboratoryInvestigationDao
import com.digitalsolutions.diagnosticlab.data.local.entities.InvestigationEntity
import com.digitalsolutions.diagnosticlab.data.local.entities.LaboratoryEntity
import com.digitalsolutions.diagnosticlab.domain.model.Investigation
import com.digitalsolutions.diagnosticlab.domain.model.Laboratory
import com.digitalsolutions.diagnosticlab.domain.model.PricedInvestigation
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

class CatalogRepository(
    private val laboratoryDao: LaboratoryDao,
    private val investigationDao: InvestigationDao,
    private val laboratoryInvestigationDao: LaboratoryInvestigationDao
) {

    fun observeLaboratories(): Flow<List<Laboratory>> =
        laboratoryDao.observeActive().map { list -> list.map { it.toDomain() } }

    suspend fun getLaboratory(id: String): Laboratory? = laboratoryDao.findById(id)?.toDomain()

    fun searchInvestigations(query: String): Flow<List<Investigation>> =
        (if (query.isBlank()) investigationDao.observeActive() else investigationDao.search(query))
            .map { list -> list.map { it.toDomain() } }

    /** Investigations offered by a specific lab, with that lab's pricing. */
    fun observePricedInvestigations(laboratoryId: String): Flow<List<PricedInvestigation>> =
        laboratoryInvestigationDao.observeForLab(laboratoryId).map { links ->
            val investigations = investigationDao.findByIds(links.map { it.investigationId }).associateBy { it.id }
            links.mapNotNull { link ->
                investigations[link.investigationId]?.let { inv ->
                    PricedInvestigation(inv.toDomain(), link.price, link.homeCollectionAvailable)
                }
            }
        }

    suspend fun findPrice(laboratoryId: String, investigationId: String): Double? =
        laboratoryInvestigationDao.find(laboratoryId, investigationId)?.price

    suspend fun labsOffering(investigationId: String): List<Laboratory> {
        val ids = laboratoryInvestigationDao.labsOffering(investigationId)
        return ids.mapNotNull { laboratoryDao.findById(it)?.toDomain() }
    }
}

private fun LaboratoryEntity.toDomain() = Laboratory(
    id = id, name = name, city = city, address = address, phone = phone,
    openTime = openTime, closeTime = closeTime, homeCollectionAvailable = homeCollectionAvailable,
    estimatedReportHours = estimatedReportHours, rating = rating
)

private fun InvestigationEntity.toDomain() = Investigation(
    id = id, name = name, description = description, category = category,
    sampleType = sampleType, preparationInstructions = preparationInstructions,
    reportTurnaroundHours = reportTurnaroundHours
)
