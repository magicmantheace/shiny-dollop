package ca.wilkins.drabbit.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ca.wilkins.drabbit.model.ActionKind
import ca.wilkins.drabbit.model.CareRules
import ca.wilkins.drabbit.model.Format
import ca.wilkins.drabbit.model.PetEvent
import ca.wilkins.drabbit.model.PetSummary
import kotlin.math.roundToInt

/**
 * The pet screen: the drabbit, its needs, the care buttons the rules
 * allow, and what it has been up to. Everything shown came from the
 * desktop — this screen is a window, not a copy.
 */
@Composable
fun PetScreen(
    pet: PetSummary,
    events: List<PetEvent>,
    online: Boolean,
    actionInFlight: Boolean,
    message: String?,
    onAction: (ActionKind) -> Unit,
    onRefresh: () -> Unit,
    onEditConnection: () -> Unit,
    onMessageShown: () -> Unit,
) {
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(message) {
        if (message != null) {
            snackbar.showSnackbar(message)
            onMessageShown()
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        LazyColumn(
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.Top,
        ) {
            item {
                Spacer(Modifier.height(16.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Column {
                        Text(pet.name, style = MaterialTheme.typography.headlineMedium)
                        Text(
                            subtitle(pet),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Column {
                        OutlinedButton(onClick = onRefresh) { Text("Refresh") }
                        TextButton(onClick = onEditConnection) { Text("Connection") }
                    }
                }
            }

            if (!online) {
                item {
                    Banner(
                        text = "PC offline — showing the last known state. " +
                            "Care actions will fail until the desktop is back.",
                    )
                }
            }
            if (CareRules.isDead(pet)) {
                item {
                    Banner(
                        text = "${pet.name} has died" +
                            (pet.deathCause?.let { " ($it)" } ?: "") +
                            ". Starting the next generation is done on the desktop.",
                    )
                }
            }

            item {
                DrabbitCanvas(
                    pet = pet,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(220.dp),
                )
            }

            item {
                NeedBar("Hunger", pet.needs.hunger)
                NeedBar("Happiness", pet.needs.happiness)
                NeedBar("Energy", pet.needs.energy)
                NeedBar("Cleanliness", pet.needs.cleanliness)
                NeedBar("Health", pet.health)
                NeedBar("Care score", pet.careScore)
                if (pet.messes > 0) {
                    Text(
                        "Messes to clean up: ${pet.messes}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
                Spacer(Modifier.height(8.dp))
            }

            item {
                Text("Care", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                ActionButtons(pet, online, actionInFlight, onAction)
                Spacer(Modifier.height(20.dp))
            }

            item {
                Text("Recent events", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
            }
            if (events.isEmpty()) {
                item {
                    Text(
                        "Nothing yet — events will appear here as they happen.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                items(events.asReversed()) { event ->
                    Column(modifier = Modifier.padding(vertical = 4.dp)) {
                        Text(event.detail, style = MaterialTheme.typography.bodyMedium)
                        Text(
                            event.kind,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            item { Spacer(Modifier.height(24.dp)) }
        }
        SnackbarHost(hostState = snackbar, modifier = Modifier.padding(8.dp))
    }
}

private fun subtitle(pet: PetSummary): String {
    val parts = mutableListOf<String>()
    parts += Format.stageLabel(pet.stage)
    pet.adultForm?.let { parts += it.replaceFirstChar { c -> c.uppercase() } }
    parts += "mood: ${pet.mood}"
    if (pet.stage != "egg" && pet.stage != "dead") parts += "age ${Format.age(pet.ageMs)}"
    parts += "generation ${pet.generation}"
    if (pet.sick) parts += "SICK"
    if (pet.asleep) parts += "asleep"
    return parts.joinToString(" · ")
}

@Composable
private fun Banner(text: String) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer,
        ),
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
    ) {
        Text(
            text,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(12.dp),
        )
    }
}

@Composable
private fun NeedBar(label: String, value: Double) {
    val fraction = (value / 100.0).toFloat().coerceIn(0f, 1f)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
        Text(value.roundToInt().toString(), style = MaterialTheme.typography.bodyMedium)
    }
    LinearProgressIndicator(
        progress = { fraction },
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun ActionButtons(
    pet: PetSummary,
    online: Boolean,
    actionInFlight: Boolean,
    onAction: (ActionKind) -> Unit,
) {
    val states = CareRules.actionsFor(pet)
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        states.chunked(2).forEach { rowStates ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                for (state in rowStates) {
                    Column(modifier = Modifier.weight(1f)) {
                        Button(
                            onClick = { onAction(state.kind) },
                            enabled = state.enabled && online && !actionInFlight,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(state.kind.label)
                        }
                        if (!state.enabled && state.reason != null) {
                            Text(
                                state.reason,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
                if (rowStates.size == 1) {
                    Spacer(Modifier.weight(1f))
                }
            }
        }
    }
}
