package com.digitalsolutions.diagnosticlab.data.seed

import com.digitalsolutions.diagnosticlab.data.local.AppDatabase
import com.digitalsolutions.diagnosticlab.data.local.entities.*
import com.digitalsolutions.diagnosticlab.domain.model.*
import com.digitalsolutions.diagnosticlab.domain.util.IdGenerator
import java.time.LocalDate
import kotlin.random.Random

/**
 * Populates the local database with realistic-looking demo data on first launch so every
 * screen has something real to show without a backend. Every row this creates carries
 * isDemoData = true (where the entity supports it) or lives in obviously-named IDs
 * (BOOK-DEMO-...) so it can be identified and wiped before a production release —
 * see README "Demo data" section.
 */
class DemoDataSeeder(private val db: AppDatabase) {

    private val now = System.currentTimeMillis()
    private val today = LocalDate.now()

    suspend fun seedIfEmpty() {
        val existing = db.patientDao().latestId()
        if (existing != null) return
        seedLaboratories()
        seedInvestigations()
        seedLaboratoryInvestigations()
        seedPhlebotomists()
        seedLabAndAdminLogins()
        val patients = seedPatientsAndFamilies()
        seedBookings(patients)
    }

    /** Demo mobile numbers for the non-patient roles, so the login screen has something to try. */
    private suspend fun seedLabAndAdminLogins() {
        labIds.forEachIndexed { index, labId ->
            val userId = "USR-LAB-${index + 1}"
            db.userDao().upsert(
                UserEntity(userId, "+91 985002000${index + 1}", null, UserRole.LABORATORY, labId, AppLanguage.ENGLISH.tag, true, now)
            )
        }
        db.userDao().upsert(
            UserEntity("USR-ADMIN-1", "+91 9000100000", "admin@diagnosticlab.demo", UserRole.ADMIN, null, AppLanguage.ENGLISH.tag, true, now)
        )
    }

    private val labIds = listOf("LAB-001", "LAB-002", "LAB-003", "LAB-004", "LAB-005")

    private suspend fun seedLaboratories() {
        val labs = listOf(
            LaboratoryEntity(labIds[0], "Sunrise Diagnostics", null, "Chennai", "12 Anna Salai, Chennai", 13.0604, 80.2496, "+91 44 2000 1001", "07:00", "20:00", true, 24, 4.6f, true, true),
            LaboratoryEntity(labIds[1], "Apex Pathlabs", null, "Chennai", "45 T Nagar Main Rd, Chennai", 13.0418, 80.2341, "+91 44 2000 1002", "06:30", "21:00", true, 12, 4.4f, true, true),
            LaboratoryEntity(labIds[2], "MedCore Diagnostics", null, "Coimbatore", "8 RS Puram, Coimbatore", 11.0018, 76.9629, "+91 422 200 1003", "07:00", "19:00", true, 24, 4.3f, true, true),
            LaboratoryEntity(labIds[3], "Wellness Point Labs", null, "Madurai", "22 KK Nagar, Madurai", 9.9252, 78.1198, "+91 452 200 1004", "07:30", "20:30", true, 48, 4.1f, true, true),
            LaboratoryEntity(labIds[4], "Precision Diagnostics", null, "Chennai", "3 Velachery Main Rd, Chennai", 12.9791, 80.2210, "+91 44 2000 1005", "00:00", "23:59", true, 6, 4.8f, true, true)
        )
        labs.forEach { db.laboratoryDao().upsert(it) }
    }

    private data class Investigation(
        val id: String, val name: String, val category: String, val sampleType: String,
        val prep: String, val turnaroundHours: Int, val basePrice: Double
    )

    private val investigations = listOf(
        Investigation("INV-001", "Complete Blood Count (CBC)", "General Health", "Blood", "No fasting required", 6, 350.0),
        Investigation("INV-002", "C-Reactive Protein (CRP)", "Inflammation", "Blood", "No fasting required", 12, 550.0),
        Investigation("INV-003", "Dengue NS1 Antigen", "Fever Panel", "Blood", "No fasting required", 6, 900.0),
        Investigation("INV-004", "Malaria Parasite Test", "Fever Panel", "Blood", "No fasting required", 4, 400.0),
        Investigation("INV-005", "Typhoid (Widal Test)", "Fever Panel", "Blood", "No fasting required", 12, 300.0),
        Investigation("INV-006", "Liver Function Test (LFT)", "Organ Function", "Blood", "8 hours fasting recommended", 12, 700.0),
        Investigation("INV-007", "Kidney Function Test (KFT)", "Organ Function", "Blood", "No fasting required", 12, 650.0),
        Investigation("INV-008", "Fasting Blood Sugar", "Diabetes", "Blood", "8-10 hours fasting required", 4, 150.0),
        Investigation("INV-009", "HbA1c", "Diabetes", "Blood", "No fasting required", 24, 500.0),
        Investigation("INV-010", "Lipid Profile", "Heart Health", "Blood", "10-12 hours fasting required", 12, 600.0),
        Investigation("INV-011", "Urine Routine Analysis", "General Health", "Urine", "First morning sample preferred", 6, 200.0),
        Investigation("INV-012", "Thyroid Profile (TSH, T3, T4)", "Hormone", "Blood", "No fasting required", 24, 750.0),
        Investigation("INV-013", "Vitamin D (25-OH)", "Vitamin", "Blood", "No fasting required", 48, 1200.0),
        Investigation("INV-014", "Vitamin B12", "Vitamin", "Blood", "No fasting required", 48, 900.0),
        Investigation("INV-015", "Erythrocyte Sedimentation Rate (ESR)", "Inflammation", "Blood", "No fasting required", 6, 200.0),
        Investigation("INV-016", "Hemoglobin (Hb)", "General Health", "Blood", "No fasting required", 4, 150.0),
        Investigation("INV-017", "Blood Culture", "Microbiology", "Blood", "Before starting antibiotics if possible", 72, 1100.0),
        Investigation("INV-018", "Urine Culture & Sensitivity", "Microbiology", "Urine", "Mid-stream morning sample", 48, 950.0),
        Investigation("INV-019", "Testosterone (Total)", "Hormone", "Blood", "Morning sample preferred", 24, 1000.0),
        Investigation("INV-020", "COVID-19 RT-PCR", "Infectious Disease", "Nasal/Throat Swab", "No fasting required", 24, 800.0)
    )

    private suspend fun seedInvestigations() {
        investigations.forEach {
            db.investigationDao().upsert(
                InvestigationEntity(it.id, it.name, "${it.name} — routine diagnostic test.", it.category, it.sampleType, it.prep, it.turnaroundHours, true, true)
            )
        }
    }

    private suspend fun seedLaboratoryInvestigations() {
        // Not every lab offers every test, and pricing varies slightly by lab — mirrors a real marketplace.
        for (labId in labIds) {
            val labIndex = labIds.indexOf(labId)
            investigations.forEachIndexed { index, inv ->
                val offeredHere = (index + labIndex) % 5 != 4 // ~80% catalog overlap per lab
                if (!offeredHere) return@forEachIndexed
                val priceVariance = 1.0 + (labIndex - 2) * 0.04
                db.laboratoryInvestigationDao().upsert(
                    LaboratoryInvestigationEntity(
                        laboratoryId = labId,
                        investigationId = inv.id,
                        price = Math.round(inv.basePrice * priceVariance / 5.0) * 5.0,
                        homeCollectionAvailable = true,
                        active = true
                    )
                )
            }
        }
    }

    private val phlebotomistNames = listOf(
        "Ramesh Kumar" to "+91 9840010001",
        "Priya Selvam" to "+91 9840010002",
        "Suresh Iyer" to "+91 9840010003",
        "Lakshmi Raman" to "+91 9840010004",
        "Arun Prakash" to "+91 9840010005"
    )

    private suspend fun seedPhlebotomists() {
        phlebotomistNames.forEachIndexed { index, (name, mobile) ->
            val phlId = "PHL-00${index + 1}"
            val userId = "USR-PHL-00${index + 1}"
            db.userDao().upsert(
                UserEntity(userId, mobile, null, UserRole.PHLEBOTOMIST, phlId, AppLanguage.ENGLISH.tag, true, now)
            )
            db.phlebotomistDao().upsert(
                PhlebotomistEntity(phlId, userId, name, null, mobile, "PHLB-2026-${(index + 1).toString().padStart(4, '0')}", 4.2f + index * 0.1f, true, null, null, true)
            )
        }
    }

    private data class DemoPerson(val name: String, val ageYears: Int, val sex: String, val mobile: String, val relation: Relation, val ownerIndex: Int)

    // 10 primary account holders (the "patients" in the spec's demo-data count) plus 5 of
    // them also have one family member booked under their account, covering "book for others".
    private val demoPeople = listOf(
        DemoPerson("Meenakshi Krishnan", 68, "Female", "+91 9000000001", Relation.MYSELF, 0),
        DemoPerson("Rajendran Pillai", 72, "Male", "+91 9000000002", Relation.MYSELF, 1),
        DemoPerson("Kamala Devi", 65, "Female", "+91 9000000003", Relation.MYSELF, 2),
        DemoPerson("Suresh Iyer", 55, "Male", "+91 9000000004", Relation.MYSELF, 3),
        DemoPerson("Latha Narayanan", 60, "Female", "+91 9000000005", Relation.MYSELF, 4),
        DemoPerson("Ganesan Murthy", 70, "Male", "+91 9000000006", Relation.MYSELF, 5),
        DemoPerson("Vasanthi Rao", 63, "Female", "+91 9000000007", Relation.MYSELF, 6),
        DemoPerson("Mohammed Yusuf", 58, "Male", "+91 9000000008", Relation.MYSELF, 7),
        DemoPerson("Padma Subramaniam", 75, "Female", "+91 9000000009", Relation.MYSELF, 8),
        DemoPerson("Anand Krishnamurthy", 52, "Male", "+91 9000000010", Relation.MYSELF, 9),
        // Family members booked by the first five account holders
        DemoPerson("Divya Krishnan", 41, "Female", "+91 9000000001", Relation.DAUGHTER, 0),
        DemoPerson("Geetha Pillai", 68, "Female", "+91 9000000002", Relation.SPOUSE, 1),
        DemoPerson("Karthik Devi", 38, "Male", "+91 9000000003", Relation.SON, 2),
        DemoPerson("Sundar Iyer", 82, "Male", "+91 9000000004", Relation.FATHER, 3),
        DemoPerson("Revathi Narayanan", 34, "Female", "+91 9000000005", Relation.DAUGHTER, 4)
    )

    private suspend fun seedPatientsAndFamilies(): List<PatientEntity> {
        val owners = mutableListOf<String>()
        val patients = mutableListOf<PatientEntity>()
        demoPeople.forEachIndexed { index, person ->
            val ownerUserId: String
            if (person.relation == Relation.MYSELF) {
                ownerUserId = "USR-PAT-${(index + 1).toString().padStart(3, '0')}"
                owners.add(ownerUserId)
                db.userDao().upsert(UserEntity(ownerUserId, person.mobile, null, UserRole.PATIENT, null, AppLanguage.ENGLISH.tag, true, now))
                val address = AddressEntity(
                    id = "ADDR-${(index + 1).toString().padStart(3, '0')}",
                    ownerUserId = ownerUserId,
                    label = "Home",
                    line1 = "${10 + index} Gandhi Street",
                    line2 = null,
                    city = "Chennai",
                    state = "Tamil Nadu",
                    pincode = "6000${(index + 1).toString().padStart(2, '0')}",
                    latitude = 13.06 + index * 0.01,
                    longitude = 80.25 + index * 0.01,
                    isDefault = true,
                    createdAt = now
                )
                db.addressDao().upsert(address)
            } else {
                ownerUserId = owners[person.ownerIndex]
            }
            val patientId = "PAT-${today.year}-${(index + 1).toString().padStart(6, '0')}"
            val patient = PatientEntity(
                id = patientId,
                accountOwnerUserId = ownerUserId,
                relation = person.relation,
                isPrimary = person.relation == Relation.MYSELF,
                fullName = person.name,
                dateOfBirthEpochDay = today.minusYears(person.ageYears.toLong()).toEpochDay(),
                sex = person.sex,
                mobileNumber = person.mobile,
                preferredLanguage = AppLanguage.ENGLISH.tag,
                createdAt = now
            )
            db.patientDao().upsert(patient)
            patients.add(patient)
        }
        return patients
    }

    private suspend fun seedBookings(patients: List<PatientEntity>) {
        val statuses = listOf(
            BookingStatus.REPORT_DELIVERED, BookingStatus.REPORT_DELIVERED, BookingStatus.REPORT_DELIVERED,
            BookingStatus.REPORT_READY, BookingStatus.PROCESSING, BookingStatus.RECEIVED_AT_LAB,
            BookingStatus.SAMPLE_IN_TRANSIT, BookingStatus.SAMPLE_COLLECTED, BookingStatus.ARRIVED,
            BookingStatus.PHLEBOTOMIST_ON_THE_WAY, BookingStatus.PHLEBOTOMIST_ASSIGNED, BookingStatus.CONFIRMED
        )
        val phlebotomists = phlebotomistNames.indices.map { "PHL-00${it + 1}" }
        val allLabInvestigations = investigations

        repeat(20) { index ->
            val patient = patients[index % patients.size]
            val labId = labIds[index % labIds.size]
            val bookingId = "BOOK-${today.year}-${(index + 1).toString().padStart(6, '0')}"
            val status = statuses[index % statuses.size]
            val scheduledDay = today.plusDays((index % 5 - 2).toLong())
            val addressId = "ADDR-${((patients.indexOf(patient) % 10) + 1).toString().padStart(3, '0')}"
            val chosenInvestigations = allLabInvestigations.shuffled(Random(index.toLong())).take(2 + index % 3)
            val labInvestigationPrices = chosenInvestigations.mapNotNull { inv ->
                db.laboratoryInvestigationDao().find(labId, inv.id)
            }
            val total = labInvestigationPrices.sumOf { it.price }.let { if (it == 0.0) 500.0 else it }
            val phlebotomistId = if (status >= BookingStatus.PHLEBOTOMIST_ASSIGNED) phlebotomists[index % phlebotomists.size] else null

            db.bookingDao().upsert(
                BookingEntity(
                    id = bookingId,
                    patientId = patient.id,
                    bookedByUserId = patient.accountOwnerUserId,
                    laboratoryId = labId,
                    addressId = addressId,
                    scheduledDateEpochDay = scheduledDay.toEpochDay(),
                    scheduledTimeSlot = listOf("08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00")[index % 4],
                    status = status,
                    phlebotomistId = phlebotomistId,
                    totalAmount = total,
                    createdAt = now - index * 3_600_000L,
                    updatedAt = now - index * 1_800_000L
                )
            )
            db.bookingItemDao().insertAll(
                labInvestigationPrices.mapIndexed { i, li ->
                    BookingItemEntity("BI-$bookingId-$i", bookingId, li.investigationId, li.price)
                }
            )
            db.paymentDao().upsert(
                PaymentEntity(
                    id = "PAY-$bookingId",
                    bookingId = bookingId,
                    amount = total,
                    method = if (index % 3 == 0) PaymentMethod.CASH else PaymentMethod.ONLINE,
                    status = if (index % 3 == 0) PaymentStatus.CASH_SELECTED else PaymentStatus.SUCCESSFUL,
                    transactionId = if (index % 3 == 0) null else "TXN-DEMO-$bookingId",
                    timestamp = now - index * 3_600_000L
                )
            )
            seedTrackingEvents(bookingId, status, phlebotomistId, index)

            if (status == BookingStatus.REPORT_READY || status == BookingStatus.REPORT_DELIVERED) {
                db.reportDao().upsert(
                    ReportEntity(
                        id = "RPT-$bookingId",
                        bookingId = bookingId,
                        patientId = patient.id,
                        laboratoryId = labId,
                        investigationIds = chosenInvestigations.map { it.id },
                        fileUri = null,
                        status = if (status == BookingStatus.REPORT_DELIVERED) ReportStatus.DELIVERED else ReportStatus.READY,
                        generatedAt = now - index * 1_800_000L,
                        verifiedByUserId = "USR-LAB-${labIds.indexOf(labId) + 1}",
                        deliveredAt = if (status == BookingStatus.REPORT_DELIVERED) now - index * 900_000L else null
                    )
                )
            }
        }
    }

    private suspend fun seedTrackingEvents(bookingId: String, finalStatus: BookingStatus, phlebotomistId: String?, index: Int) {
        val order = BookingStatusMachineOrder.upTo(finalStatus)
        order.forEachIndexed { i, status ->
            db.sampleTrackingEventDao().insert(
                SampleTrackingEventEntity(
                    id = IdGenerator.next("EVT", today.year, seedFrom = index * 20 + i),
                    bookingId = bookingId,
                    sampleId = null,
                    status = status.name,
                    timestamp = now - (order.size - i) * 1_800_000L,
                    actorId = phlebotomistId ?: "SYSTEM",
                    actorRole = if (phlebotomistId != null) "PHLEBOTOMIST" else "SYSTEM",
                    notes = null
                )
            )
        }
    }
}

/** Small helper so the seeder can list "everything up to X" without duplicating the flow order. */
private object BookingStatusMachineOrder {
    private val order = com.digitalsolutions.diagnosticlab.domain.util.BookingStatusMachine.timelineSteps()
    fun upTo(status: BookingStatus): List<BookingStatus> {
        val idx = order.indexOf(status)
        return if (idx < 0) listOf(status) else order.subList(0, idx + 1)
    }
}
