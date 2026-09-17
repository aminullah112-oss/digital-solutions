package com.digitalsolutions.diagnosticlab.presentation.patient.family

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.digitalsolutions.diagnosticlab.data.repository.PatientRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.domain.model.Patient
import com.digitalsolutions.diagnosticlab.domain.model.Relation
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.time.LocalDate

class FamilyViewModel(
    private val patientRepository: PatientRepository,
    private val sessionManager: SessionManager
) : ViewModel() {

    val family: StateFlow<List<Patient>> = sessionManager.session
        .filterNotNull()
        .flatMapLatest { patientRepository.observeFamily(it.userId) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    fun addFamilyMember(fullName: String, ageYears: Int, sex: String, relation: Relation, mobileNumber: String) {
        viewModelScope.launch {
            val ownerUserId = sessionManager.session.first()?.userId ?: return@launch
            patientRepository.addFamilyMember(
                ownerUserId = ownerUserId,
                fullName = fullName,
                dateOfBirth = LocalDate.now().minusYears(ageYears.toLong()),
                sex = sex,
                relation = relation,
                mobileNumber = mobileNumber
            )
        }
    }
}
