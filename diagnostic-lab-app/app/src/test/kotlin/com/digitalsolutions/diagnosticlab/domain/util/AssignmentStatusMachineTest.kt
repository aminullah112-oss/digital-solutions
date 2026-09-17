package com.digitalsolutions.diagnosticlab.domain.util

import com.digitalsolutions.diagnosticlab.domain.model.AssignmentStatus
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AssignmentStatusMachineTest {

    @Test
    fun `a fresh assignment can only be accepted or rejected`() {
        assertTrue(AssignmentStatusMachine.canTransition(AssignmentStatus.ASSIGNED, AssignmentStatus.ACCEPTED))
        assertTrue(AssignmentStatusMachine.canTransition(AssignmentStatus.ASSIGNED, AssignmentStatus.REJECTED))
        assertFalse(AssignmentStatusMachine.canTransition(AssignmentStatus.ASSIGNED, AssignmentStatus.ARRIVED))
    }

    @Test
    fun `a rejected assignment can be re-offered to someone else`() {
        assertTrue(AssignmentStatusMachine.canTransition(AssignmentStatus.REJECTED, AssignmentStatus.ASSIGNED))
    }

    @Test
    fun `travel statuses only move forward one step at a time`() {
        assertTrue(AssignmentStatusMachine.canTransition(AssignmentStatus.ACCEPTED, AssignmentStatus.ON_THE_WAY))
        assertTrue(AssignmentStatusMachine.canTransition(AssignmentStatus.ON_THE_WAY, AssignmentStatus.ARRIVED))
        assertFalse(AssignmentStatusMachine.canTransition(AssignmentStatus.ACCEPTED, AssignmentStatus.ARRIVED))
    }

    @Test
    fun `a completed assignment is terminal`() {
        AssignmentStatus.values().forEach { target ->
            assertFalse(AssignmentStatusMachine.canTransition(AssignmentStatus.COMPLETED, target))
        }
    }
}
