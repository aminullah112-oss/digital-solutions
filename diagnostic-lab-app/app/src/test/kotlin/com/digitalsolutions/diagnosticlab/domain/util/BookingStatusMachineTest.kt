package com.digitalsolutions.diagnosticlab.domain.util

import com.digitalsolutions.diagnosticlab.domain.model.BookingStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Locks down the chain-of-custody rules from spec section 16 so a future refactor can't
 * accidentally let a booking skip a step (e.g. going straight from CONFIRMED to
 * REPORT_READY) or resurrect a cancelled booking.
 */
class BookingStatusMachineTest {

    @Test
    fun `the full forward journey is allowed one step at a time`() {
        val steps = BookingStatusMachine.timelineSteps()
        for (i in 0 until steps.lastIndex) {
            assertTrue("${steps[i]} -> ${steps[i + 1]} should be allowed", BookingStatusMachine.canTransition(steps[i], steps[i + 1]))
        }
    }

    @Test
    fun `skipping a step is rejected`() {
        assertFalse(BookingStatusMachine.canTransition(BookingStatus.CONFIRMED, BookingStatus.SAMPLE_COLLECTED))
        assertFalse(BookingStatusMachine.canTransition(BookingStatus.PENDING_PAYMENT, BookingStatus.REPORT_READY))
    }

    @Test
    fun `going backwards is rejected`() {
        assertFalse(BookingStatusMachine.canTransition(BookingStatus.SAMPLE_COLLECTED, BookingStatus.CONFIRMED))
    }

    @Test
    fun `cancellation is only allowed before the sample is collected`() {
        assertTrue(BookingStatusMachine.canCancel(BookingStatus.CONFIRMED))
        assertTrue(BookingStatusMachine.canCancel(BookingStatus.PHLEBOTOMIST_ON_THE_WAY))
        assertFalse(BookingStatusMachine.canCancel(BookingStatus.SAMPLE_COLLECTED))
        assertFalse(BookingStatusMachine.canCancel(BookingStatus.REPORT_DELIVERED))
    }

    @Test
    fun `a terminal booking never accepts another transition`() {
        assertFalse(BookingStatusMachine.canTransition(BookingStatus.REPORT_DELIVERED, BookingStatus.PROCESSING))
        assertFalse(BookingStatusMachine.canTransition(BookingStatus.CANCELLED_BY_PATIENT, BookingStatus.CONFIRMED))
    }

    @Test
    fun `a rejected sample can only be re-routed through a fresh phlebotomist assignment`() {
        assertTrue(BookingStatusMachine.canTransition(BookingStatus.RECEIVED_AT_LAB, BookingStatus.REJECTED_RECOLLECTION_NEEDED))
        assertTrue(BookingStatusMachine.canTransition(BookingStatus.REJECTED_RECOLLECTION_NEEDED, BookingStatus.PHLEBOTOMIST_ASSIGNED))
        assertFalse(BookingStatusMachine.canTransition(BookingStatus.REJECTED_RECOLLECTION_NEEDED, BookingStatus.REPORT_READY))
    }

    @Test
    fun `nextStep returns null once the journey is complete`() {
        assertEquals(BookingStatus.CONFIRMED, BookingStatusMachine.nextStep(BookingStatus.PENDING_PAYMENT))
        assertEquals(null, BookingStatusMachine.nextStep(BookingStatus.REPORT_DELIVERED))
    }
}
