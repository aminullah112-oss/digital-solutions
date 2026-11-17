package com.digitalsolutions.diagnosticlab.presentation.components

import android.graphics.Bitmap
import android.graphics.Color
import androidx.compose.foundation.Image
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.asImageBitmap
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel

/** Draws [content] as a QR code, always black on white regardless of the app theme (a QR on a
 * dark background won't scan) and without smoothing, so the modules stay sharp for a UPI app
 * reading it from a screenshot. Draws nothing if the content can't be encoded. */
@Composable
fun QrCodeImage(content: String, modifier: Modifier = Modifier) {
    val bitmap = remember(content) { runCatching { renderQr(content, 800) }.getOrNull() }
    if (bitmap != null) {
        Image(
            bitmap = bitmap.asImageBitmap(),
            contentDescription = "UPI payment QR code",
            filterQuality = FilterQuality.None,
            modifier = modifier
        )
    }
}

private fun renderQr(content: String, sizePx: Int): Bitmap {
    // No CHARACTER_SET hint on purpose: setting one (even UTF-8) makes zxing prepend an ECI header,
    // which some scanners handle poorly. UPI payloads are plain ASCII (PaymentConfigRepository
    // rejects anything else), so the default encoding is exact and produces a header-free QR like
    // the ones UPI apps scan every day.
    val hints = mapOf(
        EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M,
        EncodeHintType.MARGIN to 4
    )
    val matrix = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, sizePx, sizePx, hints)
    val pixels = IntArray(sizePx * sizePx) { i ->
        if (matrix.get(i % sizePx, i / sizePx)) Color.BLACK else Color.WHITE
    }
    return Bitmap.createBitmap(pixels, sizePx, sizePx, Bitmap.Config.ARGB_8888)
}
