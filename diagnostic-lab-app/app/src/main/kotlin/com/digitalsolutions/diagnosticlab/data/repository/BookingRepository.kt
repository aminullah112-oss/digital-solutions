package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.*
import com.digitalsolutions.diagnosticlab.domain.util.AssignmentStatusMachine
import com.digitalsolutions.diagnosticlab.domain.util.BookingStatusMachine
import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await
import java.time.LocalDate
import java.time.Year

/**
 * The central orchestrator for the whole booking -> collection -> lab -> report journey.
 * Every status change goes through [transitionBooking] so [BookingStatusMachine] and
 * [AssignmentStatusMachine] stay the single source of truth for what transitions are legal,
 * and every transition is written to bookings/{id}/trackingEvents for the patient-visible
 * timeline.
 *
 * Patient-facing notifications for most status changes are handled server-side by the
 * onBookingStatusChange Cloud Function reacting to the status field written here — this
 * class only writes notifications directly for the two cases that Cloud Function doesn't
 * cover (an assignment acceptance and a sample rejection notice), since neither is itself a
 * booking-status transition.
 */
class BookingRepository(
    private val firestore: FirebaseFirestore,
    private val notificationRepository: NotificationRepository,
    private val paymentGateway: PaymentGateway
) {

    private fun bookingsRef() = firestore.collection("bookings")
    private fun trackingEventsOf(bookingId: String) = bookingsRef().document(bookingId).collection("trackingEvents")

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
        val patientSnap = firestore.collection("patients").document(patientId).get().await()
        val labSnap = firestore.collection("laboratories").document(laboratoryId).get().await()
        val addressSnap = firestore.collection("users").document(bookedByUserId)
            .collection("addresses").document(addressId).get().await()
        val investigationSnaps = if (investigationPrices.isEmpty()) emptyList() else
            firestore.collection("investigations")
                .whereIn(com.google.firebase.firestore.FieldPath.documentId(), investigationPrices.keys.toList().take(30))
                .get().await().documents

        val items = investigationSnaps.map { doc ->
            mapOf(
                "investigationId" to doc.id,
                "name" to doc.getString("name").orEmpty(),
                "description" to doc.getString("description").orEmpty(),
                "category" to doc.getString("category").orEmpty(),
                "sampleType" to doc.getString("sampleType").orEmpty(),
                "preparationInstructions" to doc.getString("preparationInstructions").orEmpty(),
                "reportTurnaroundHours" to (doc.getLong("reportTurnaroundHours") ?: 0L),
                "price" to (investigationPrices[doc.id] ?: 0.0)
            )
        }
        val total = investigationPrices.values.sum()
        val bookingId = nextBookingId()
        val now = System.currentTimeMillis()

        val addressLine = listOfNotNull(
            addressSnap.getString("line1"), addressSnap.getString("line2"),
            addressSnap.getString("city"), addressSnap.getString("state"), addressSnap.getString("pincode")
        ).joinToString(", ")

        bookingsRef().document(bookingId).set(
            mapOf(
                "patientId" to patientId,
                "patientName" to (patientSnap.getString("fullName")?.ifBlank { null } ?: "Patient"),
                "patientAccountOwnerUserId" to bookedByUserId,
                "bookedByUserId" to bookedByUserId,
                "laboratoryId" to laboratoryId,
                "laboratoryName" to (labSnap.getString("name") ?: "Laboratory"),
                "addressLabel" to addressSnap.getString("label").orEmpty(),
                "addressLine" to addressLine,
                "addressLatitude" to addressSnap.getDouble("latitude"),
                "addressLongitude" to addressSnap.getDouble("longitude"),
                "scheduledDate" to scheduledDate.toString(),
                "scheduledTimeSlot" to scheduledTimeSlot,
                "status" to BookingStatus.PENDING_PAYMENT.name,
                "items" to items,
                "totalAmount" to total,
                "assignedPhlebotomistUid" to null,
                "createdAtMillis" to now,
                "updatedAtMillis" to now
            )
        ).await()
        return bookingId
    }

    suspend fun pay(bookingId: String, method: PaymentMethod): PaymentGatewayResult {
        val booking = bookingsRef().document(bookingId).get().await()
        val totalAmount = booking.getDouble("totalAmount") ?: return PaymentGatewayResult.Failure("Booking not found")
        val result = paymentGateway.charge(totalAmount, method)
        val status = when {
            method == PaymentMethod.CASH -> PaymentStatus.CASH_SELECTED
            result is PaymentGatewayResult.Success -> PaymentStatus.SUCCESSFUL
            else -> PaymentStatus.FAILED
        }
        bookingsRef().document(bookingId).update(
            "payment", mapOf(
                "method" to method.name,
                "status" to status.name,
                "transactionId" to (result as? PaymentGatewayResult.Success)?.transactionId,
                "timestampMillis" to System.currentTimeMillis()
            )
        ).await()
        if (status == PaymentStatus.SUCCESSFUL || status == PaymentStatus.CASH_SELECTED) {
            transitionBooking(bookingId, booking.toStatus(), BookingStatus.CONFIRMED, booking.getString("bookedByUserId").orEmpty(), "PATIENT")
            assignPhlebotomist(bookingId)
        }
        return result
    }

    // ---------- Allocation & phlebotomist workflow ----------

    /** MVP allocator: picks any user with the PHLEBOTOMIST role. A real deployment would consider service area and load. */
    suspend fun assignPhlebotomist(bookingId: String) {
        val bookingRef = bookingsRef().document(bookingId)
        val booking = bookingRef.get().await()
        val phlebotomistDoc = firestore.collection("users").whereEqualTo("role", UserRole.PHLEBOTOMIST.name)
            .limit(1).get().await().documents.firstOrNull() ?: return

        bookingRef.update(
            mapOf(
                "assignedPhlebotomistUid" to phlebotomistDoc.id,
                "assignment" to mapOf(
                    "phlebotomistUid" to phlebotomistDoc.id,
                    "name" to (phlebotomistDoc.getString("name") ?: "Lab Assistant"),
                    "mobileNumber" to phlebotomistDoc.getString("mobileNumber").orEmpty(),
                    "professionalId" to phlebotomistDoc.getString("professionalId").orEmpty(),
                    "rating" to (phlebotomistDoc.getDouble("rating") ?: 0.0),
                    "status" to AssignmentStatus.ASSIGNED.name,
                    "assignedAtMillis" to System.currentTimeMillis()
                )
            )
        ).await()
        transitionBooking(bookingId, booking.toStatus(), BookingStatus.PHLEBOTOMIST_ASSIGNED, phlebotomistDoc.id, "PHLEBOTOMIST")
    }

    suspend fun respondToAssignment(bookingId: String, accept: Boolean) {
        val bookingRef = bookingsRef().document(bookingId)
        val booking = bookingRef.get().await()
        val assignment = booking.get("assignment") as? Map<*, *> ?: return
        val currentStatus = runCatching { AssignmentStatus.valueOf(assignment["status"] as? String ?: "") }.getOrNull() ?: return
        val newStatus = if (accept) AssignmentStatus.ACCEPTED else AssignmentStatus.REJECTED
        if (!AssignmentStatusMachine.canTransition(currentStatus, newStatus)) return

        bookingRef.update("assignment.status", newStatus.name, "assignment.respondedAtMillis", System.currentTimeMillis()).await()
        val ownerUid = booking.getString("patientAccountOwnerUserId") ?: return
        if (accept) {
            notificationRepository.notify(
                ownerUid, NotificationType.PHLEBOTOMIST_ACCEPTED,
                "Lab assistant confirmed", "Your sample collection is confirmed for ${booking.getString("scheduledTimeSlot")}.", bookingId
            )
        } else {
            assignPhlebotomist(bookingId)
        }
    }

    suspend fun updateAssignmentTravelStatus(bookingId: String, status: AssignmentStatus) {
        val bookingRef = bookingsRef().document(bookingId)
        val booking = bookingRef.get().await()
        val assignment = booking.get("assignment") as? Map<*, *> ?: return
        val currentStatus = runCatching { AssignmentStatus.valueOf(assignment["status"] as? String ?: "") }.getOrNull() ?: return
        if (!AssignmentStatusMachine.canTransition(currentStatus, status)) return
        val now = System.currentTimeMillis()

        val updates = mutableMapOf<String, Any>("assignment.status" to status.name)
        if (status == AssignmentStatus.ARRIVED) updates["assignment.arrivedAtMillis"] = now
        bookingRef.update(updates).await()

        val bookingStatus = when (status) {
            AssignmentStatus.ON_THE_WAY -> BookingStatus.PHLEBOTOMIST_ON_THE_WAY
            AssignmentStatus.ARRIVED -> BookingStatus.ARRIVED
            else -> return
        }
        val phlebotomistUid = assignment["phlebotomistUid"] as? String ?: ""
        transitionBooking(bookingId, booking.toStatus(), bookingStatus, phlebotomistUid, "PHLEBOTOMIST")
    }

    // ---------- Sample collection & chain of custody ----------

    suspend fun recordSampleCollected(bookingId: String, sampleType: String, collectionLocation: String) {
        val bookingRef = bookingsRef().document(bookingId)
        val booking = bookingRef.get().await()
        val assignment = booking.get("assignment") as? Map<*, *> ?: return
        val currentStatus = runCatching { AssignmentStatus.valueOf(assignment["status"] as? String ?: "") }.getOrNull() ?: return
        if (!AssignmentStatusMachine.canTransition(currentStatus, AssignmentStatus.SAMPLE_COLLECTED)) return
        val now = System.currentTimeMillis()
        val phlebotomistUid = assignment["phlebotomistUid"] as? String ?: ""

        bookingRef.update(
            mapOf(
                "sample" to mapOf("collectionTimeMillis" to now, "sampleType" to sampleType, "collectionLocation" to collectionLocation, "status" to SampleStatus.COLLECTED.name),
                "assignment.status" to AssignmentStatus.COMPLETED.name,
                "assignment.completedAtMillis" to now
            )
        ).await()
        transitionBooking(bookingId, booking.toStatus(), BookingStatus.SAMPLE_COLLECTED, phlebotomistUid, "PHLEBOTOMIST")
    }

    suspend fun markSampleInTransit(bookingId: String) {
        val bookingRef = bookingsRef().document(bookingId)
        val booking = bookingRef.get().await()
        val sample = booking.get("sample") as? Map<*, *> ?: return
        bookingRef.update("sample.status", SampleStatus.IN_TRANSIT.name).await()
        transitionBooking(bookingId, booking.toStatus(), BookingStatus.SAMPLE_IN_TRANSIT, (sample["collectorId"] as? String).orEmpty(), "PHLEBOTOMIST")
    }

    suspend fun labReceiveSample(bookingId: String, receivedByUserId: String) {
        val bookingRef = bookingsRef().document(bookingId)
        val booking = bookingRef.get().await()
        bookingRef.update("sample.status", SampleStatus.RECEIVED_AT_LAB.name).await()
        transitionBooking(bookingId, booking.toStatus(), BookingStatus.RECEIVED_AT_LAB, receivedByUserId, "LABORATORY")
    }

    suspend fun rejectSample(bookingId: String, reason: SampleRejectionReason, notes: String?, rejectedByUserId: String) {
        val bookingRef = bookingsRef().document(bookingId)
        val booking = bookingRef.get().await()
        bookingRef.update(mapOf("sample.status" to SampleStatus.REJECTED.name, "sample.rejectionReason" to reason.name)).await()
        transitionBooking(bookingId, booking.toStatus(), BookingStatus.REJECTED_RECOLLECTION_NEEDED, rejectedByUserId, "LABORATORY", notes)
        booking.getString("patientAccountOwnerUserId")?.let { ownerUid ->
            notificationRepository.notify(
                ownerUid, NotificationType.GENERAL,
                "Recollection needed", "The lab could not accept your sample (${reason.name.lowercase().replace('_', ' ')}). We will arrange a new collection.", bookingId
            )
        }
        assignPhlebotomist(bookingId)
    }

    suspend fun startProcessing(bookingId: String, labUserId: String) {
        val booking = bookingsRef().document(bookingId).get().await()
        transitionBooking(bookingId, booking.toStatus(), BookingStatus.PROCESSING, labUserId, "LABORATORY")
    }

    suspend fun uploadReport(bookingId: String, fileUri: String, verifiedByUserId: String) {
        val booking = bookingsRef().document(bookingId).get().await()
        @Suppress("UNCHECKED_CAST")
        val items = booking.get("items") as? List<Map<String, Any?>> ?: emptyList()
        firestore.collection("reports").document("RPT-$bookingId").set(
            mapOf(
                "bookingId" to bookingId,
                "patientId" to booking.getString("patientId").orEmpty(),
                "patientAccountOwnerUserId" to booking.getString("patientAccountOwnerUserId").orEmpty(),
                "laboratoryId" to booking.getString("laboratoryId").orEmpty(),
                "laboratoryName" to booking.getString("laboratoryName").orEmpty(),
                "investigationNames" to items.map { it["name"] as? String ?: "" },
                "fileUri" to fileUri,
                "status" to ReportStatus.READY.name,
                "generatedAtMillis" to System.currentTimeMillis(),
                "verifiedByUserId" to verifiedByUserId
            )
        ).await()
        transitionBooking(bookingId, booking.toStatus(), BookingStatus.REPORT_READY, verifiedByUserId, "LABORATORY")
    }

    suspend fun markReportDelivered(bookingId: String) {
        val booking = bookingsRef().document(bookingId).get().await()
        val reportRef = firestore.collection("reports").document("RPT-$bookingId")
        val report = reportRef.get().await()
        if (!report.exists() || report.getString("status") == ReportStatus.DELIVERED.name) return
        reportRef.update("status", ReportStatus.DELIVERED.name, "deliveredAtMillis", System.currentTimeMillis()).await()
        transitionBooking(bookingId, booking.toStatus(), BookingStatus.REPORT_DELIVERED, booking.getString("bookedByUserId").orEmpty(), "PATIENT")
    }

    suspend fun cancelBooking(bookingId: String, reason: String, cancelledByUserId: String, byLab: Boolean) {
        val bookingRef = bookingsRef().document(bookingId)
        val booking = bookingRef.get().await()
        val currentStatus = booking.toStatus()
        if (!BookingStatusMachine.canCancel(currentStatus)) return
        val target = if (byLab) BookingStatus.CANCELLED_BY_LAB else BookingStatus.CANCELLED_BY_PATIENT
        bookingRef.update(mapOf("status" to target.name, "cancellationReason" to reason, "updatedAtMillis" to System.currentTimeMillis())).await()
        recordTrackingEvent(bookingId, target.name, cancelledByUserId, if (byLab) "LABORATORY" else "PATIENT", notes = reason)
    }

    // ---------- Reads ----------

    fun observeBookingsForOwner(ownerUserId: String): Flow<List<Booking>> =
        observeQuery(bookingsRef().whereEqualTo("patientAccountOwnerUserId", ownerUserId))

    fun observeBookingsForLab(laboratoryId: String): Flow<List<Booking>> =
        observeQuery(bookingsRef().whereEqualTo("laboratoryId", laboratoryId))

    fun observeActiveForPhlebotomist(phlebotomistUid: String): Flow<List<Booking>> = callbackFlow {
        val activeStatuses = listOf(
            BookingStatus.PHLEBOTOMIST_ASSIGNED.name, BookingStatus.PHLEBOTOMIST_ON_THE_WAY.name, BookingStatus.ARRIVED.name
        )
        val registration = bookingsRef()
            .whereEqualTo("assignedPhlebotomistUid", phlebotomistUid)
            .whereIn("status", activeStatuses)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                trySend(snapshot?.documents.orEmpty().mapNotNull { it.toBooking() })
            }
        awaitClose { registration.remove() }
    }

    fun observeBooking(bookingId: String): Flow<Booking?> = callbackFlow {
        val registration = bookingsRef().document(bookingId).addSnapshotListener { snapshot, error ->
            if (error != null) {
                close(error)
                return@addSnapshotListener
            }
            trySend(snapshot?.toBooking())
        }
        awaitClose { registration.remove() }
    }

    fun observeTrackingEvents(bookingId: String): Flow<List<TrackingEvent>> = callbackFlow {
        val registration = trackingEventsOf(bookingId).orderBy("timestampMillis").addSnapshotListener { snapshot, error ->
            if (error != null) {
                close(error)
                return@addSnapshotListener
            }
            trySend(
                snapshot?.documents.orEmpty().map { doc ->
                    TrackingEvent(
                        status = doc.getString("status").orEmpty(),
                        timestampMillis = doc.getLong("timestampMillis") ?: 0L,
                        actorRole = doc.getString("actorRole").orEmpty(),
                        notes = doc.getString("notes")
                    )
                }
            )
        }
        awaitClose { registration.remove() }
    }

    fun observeAssignment(bookingId: String): Flow<Assignment?> = callbackFlow {
        val registration = bookingsRef().document(bookingId).addSnapshotListener { snapshot, error ->
            if (error != null) {
                close(error)
                return@addSnapshotListener
            }
            val assignment = snapshot?.get("assignment") as? Map<*, *>
            if (assignment == null) {
                trySend(null)
            } else {
                val status = runCatching { AssignmentStatus.valueOf(assignment["status"] as? String ?: "") }.getOrDefault(AssignmentStatus.UNASSIGNED)
                trySend(
                    Assignment(
                        id = "${snapshot.id}-assignment",
                        bookingId = snapshot.id,
                        phlebotomist = PhlebotomistProfile(
                            id = assignment["phlebotomistUid"] as? String ?: "",
                            name = assignment["name"] as? String ?: "Unassigned",
                            mobileNumber = assignment["mobileNumber"] as? String ?: "",
                            professionalId = assignment["professionalId"] as? String ?: "",
                            rating = (assignment["rating"] as? Double)?.toFloat() ?: 0f
                        ),
                        status = status
                    )
                )
            }
        }
        awaitClose { registration.remove() }
    }

    fun observeAllBookings(): Flow<List<Booking>> = observeQuery(bookingsRef())

    // ---------- Internal helpers ----------

    private fun observeQuery(query: com.google.firebase.firestore.Query): Flow<List<Booking>> = callbackFlow {
        val registration = query.addSnapshotListener { snapshot, error ->
            if (error != null) {
                close(error)
                return@addSnapshotListener
            }
            trySend(snapshot?.documents.orEmpty().mapNotNull { it.toBooking() })
        }
        awaitClose { registration.remove() }
    }

    private suspend fun nextBookingId(): String {
        val year = Year.now().value
        val counterRef = firestore.collection("counters").document("BOOK-$year")
        val next = firestore.runTransaction { txn ->
            val current = txn.get(counterRef).getLong("value") ?: 0L
            val updated = current + 1
            txn.set(counterRef, mapOf("value" to updated))
            updated
        }.await()
        return "BOOK-$year-${next.toString().padStart(6, '0')}"
    }

    private suspend fun transitionBooking(bookingId: String, from: BookingStatus, to: BookingStatus, actorId: String, actorRole: String, notes: String? = null) {
        if (!BookingStatusMachine.canTransition(from, to)) return
        bookingsRef().document(bookingId).update("status", to.name, "updatedAtMillis", System.currentTimeMillis()).await()
        recordTrackingEvent(bookingId, to.name, actorId, actorRole, notes)
    }

    private suspend fun recordTrackingEvent(bookingId: String, status: String, actorId: String, actorRole: String, notes: String? = null) {
        trackingEventsOf(bookingId).add(
            mapOf(
                "status" to status,
                "timestampMillis" to System.currentTimeMillis(),
                "actorId" to actorId,
                "actorRole" to actorRole,
                "notes" to notes
            )
        ).await()
    }
}

private fun DocumentSnapshot.toStatus(): BookingStatus =
    runCatching { BookingStatus.valueOf(getString("status") ?: "") }.getOrDefault(BookingStatus.PENDING_PAYMENT)

private fun DocumentSnapshot.toBooking(): Booking? {
    if (!exists()) return null
    @Suppress("UNCHECKED_CAST")
    val items = get("items") as? List<Map<String, Any?>> ?: emptyList()
    return Booking(
        id = id,
        patientId = getString("patientId").orEmpty(),
        patientName = getString("patientName")?.ifBlank { null } ?: "Patient",
        laboratoryId = getString("laboratoryId").orEmpty(),
        laboratoryName = getString("laboratoryName") ?: "Laboratory",
        addressLabel = getString("addressLabel").orEmpty(),
        addressLine = getString("addressLine").orEmpty(),
        addressLatitude = getDouble("addressLatitude"),
        addressLongitude = getDouble("addressLongitude"),
        scheduledDate = getString("scheduledDate")?.let { runCatching { LocalDate.parse(it) }.getOrNull() } ?: LocalDate.now(),
        scheduledTimeSlot = getString("scheduledTimeSlot").orEmpty(),
        status = toStatus(),
        items = items.map { item ->
            BookingItem(
                Investigation(
                    id = item["investigationId"] as? String ?: "",
                    name = item["name"] as? String ?: "",
                    description = item["description"] as? String ?: "",
                    category = item["category"] as? String ?: "",
                    sampleType = item["sampleType"] as? String ?: "",
                    preparationInstructions = item["preparationInstructions"] as? String ?: "",
                    reportTurnaroundHours = (item["reportTurnaroundHours"] as? Long)?.toInt() ?: 0
                ),
                price = (item["price"] as? Double) ?: 0.0
            )
        },
        totalAmount = getDouble("totalAmount") ?: 0.0,
        phlebotomistId = getString("assignedPhlebotomistUid"),
        createdAtMillis = getLong("createdAtMillis") ?: 0L
    )
}
