package com.digitalsolutions.diagnosticlab.data.repository

import com.digitalsolutions.diagnosticlab.domain.model.Address
import com.digitalsolutions.diagnosticlab.domain.model.Patient
import com.digitalsolutions.diagnosticlab.domain.model.Relation
import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await
import java.time.LocalDate

class PatientRepository(private val firestore: FirebaseFirestore) {

    private fun addressesOf(ownerUserId: String) =
        firestore.collection("users").document(ownerUserId).collection("addresses")

    fun observeFamily(ownerUserId: String): Flow<List<Patient>> = callbackFlow {
        val registration = firestore.collection("patients")
            .whereEqualTo("accountOwnerUserId", ownerUserId)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                trySend(snapshot?.documents.orEmpty().mapNotNull { it.toPatient() })
            }
        awaitClose { registration.remove() }
    }

    suspend fun getPatient(patientId: String): Patient? =
        firestore.collection("patients").document(patientId).get().await().toPatient()

    suspend fun updateProfile(
        patientId: String,
        fullName: String,
        dateOfBirth: LocalDate?,
        sex: String,
        email: String?,
        emergencyContact: String?
    ) {
        firestore.collection("patients").document(patientId).update(
            mapOf(
                "fullName" to fullName,
                "dateOfBirth" to dateOfBirth?.toString(),
                "sex" to sex,
                "email" to email,
                "emergencyContact" to emergencyContact
            )
        ).await()
    }

    suspend fun addFamilyMember(
        ownerUserId: String,
        fullName: String,
        dateOfBirth: LocalDate?,
        sex: String,
        relation: Relation,
        mobileNumber: String
    ): Patient {
        val ref = firestore.collection("patients").document()
        val data = mapOf(
            "id" to ref.id,
            "accountOwnerUserId" to ownerUserId,
            "relation" to relation.name,
            "isPrimary" to false,
            "fullName" to fullName,
            "dateOfBirth" to dateOfBirth?.toString(),
            "sex" to sex,
            "mobileNumber" to mobileNumber,
            "email" to null,
            "createdAtMillis" to System.currentTimeMillis()
        )
        ref.set(data).await()
        return Patient(ref.id, ownerUserId, relation, false, fullName, dateOfBirth, sex, mobileNumber, null)
    }

    fun observeAddresses(ownerUserId: String): Flow<List<Address>> = callbackFlow {
        val registration = addressesOf(ownerUserId).addSnapshotListener { snapshot, error ->
            if (error != null) {
                close(error)
                return@addSnapshotListener
            }
            trySend(snapshot?.documents.orEmpty().mapNotNull { it.toAddress() })
        }
        awaitClose { registration.remove() }
    }

    suspend fun saveAddress(
        ownerUserId: String,
        existingId: String?,
        label: String,
        line1: String,
        line2: String?,
        city: String,
        state: String,
        pincode: String,
        latitude: Double?,
        longitude: Double?,
        makeDefault: Boolean
    ): Address {
        val collection = addressesOf(ownerUserId)
        val ref = existingId?.let { collection.document(it) } ?: collection.document()

        if (makeDefault) {
            val existingDefaults = collection.whereEqualTo("isDefault", true).get().await()
            val batch = firestore.batch()
            existingDefaults.documents.forEach { batch.update(it.reference, "isDefault", false) }
            batch.set(
                ref,
                mapOf(
                    "id" to ref.id, "label" to label, "line1" to line1, "line2" to line2,
                    "city" to city, "state" to state, "pincode" to pincode,
                    "latitude" to latitude, "longitude" to longitude, "isDefault" to true,
                    "createdAtMillis" to System.currentTimeMillis()
                )
            )
            batch.commit().await()
        } else {
            ref.set(
                mapOf(
                    "id" to ref.id, "label" to label, "line1" to line1, "line2" to line2,
                    "city" to city, "state" to state, "pincode" to pincode,
                    "latitude" to latitude, "longitude" to longitude, "isDefault" to false,
                    "createdAtMillis" to System.currentTimeMillis()
                )
            ).await()
        }
        return Address(ref.id, label, line1, line2, city, state, pincode, latitude, longitude, makeDefault)
    }
}

private fun DocumentSnapshot.toPatient(): Patient? {
    if (!exists()) return null
    return Patient(
        id = id,
        accountOwnerUserId = getString("accountOwnerUserId") ?: return null,
        relation = runCatching { Relation.valueOf(getString("relation") ?: "OTHER") }.getOrDefault(Relation.OTHER),
        isPrimary = getBoolean("isPrimary") ?: false,
        fullName = getString("fullName").orEmpty(),
        dateOfBirth = getString("dateOfBirth")?.let { runCatching { LocalDate.parse(it) }.getOrNull() },
        sex = getString("sex").orEmpty(),
        mobileNumber = getString("mobileNumber").orEmpty(),
        email = getString("email")
    )
}

private fun DocumentSnapshot.toAddress(): Address? {
    if (!exists()) return null
    return Address(
        id = id,
        label = getString("label").orEmpty(),
        line1 = getString("line1").orEmpty(),
        line2 = getString("line2"),
        city = getString("city").orEmpty(),
        state = getString("state").orEmpty(),
        pincode = getString("pincode").orEmpty(),
        latitude = getDouble("latitude"),
        longitude = getDouble("longitude"),
        isDefault = getBoolean("isDefault") ?: false
    )
}
