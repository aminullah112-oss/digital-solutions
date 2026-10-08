package com.digitalsolutions.diagnosticlab.presentation.components

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.google.android.gms.maps.model.BitmapDescriptorFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.LatLngBounds
import com.google.maps.android.compose.GoogleMap
import com.google.maps.android.compose.Marker
import com.google.maps.android.compose.MarkerState
import com.google.maps.android.compose.rememberCameraPositionState

/**
 * Shown on BookingDetailScreen only while a phlebotomist is actually en route (assignment.status
 * == ON_THE_WAY) and has reported at least one location fix — see
 * BookingRepository.updatePhlebotomistLocation and PhlebotomistAssignmentScreen's location
 * reporting. Camera auto-fits both pins once on first composition rather than continuously
 * re-centering on every update, so the user can freely pan/zoom without the map fighting them.
 */
@Composable
fun LiveTrackingMap(
    patientLatitude: Double,
    patientLongitude: Double,
    phlebotomistLatitude: Double,
    phlebotomistLongitude: Double,
    modifier: Modifier = Modifier
) {
    val destination = LatLng(patientLatitude, patientLongitude)
    val phlebotomist = LatLng(phlebotomistLatitude, phlebotomistLongitude)

    val cameraPositionState = rememberCameraPositionState {
        val bounds = LatLngBounds.builder().include(destination).include(phlebotomist).build()
        position = CameraPosition.fromLatLngZoom(bounds.center, 14f)
    }

    SectionCard("Lab assistant's location") {
        GoogleMap(
            modifier = modifier.fillMaxWidth().height(220.dp),
            cameraPositionState = cameraPositionState
        ) {
            Marker(
                state = remember(destination) { MarkerState(destination) },
                title = "Collection address",
                icon = BitmapDescriptorFactory.defaultMarker(BitmapDescriptorFactory.HUE_RED)
            )
            Marker(
                state = remember(phlebotomist) { MarkerState(phlebotomist) },
                title = "Lab assistant",
                icon = BitmapDescriptorFactory.defaultMarker(BitmapDescriptorFactory.HUE_AZURE)
            )
        }
    }
}
