package com.digitalsolutions.diagnosticlab.presentation.patient.booking

import android.app.Activity
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
import com.digitalsolutions.diagnosticlab.domain.model.TestPackage
import com.digitalsolutions.diagnosticlab.payment.RazorpayCheckoutResult
import com.digitalsolutions.diagnosticlab.payment.RazorpayResultBridge
import com.razorpay.Checkout
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import org.json.JSONObject
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
        val availablePackages: List<TestPackage> = emptyList(),
        val selectedPackageId: String? = null,
        val scheduledDate: LocalDate? = null,
        val scheduledTimeSlot: String? = null,
        val address: Address? = null,
        val paymentMethod: PaymentMethod = PaymentMethod.ONLINE,
        val submitting: Boolean = false,
        val error: String? = null,
        val createdBookingId: String? = null
    ) {
        val selectedPackage: TestPackage? get() = availablePackages.find { it.id == selectedPackageId }

        /** Tests covered by the selected package's fixed price — never individually priced,
         * even if their IDs are also sitting in selectedInvestigationIds (selectPackage keeps
         * them there so the catalog list shows them as included/checked). */
        private val packageInvestigationIds: Set<String> get() = selectedPackage?.investigationIds?.toSet().orEmpty()

        val adHocInvestigationIds: Set<String> get() = selectedInvestigationIds - packageInvestigationIds

        val totalAmount: Double
            get() {
                val adHocTotal = availableInvestigations
                    .filter { it.investigation.id in adHocInvestigationIds }
                    .sumOf { it.price }
                return adHocTotal + (selectedPackage?.price ?: 0.0)
            }

        val selectedCount: Int get() = adHocInvestigationIds.size + (if (selectedPackage != null) 1 else 0)
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
        _state.value = _state.value.copy(
            laboratory = laboratory,
            selectedInvestigationIds = emptySet(),
            availablePackages = emptyList(),
            selectedPackageId = null
        )
        viewModelScope.launch {
            catalogRepository.observePricedInvestigations(laboratory.id).collect { list ->
                _state.value = _state.value.copy(availableInvestigations = list)
            }
        }
        viewModelScope.launch {
            catalogRepository.observePackagesForLab(laboratory.id).collect { list ->
                _state.value = _state.value.copy(availablePackages = list)
            }
        }
    }

    /** A test that's part of the currently selected package can't be individually toggled off
     * (see InvestigationCatalogScreen — those rows render non-interactive) — this only ever
     * runs for ad-hoc tests outside whatever package is selected. */
    fun toggleInvestigation(investigationId: String) {
        val current = _state.value.selectedInvestigationIds
        _state.value = _state.value.copy(
            selectedInvestigationIds = if (investigationId in current) current - investigationId else current + investigationId
        )
    }

    /** Selecting a package folds its tests into selectedInvestigationIds (so the catalog list
     * shows them checked) without individually pricing them — see UiState.totalAmount. Passing
     * null, or tapping an already-selected package again, clears it and un-checks those tests
     * (any the patient separately ad-hoc-selected stay selected only if they're also outside
     * every package, which is already true since a test can't be ad-hoc-toggled while covered
     * by the active package). */
    fun selectPackage(testPackage: TestPackage?) {
        val current = _state.value
        val next = if (current.selectedPackageId == testPackage?.id) null else testPackage
        var ids = current.selectedInvestigationIds - current.selectedPackage?.investigationIds.orEmpty().toSet()
        if (next != null) ids = ids + next.investigationIds.toSet()
        _state.value = current.copy(selectedPackageId = next?.id, selectedInvestigationIds = ids)
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

    /** Creates the booking (PENDING_PAYMENT) and immediately attempts payment. [activity] is
     * only used for the ONLINE path, to launch Razorpay's own checkout UI — RBI requires a real
     * payment gateway screen (card/UPI/wallet, OTP 2FA), not a plain API call. */
    fun submitAndPay(activity: Activity) {
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
                .filter { it.investigation.id in s.adHocInvestigationIds }
                .associate { it.investigation.id to it.price }
            val bookingId = bookingRepository.createBooking(
                patientId = patient.id,
                bookedByUserId = ownerUserId,
                laboratoryId = lab.id,
                addressId = address.id,
                investigationPrices = prices,
                selectedPackage = s.selectedPackage,
                scheduledDate = date,
                scheduledTimeSlot = slot
            )
            val result = if (s.paymentMethod == PaymentMethod.CASH) {
                bookingRepository.payCash(bookingId)
            } else {
                payOnline(activity, bookingId)
            }
            when (result) {
                is PaymentGatewayResult.Success ->
                    _state.value = _state.value.copy(submitting = false, createdBookingId = bookingId)
                is PaymentGatewayResult.Failure ->
                    _state.value = _state.value.copy(submitting = false, error = result.reason)
            }
        }
    }

    /**
     * createRazorpayOrder and verifyRazorpayPayment are two separate server round-trips
     * (functions/src/index.ts) — order creation needs the account's secret key, and the
     * payment's signature has to be recomputed and checked server-side afterward, since
     * trusting Checkout's own success callback would let a modified app mark any booking paid
     * without a real charge. This function's own return value is just UI signal for this
     * screen; the Firestore write that actually confirms the booking happens inside
     * verifyRazorpayPayment, not here.
     */
    private suspend fun payOnline(activity: Activity, bookingId: String): PaymentGatewayResult {
        val order = try {
            bookingRepository.createRazorpayOrder(bookingId)
        } catch (e: Exception) {
            return PaymentGatewayResult.Failure(e.message ?: "Could not start payment. Please try again.")
        }

        val checkout = Checkout()
        checkout.setKeyID(order.keyId)
        val options = JSONObject().apply {
            put("name", "Medwyn Labs")
            put("description", "Booking $bookingId")
            put("order_id", order.orderId)
            put("currency", order.currency)
            put("amount", order.amountPaise)
        }
        val deferredResult = RazorpayResultBridge.beginAwaiting()
        try {
            checkout.open(activity, options)
        } catch (e: Exception) {
            return PaymentGatewayResult.Failure("Could not open the payment screen: ${e.message}")
        }

        return when (val checkoutResult = deferredResult.await()) {
            is RazorpayCheckoutResult.Success -> try {
                bookingRepository.verifyRazorpayPayment(
                    bookingId, checkoutResult.paymentId, checkoutResult.orderId, checkoutResult.signature
                )
                PaymentGatewayResult.Success(checkoutResult.paymentId)
            } catch (e: Exception) {
                PaymentGatewayResult.Failure(
                    e.message ?: "Payment could not be verified. If money was deducted, contact support with your booking ID."
                )
            }
            is RazorpayCheckoutResult.Failure -> PaymentGatewayResult.Failure(checkoutResult.message)
        }
    }
}
