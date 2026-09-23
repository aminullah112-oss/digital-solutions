package com.digitalsolutions.diagnosticlab

import android.graphics.Bitmap
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.test.espresso.Espresso
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithContentDescription
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.FileOutputStream

/**
 * Drives the real app through every role's main screens and captures a screenshot after
 * each meaningful step, for a customer-facing review report — not a correctness test (that's
 * what the JVM unit tests are for). Runs against the actual seeded demo data on a real
 * emulator via CI (see .github/workflows/build-diagnostic-lab-apk.yml); this sandbox has no
 * emulator, so this file has never been executed locally.
 *
 * Screenshots land in the app's external files dir under "screenshots/" and are pulled off
 * the emulator by the CI job after the test run, win or lose — a late failure here should
 * never erase the screenshots earlier steps already captured.
 */
@RunWith(AndroidJUnit4::class)
class FullAppWalkthroughTest {

    @get:Rule
    val composeTestRule = createAndroidComposeRule<MainActivity>()

    private var shotIndex = 0

    private fun screenshot(name: String) {
        shotIndex++
        val bitmap: Bitmap? = InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot()
        val dir = File(InstrumentationRegistry.getInstrumentation().targetContext.getExternalFilesDir(null), "screenshots")
        dir.mkdirs()
        val label = shotIndex.toString().padStart(2, '0')
        FileOutputStream(File(dir, "${label}_$name.png")).use { out ->
            bitmap?.compress(Bitmap.CompressFormat.PNG, 100, out)
        }
    }

    private fun login(mobileDigits: String) {
        // Generous on this specific wait: on a cold app launch this is waiting on Compose's
        // first frame *and* Application.onCreate()'s one-time demo-data seed, which can take
        // longer on a freshly booted CI emulator than any of the steady-state waits below.
        composeTestRule.waitUntil(45_000) {
            composeTestRule.onAllNodesWithTag("login_mobile_field").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("login")
        composeTestRule.onNodeWithTag("login_mobile_field").performTextInput(mobileDigits)
        composeTestRule.onNodeWithText("Send OTP").performClick()

        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("demo_otp_text").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("otp")
        val otpNode = composeTestRule.onNodeWithTag("demo_otp_text").fetchSemanticsNode()
        val otpText = otpNode.config.getOrNull(SemanticsProperties.Text)?.joinToString("") { it.text }.orEmpty()
        val code = Regex("(\\d{4})").find(otpText)?.value ?: error("Could not read demo OTP from: $otpText")
        composeTestRule.onNodeWithTag("otp_field").performTextInput(code)
        composeTestRule.onNodeWithText("Verify & Continue").performClick()
    }

    private fun signOutFromRoleHome() {
        composeTestRule.onNodeWithContentDescription("Sign out").performClick()
    }

    @Test
    fun fullAppWalkthrough() {
        // ---------- Patient: the full primary journey ----------
        login("9000000001")

        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("patient_home_book_button").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("patient_home")

        composeTestRule.onNodeWithTag("patient_home_book_button").performClick()
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("patient_row").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("choose_patient")

        composeTestRule.onAllNodesWithTag("patient_row")[0].performClick()
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("lab_row").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("choose_lab")

        composeTestRule.onAllNodesWithTag("lab_row")[0].performClick()
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("investigation_row").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("choose_tests")

        composeTestRule.onAllNodesWithTag("investigation_row")[0].performClick()
        composeTestRule.onAllNodesWithTag("investigation_row")[1].performClick()
        screenshot("tests_selected")
        composeTestRule.onNodeWithText("Continue").performClick()

        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("date_chip_0").fetchSemanticsNodes().isNotEmpty()
        }
        composeTestRule.onNodeWithTag("date_chip_0").performClick()
        composeTestRule.onNodeWithTag("time_chip_1").performClick()
        screenshot("choose_datetime")
        composeTestRule.onNodeWithText("Continue").performClick()

        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("address_row").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("choose_address")
        composeTestRule.onAllNodesWithTag("address_row")[0].performClick()

        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithText("Cash at collection").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("review_booking")
        // This screen stacks patient/lab/tests/schedule/address/payment cards inside a plain
        // verticalScroll Column, so both the payment row and the CTA below it can sit below
        // the viewport on a real device. A printToLog() dump on a prior CI run confirmed the
        // "Cash at collection" click was landing off-screen and silently doing nothing (no
        // exception, no state change) — performClick() alone targets a node's actual layout
        // coordinates regardless of visibility, so every click on this screen needs
        // performScrollTo() first.
        composeTestRule.onNodeWithText("Cash at collection").performScrollTo().performClick()
        // Selecting cash flips the CTA's label from "Pay ₹… & Confirm" to "Confirm Booking" —
        // wait for that recomposition before searching for the new text, same as every other
        // step here.
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithText("Confirm Booking").fetchSemanticsNodes().isNotEmpty()
        }
        composeTestRule.onNodeWithText("Confirm Booking").performScrollTo().performClick()

        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithText("Booking confirmed!").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("booking_confirmed")
        composeTestRule.onNodeWithText("Back to Home").performClick()

        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("patient_home_book_button").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("home_with_active_booking")

        composeTestRule.onNodeWithText("Bookings").performClick()
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("booking_row").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("my_bookings")

        composeTestRule.onAllNodesWithTag("booking_row")[0].performClick()
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithText("Collection address").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("booking_detail_tracking")

        Espresso.pressBack()
        Espresso.pressBack()
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("patient_home_book_button").fetchSemanticsNodes().isNotEmpty()
        }

        composeTestRule.onNodeWithText("Reports").performClick()
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithText("My Reports").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("reports")
        Espresso.pressBack()

        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("patient_home_book_button").fetchSemanticsNodes().isNotEmpty()
        }
        composeTestRule.onNodeWithText("My Family").performClick()
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("family_member_row").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("family")
        Espresso.pressBack()

        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithTag("patient_home_book_button").fetchSemanticsNodes().isNotEmpty()
        }
        composeTestRule.onNodeWithText("Help & Support").performClick()
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithText("Raise a complaint").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("help_support")
        Espresso.pressBack()

        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithContentDescription("Notifications").fetchSemanticsNodes().isNotEmpty()
        }
        composeTestRule.onNodeWithContentDescription("Notifications").performClick()
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithText("Notifications").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("notifications")
        Espresso.pressBack()

        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithContentDescription("Profile").fetchSemanticsNodes().isNotEmpty()
        }
        composeTestRule.onNodeWithContentDescription("Profile").performClick()
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithText("Sign out").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("settings")
        composeTestRule.onNodeWithText("Sign out").performClick()

        // ---------- Phlebotomist ----------
        login("9840010001")
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithText("Today's Collections").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("phlebotomist_home")
        signOutFromRoleHome()

        // ---------- Laboratory ----------
        login("9850020001")
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithText("Incoming Orders").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("laboratory_home")
        signOutFromRoleHome()

        // ---------- Admin ----------
        login("9000100000")
        composeTestRule.waitUntil(15_000) {
            composeTestRule.onAllNodesWithText("Admin Dashboard").fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("admin_dashboard")
    }
}
