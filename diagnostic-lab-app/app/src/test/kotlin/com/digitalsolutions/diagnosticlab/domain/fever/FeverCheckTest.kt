package com.digitalsolutions.diagnosticlab.domain.fever

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FeverCheckTest {

    private fun base(
        age: AgeGroup = AgeGroup.ADULT,
        duration: FeverDuration = FeverDuration.D1_2,
        pattern: FeverPattern = FeverPattern.CONTINUOUS,
        conditions: Set<HealthCondition> = emptySet(),
        symptoms: Set<Symptom> = emptySet(),
        exposures: Set<Exposure> = emptySet(),
        warnings: Set<WarningSign> = emptySet()
    ) = FeverAnswers(age, Sex.MALE, conditions, duration, pattern, symptoms, exposures, warnings)

    private fun FeverAssessment.test(name: String) = tests.firstOrNull { it.name.contains(name, ignoreCase = true) }

    @Test
    fun plainShortFeverIsHomeCareWithOnlyCbc() {
        val r = assess(base())
        assertEquals(Urgency.HOME_CARE, r.urgency)
        assertEquals(listOf("Complete Blood Count (CBC)"), r.tests.map { it.name })
    }

    @Test
    fun infantIsAlwaysAnEmergency() {
        assertEquals(Urgency.EMERGENCY, assess(base(age = AgeGroup.INFANT)).urgency)
    }

    @Test
    fun anyWarningSignIsAnEmergency() {
        val r = assess(base(warnings = setOf(WarningSign.BLEEDING)))
        assertEquals(Urgency.EMERGENCY, r.urgency)
    }

    @Test
    fun pregnancyIsSeenTheSameDay() {
        val r = assess(base(conditions = setOf(HealthCondition.PREGNANT)))
        assertEquals(Urgency.SAME_DAY, r.urgency)
    }

    @Test
    fun feverOfSixDaysOrMoreIsSeenTheSameDay() {
        assertEquals(Urgency.SAME_DAY, assess(base(duration = FeverDuration.D6_7)).urgency)
    }

    @Test
    fun chillsMeansMalariaTestIsEssential() {
        val r = assess(base(pattern = FeverPattern.CHILLS))
        assertEquals(TestPriority.ESSENTIAL, r.test("Malaria")?.priority)
    }

    @Test
    fun earlyDengueSymptomsAskForNs1() {
        val r = assess(base(symptoms = setOf(Symptom.BODY_PAIN), exposures = setOf(Exposure.DENGUE_AREA)))
        assertEquals(TestPriority.ESSENTIAL, r.test("NS1")?.priority)
        assertTrue("INV-003" in r.bookableIds)
    }

    @Test
    fun ns1IsNotOfferedLateInTheFever() {
        val r = assess(base(duration = FeverDuration.D8_14, symptoms = setOf(Symptom.BODY_PAIN), exposures = setOf(Exposure.DENGUE_AREA)))
        assertEquals(null, r.test("NS1"))
        assertTrue(r.test("IgM / IgG") != null)
    }

    @Test
    fun floodWaterWithCalfPainSuggestsLeptospiraAndOrganTests() {
        val r = assess(base(duration = FeverDuration.D3_5, symptoms = setOf(Symptom.CALF_PAIN), exposures = setOf(Exposure.FLOOD_WATER)))
        assertEquals(TestPriority.ESSENTIAL, r.test("Leptospira")?.priority)
        assertTrue(r.test("Liver") != null)
        assertTrue(r.test("Creatinine") != null)
    }

    @Test
    fun urinarySymptomsSuggestUrineTests() {
        val r = assess(base(symptoms = setOf(Symptom.URINE_BURNING)))
        assertEquals(TestPriority.ESSENTIAL, r.test("Urine routine")?.priority)
        assertTrue(r.test("Urine culture") != null)
    }

    @Test
    fun widalIsNotSuggestedInTheFirstDays() {
        val r = assess(base(duration = FeverDuration.D3_5, pattern = FeverPattern.RISING))
        assertEquals(null, r.test("Widal"))
        assertTrue(r.test("Blood culture") != null)
    }

    @Test
    fun testsAreSortedMostImportantFirst() {
        val r = assess(base(duration = FeverDuration.OVER_14, symptoms = setOf(Symptom.COUGH_2W)))
        assertEquals(r.tests.sortedBy { it.priority.ordinal }, r.tests)
    }

    @Test
    fun doctorOnlyTestsAreNotBookable() {
        val r = assess(base(duration = FeverDuration.OVER_14))
        assertFalse("INV-017" in r.bookableIds)
    }
}
