package com.digitalsolutions.diagnosticlab.domain.util

import java.time.Year
import java.util.concurrent.atomic.AtomicInteger

/**
 * Generates human-readable IDs in the PREFIX-YYYY-NNNNNN shape used throughout the
 * product (PAT-2026-000001, BOOK-2026-000123, SMP-2026-000567, ...).
 *
 * Sequence numbers are seeded from the highest existing number for that prefix+year
 * (passed in by the caller from the DB) so restarts don't collide with existing rows.
 */
object IdGenerator {

    private val counters = mutableMapOf<String, AtomicInteger>()

    fun next(prefix: String, currentYear: Int = Year.now().value, seedFrom: Int = 0): String {
        val key = "$prefix-$currentYear"
        val counter = counters.getOrPut(key) { AtomicInteger(seedFrom) }
        val value = counter.incrementAndGet()
        return "$key-${value.toString().padStart(6, '0')}"
    }

    fun seed(prefix: String, currentYear: Int, highestSequence: Int) {
        val key = "$prefix-$currentYear"
        counters[key] = AtomicInteger(highestSequence)
    }

    /** Extracts the trailing sequence number from an id like PAT-2026-000042 -> 42. */
    fun sequenceOf(id: String): Int = id.substringAfterLast('-').toIntOrNull() ?: 0
}
