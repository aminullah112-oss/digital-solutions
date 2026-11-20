package com.digitalsolutions.diagnosticlab.presentation.patient.fever

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewmodel.compose.viewModel
import com.digitalsolutions.diagnosticlab.domain.fever.*
import com.digitalsolutions.diagnosticlab.presentation.components.BigPrimaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.BigSecondaryButton
import com.digitalsolutions.diagnosticlab.presentation.components.SectionCard
import com.digitalsolutions.diagnosticlab.presentation.components.StatusChip
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

private const val STEP_INTRO = 0
private const val STEP_ABOUT = 1
private const val STEP_FEVER = 2
private const val STEP_SYMPTOMS = 3
private const val STEP_EXPOSURES = 4
private const val STEP_WARNINGS = 5
private const val STEP_RESULT = 6

/** Holds the answers for one run. Nothing is saved or sent anywhere: closing the screen
 * discards them. */
class FeverCheckViewModel : ViewModel() {
    private val _answers = MutableStateFlow(FeverAnswers())
    val answers: StateFlow<FeverAnswers> = _answers.asStateFlow()
    private val _step = MutableStateFlow(STEP_INTRO)
    val step: StateFlow<Int> = _step.asStateFlow()

    fun setAge(v: AgeGroup) { _answers.value = _answers.value.copy(age = v) }
    fun setSex(v: Sex) {
        // Pregnancy only applies to women; clear it if the answer changes.
        val a = _answers.value
        _answers.value = a.copy(sex = v, conditions = if (v != Sex.FEMALE) a.conditions - HealthCondition.PREGNANT else a.conditions)
    }
    fun setDuration(v: FeverDuration) { _answers.value = _answers.value.copy(duration = v) }
    fun setPattern(v: FeverPattern) { _answers.value = _answers.value.copy(pattern = v) }
    fun toggleCondition(v: HealthCondition) { _answers.value = _answers.value.copy(conditions = _answers.value.conditions.toggle(v)) }
    fun toggleSymptom(v: Symptom) { _answers.value = _answers.value.copy(symptoms = _answers.value.symptoms.toggle(v)) }
    fun toggleExposure(v: Exposure) { _answers.value = _answers.value.copy(exposures = _answers.value.exposures.toggle(v)) }
    fun toggleWarning(v: WarningSign) { _answers.value = _answers.value.copy(warningSigns = _answers.value.warningSigns.toggle(v)) }
    fun clearWarnings() { _answers.value = _answers.value.copy(warningSigns = emptySet()) }

    fun canContinue(): Boolean = when (_step.value) {
        STEP_ABOUT -> _answers.value.age != null && _answers.value.sex != null
        STEP_FEVER -> _answers.value.duration != null
        else -> true
    }

    fun next() { if (_step.value < STEP_RESULT && canContinue()) _step.value = _step.value + 1 }
    fun back() { if (_step.value > STEP_INTRO) _step.value = _step.value - 1 }
    fun restart() { _answers.value = FeverAnswers(); _step.value = STEP_INTRO }

    private fun <T> Set<T>.toggle(v: T): Set<T> = if (v in this) this - v else this + v
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FeverCheckScreen(onBack: () -> Unit, onBookTests: (Set<String>) -> Unit) {
    val vm: FeverCheckViewModel = viewModel()
    val step by vm.step.collectAsState()
    val answers by vm.answers.collectAsState()

    BackHandler(enabled = step > STEP_INTRO) { vm.back() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Fever Check") },
                navigationIcon = {
                    IconButton(onClick = { if (step > STEP_INTRO) vm.back() else onBack() }) { Icon(Icons.Filled.ArrowBack, null) }
                }
            )
        },
        bottomBar = {
            if (step in STEP_ABOUT..STEP_WARNINGS) {
                Surface(shadowElevation = 8.dp) {
                    Column(Modifier.padding(16.dp)) {
                        BigPrimaryButton(
                            text = if (step == STEP_WARNINGS) "See suggested tests" else "Next",
                            enabled = vm.canContinue(),
                            onClick = { vm.next() }
                        )
                    }
                }
            }
        }
    ) { padding ->
        Column(
            Modifier.padding(padding).padding(horizontal = 16.dp).verticalScroll(rememberScrollState())
        ) {
            if (step in STEP_ABOUT..STEP_WARNINGS) {
                Spacer(Modifier.height(8.dp))
                LinearProgressIndicator(progress = step / 5f, modifier = Modifier.fillMaxWidth())
                Text("Step $step of 5", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(12.dp))
            }
            when (step) {
                STEP_INTRO -> IntroStep(onStart = { vm.next() })
                STEP_ABOUT -> AboutStep(answers, vm)
                STEP_FEVER -> FeverStep(answers, vm)
                STEP_SYMPTOMS -> SymptomsStep(answers, vm)
                STEP_EXPOSURES -> ExposuresStep(answers, vm)
                STEP_WARNINGS -> WarningsStep(answers, vm)
                else -> ResultStep(assess(answers), onBookTests = onBookTests, onRestart = { vm.restart() })
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun IntroStep(onStart: () -> Unit) {
    Spacer(Modifier.height(12.dp))
    Text("Which tests might you need?", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
    Spacer(Modifier.height(12.dp))
    Text(
        "Answer a few simple questions about your fever. We'll suggest the blood and urine tests doctors commonly advise for it, based on fevers that are common in South India, such as dengue, typhoid, scrub typhus and leptospirosis.",
        style = MaterialTheme.typography.bodyLarge
    )
    Spacer(Modifier.height(12.dp))
    SectionCard {
        Text("Please remember", fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(4.dp))
        Text("• This is guidance, not a diagnosis. Only a doctor can tell you what is wrong.")
        Text("• Your answers stay on your phone. Nothing is saved or sent.")
        Text("• If you feel very unwell, go to a hospital. Don't wait for test results.")
    }
    Spacer(Modifier.height(20.dp))
    BigPrimaryButton(text = "Start", onClick = onStart)
}

@Composable
private fun StepTitle(title: String, subtitle: String? = null) {
    Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
    if (subtitle != null) {
        Spacer(Modifier.height(4.dp))
        Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    Spacer(Modifier.height(12.dp))
}

@Composable
private fun SectionLabel(text: String) {
    Spacer(Modifier.height(16.dp))
    Text(text, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    Spacer(Modifier.height(4.dp))
}

@Composable
private fun AboutStep(a: FeverAnswers, vm: FeverCheckViewModel) {
    StepTitle("About the person with fever")
    SectionLabel("Age")
    AgeGroup.values().forEach { SingleRow(it.label, a.age == it) { vm.setAge(it) } }
    SectionLabel("Sex")
    Sex.values().forEach { SingleRow(it.label, a.sex == it) { vm.setSex(it) } }
    SectionLabel("Any of these? (tick all that apply)")
    HealthCondition.values()
        .filter { it != HealthCondition.PREGNANT || (a.sex == Sex.FEMALE && a.age != AgeGroup.INFANT && a.age != AgeGroup.CHILD) }
        .forEach { c -> MultiRow(c.label, c in a.conditions) { vm.toggleCondition(c) } }
}

@Composable
private fun FeverStep(a: FeverAnswers, vm: FeverCheckViewModel) {
    StepTitle("About the fever")
    SectionLabel("How long has the fever lasted?")
    FeverDuration.values().forEach { SingleRow(it.label, a.duration == it) { vm.setDuration(it) } }
    SectionLabel("How does it behave?")
    FeverPattern.values().forEach { SingleRow(it.label, a.pattern == it) { vm.setPattern(it) } }
}

@Composable
private fun SymptomsStep(a: FeverAnswers, vm: FeverCheckViewModel) {
    StepTitle("Other symptoms", "Tick everything that applies. Skip if none.")
    Symptom.values().forEach { s -> MultiRow(s.label, s in a.symptoms) { vm.toggleSymptom(s) } }
}

@Composable
private fun ExposuresStep(a: FeverAnswers, vm: FeverCheckViewModel) {
    StepTitle("In the last 2 weeks", "Where the person has been matters for fever. Tick everything that applies.")
    Exposure.values().forEach { e -> MultiRow(e.label, e in a.exposures) { vm.toggleExposure(e) } }
}

@Composable
private fun WarningsStep(a: FeverAnswers, vm: FeverCheckViewModel) {
    StepTitle("Warning signs", "Any of these needs medical help straight away.")
    WarningSign.values().forEach { w -> MultiRow(w.label, w in a.warningSigns) { vm.toggleWarning(w) } }
    MultiRow("None of these", a.warningSigns.isEmpty()) { vm.clearWarnings() }
}

@Composable
private fun SingleRow(label: String, selected: Boolean, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        RadioButton(selected = selected, onClick = null)
        Spacer(Modifier.width(12.dp))
        Text(label, style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
private fun MultiRow(label: String, checked: Boolean, onToggle: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onToggle).padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Checkbox(checked = checked, onCheckedChange = null)
        Spacer(Modifier.width(12.dp))
        Text(label, style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
private fun ResultStep(result: FeverAssessment, onBookTests: (Set<String>) -> Unit, onRestart: () -> Unit) {
    val (container, content) = when (result.urgency) {
        Urgency.EMERGENCY -> MaterialTheme.colorScheme.errorContainer to MaterialTheme.colorScheme.onErrorContainer
        Urgency.SAME_DAY -> MaterialTheme.colorScheme.tertiaryContainer to MaterialTheme.colorScheme.onTertiaryContainer
        Urgency.WITHIN_DAYS -> MaterialTheme.colorScheme.secondaryContainer to MaterialTheme.colorScheme.onSecondaryContainer
        Urgency.HOME_CARE -> MaterialTheme.colorScheme.primaryContainer to MaterialTheme.colorScheme.onPrimaryContainer
    }
    Spacer(Modifier.height(8.dp))
    Card(colors = CardDefaults.cardColors(containerColor = container, contentColor = content), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(result.urgency.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(6.dp))
            result.urgencyReasons.forEach { Text("• $it", style = MaterialTheme.typography.bodyMedium) }
        }
    }

    Spacer(Modifier.height(16.dp))
    Text("Tests doctors commonly advise for this", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
    Text(
        "These are suggestions to discuss with your doctor, who decides what you actually need.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )
    Spacer(Modifier.height(8.dp))
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        result.tests.forEach { TestCard(it) }
    }

    Spacer(Modifier.height(16.dp))
    SectionCard("Good to know") {
        result.notes.forEach { Text("• $it", style = MaterialTheme.typography.bodyMedium) }
    }

    Spacer(Modifier.height(16.dp))
    if (result.bookableIds.isNotEmpty()) {
        BigPrimaryButton(text = "Book tests", onClick = { onBookTests(result.bookableIds) })
        Spacer(Modifier.height(4.dp))
        Text(
            "We'll pre-select these tests where your chosen lab offers them. You can change the selection.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(Modifier.height(8.dp))
    }
    BigSecondaryButton(text = "Start again", onClick = onRestart)
    Spacer(Modifier.height(16.dp))
    Text(
        "Fever Check gives general guidance only. It is not a diagnosis and does not replace a doctor. Your answers were not saved or sent anywhere.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )
}

@Composable
private fun TestCard(test: TestAdvice) {
    val chipColor: Color = when (test.priority) {
        TestPriority.ESSENTIAL -> MaterialTheme.colorScheme.error
        TestPriority.RECOMMENDED -> MaterialTheme.colorScheme.primary
        TestPriority.IF_DOCTOR_ADVISES -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    SectionCard {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
            Text(test.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            Spacer(Modifier.width(8.dp))
            StatusChip(test.priority.label, chipColor)
        }
        Spacer(Modifier.height(4.dp))
        test.reasons.forEach { Text(it, style = MaterialTheme.typography.bodyMedium) }
        test.timing?.let {
            Spacer(Modifier.height(4.dp))
            Text(it, style = MaterialTheme.typography.bodySmall, fontStyle = FontStyle.Italic, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(6.dp))
        Text(
            if (test.catalogIds.isNotEmpty()) "Available to book in the app" else "Ask your doctor or lab about this test",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
