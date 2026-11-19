package com.digitalsolutions.diagnosticlab.data.repository

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import com.digitalsolutions.diagnosticlab.domain.model.DocumentCategory
import com.digitalsolutions.diagnosticlab.domain.model.PatientDocument
import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.storage.FirebaseStorage
import com.google.firebase.storage.StorageMetadata
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await
import java.io.File

/**
 * Prescriptions and reports patients store themselves (from a doctor, another lab, a hospital).
 * Files live in Storage at userDocuments/{ownerUid}/{docId}; the list and details live in the
 * patientDocuments collection. Both are readable only by the uploading account — labs, admins
 * and other patients never see them (see firestore.rules and storage.rules).
 */
class DocumentRepository(
    private val firestore: FirebaseFirestore,
    private val storage: () -> FirebaseStorage
) {
    private fun collection() = firestore.collection("patientDocuments")

    fun observeForOwner(ownerUserId: String): Flow<List<PatientDocument>> = callbackFlow {
        val registration = collection().whereEqualTo("ownerUserId", ownerUserId)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    close(error)
                    return@addSnapshotListener
                }
                trySend(
                    snapshot?.documents.orEmpty().mapNotNull { it.toDocument() }
                        .sortedByDescending { it.uploadedAtMillis }
                )
            }
        awaitClose { registration.remove() }
    }

    /** Name and size of a picked file, or null when the provider doesn't say. */
    fun describe(context: Context, uri: Uri): Pair<String?, Long?> {
        context.contentResolver.query(uri, null, null, null, null)?.use { c ->
            if (c.moveToFirst()) {
                val nameIdx = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                val sizeIdx = c.getColumnIndex(OpenableColumns.SIZE)
                val name = if (nameIdx >= 0) c.getString(nameIdx) else null
                val size = if (sizeIdx >= 0 && !c.isNull(sizeIdx)) c.getLong(sizeIdx) else null
                return name to size
            }
        }
        return null to null
    }

    /** Throws IllegalArgumentException with a user-readable message for a file we won't store. */
    suspend fun upload(context: Context, ownerUserId: String, uri: Uri, title: String, category: DocumentCategory) {
        val mime = context.contentResolver.getType(uri)
        require(mime in ALLOWED_TYPES) { "Only PDF, JPG or PNG files can be stored." }
        val size = describe(context, uri).second
        require(size == null || size < MAX_BYTES) { "That file is larger than 10 MB. Please choose a smaller one." }
        val docRef = collection().document()
        val path = "userDocuments/$ownerUserId/${docRef.id}"
        val uploaded = storage().reference.child(path)
            .putFile(uri, StorageMetadata.Builder().setContentType(mime).build())
            .await()
        docRef.set(
            mapOf(
                "ownerUserId" to ownerUserId,
                "title" to title.trim().ifBlank { "Document" },
                "category" to category.name,
                "mimeType" to mime,
                "storagePath" to path,
                "sizeBytes" to (size ?: uploaded.metadata?.sizeBytes ?: 0L),
                "uploadedAtMillis" to System.currentTimeMillis()
            )
        ).await()
    }

    /** Downloads into [cacheDir]/documents and returns the file, named so viewers recognise it. */
    suspend fun download(document: PatientDocument, cacheDir: File): File {
        val dir = File(cacheDir, "documents").apply { mkdirs() }
        val ext = when (document.mimeType) { "application/pdf" -> "pdf"; "image/png" -> "png"; else -> "jpg" }
        val file = File(dir, "${document.id}.$ext")
        storage().reference.child(document.storagePath).getFile(file).await()
        return file
    }

    suspend fun delete(document: PatientDocument) {
        // File first: if that fails the record stays and the patient can retry. A missing file
        // (already deleted) shouldn't block removing the record.
        try {
            storage().reference.child(document.storagePath).delete().await()
        } catch (e: com.google.firebase.storage.StorageException) {
            if (e.errorCode != com.google.firebase.storage.StorageException.ERROR_OBJECT_NOT_FOUND) throw e
        }
        collection().document(document.id).delete().await()
    }

    companion object {
        const val MAX_BYTES = 10L * 1024 * 1024
        val ALLOWED_TYPES = setOf("application/pdf", "image/jpeg", "image/png")
    }
}

private fun DocumentSnapshot.toDocument(): PatientDocument? {
    if (!exists()) return null
    return PatientDocument(
        id = id,
        title = getString("title")?.ifBlank { null } ?: "Document",
        category = runCatching { DocumentCategory.valueOf(getString("category") ?: "") }.getOrDefault(DocumentCategory.OTHER),
        mimeType = getString("mimeType").orEmpty(),
        storagePath = getString("storagePath").orEmpty(),
        sizeBytes = getLong("sizeBytes") ?: 0L,
        uploadedAtMillis = getLong("uploadedAtMillis") ?: 0L
    )
}
