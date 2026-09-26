package com.digitalsolutions.diagnosticlab.presentation.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.UserRole
import com.digitalsolutions.diagnosticlab.presentation.admin.AdminHomeScreen
import com.digitalsolutions.diagnosticlab.presentation.auth.LoginScreen
import com.digitalsolutions.diagnosticlab.presentation.auth.OtpScreen
import com.digitalsolutions.diagnosticlab.presentation.auth.ProfileSetupScreen
import com.digitalsolutions.diagnosticlab.presentation.auth.WelcomeScreen
import com.digitalsolutions.diagnosticlab.presentation.lab.LabHomeScreen
import com.digitalsolutions.diagnosticlab.presentation.lab.LabOrderDetailScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.booking.BookingAddressScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.booking.BookingDateTimeScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.booking.BookingReviewScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.booking.BookingConfirmationScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.booking.BookingViewModel
import com.digitalsolutions.diagnosticlab.presentation.patient.bookings.BookingDetailScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.bookings.MyBookingsScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.family.BookingPatientSelectScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.family.FamilyScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.history.MedicalHistoryScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.home.PatientHomeScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.investigations.InvestigationCatalogScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.labs.LabListScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.notifications.NotificationsScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.reports.ReportsScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.settings.SettingsScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.support.ComplaintScreen
import com.digitalsolutions.diagnosticlab.presentation.patient.support.HelpSupportScreen
import com.digitalsolutions.diagnosticlab.presentation.phlebotomist.PhlebotomistAssignmentScreen
import com.digitalsolutions.diagnosticlab.presentation.phlebotomist.PhlebotomistHomeScreen
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory

@Composable
fun DiagnosticLabNavGraph() {
    val container = LocalAppContainer.current
    val navController = rememberNavController()
    val session by container.sessionManager.session.collectAsState(initial = null)

    val startDestination = when (session?.role) {
        null -> Routes.WELCOME
        UserRole.PATIENT -> Routes.PATIENT_HOME
        UserRole.PHLEBOTOMIST -> Routes.PHLEBOTOMIST_HOME
        UserRole.LABORATORY -> Routes.LAB_HOME
        UserRole.ADMIN -> Routes.ADMIN_HOME
    }

    // A single shared booking-in-progress ViewModel, reset explicitly each time a new
    // booking starts from PatientHomeScreen/LabListScreen — see BookingViewModel kdoc.
    val bookingViewModel: BookingViewModel = viewModel(
        factory = viewModelFactory {
            initializer { BookingViewModel(container.catalogRepository, container.bookingRepository, container.patientRepository, container.sessionManager) }
        }
    )

    NavHost(navController = navController, startDestination = startDestination) {
        composable(Routes.WELCOME) {
            WelcomeScreen(onContinue = { navController.navigate(Routes.LOGIN) })
        }
        composable(Routes.LOGIN) {
            LoginScreen(onOtpRequested = { mobile -> navController.navigate(Routes.otp(mobile)) })
        }
        composable(
            Routes.OTP,
            arguments = listOf(navArgument("mobile") { type = NavType.StringType })
        ) { backStackEntry ->
            val mobile = backStackEntry.arguments?.getString("mobile").orEmpty()
            OtpScreen(mobile = mobile) { role, isNewAccount ->
                val destination = when {
                    role == UserRole.PATIENT && isNewAccount -> Routes.PROFILE_SETUP
                    role == UserRole.PATIENT -> Routes.PATIENT_HOME
                    role == UserRole.PHLEBOTOMIST -> Routes.PHLEBOTOMIST_HOME
                    role == UserRole.LABORATORY -> Routes.LAB_HOME
                    else -> Routes.ADMIN_HOME
                }
                navController.navigate(destination) { popUpTo(Routes.LOGIN) { inclusive = true } }
            }
        }
        composable(Routes.PROFILE_SETUP) {
            ProfileSetupScreen(onDone = {
                navController.navigate(Routes.PATIENT_HOME) { popUpTo(Routes.LOGIN) { inclusive = true } }
            })
        }

        // ---------- Patient ----------
        composable(Routes.PATIENT_HOME) {
            PatientHomeScreen(
                onBookTest = { bookingViewModel.reset(); navController.navigate(Routes.BOOKING_PATIENT_SELECT) },
                onMyBookings = { navController.navigate(Routes.MY_BOOKINGS) },
                onReports = { navController.navigate(Routes.REPORTS) },
                onFamily = { navController.navigate(Routes.FAMILY) },
                onHelp = { navController.navigate(Routes.HELP_SUPPORT) },
                onNotifications = { navController.navigate(Routes.NOTIFICATIONS) },
                onSettings = { navController.navigate(Routes.SETTINGS) },
                onMedicalHistory = { navController.navigate(Routes.MEDICAL_HISTORY) },
                onOpenBooking = { bookingId -> navController.navigate(Routes.bookingDetail(bookingId)) }
            )
        }
        composable(Routes.FAMILY) { FamilyScreen(onBack = { navController.popBackStack() }) }
        composable(Routes.BOOKING_PATIENT_SELECT) {
            BookingPatientSelectScreen(
                onPatientSelected = { patient ->
                    bookingViewModel.selectPatient(patient)
                    navController.navigate(Routes.LABS)
                },
                onBack = { navController.popBackStack() }
            )
        }
        composable(Routes.LABS) {
            LabListScreen(
                onLabSelected = { lab ->
                    bookingViewModel.selectLaboratory(lab)
                    navController.navigate(Routes.investigations(lab.id))
                },
                onBack = { navController.popBackStack() }
            )
        }
        composable(
            Routes.INVESTIGATIONS,
            arguments = listOf(navArgument("labId") { type = NavType.StringType })
        ) {
            InvestigationCatalogScreen(
                bookingViewModel = bookingViewModel,
                onContinue = { navController.navigate(Routes.bookingDateTime(it)) },
                onBack = { navController.popBackStack() }
            )
        }
        composable(
            Routes.BOOKING_DATETIME,
            arguments = listOf(navArgument("labId") { type = NavType.StringType })
        ) {
            BookingDateTimeScreen(
                bookingViewModel = bookingViewModel,
                onContinue = { navController.navigate(Routes.BOOKING_ADDRESS) },
                onBack = { navController.popBackStack() }
            )
        }
        composable(Routes.BOOKING_ADDRESS) {
            BookingAddressScreen(
                bookingViewModel = bookingViewModel,
                onContinue = { navController.navigate(Routes.BOOKING_REVIEW) },
                onBack = { navController.popBackStack() }
            )
        }
        composable(Routes.BOOKING_REVIEW) {
            BookingReviewScreen(
                bookingViewModel = bookingViewModel,
                onConfirmed = { bookingId ->
                    navController.navigate(Routes.bookingConfirmation(bookingId)) { popUpTo(Routes.PATIENT_HOME) }
                },
                onBack = { navController.popBackStack() }
            )
        }
        composable(
            Routes.BOOKING_CONFIRMATION,
            arguments = listOf(navArgument("bookingId") { type = NavType.StringType })
        ) { backStackEntry ->
            val bookingId = backStackEntry.arguments?.getString("bookingId").orEmpty()
            BookingConfirmationScreen(
                bookingId = bookingId,
                onDone = { navController.navigate(Routes.PATIENT_HOME) { popUpTo(Routes.PATIENT_HOME) { inclusive = true } } }
            )
        }
        composable(Routes.MY_BOOKINGS) {
            MyBookingsScreen(
                onOpenBooking = { navController.navigate(Routes.bookingDetail(it)) },
                onBack = { navController.popBackStack() }
            )
        }
        composable(
            Routes.BOOKING_DETAIL,
            arguments = listOf(navArgument("bookingId") { type = NavType.StringType })
        ) { backStackEntry ->
            val bookingId = backStackEntry.arguments?.getString("bookingId").orEmpty()
            BookingDetailScreen(bookingId = bookingId, onBack = { navController.popBackStack() })
        }
        composable(Routes.REPORTS) { ReportsScreen(onBack = { navController.popBackStack() }) }
        composable(Routes.MEDICAL_HISTORY) { MedicalHistoryScreen(onBack = { navController.popBackStack() }) }
        composable(Routes.HELP_SUPPORT) {
            HelpSupportScreen(
                onRaiseComplaint = { navController.navigate(Routes.COMPLAINT_NEW) },
                onBack = { navController.popBackStack() }
            )
        }
        composable(Routes.COMPLAINT_NEW) { ComplaintScreen(onDone = { navController.popBackStack() }) }
        composable(Routes.NOTIFICATIONS) { NotificationsScreen(onBack = { navController.popBackStack() }) }
        composable(Routes.SETTINGS) {
            SettingsScreen(
                onSignedOut = { navController.navigate(Routes.LOGIN) { popUpTo(0) } },
                onBack = { navController.popBackStack() },
                onReports = { navController.navigate(Routes.REPORTS) },
                onMedicalHistory = { navController.navigate(Routes.MEDICAL_HISTORY) }
            )
        }

        // ---------- Phlebotomist ----------
        composable(Routes.PHLEBOTOMIST_HOME) {
            PhlebotomistHomeScreen(
                onOpenAssignment = { navController.navigate(Routes.phlebotomistAssignment(it)) },
                onSignedOut = { navController.navigate(Routes.LOGIN) { popUpTo(0) } }
            )
        }
        composable(
            Routes.PHLEBOTOMIST_ASSIGNMENT,
            arguments = listOf(navArgument("bookingId") { type = NavType.StringType })
        ) { backStackEntry ->
            val bookingId = backStackEntry.arguments?.getString("bookingId").orEmpty()
            PhlebotomistAssignmentScreen(bookingId = bookingId, onBack = { navController.popBackStack() })
        }

        // ---------- Laboratory ----------
        composable(Routes.LAB_HOME) {
            LabHomeScreen(
                onOpenOrder = { navController.navigate(Routes.labOrder(it)) },
                onSignedOut = { navController.navigate(Routes.LOGIN) { popUpTo(0) } }
            )
        }
        composable(
            Routes.LAB_ORDER,
            arguments = listOf(navArgument("bookingId") { type = NavType.StringType })
        ) { backStackEntry ->
            val bookingId = backStackEntry.arguments?.getString("bookingId").orEmpty()
            LabOrderDetailScreen(bookingId = bookingId, onBack = { navController.popBackStack() })
        }

        // ---------- Admin ----------
        composable(Routes.ADMIN_HOME) {
            AdminHomeScreen(onSignedOut = { navController.navigate(Routes.LOGIN) { popUpTo(0) } })
        }
    }
}
