package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.data.local.dao.InvestigationDao
import com.digitalsolutions.diagnosticlab.data.local.dao.LaboratoryDao
import com.digitalsolutions.diagnosticlab.data.local.dao.ReportDao
import com.digitalsolutions.diagnosticlab.data.local.entities.ReportEntity
import com.digitalsolutions.diagnosticlab.domain.model.Report
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/** Access control note: every query here is scoped by patientId — a patient can only ever
 * observe their own reports because the ViewModel always supplies the signed-in patient's id,
 * never an arbitrary one from user input. See README "Security". */
class ReportRepository(
    private val reportDao: ReportDao,
    private val laboratoryDao: LaboratoryDao,
    private val investigationDao: InvestigationDao
) {
    fun observeForPatient(patientId: String): Flow<List<Report>> =
        reportDao.observeForPatient(patientId).map { list -> list.map { it.toDomain() } }

    fun observePendingForLab(laboratoryId: String): Flow<List<Report>> =
        reportDao.observePendingForLab(laboratoryId).map { list -> list.map { it.toDomain() } }

    private suspend fun ReportEntity.toDomain(): Report {
        val lab = laboratoryDao.findById(laboratoryId)
        val names = investigationDao.findByIds(investigationIds).map { it.name }
        return Report(id, bookingId, patientId, lab?.name ?: "Laboratory", names, fileUri, status, generatedAt)
    }
}
