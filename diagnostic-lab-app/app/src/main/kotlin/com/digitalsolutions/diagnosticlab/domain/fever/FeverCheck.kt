package com.digitalsolutions.diagnosticlab.domain.fever

/*
 * Fever Check: a questionnaire about a fever and the tests doctors commonly consider for it,
 * tuned for the exposures common in South India (flood water and rats, scrub-typhus country,
 * dengue, typhoid, malaria).
 *
 * This is deliberately rule-based, not a model: every suggestion traces to a rule below that a
 * doctor can read and correct, and nothing about the patient's answers leaves the phone. It
 * suggests TESTS, never a diagnosis. The rules are a starting point written for Dr. Sheela's
 * review; they should be treated as unreviewed until she signs them off, which is why the app
 * only shows the feature when config/features.feverCheckEnabled is true.
 */

enum class AgeGroup(val label: String) {
    INFANT("Under 1 year"), CHILD("1–5 years"), TEEN("6–17 years"), ADULT("18–59 years"), SENIOR("60 years or more")
}

enum class Sex(val label: String) { FEMALE("Female"), MALE("Male"), OTHER("Prefer not to say") }

enum class HealthCondition(val label: String) {
    DIABETES("Diabetes"),
    PREGNANT("Pregnant"),
    WEAK_IMMUNITY("Weak immunity (HIV, steroids, chemotherapy, transplant)"),
    ORGAN_DISEASE("Long-term kidney, liver or heart disease")
}

enum class FeverDuration(val label: String) {
    D1_2("1–2 days"), D3_5("3–5 days"), D6_7("6–7 days"), D8_14("8–14 days"), OVER_14("More than 14 days")
}

enum class FeverPattern(val label: String) {
    CONTINUOUS("Stays high through the day"),
    CHILLS("Comes and goes, with shivering or chills"),
    RISING("Rises a little higher each day"),
    NOT_SURE("Not sure")
}

enum class Symptom(val label: String) {
    HEADACHE("Headache"),
    BODY_PAIN("Severe body or joint pain"),
    EYE_PAIN("Pain behind the eyes"),
    RASH("Skin rash"),
    NAUSEA("Nausea or vomiting"),
    DIARRHOEA("Loose motions"),
    ABDOMEN("Stomach pain"),
    COUGH("Cough"),
    SORE_THROAT("Sore throat or cold"),
    COUGH_2W("Cough lasting more than 2 weeks"),
    URINE_BURNING("Burning while passing urine"),
    FLANK_PAIN("Pain in the lower back or side"),
    JAUNDICE("Yellow eyes or yellow urine"),
    RED_EYES("Red eyes"),
    CALF_PAIN("Painful calf muscles"),
    ESCHAR("Black scab or sore on the skin, swollen glands"),
    NIGHT_SWEATS("Night sweats or weight loss")
}

enum class Exposure(val label: String) {
    FLOOD_WATER("Walked through flood water, dirty water or paddy fields"),
    RODENTS("Rats or rat droppings at home or work"),
    BUSHES("Worked or walked in bushes, farms, grass or forest"),
    STREET_FOOD("Street food, outside food or untreated water"),
    MOSQUITOES("Mosquito bites, or water collecting near home"),
    DENGUE_AREA("Dengue or fever cases in my area or family"),
    ANIMALS("Contact with cattle, goats or raw milk"),
    MALARIA_TRAVEL("Recent travel to a place with malaria"),
    TB_CONTACT("Close contact with someone who has TB")
}

enum class WarningSign(val label: String) {
    BREATHING("Trouble breathing or chest pain"),
    CONFUSION("Confusion, extreme drowsiness or a fit"),
    VOMITING("Vomiting that won't stop, or can't keep fluids down"),
    BLEEDING("Bleeding from the gums or nose, or black stools"),
    LOW_URINE("Passing very little urine"),
    SEVERE_ABDOMEN("Severe stomach pain"),
    STIFF_NECK("Stiff neck, or strong dislike of light")
}

data class FeverAnswers(
    val age: AgeGroup? = null,
    val sex: Sex? = null,
    val conditions: Set<HealthCondition> = emptySet(),
    val duration: FeverDuration? = null,
    val pattern: FeverPattern? = null,
    val symptoms: Set<Symptom> = emptySet(),
    val exposures: Set<Exposure> = emptySet(),
    val warningSigns: Set<WarningSign> = emptySet()
)

/** Lowest ordinal is the most urgent. */
enum class Urgency(val title: String) {
    EMERGENCY("Get medical help now"),
    SAME_DAY("See a doctor today"),
    WITHIN_DAYS("See a doctor within a day or two"),
    HOME_CARE("Rest at home and watch closely")
}

/** Lowest ordinal is the most important. */
enum class TestPriority(val label: String) {
    ESSENTIAL("Essential"), RECOMMENDED("Recommended"), IF_DOCTOR_ADVISES("If your doctor advises")
}

data class TestAdvice(
    val name: String,
    val priority: TestPriority,
    val reasons: List<String>,
    val timing: String?,
    /** Investigation IDs in the app's catalogue (INV-xxx) that cover this test; empty when the
     * test isn't something the app can book yet. */
    val catalogIds: List<String>
)

data class FeverAssessment(
    val urgency: Urgency,
    val urgencyReasons: List<String>,
    val tests: List<TestAdvice>,
    val notes: List<String>
) {
    val bookableIds: Set<String>
        get() = tests.filter { it.priority != TestPriority.IF_DOCTOR_ADVISES }.flatMap { it.catalogIds }.toSet()
}

private class TestList {
    private val map = LinkedHashMap<String, TestAdvice>()

    fun add(name: String, priority: TestPriority, reason: String, timing: String? = null, ids: List<String> = emptyList()) {
        val existing = map[name]
        map[name] = if (existing == null) {
            TestAdvice(name, priority, listOf(reason), timing, ids)
        } else {
            existing.copy(
                priority = if (priority.ordinal < existing.priority.ordinal) priority else existing.priority,
                reasons = (existing.reasons + reason).distinct(),
                timing = existing.timing ?: timing
            )
        }
    }

    fun sorted(): List<TestAdvice> = map.values.sortedBy { it.priority.ordinal }
}

// Catalogue IDs, from the investigations the app already sells.
private const val CBC = "INV-001"
private const val CRP = "INV-002"
private const val DENGUE_NS1 = "INV-003"
private const val MALARIA = "INV-004"
private const val WIDAL = "INV-005"
private const val LFT = "INV-006"
private const val FASTING_SUGAR = "INV-008"
private const val URINE_ROUTINE = "INV-011"
private const val ESR = "INV-015"
private const val BLOOD_CULTURE = "INV-017"
private const val URINE_CULTURE = "INV-018"
private const val COVID_PCR = "INV-020"
private const val CREATININE = "INV-021"
private const val ELECTROLYTES = "INV-022"

fun assess(a: FeverAnswers): FeverAssessment {
    val duration = a.duration ?: FeverDuration.D1_2
    val days = duration.ordinal // 0: 1–2d, 1: 3–5d, 2: 6–7d, 3: 8–14d, 4: >14d
    val early = days <= FeverDuration.D3_5.ordinal
    val sx = a.symptoms
    val ex = a.exposures
    val pregnant = HealthCondition.PREGNANT in a.conditions
    val tests = TestList()

    // ---------- What the answers point towards ----------
    val dengueLikely = ex.any { it == Exposure.DENGUE_AREA || it == Exposure.MOSQUITOES } ||
        sx.any { it == Symptom.BODY_PAIN || it == Symptom.EYE_PAIN || it == Symptom.RASH }
    val dengueStrong = Exposure.DENGUE_AREA in ex || sx.any { it == Symptom.BODY_PAIN || it == Symptom.EYE_PAIN || it == Symptom.RASH }
    val malariaLikely = a.pattern == FeverPattern.CHILLS || Exposure.MALARIA_TRAVEL in ex
    val entericLikely = days >= FeverDuration.D3_5.ordinal &&
        (a.pattern == FeverPattern.RISING || Symptom.ABDOMEN in sx || Symptom.DIARRHOEA in sx || Exposure.STREET_FOOD in ex)
    val scrubLikely = days >= FeverDuration.D3_5.ordinal &&
        (Symptom.ESCHAR in sx || (Exposure.BUSHES in ex && sx.any { it == Symptom.RASH || it == Symptom.HEADACHE || it == Symptom.BODY_PAIN }))
    val leptoLikely = (Exposure.FLOOD_WATER in ex || Exposure.RODENTS in ex) &&
        sx.any { it == Symptom.BODY_PAIN || it == Symptom.CALF_PAIN || it == Symptom.RED_EYES || it == Symptom.JAUNDICE }
    val urineLikely = Symptom.URINE_BURNING in sx || Symptom.FLANK_PAIN in sx
    val chestLikely = Symptom.COUGH in sx || Symptom.SORE_THROAT in sx
    val tbLikely = Symptom.COUGH_2W in sx || Symptom.NIGHT_SWEATS in sx || Exposure.TB_CONTACT in ex

    // ---------- Tests ----------
    tests.add(
        "Complete Blood Count (CBC)", TestPriority.ESSENTIAL,
        "A first test for any fever: shows infection and the platelet count, which matters in dengue.",
        ids = listOf(CBC)
    )
    if (days >= FeverDuration.D3_5.ordinal) {
        tests.add("C-Reactive Protein (CRP)", TestPriority.RECOMMENDED, "Shows how much inflammation the body has.", ids = listOf(CRP))
    }
    if (days >= FeverDuration.D8_14.ordinal) {
        tests.add("ESR", TestPriority.RECOMMENDED, "Often raised in fever that lasts for weeks.", ids = listOf(ESR))
    }

    // Malaria
    if (malariaLikely) {
        tests.add(
            "Malaria parasite test", TestPriority.ESSENTIAL,
            "Fever that comes and goes with chills, or travel to a malaria area, needs malaria excluded.",
            ids = listOf(MALARIA)
        )
    } else if (Exposure.MOSQUITOES in ex && days <= FeverDuration.D6_7.ordinal) {
        tests.add("Malaria parasite test", TestPriority.RECOMMENDED, "Mosquito exposure with fever.", ids = listOf(MALARIA))
    }

    // Dengue
    if (dengueLikely && early) {
        tests.add(
            "Dengue NS1 antigen",
            if (dengueStrong) TestPriority.ESSENTIAL else TestPriority.RECOMMENDED,
            "Body or eye pain, rash, mosquitoes or dengue nearby in the first days of fever.",
            timing = "Works best in days 1–5 of fever",
            ids = listOf(DENGUE_NS1)
        )
    } else if (dengueLikely && dengueStrong && days >= FeverDuration.D6_7.ordinal) {
        tests.add(
            "Dengue IgM / IgG antibody test", TestPriority.RECOMMENDED,
            "NS1 becomes less reliable after day 5, so antibodies are checked instead.",
            timing = "After day 5 of fever"
        )
    }
    val dengueWarning = dengueLikely && Symptom.NAUSEA in sx && Symptom.ABDOMEN in sx
    if (dengueLikely && (Symptom.NAUSEA in sx || Symptom.ABDOMEN in sx)) {
        tests.add("Liver Function Test (LFT)", TestPriority.RECOMMENDED, "Dengue can affect the liver, which can cause vomiting and stomach pain.", ids = listOf(LFT))
    }

    // Typhoid
    if (entericLikely) {
        if (days <= FeverDuration.D6_7.ordinal) {
            tests.add(
                "Blood culture", TestPriority.RECOMMENDED,
                "The most reliable test for typhoid in the first week, before antibiotics are started.",
                timing = "Best in the first 7 days, before antibiotics",
                ids = listOf(BLOOD_CULTURE)
            )
        }
        if (days >= FeverDuration.D6_7.ordinal) {
            tests.add(
                "Widal test", TestPriority.RECOMMENDED,
                "A blood test for typhoid, usually positive from about day 7. It can be falsely positive, so your doctor reads it with the rest.",
                timing = "From about day 7 of fever",
                ids = listOf(WIDAL)
            )
        }
    }

    // Scrub typhus
    if (scrubLikely) {
        tests.add(
            "Scrub typhus IgM antibody (ELISA)",
            if (Symptom.ESCHAR in sx) TestPriority.ESSENTIAL else TestPriority.RECOMMENDED,
            "Fever for several days after walking in bushes or farmland, or with a black scab, can be scrub typhus.",
            timing = "Positive from about day 5–7"
        )
    }

    // Leptospirosis
    if (leptoLikely) {
        tests.add(
            "Leptospira IgM antibody test",
            if (sx.any { it == Symptom.CALF_PAIN || it == Symptom.RED_EYES || it == Symptom.JAUNDICE }) TestPriority.ESSENTIAL else TestPriority.RECOMMENDED,
            "Contact with flood water or rats, plus muscle pain, red eyes or jaundice, can be leptospirosis.",
            timing = "Positive from about day 5–7"
        )
        tests.add("Liver Function Test (LFT)", TestPriority.RECOMMENDED, "Leptospirosis can affect the liver.", ids = listOf(LFT))
        tests.add("Creatinine", TestPriority.RECOMMENDED, "Leptospirosis can affect the kidneys.", ids = listOf(CREATININE))
    }

    // Liver
    if (Symptom.JAUNDICE in sx) {
        tests.add("Liver Function Test (LFT)", TestPriority.ESSENTIAL, "Yellow eyes or urine with fever needs the liver checked.", ids = listOf(LFT))
        if (Exposure.STREET_FOOD in ex) {
            tests.add("Hepatitis A / E antibody tests", TestPriority.IF_DOCTOR_ADVISES, "Jaundice after outside food or untreated water.")
        }
    }

    // Urine
    if (urineLikely) {
        tests.add("Urine routine analysis", TestPriority.ESSENTIAL, "Burning urine or side pain with fever suggests a urine infection.", ids = listOf(URINE_ROUTINE))
        tests.add(
            "Urine culture & sensitivity", TestPriority.RECOMMENDED,
            "Finds the germ and the antibiotics that work. Best collected before antibiotics.", ids = listOf(URINE_CULTURE)
        )
    }

    // Chest and respiratory
    if (chestLikely) {
        tests.add("COVID-19 RT-PCR", TestPriority.RECOMMENDED, "Cough or sore throat with fever.", ids = listOf(COVID_PCR))
        tests.add("Influenza test", TestPriority.IF_DOCTOR_ADVISES, "Seasonal flu is common with cough and fever.")
    }
    if (Symptom.COUGH in sx && (Symptom.COUGH_2W in sx || days >= FeverDuration.D8_14.ordinal)) {
        tests.add("Chest X-ray", TestPriority.IF_DOCTOR_ADVISES, "For a cough that has lasted a long time.")
    }

    // Long-running fever and TB
    if (tbLikely) {
        tests.add(
            "TB tests (sputum AFB, CBNAAT)",
            if (Symptom.COUGH_2W in sx || Symptom.NIGHT_SWEATS in sx) TestPriority.RECOMMENDED else TestPriority.IF_DOCTOR_ADVISES,
            "Cough for more than two weeks, night sweats, weight loss, or contact with TB."
        )
        tests.add("ESR", TestPriority.RECOMMENDED, "Often raised in TB.", ids = listOf(ESR))
    }
    if (days >= FeverDuration.OVER_14.ordinal) {
        tests.add(
            "Further tests your doctor may add", TestPriority.IF_DOCTOR_ADVISES,
            "Fever for more than two weeks needs a doctor's full assessment. They may add blood culture, HIV, TB or thyroid tests."
        )
        tests.add("Blood culture", TestPriority.IF_DOCTOR_ADVISES, "For a fever that has lasted weeks.", ids = listOf(BLOOD_CULTURE))
    }

    // Joint pain and rash with mosquitoes: chikungunya
    if (Symptom.BODY_PAIN in sx && Exposure.MOSQUITOES in ex && days <= FeverDuration.D8_14.ordinal) {
        tests.add("Chikungunya antibody test", TestPriority.IF_DOCTOR_ADVISES, "Severe joint pain after mosquito exposure.")
    }

    // Kidneys and fluids
    val dehydrated = (Symptom.NAUSEA in sx && Symptom.DIARRHOEA in sx)
    if (dehydrated || a.age == AgeGroup.SENIOR || HealthCondition.ORGAN_DISEASE in a.conditions) {
        tests.add("Creatinine", TestPriority.RECOMMENDED, "Checks the kidneys when fluid loss, age or long-term illness raises the risk.", ids = listOf(CREATININE))
        tests.add("Electrolytes (Na, K, Cl)", TestPriority.RECOMMENDED, "Vomiting, loose motions or kidney disease can upset body salts.", ids = listOf(ELECTROLYTES))
    }

    // Diabetes
    if (HealthCondition.DIABETES in a.conditions) {
        tests.add("Fasting blood sugar", TestPriority.RECOMMENDED, "Infection can push blood sugar up, and fever is riskier with diabetes.", ids = listOf(FASTING_SUGAR))
    }

    // Pregnancy: keep to safe, basic checks; the doctor decides the rest.
    if (pregnant) {
        tests.add("Urine routine analysis", TestPriority.RECOMMENDED, "Urine infections are common and need treatment in pregnancy.", ids = listOf(URINE_ROUTINE))
    }

    // ---------- Urgency ----------
    val urgent = mutableListOf<Pair<Urgency, String>>()
    if (a.warningSigns.isNotEmpty()) {
        urgent += Urgency.EMERGENCY to "You ticked a warning sign: ${a.warningSigns.joinToString(", ") { it.label.lowercase() }}."
    }
    if (a.age == AgeGroup.INFANT) urgent += Urgency.EMERGENCY to "A fever in a baby under 1 year needs a doctor straight away."
    if (pregnant) urgent += Urgency.SAME_DAY to "Fever in pregnancy needs a doctor's review the same day."
    if (Symptom.JAUNDICE in sx) urgent += Urgency.SAME_DAY to "Yellow eyes or urine with fever needs a doctor today."
    if (days >= FeverDuration.D6_7.ordinal) urgent += Urgency.SAME_DAY to "Fever for 6 days or more needs a doctor's examination."
    if (a.age == AgeGroup.CHILD && days >= FeverDuration.D3_5.ordinal) urgent += Urgency.SAME_DAY to "A child under 6 with fever for 3 days or more should be seen today."
    val vulnerable = a.age == AgeGroup.SENIOR || HealthCondition.WEAK_IMMUNITY in a.conditions || HealthCondition.ORGAN_DISEASE in a.conditions
    if (vulnerable) {
        urgent += if (days >= FeverDuration.D3_5.ordinal) Urgency.SAME_DAY to "At your age or health condition, fever for 3 days or more should be seen today."
        else Urgency.WITHIN_DAYS to "At your age or health condition, see a doctor early even for a short fever."
    }
    if (dengueWarning) urgent += Urgency.SAME_DAY to "Vomiting with stomach pain during a possible dengue fever can be a warning sign."
    if (days == FeverDuration.D3_5.ordinal) urgent += Urgency.WITHIN_DAYS to "Fever for 3 days or more should be examined by a doctor."
    if (HealthCondition.DIABETES in a.conditions) urgent += Urgency.WITHIN_DAYS to "With diabetes, see a doctor early."
    val level = urgent.minByOrNull { it.first.ordinal }?.first ?: Urgency.HOME_CARE
    val urgencyReasons = if (level == Urgency.HOME_CARE) {
        listOf("Rest, drink plenty of fluids, and see a doctor if the fever lasts more than 3 days or any warning sign appears.")
    } else {
        urgent.filter { it.first == level }.map { it.second }.distinct()
    }

    // ---------- Notes ----------
    val notes = mutableListOf(
        "Take fever medicine only as your doctor or pharmacist advises. Never give aspirin to a child."
    )
    if (dengueLikely) {
        notes += "Until dengue is ruled out, avoid aspirin and ibuprofen-type painkillers. Paracetamol is the usual choice, and drink plenty of fluids."
    }
    if (entericLikely || scrubLikely || leptoLikely || urineLikely) {
        notes += "If possible, give blood and urine samples before starting antibiotics. Antibiotics taken first can hide the result."
    }
    if (pregnant) {
        notes += "Do not start any medicine in pregnancy without your doctor's advice."
    }

    return FeverAssessment(level, urgencyReasons, tests.sorted(), notes)
}
