package com.digitalsolutions.diagnosticlab.presentation.components

import android.graphics.Bitmap
import android.content.ContentValues
import android.content.Context
import android.graphics.Color
import android.os.Build
import android.provider.MediaStore
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

/** Saves [content] as a QR image in the phone's gallery (Pictures/MedwynLabs) so the patient can
 * pick it from their UPI app's gallery scan without taking a screenshot. Needs no permission on
 * Android 10+; on older versions returns false and the caller falls back to "take a screenshot". */
fun saveQrToGallery(context: Context, content: String, name: String): Boolean {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return false
    return runCatching {
        val bitmap = renderQr(content, 800)
        val resolver = context.contentResolver
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, "$name.png")
            put(MediaStore.Images.Media.MIME_TYPE, "image/png")
            put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/MedwynLabs")
            put(MediaStore.Images.Media.IS_PENDING, 1)
        }
        val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values) ?: return false
        val ok = resolver.openOutputStream(uri)?.use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) } ?: false
        if (!ok) {
            resolver.delete(uri, null, null)
            return false
        }
        values.clear()
        values.put(MediaStore.Images.Media.IS_PENDING, 0)
        resolver.update(uri, values, null, null)
        true
    }.getOrDefault(false)
}
