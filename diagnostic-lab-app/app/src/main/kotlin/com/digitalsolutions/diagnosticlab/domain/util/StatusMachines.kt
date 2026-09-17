package com.digitalsolutions.diagnosticlab.domain.util

import com.digitalsolutions.diagnosticlab.domain.model.AssignmentStatus
import com.digitalsolutions.diagnosticlab.domain.model.BookingStatus

/**
 * Encodes the chain-of-custody transitions from the spec (section 16) so every part of
 * the app enforces the same rules instead of setting status columns ad hoc.
 */
object BookingStatusMachine {

    private val forwardFlow = listOf(
        BookingStatus.PENDING_PAYMENT,
        BookingStatus.CONFIRMED,
        BookingStatus.PHLEBOTOMIST_ASSIGNED,
        BookingStatus.PHLEBOTOMIST_ON_THE_WAY,
        BookingStatus.ARRIVED,
        BookingStatus.SAMPLE_COLLECTED,
        BookingStatus.SAMPLE_IN_TRANSIT,
        BookingStatus.RECEIVED_AT_LAB,
        BookingStatus.PROCESSING,
        BookingStatus.REPORT_READY,
        BookingStatus.REPORT_DELIVERED
    )

    private val terminal = setOf(
        BookingStatus.REPORT_DELIVERED,
        BookingStatus.CANCELLED_BY_PATIENT,
        BookingStatus.CANCELLED_BY_LAB
    )

    fun isTerminal(status: BookingStatus) = status in terminal

    /** Cancellation is allowed any time before the sample has actually been collected. */
    fun canCancel(status: BookingStatus): Boolean {
        val index = forwardFlow.indexOf(status)
        return index in 0 until forwardFlow.indexOf(BookingStatus.SAMPLE_COLLECTED)
    }

    fun canTransition(from: BookingStatus, to: BookingStatus): Boolean {
        if (isTerminal(from)) return false
        if (to == BookingStatus.CANCELLED_BY_PATIENT || to == BookingStatus.CANCELLED_BY_LAB) {
            return canCancel(from)
        }
        if (to == BookingStatus.REJECTED_RECOLLECTION_NEEDED) {
            return from == BookingStatus.RECEIVED_AT_LAB
        }
        if (from == BookingStatus.REJECTED_RECOLLECTION_NEEDED) {
            return to == BookingStatus.PHLEBOTOMIST_ASSIGNED
        }
        val fromIndex = forwardFlow.indexOf(from)
        val toIndex = forwardFlow.indexOf(to)
        return fromIndex >= 0 && toIndex == fromIndex + 1
    }

    fun nextStep(from: BookingStatus): BookingStatus? {
        val index = forwardFlow.indexOf(from)
        return if (index in 0 until forwardFlow.lastIndex) forwardFlow[index + 1] else null
    }

    fun timelineSteps(): List<BookingStatus> = forwardFlow
}

object AssignmentStatusMachine {

    private val allowed = mapOf(
        AssignmentStatus.UNASSIGNED to setOf(AssignmentStatus.ASSIGNED),
        AssignmentStatus.ASSIGNED to setOf(AssignmentStatus.ACCEPTED, AssignmentStatus.REJECTED),
        AssignmentStatus.ACCEPTED to setOf(AssignmentStatus.ON_THE_WAY, AssignmentStatus.CANCELLED),
        AssignmentStatus.ON_THE_WAY to setOf(AssignmentStatus.ARRIVED, AssignmentStatus.CANCELLED),
        AssignmentStatus.ARRIVED to setOf(AssignmentStatus.SAMPLE_COLLECTED, AssignmentStatus.CANCELLED),
        AssignmentStatus.SAMPLE_COLLECTED to setOf(AssignmentStatus.COMPLETED),
        AssignmentStatus.REJECTED to setOf(AssignmentStatus.ASSIGNED),
        AssignmentStatus.COMPLETED to emptySet(),
        AssignmentStatus.CANCELLED to setOf(AssignmentStatus.ASSIGNED)
    )

    fun canTransition(from: AssignmentStatus, to: AssignmentStatus): Boolean =
        allowed[from]?.contains(to) == true
}
