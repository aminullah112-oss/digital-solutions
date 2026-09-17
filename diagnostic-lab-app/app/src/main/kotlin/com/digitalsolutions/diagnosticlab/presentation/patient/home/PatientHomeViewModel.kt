package com.digitalsolutions.diagnosticlab.presentation.patient.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.digitalsolutions.diagnosticlab.data.repository.BookingRepository
import com.digitalsolutions.diagnosticlab.data.repository.NotificationRepository
import com.digitalsolutions.diagnosticlab.data.repository.PatientRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.domain.model.Booking
import com.digitalsolutions.diagnosticlab.domain.model.BookingStatus
import com.digitalsolutions.diagnosticlab.domain.model.Patient
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn

private val ACTIVE_STATUSES = setOf(
    BookingStatus.CONFIRMED, BookingStatus.PHLEBOTOMIST_ASSIGNED, BookingStatus.PHLEBOTOMIST_ON_THE_WAY,
    BookingStatus.ARRIVED, BookingStatus.SAMPLE_COLLECTED, BookingStatus.SAMPLE_IN_TRANSIT,
    BookingStatus.RECEIVED_AT_LAB, BookingStatus.PROCESSING, BookingStatus.REPORT_READY
)

class PatientHomeViewModel(
    private val patientRepository: PatientRepository,
    private val bookingRepository: BookingRepository,
    private val notificationRepository: NotificationRepository,
    private val sessionManager: SessionManager
) : ViewModel() {

    data class HomeState(val primaryPatient: Patient?, val activeBooking: Booking?, val unreadNotifications: Int)

    val state: StateFlow<HomeState> = sessionManager.session
        .filterNotNull()
        .flatMapLatest { session ->
            combine(
                patientRepository.observeFamily(session.userId),
                bookingRepository.observeBookingsForOwner(session.userId),
                notificationRepository.observeUnreadCount(session.userId)
            ) { family, bookings, unread ->
                HomeState(
                    primaryPatient = family.firstOrNull { it.isPrimary },
                    activeBooking = bookings.firstOrNull { it.status in ACTIVE_STATUSES },
                    unreadNotifications = unread
                )
            }
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), HomeState(null, null, 0))
}
