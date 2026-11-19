package com.digitalsolutions.diagnosticlab.presentation.patient.documents

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Image
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.digitalsolutions.diagnosticlab.data.repository.DocumentRepository
import com.digitalsolutions.diagnosticlab.data.repository.SessionManager
import com.digitalsolutions.diagnosticlab.di.LocalAppContainer
import com.digitalsolutions.diagnosticlab.domain.model.DocumentCategory
import com.digitalsolutions.diagnosticlab.domain.model.PatientDocument
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.EmptyState
import com.digitalsolutions.diagnosticlab.presentation.components.LoadingState
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.components.StatusChip
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.io.File
import java.text.DateFormat
import java.util.Date

class DocumentsViewModel(
    private val documentRepository: DocumentRepository,
    private val sessionManager: SessionManager
) : ViewModel() {
    private val _loadError = MutableStateFlow<String?>(null)
    val loadError: StateFlow<String?> = _loadError

    val documents: StateFlow<List<PatientDocument>?> = sessionManager.session.filterNotNull()
        .flatMapLatest { session ->
            documentRepository.observeForOwner(session.userId).catch { e ->
                _loadError.value = e.message ?: e.javaClass.simpleName
                emit(emptyList())
            }
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy
    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message

    fun messageShown() { _message.value = null }
    fun showMessage(text: String) { _message.value = text }

    fun add(context: Context, uri: Uri, title: String, category: DocumentCategory) {
        if (_busy.value) return
        viewModelScope.launch {
            _busy.value = true
            try {
                val ownerUserId = sessionManager.session.first()?.userId ?: return@launch
                documentRepository.upload(context, ownerUserId, uri, title, category)
                _message.value = "Saved to My Documents."
            } catch (e: CancellationException) {
                throw e
            } catch (e: IllegalArgumentException) {
                _message.value = e.message
            } catch (e: Exception) {
                _message.value = "Couldn't save the file. Check your connection and try again."
            } finally {
                _busy.value = false
            }
        }
    }

    fun open(document: PatientDocument, cacheDir: File, onReady: (File) -> Unit) {
        if (_busy.value) return
        viewModelScope.launch {
            _busy.value = true
            try {
                onReady(documentRepository.download(document, cacheDir))
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _message.value = "Couldn't open this file. Check your connection and try again."
            } finally {
                _busy.value = false
            }
        }
    }

    fun delete(document: PatientDocument) {
        if (_busy.value) return
        viewModelScope.launch {
            _busy.value = true
            try {
                documentRepository.delete(document)
                _message.value = "Deleted."
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _message.value = "Couldn't delete this file. Please try again."
            } finally {
                _busy.value = false
            }
        }
    }
}

private fun openFile(context: Context, file: File, mime: String): Boolean {
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    val intent = Intent(Intent.ACTION_VIEW).apply {
        setDataAndType(uri, mime)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    return try {
        context.startActivity(intent)
        true
    } catch (e: ActivityNotFoundException) {
        false
    }
}

private fun formatSize(bytes: Long): String = when {
    bytes >= 1024 * 1024 -> String.format("%.1f MB", bytes / (1024.0 * 1024.0))
    bytes >= 1024 -> "${bytes / 1024} KB"
    else -> "$bytes B"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DocumentsScreen(onBack: () -> Unit) {
    val container = LocalAppContainer.current
    val viewModel: DocumentsViewModel = viewModel(
        factory = viewModelFactory { initializer { DocumentsViewModel(container.documentRepository, container.sessionManager) } }
    )
    val documents by viewModel.documents.collectAsState()
    val loadError by viewModel.loadError.collectAsState()
    val busy by viewModel.busy.collectAsState()
    val message by viewModel.message.collectAsState()
    val context = LocalContext.current
    val snackbarHostState = remember { SnackbarHostState() }
    LaunchedEffect(message) {
        message?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.messageShown()
        }
    }

    // A picked file waits here until the patient has named and categorised it.
    var pending by remember { mutableStateOf<Uri?>(null) }
    var pendingName by remember { mutableStateOf("") }
    var toDelete by remember { mutableStateOf<PatientDocument?>(null) }

    fun onPicked(uri: Uri?) {
        if (uri == null) return
        pendingName = container.documentRepository.describe(context, uri).first
            ?.substringBeforeLast('.')?.take(60).orEmpty()
        pending = uri
    }
    val pdfPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { onPicked(it) }
    val photoPicker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { onPicked(it) }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = { Text("My Documents") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Filled.ArrowBack, null) } }
            )
        }
    ) { padding ->
        Column(Modifier.padding(padding).padding(16.dp)) {
            Text(
                "Keep prescriptions and reports from other doctors and labs here. Only you can see them.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    enabled = !busy,
                    onClick = { photoPicker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                    modifier = Modifier.weight(1f)
                ) { Text("Add photo") }
                OutlinedButton(
                    enabled = !busy,
                    onClick = { pdfPicker.launch(arrayOf("application/pdf")) },
                    modifier = Modifier.weight(1f)
                ) { Text("Add PDF") }
            }
            if (busy) {
                Spacer(Modifier.height(8.dp))
                LinearProgressIndicator(Modifier.fillMaxWidth())
            }
            Spacer(Modifier.height(12.dp))
            when {
                loadError != null -> EmptyState("Couldn't load your documents: $loadError")
                documents == null -> LoadingState()
                documents!!.isEmpty() -> EmptyState("No documents yet. Add a photo or PDF of a prescription or report.")
                else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    items(documents!!, key = { it.id }) { doc ->
                        SectionCard {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(if (doc.mimeType == "application/pdf") Icons.Filled.Description else Icons.Filled.Image, null)
                                Spacer(Modifier.width(12.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(doc.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                                    Text(
                                        "${DateFormat.getDateInstance(DateFormat.MEDIUM).format(Date(doc.uploadedAtMillis))} · ${formatSize(doc.sizeBytes)}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                StatusChip(doc.category.label, MaterialTheme.colorScheme.primary)
                            }
                            Row {
                                TextButton(enabled = !busy, onClick = {
                                    viewModel.open(doc, context.cacheDir) { file ->
                                        if (!openFile(context, file, doc.mimeType)) {
                                            viewModel.showMessage("No app found to open this file.")
                                        }
                                    }
                                }) { Text("View") }
                                Spacer(Modifier.weight(1f))
                                IconButton(enabled = !busy, onClick = { toDelete = doc }) {
                                    Icon(Icons.Filled.Delete, contentDescription = "Delete")
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    pending?.let { uri ->
        var category by remember { mutableStateOf(DocumentCategory.PRESCRIPTION) }
        var title by remember { mutableStateOf(pendingName) }
        AlertDialog(
            onDismissRequest = { pending = null },
            title = { Text("Save document") },
            text = {
                Column {
                    OutlinedTextField(title, { title = it.take(80) }, label = { Text("Name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    Spacer(Modifier.height(8.dp))
                    DocumentCategory.values().forEach { option ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(selected = category == option, onClick = { category = option })
                            Text(option.label)
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.add(context, uri, title, category)
                    pending = null
                }) { Text("Save") }
            },
            dismissButton = { TextButton(onClick = { pending = null }) { Text("Cancel") } }
        )
    }

    toDelete?.let { doc ->
        AlertDialog(
            onDismissRequest = { toDelete = null },
            title = { Text("Delete this document?") },
            text = { Text("\"${doc.title}\" will be removed permanently.") },
            confirmButton = { TextButton(onClick = { viewModel.delete(doc); toDelete = null }) { Text("Delete") } },
            dismissButton = { TextButton(onClick = { toDelete = null }) { Text("Cancel") } }
        )
    }
}
