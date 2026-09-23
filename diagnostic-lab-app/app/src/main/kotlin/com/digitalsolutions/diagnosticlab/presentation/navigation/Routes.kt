package com.digitalsolutions.diagnosticlab.presentation.navigation

object Routes {
    const val LOGIN = "login"
    const val OTP = "otp/{mobile}"
    fun otp(mobile: String) = "otp/${encode(mobile)}"
    const val PROFILE_SETUP = "profile_setup"

    // Patient
    const val PATIENT_HOME = "patient_home"
    const val FAMILY = "family"
    const val BOOKING_PATIENT_SELECT = "booking_patient_select"
    const val LABS = "labs"
    const val INVESTIGATIONS = "investigations/{labId}"
    fun investigations(labId: String) = "investigations/${encode(labId)}"
    const val BOOKING_DATETIME = "booking_datetime/{labId}"
    fun bookingDateTime(labId: String) = "booking_datetime/${encode(labId)}"
    const val BOOKING_ADDRESS = "booking_address"
    const val BOOKING_REVIEW = "booking_review"
    const val BOOKING_CONFIRMATION = "booking_confirmation/{bookingId}"
    fun bookingConfirmation(bookingId: String) = "booking_confirmation/${encode(bookingId)}"
    const val MY_BOOKINGS = "my_bookings"
    const val BOOKING_DETAIL = "booking_detail/{bookingId}"
    fun bookingDetail(bookingId: String) = "booking_detail/${encode(bookingId)}"
    const val REPORTS = "reports"
    const val MEDICAL_HISTORY = "medical_history"
    const val HELP_SUPPORT = "help_support"
    const val COMPLAINT_NEW = "complaint_new"
    const val NOTIFICATIONS = "notifications"
    const val SETTINGS = "settings"

    // Phlebotomist
    const val PHLEBOTOMIST_HOME = "phlebotomist_home"
    const val PHLEBOTOMIST_ASSIGNMENT = "phlebotomist_assignment/{bookingId}"
    fun phlebotomistAssignment(bookingId: String) = "phlebotomist_assignment/${encode(bookingId)}"

    // Laboratory
    const val LAB_HOME = "lab_home"
    const val LAB_ORDER = "lab_order/{bookingId}"
    fun labOrder(bookingId: String) = "lab_order/${encode(bookingId)}"

    // Admin
    const val ADMIN_HOME = "admin_home"

    // Uri.encode (not URLEncoder.encode) — URLEncoder is form-encoding, where a space becomes
    // '+'; Navigation's own route-argument extraction only reverses %XX percent-escapes, not
    // that form convention, so a '+' round-trips as a literal '+' instead of a space. Uri.encode
    // percent-escapes the space itself (%20), which decodes back correctly on the other end —
    // this matters here because mobile numbers ("+91 9000000001") carry a real space.
    private fun encode(value: String) = android.net.Uri.encode(value)
}
