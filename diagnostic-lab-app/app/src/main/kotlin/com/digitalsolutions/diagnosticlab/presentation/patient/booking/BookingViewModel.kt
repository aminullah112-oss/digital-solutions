package com.digitalsolutions.diagnosticlab.presentation.patient.booking

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.digitalsolutions.diagnosticlab.data.repository.BookingRepository
import com.digitalsolutions.diagnosticlab.data.repository.CatalogRepository
import com.digitalsolutions.diagnosticlab.data.repository.PatientRepository
import com.digitalsolutions.diagnosticlab.data.repository.PaymentGatewayResult
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.domain.model.Address
import com.digitalsolutions.diagnosticlab.domain.model.Laboratory
import com.digitalsolutions.diagnosticlab.domain.model.Patient
import com.digitalsolutions.diagnosticlab.domain.model.PaymentMethod
import com.digitalsolutions.diagnosticlab.domain.model.PricedInvestigation
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.time.LocalDate

/**
 * Holds everything selected across the multi-screen booking wizard (spec section 10). One
 * instance is shared across all booking screens for the activity's lifetime and explicitly
 * [reset] whenever "Book a Test" is tapped from the home screen — see NavGraph.
 */
class BookingViewModel(
    private val catalogRepository: CatalogRepository,
    private val bookingRepository: BookingRepository,
    private val patientRepository: PatientRepository,
    private val sessionManager: SessionManager
) : ViewModel() {

    data class UiState(
        val patient: Patient? = null,
        val laboratory: Laboratory? = null,
        val availableInvestigations: List<PricedInvestigation> = emptyList(),
        val selectedInvestigationIds: Set<String> = emptySet(),
        val scheduledDate: LocalDate? = null,
        val scheduledTimeSlot: String? = null,
        val address: Address? = null,
        val paymentMethod: PaymentMethod = PaymentMethod.ONLINE,
        val submitting: Boolean = false,
        val error: String? = null,
        val createdBookingId: String? = null
    ) {
        val totalAmount: Double get() = availableInvestigations.filter { it.investigation.id in selectedInvestigationIds }.sumOf { it.price }
        val selectedCount: Int get() = selectedInvestigationIds.size
    }

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    fun reset() {
        _state.value = UiState()
    }

    fun selectPatient(patient: Patient) {
        _state.value = _state.value.copy(patient = patient)
    }

    fun selectLaboratory(laboratory: Laboratory) {
        _state.value = _state.value.copy(laboratory = laboratory, selectedInvestigationIds = emptySet())
        viewModelScope.launch {
            catalogRepository.observePricedInvestigations(laboratory.id).collect { list ->
                _state.value = _state.value.copy(availableInvestigations = list)
            }
        }
    }

    fun toggleInvestigation(investigationId: String) {
        val current = _state.value.selectedInvestigationIds
        _state.value = _state.value.copy(
            selectedInvestigationIds = if (investigationId in current) current - investigationId else current + investigationId
        )
    }

    fun setSchedule(date: LocalDate, timeSlot: String) {
        _state.value = _state.value.copy(scheduledDate = date, scheduledTimeSlot = timeSlot)
    }

    fun setAddress(address: Address) {
        _state.value = _state.value.copy(address = address)
    }

    fun setPaymentMethod(method: PaymentMethod) {
        _state.value = _state.value.copy(paymentMethod = method)
    }

    /** Creates the booking (PENDING_PAYMENT) and immediately attempts payment. */
    fun submitAndPay() {
        val s = _state.value
        val patient = s.patient ?: return
        val lab = s.laboratory ?: return
        val date = s.scheduledDate ?: return
        val slot = s.scheduledTimeSlot ?: return
        val address = s.address ?: return
        if (s.selectedInvestigationIds.isEmpty()) return

        viewModelScope.launch {
            _state.value = s.copy(submitting = true, error = null)
            val ownerUserId = sessionManager.session.first()?.userId ?: return@launch
            val prices = s.availableInvestigations
                .filter { it.investigation.id in s.selectedInvestigationIds }
                .associate { it.investigation.id to it.price }
            val bookingId = bookingRepository.createBooking(
                patientId = patient.id,
                bookedByUserId = ownerUserId,
                laboratoryId = lab.id,
                addressId = address.id,
                investigationPrices = prices,
                scheduledDate = date,
                scheduledTimeSlot = slot
            )
            when (val result = bookingRepository.pay(bookingId, s.paymentMethod)) {
                is PaymentGatewayResult.Success ->
                    _state.value = _state.value.copy(submitting = false, createdBookingId = bookingId)
                is PaymentGatewayResult.Failure ->
                    _state.value = _state.value.copy(submitting = false, error = result.reason)
            }
        }
    }
}
