package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.data.local.dao.*
import com.digitalsolutions.diagnosticlab.data.local.entities.*
import com.digitalsolutions.diagnosticlab.domain.model.*
import com.digitalsolutions.diagnosticlab.domain.util.AssignmentStatusMachine
import com.digitalsolutions.diagnosticlab.domain.util.BookingStatusMachine
import com.digitalsolutions.diagnosticlab.domain.util.IdGenerator
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.LocalDate

/**
 * The central orchestrator for the whole booking -> collection -> lab -> report journey
 * (spec sections 10-17). Every status change goes through here so [BookingStatusMachine]
 * and [AssignmentStatusMachine] are the single source of truth for what transitions are
 * legal, every transition is written to sample_tracking_events for the patient-visible
 * timeline, and every transition raises a notification.
 */
class BookingRepository(
    private val bookingDao: BookingDao,
    private val bookingItemDao: BookingItemDao,
    private val paymentDao: PaymentDao,
    private val assignmentDao: PhlebotomistAssignmentDao,
    private val phlebotomistDao: PhlebotomistDao,
    private val sampleDao: SampleDao,
    private val trackingEventDao: SampleTrackingEventDao,
    private val reportDao: ReportDao,
    private val patientDao: PatientDao,
    private val laboratoryDao: LaboratoryDao,
    private val addressDao: AddressDao,
    private val investigationDao: InvestigationDao,
    private val auditLogDao: AuditLogDao,
    private val notificationRepository: NotificationRepository,
    private val paymentGateway: PaymentGateway
) {

    // ---------- Creation & payment ----------

    suspend fun createBooking(
        patientId: String,
        bookedByUserId: String,
        laboratoryId: String,
        addressId: String,
        investigationPrices: Map<String, Double>,
        scheduledDate: LocalDate,
        scheduledTimeSlot: String
    ): String {
        val now = System.currentTimeMillis()
        val latest = bookingDao.latestId()
        val seedSeq = latest?.let { IdGenerator.sequenceOf(it) } ?: 0
        val bookingId = IdGenerator.next("BOOK", seedFrom = seedSeq)
        val total = investigationPrices.values.sum()
        bookingDao.upsert(
            BookingEntity(
                id = bookingId,
                patientId = patientId,
                bookedByUserId = bookedByUserId,
                laboratoryId = laboratoryId,
                addressId = addressId,
                scheduledDateEpochDay = scheduledDate.toEpochDay(),
                scheduledTimeSlot = scheduledTimeSlot,
                status = BookingStatus.PENDING_PAYMENT,
                totalAmount = total,
                createdAt = now,
                updatedAt = now
            )
        )
        bookingItemDao.insertAll(
            investigationPrices.entries.mapIndexed { i, (invId, price) ->
                BookingItemEntity("BI-$bookingId-$i", bookingId, invId, price)
            }
        )
        audit(bookedByUserId, "PATIENT", "CREATE_BOOKING", "booking", bookingId)
        return bookingId
    }

    suspend fun pay(bookingId: String, method: PaymentMethod): PaymentGatewayResult {
        val booking = bookingDao.findById(bookingId) ?: return PaymentGatewayResult.Failure("Booking not found")
        val result = paymentGateway.charge(booking.totalAmount, method)
        val status = when {
            method == PaymentMethod.CASH -> PaymentStatus.CASH_SELECTED
            result is PaymentGatewayResult.Success -> PaymentStatus.SUCCESSFUL
            else -> PaymentStatus.FAILED
        }
        paymentDao.upsert(
            PaymentEntity(
                id = "PAY-$bookingId",
                bookingId = bookingId,
                amount = booking.totalAmount,
                method = method,
                status = status,
                transactionId = (result as? PaymentGatewayResult.Success)?.transactionId,
                timestamp = System.currentTimeMillis()
            )
        )
        if (status == PaymentStatus.SUCCESSFUL || status == PaymentStatus.CASH_SELECTED) {
            transitionBooking(booking, BookingStatus.CONFIRMED, booking.bookedByUserId, "PATIENT")
            notificationRepository.notify(
                booking.bookedByUserId, NotificationType.PAYMENT_CONFIRMED,
                "Payment confirmed", "Your booking $bookingId is confirmed.", bookingId
            )
            notificationRepository.notify(
                booking.bookedByUserId, NotificationType.BOOKING_CONFIRMED,
                "Booking confirmed", "We'll assign a lab assistant shortly.", bookingId
            )
            assignPhlebotomist(bookingId)
        }
        return result
    }

    // ---------- Allocation & phlebotomist workflow ----------

    /** MVP allocator: picks any active phlebotomist. A real deployment would consider service area and load. */
    suspend fun assignPhlebotomist(bookingId: String) {
        val booking = bookingDao.findById(bookingId) ?: return
        val phlebotomist = phlebotomistDao.pickAvailable() ?: return
        assignmentDao.upsert(
            PhlebotomistAssignmentEntity(
                id = "ASSIGN-$bookingId-${System.currentTimeMillis()}",
                bookingId = bookingId,
                phlebotomistId = phlebotomist.id,
                status = AssignmentStatus.ASSIGNED,
                assignedAt = System.currentTimeMillis()
            )
        )
        bookingDao.update(booking.copy(phlebotomistId = phlebotomist.id, status = BookingStatus.PHLEBOTOMIST_ASSIGNED, updatedAt = System.currentTimeMillis()))
        recordTrackingEvent(bookingId, BookingStatus.PHLEBOTOMIST_ASSIGNED.name, phlebotomist.id, "PHLEBOTOMIST")
        notificationRepository.notify(
            booking.bookedByUserId, NotificationType.PHLEBOTOMIST_ASSIGNED,
            "Lab assistant assigned", "${phlebotomist.name} will collect the sample.", bookingId
        )
        audit(phlebotomist.id, "SYSTEM", "ASSIGN_PHLEBOTOMIST", "booking", bookingId)
    }

    suspend fun respondToAssignment(bookingId: String, accept: Boolean) {
        val assignment = assignmentDao.latestForBooking(bookingId) ?: return
        val booking = bookingDao.findById(bookingId) ?: return
        val newStatus = if (accept) AssignmentStatus.ACCEPTED else AssignmentStatus.REJECTED
        if (!AssignmentStatusMachine.canTransition(assignment.status, newStatus)) return
        assignmentDao.upsert(assignment.copy(status = newStatus, respondedAt = System.currentTimeMillis()))
        if (accept) {
            notificationRepository.notify(
                booking.bookedByUserId, NotificationType.PHLEBOTOMIST_ACCEPTED,
                "Lab assistant confirmed", "Your sample collection is confirmed for ${booking.scheduledTimeSlot}.", bookingId
            )
        } else {
            assignPhlebotomist(bookingId) // re-allocate
        }
    }

    suspend fun updateAssignmentTravelStatus(bookingId: String, status: AssignmentStatus) {
        val assignment = assignmentDao.latestForBooking(bookingId) ?: return
        val booking = bookingDao.findById(bookingId) ?: return
        if (!AssignmentStatusMachine.canTransition(assignment.status, status)) return
        val now = System.currentTimeMillis()
        assignmentDao.upsert(
            assignment.copy(status = status, arrivedAt = if (status == AssignmentStatus.ARRIVED) now else assignment.arrivedAt)
        )
        val bookingStatus = when (status) {
            AssignmentStatus.ON_THE_WAY -> BookingStatus.PHLEBOTOMIST_ON_THE_WAY
            AssignmentStatus.ARRIVED -> BookingStatus.ARRIVED
            else -> return
        }
        transitionBooking(booking, bookingStatus, assignment.phlebotomistId, "PHLEBOTOMIST")
        val notifType = if (status == AssignmentStatus.ON_THE_WAY) NotificationType.PHLEBOTOMIST_ON_THE_WAY else NotificationType.PHLEBOTOMIST_ARRIVED
        val message = if (status == AssignmentStatus.ON_THE_WAY) "Your lab assistant is on the way." else "Your lab assistant has arrived."
        notificationRepository.notify(booking.bookedByUserId, notifType, "Collection update", message, bookingId)
    }

    // ---------- Sample collection & chain of custody ----------

    suspend fun recordSampleCollected(bookingId: String, sampleType: String, collectionLocation: String) {
        val booking = bookingDao.findById(bookingId) ?: return
        val assignment = assignmentDao.latestForBooking(bookingId) ?: return
        if (!AssignmentStatusMachine.canTransition(assignment.status, AssignmentStatus.SAMPLE_COLLECTED)) return
        val now = System.currentTimeMillis()
        val sampleId = IdGenerator.next("SMP")
        sampleDao.upsert(
            SampleEntity(
                id = sampleId, bookingId = bookingId, patientId = booking.patientId,
                collectorId = assignment.phlebotomistId, collectionTime = now,
                collectionLocation = collectionLocation, sampleType = sampleType,
                status = SampleStatus.COLLECTED
            )
        )
        transitionBooking(booking, BookingStatus.SAMPLE_COLLECTED, assignment.phlebotomistId, "PHLEBOTOMIST")
        notificationRepository.notify(
            booking.bookedByUserId, NotificationType.SAMPLE_COLLECTED,
            "Sample collected", "Your sample has been collected and is on its way to the lab.", bookingId
        )
        assignmentDao.upsert(assignment.copy(status = AssignmentStatus.COMPLETED, completedAt = now))
    }

    suspend fun markSampleInTransit(bookingId: String) {
        val booking = bookingDao.findById(bookingId) ?: return
        val sample = sampleDao.findByBooking(bookingId) ?: return
        sampleDao.update(sample.copy(status = SampleStatus.IN_TRANSIT))
        transitionBooking(booking, BookingStatus.SAMPLE_IN_TRANSIT, sample.collectorId, "PHLEBOTOMIST")
    }

    suspend fun labReceiveSample(bookingId: String, receivedByUserId: String) {
        val booking = bookingDao.findById(bookingId) ?: return
        val sample = sampleDao.findByBooking(bookingId)
        sample?.let { sampleDao.update(it.copy(status = SampleStatus.RECEIVED_AT_LAB)) }
        transitionBooking(booking, BookingStatus.RECEIVED_AT_LAB, receivedByUserId, "LABORATORY")
        notificationRepository.notify(
            booking.bookedByUserId, NotificationType.SAMPLE_RECEIVED_AT_LAB,
            "Sample received", "The laboratory has received your sample.", bookingId
        )
    }

    suspend fun rejectSample(bookingId: String, reason: SampleRejectionReason, notes: String?, rejectedByUserId: String) {
        val booking = bookingDao.findById(bookingId) ?: return
        val sample = sampleDao.findByBooking(bookingId) ?: return
        sampleDao.update(sample.copy(status = SampleStatus.REJECTED, rejectionReason = reason, rejectionNotes = notes))
        transitionBooking(booking, BookingStatus.REJECTED_RECOLLECTION_NEEDED, rejectedByUserId, "LABORATORY", notes)
        notificationRepository.notify(
            booking.bookedByUserId, NotificationType.GENERAL,
            "Recollection needed", "The lab could not accept your sample (${reason.name.lowercase().replace('_', ' ')}). We will arrange a new collection.", bookingId
        )
        assignPhlebotomist(bookingId)
    }

    suspend fun startProcessing(bookingId: String, labUserId: String) {
        val booking = bookingDao.findById(bookingId) ?: return
        transitionBooking(booking, BookingStatus.PROCESSING, labUserId, "LABORATORY")
        notificationRepository.notify(
            booking.bookedByUserId, NotificationType.SAMPLE_PROCESSING,
            "Processing started", "Your investigations are now being processed.", bookingId
        )
    }

    suspend fun uploadReport(bookingId: String, fileUri: String, verifiedByUserId: String) {
        val booking = bookingDao.findById(bookingId) ?: return
        val items = bookingItemDao.forBooking(bookingId)
        reportDao.upsert(
            ReportEntity(
                id = "RPT-$bookingId", bookingId = bookingId, patientId = booking.patientId,
                laboratoryId = booking.laboratoryId, investigationIds = items.map { it.investigationId },
                fileUri = fileUri, status = ReportStatus.READY, generatedAt = System.currentTimeMillis(),
                verifiedByUserId = verifiedByUserId
            )
        )
        transitionBooking(booking, BookingStatus.REPORT_READY, verifiedByUserId, "LABORATORY")
        notificationRepository.notify(
            booking.bookedByUserId, NotificationType.REPORT_READY,
            "Report ready", "Your report for booking $bookingId is ready to view.", bookingId
        )
        audit(verifiedByUserId, "LABORATORY", "UPLOAD_REPORT", "booking", bookingId)
    }

    suspend fun markReportDelivered(bookingId: String) {
        val booking = bookingDao.findById(bookingId) ?: return
        val report = reportDao.findByBooking(bookingId) ?: return
        if (report.status == ReportStatus.DELIVERED) return
        reportDao.update(report.copy(status = ReportStatus.DELIVERED, deliveredAt = System.currentTimeMillis()))
        transitionBooking(booking, BookingStatus.REPORT_DELIVERED, booking.bookedByUserId, "PATIENT")
    }

    suspend fun cancelBooking(bookingId: String, reason: String, cancelledByUserId: String, byLab: Boolean) {
        val booking = bookingDao.findById(bookingId) ?: return
        if (!BookingStatusMachine.canCancel(booking.status)) return
        val target = if (byLab) BookingStatus.CANCELLED_BY_LAB else BookingStatus.CANCELLED_BY_PATIENT
        bookingDao.update(booking.copy(status = target, cancellationReason = reason, updatedAt = System.currentTimeMillis()))
        recordTrackingEvent(bookingId, target.name, cancelledByUserId, if (byLab) "LABORATORY" else "PATIENT", notes = reason)
        audit(cancelledByUserId, if (byLab) "LABORATORY" else "PATIENT", "CANCEL_BOOKING", "booking", bookingId, reason)
    }

    // ---------- Reads ----------

    fun observeBookingsForOwner(ownerUserId: String): Flow<List<Booking>> =
        bookingDao.observeByOwner(ownerUserId).map { list -> list.map { it.toDomain() } }

    fun observeBookingsForLab(laboratoryId: String): Flow<List<Booking>> =
        bookingDao.observeByLaboratory(laboratoryId).map { list -> list.map { it.toDomain() } }

    fun observeActiveForPhlebotomist(phlebotomistId: String): Flow<List<Booking>> =
        bookingDao.observeActiveForPhlebotomist(phlebotomistId).map { list -> list.map { it.toDomain() } }

    fun observeBooking(bookingId: String): Flow<Booking?> =
        bookingDao.observeById(bookingId).map { it?.toDomain() }

    fun observeTrackingEvents(bookingId: String): Flow<List<TrackingEvent>> =
        trackingEventDao.observeForBooking(bookingId).map { list ->
            list.map { TrackingEvent(it.status, it.timestamp, it.actorRole, it.notes) }
        }

    fun observeAssignment(bookingId: String): Flow<Assignment?> =
        assignmentDao.observeLatestForBooking(bookingId).map { assignment ->
            assignment?.let {
                Assignment(it.id, it.bookingId, phlebotomistProfile(it.phlebotomistId), it.status)
            }
        }

    fun observeAllBookings(): Flow<List<Booking>> = bookingDao.observeAll().map { list -> list.map { it.toDomain() } }

    // ---------- Internal helpers ----------

    private suspend fun transitionBooking(
        booking: BookingEntity,
        to: BookingStatus,
        actorId: String,
        actorRole: String,
        notes: String? = null
    ) {
        if (!BookingStatusMachine.canTransition(booking.status, to)) return
        bookingDao.update(booking.copy(status = to, updatedAt = System.currentTimeMillis()))
        recordTrackingEvent(booking.id, to.name, actorId, actorRole, notes)
    }

    private suspend fun recordTrackingEvent(bookingId: String, status: String, actorId: String, actorRole: String, notes: String? = null) {
        trackingEventDao.insert(
            SampleTrackingEventEntity(
                id = "EVT-$bookingId-${System.currentTimeMillis()}",
                bookingId = bookingId,
                status = status,
                timestamp = System.currentTimeMillis(),
                actorId = actorId,
                actorRole = actorRole,
                notes = notes
            )
        )
    }

    private suspend fun audit(actorId: String, actorRole: String, action: String, entityType: String, entityId: String, details: String? = null) {
        auditLogDao.insert(
            AuditLogEntity(
                id = "AUDIT-${System.currentTimeMillis()}-$entityId",
                actorId = actorId, actorRole = actorRole, action = action,
                entityType = entityType, entityId = entityId,
                timestamp = System.currentTimeMillis(), details = details
            )
        )
    }

    private suspend fun phlebotomistProfile(id: String): PhlebotomistProfile {
        val p = phlebotomistDao.findById(id)
        return PhlebotomistProfile(id, p?.name ?: "Unassigned", p?.mobileNumber ?: "", p?.professionalId ?: "", p?.rating ?: 0f)
    }

    private suspend fun BookingEntity.toDomain(): Booking {
        val patient = patientDao.findById(patientId)
        val lab = laboratoryDao.findById(laboratoryId)
        val address = addressDao.findById(addressId)
        val items = bookingItemDao.forBooking(id)
        val investigations = investigationDao.findByIds(items.map { it.investigationId }).associateBy { it.id }
        return Booking(
            id = id,
            patientId = patientId,
            patientName = patient?.fullName.orEmpty().ifBlank { "Patient" },
            laboratoryId = laboratoryId,
            laboratoryName = lab?.name ?: "Laboratory",
            addressLabel = address?.label ?: "",
            addressLine = address?.let { listOfNotNull(it.line1, it.line2, it.city, it.state, it.pincode).joinToString(", ") } ?: "",
            addressLatitude = address?.latitude,
            addressLongitude = address?.longitude,
            scheduledDate = LocalDate.ofEpochDay(scheduledDateEpochDay),
            scheduledTimeSlot = scheduledTimeSlot,
            status = status,
            items = items.mapNotNull { item ->
                investigations[item.investigationId]?.let { inv ->
                    BookingItem(
                        Investigation(inv.id, inv.name, inv.description, inv.category, inv.sampleType, inv.preparationInstructions, inv.reportTurnaroundHours),
                        item.priceAtBooking
                    )
                }
            },
            totalAmount = totalAmount,
            phlebotomistId = phlebotomistId,
            createdAtMillis = createdAt
        )
    }
}
