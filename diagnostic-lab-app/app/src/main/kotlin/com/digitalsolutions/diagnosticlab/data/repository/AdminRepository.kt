package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.data.local.dao.*
import com.digitalsolutions.diagnosticlab.data.local.entities.LaboratoryEntity
import com.digitalsolutions.diagnosticlab.domain.model.DashboardStats
import com.digitalsolutions.diagnosticlab.domain.model.Laboratory
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import java.time.Instant
import java.time.temporal.ChronoUnit

/** Backs the admin/owner dashboard (spec section 23). Pure read-side aggregation over the same tables everything else writes to. */
class AdminRepository(
    private val patientDao: PatientDao,
    private val bookingDao: BookingDao,
    private val reportDao: ReportDao,
    private val complaintDao: ComplaintDao,
    private val laboratoryDao: LaboratoryDao,
    private val sampleDao: SampleDao
) {
    fun observeDashboard(): Flow<DashboardStats> {
        val sevenDaysAgo = Instant.now().minus(7, ChronoUnit.DAYS).toEpochMilli()
        val startOfToday = Instant.now().truncatedTo(ChronoUnit.DAYS).toEpochMilli()
        return combine(
            patientDao.observeTotalCount(),
            patientDao.observeNewSince(sevenDaysAgo),
            bookingDao.observeCountSince(0),
            bookingDao.observeCountSince(startOfToday),
            bookingDao.observeCountByStatus("PHLEBOTOMIST_ASSIGNED"),
            sampleDao.observeInTransit(),
            reportDao.observePendingCount(),
            reportDao.observeCompletedCount(),
            bookingDao.observeTotalRevenue(),
            complaintDao.observeOpenCount(),
            laboratoryDao.observeActiveCount()
        ) { values ->
            DashboardStats(
                totalPatients = values[0] as Int,
                newPatientsLast7Days = values[1] as Int,
                totalBookings = values[2] as Int,
                todaysBookings = values[3] as Int,
                pendingCollections = values[4] as Int,
                samplesInTransit = (values[5] as List<*>).size,
                reportsPending = values[6] as Int,
                reportsCompleted = values[7] as Int,
                totalRevenue = values[8] as Double,
                openComplaints = values[9] as Int,
                activeLabs = values[10] as Int
            )
        }
    }

    fun observeAllLaboratories(): Flow<List<Laboratory>> =
        laboratoryDao.observeAll().map { list -> list.map { it.toDomain() } }

    suspend fun setLabActive(id: String, active: Boolean) {
        val existing = laboratoryDao.findById(id) ?: return
        laboratoryDao.update(existing.copy(active = active))
    }
}

private fun LaboratoryEntity.toDomain() = Laboratory(
    id = id, name = name, city = city, address = address, phone = phone,
    openTime = openTime, closeTime = closeTime, homeCollectionAvailable = homeCollectionAvailable,
    estimatedReportHours = estimatedReportHours, rating = rating, active = active
)
