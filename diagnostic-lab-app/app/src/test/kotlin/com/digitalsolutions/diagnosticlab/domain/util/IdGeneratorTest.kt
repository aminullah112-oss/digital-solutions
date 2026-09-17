package com.digitalsolutions.diagnosticlab.domain.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class IdGeneratorTest {

    @Test
    fun `first id for a fresh prefix starts at 1`() {
        val id = IdGenerator.next("TEST-FRESH", currentYear = 2026)
        assertEquals("TEST-FRESH-2026-000001", id)
    }

    @Test
    fun `consecutive ids increment and stay unique`() {
        val prefix = "TEST-SEQ"
        val first = IdGenerator.next(prefix, currentYear = 2026)
        val second = IdGenerator.next(prefix, currentYear = 2026)
        val third = IdGenerator.next(prefix, currentYear = 2026)
        assertNotEquals(first, second)
        assertNotEquals(second, third)
        assertEquals(IdGenerator.sequenceOf(first) + 1, IdGenerator.sequenceOf(second))
        assertEquals(IdGenerator.sequenceOf(second) + 1, IdGenerator.sequenceOf(third))
    }

    @Test
    fun `seeding resumes numbering after an app restart instead of colliding`() {
        val prefix = "TEST-SEEDED"
        IdGenerator.seed(prefix, 2026, highestSequence = 41)
        val next = IdGenerator.next(prefix, currentYear = 2026)
        assertEquals(42, IdGenerator.sequenceOf(next))
    }

    @Test
    fun `sequenceOf extracts the trailing number from a formatted id`() {
        assertEquals(123, IdGenerator.sequenceOf("BOOK-2026-000123"))
        assertEquals(0, IdGenerator.sequenceOf("not-a-valid-id"))
    }

    @Test
    fun `different prefixes never collide even at the same sequence number`() {
        val patientId = IdGenerator.next("PAT-ISOLATED", currentYear = 2026)
        val bookingId = IdGenerator.next("BOOK-ISOLATED", currentYear = 2026)
        assertNotEquals(patientId, bookingId)
    }
}
