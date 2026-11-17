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
    val hints = mapOf(
        EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M,
        EncodeHintType.MARGIN to 4,
        EncodeHintType.CHARACTER_SET to "UTF-8"
    )
    val matrix = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, sizePx, sizePx, hints)
    val pixels = IntArray(sizePx * sizePx) { i ->
        if (matrix.get(i % sizePx, i / sizePx)) Color.BLACK else Color.WHITE
    }
    return Bitmap.createBitmap(pixels, sizePx, sizePx, Bitmap.Config.ARGB_8888)
}
