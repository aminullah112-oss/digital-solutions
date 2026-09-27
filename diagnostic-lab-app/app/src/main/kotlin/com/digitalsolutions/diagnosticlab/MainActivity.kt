package com.digitalsolutions.diagnosticlab

import android.Manifest
import android.content.Context
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.CompositionLocalProvider
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.locale.LocaleHelper
import com.digitalsolutions.diagnosticlab.payment.RazorpayResultBridge
import com.digitalsolutions.diagnosticlab.presentation.navigation.DiagnosticLabNavGraph
import com.digitalsolutions.diagnosticlab.presentation.theme.DiagnosticLabTheme
import com.razorpay.PaymentData
import com.razorpay.PaymentResultWithDataListener

class MainActivity : ComponentActivity(), PaymentResultWithDataListener {

    private val notificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { /* no-op: app works without it */ }

    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(LocaleHelper.wrap(newBase))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }

        val container = (application as DiagnosticLabApp).container

        setContent {
            CompositionLocalProvider(LocalAppContainer provides container) {
                DiagnosticLabTheme {
                    DiagnosticLabNavGraph()
                }
            }
        }
    }

    // Razorpay's Checkout SDK calls these on whichever Activity started it — MainActivity is
    // the only one in the app. Forwarded to RazorpayResultBridge since the actual payment flow
    // lives in BookingViewModel, several layers below where this callback fires.
    override fun onPaymentSuccess(razorpayPaymentId: String?, paymentData: PaymentData?) {
        val orderId = paymentData?.orderId
        val signature = paymentData?.signature
        if (razorpayPaymentId != null && orderId != null && signature != null) {
            RazorpayResultBridge.completeSuccess(razorpayPaymentId, orderId, signature)
        } else {
            RazorpayResultBridge.completeFailure("Payment completed but verification data was missing.")
        }
    }

    override fun onPaymentError(code: Int, description: String?, paymentData: PaymentData?) {
        RazorpayResultBridge.completeFailure(description ?: "Payment was cancelled or failed.")
    }
}
