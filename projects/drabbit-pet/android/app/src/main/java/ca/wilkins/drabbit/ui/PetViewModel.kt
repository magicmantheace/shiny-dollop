package ca.wilkins.drabbit.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import ca.wilkins.drabbit.data.ConnectionSettings
import ca.wilkins.drabbit.data.SettingsStore
import ca.wilkins.drabbit.model.ActionKind
import ca.wilkins.drabbit.model.PetEvent
import ca.wilkins.drabbit.model.PetSummary
import ca.wilkins.drabbit.net.DrabbitClient
import ca.wilkins.drabbit.net.DrabbitError
import ca.wilkins.drabbit.net.HttpUrlConnectionTransport
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class Phase { Connect, Pet }

data class PetUiState(
    val phase: Phase = Phase.Connect,
    /** Settings as loaded from the store (the connect form's prefill). */
    val savedSettings: ConnectionSettings,
    val connecting: Boolean = false,
    val connectError: String? = null,
    val pet: PetSummary? = null,
    /** Oldest first, as the server's log is; the screen reverses for display. */
    val events: List<PetEvent> = emptyList(),
    /** False after a failed poll: the screen shows last-known state + a banner. */
    val online: Boolean = true,
    val actionInFlight: Boolean = false,
    /** One-shot message for the snackbar; cleared by [PetViewModel.consumeMessage]. */
    val message: String? = null,
)

/**
 * Holds the companion session: connection, polling, actions.
 *
 * The app holds NO simulation — every number on screen came from the
 * desktop's companion server, and the pet keeps living there whether
 * or not this phone is looking.
 */
class PetViewModel(application: Application) : AndroidViewModel(application) {

    private val settingsStore = SettingsStore(application)

    @Volatile
    private var settings: ConnectionSettings = settingsStore.load()

    private val client = DrabbitClient(HttpUrlConnectionTransport()) { settings }

    private val _uiState = MutableStateFlow(PetUiState(savedSettings = settings))
    val uiState: StateFlow<PetUiState> = _uiState.asStateFlow()

    /** Event-log cursor for delta polling (null until first sync). */
    private var eventCursor: Long? = null

    private var pollJob: Job? = null

    init {
        // Returning owner with a full saved connection: try it right away.
        if (settings.isComplete) connectInternal(save = false)
    }

    // -- connect -------------------------------------------------------

    fun connect(hostRaw: String, portRaw: String, tokenRaw: String) {
        settings = ConnectionSettings.normalize(hostRaw, portRaw, tokenRaw)
        connectInternal(save = true)
    }

    private fun connectInternal(save: Boolean) {
        if (_uiState.value.connecting) return
        _uiState.update { it.copy(connecting = true, connectError = null) }
        viewModelScope.launch {
            try {
                val pet = io { client.fetchStatus() }
                if (save) settingsStore.save(settings)
                eventCursor = null
                _uiState.update {
                    it.copy(
                        phase = Phase.Pet,
                        connecting = false,
                        connectError = null,
                        savedSettings = settings,
                        pet = pet,
                        online = true,
                    )
                }
                syncEvents()
                restartPolling()
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        phase = Phase.Connect,
                        connecting = false,
                        connectError = userMessage(e),
                    )
                }
            }
        }
    }

    /** Back to the connect form (e.g. to fix the token or address). */
    fun backToConnect() {
        pollJob?.cancel()
        pollJob = null
        _uiState.update {
            it.copy(phase = Phase.Connect, savedSettings = settings, connectError = null)
        }
    }

    // -- polling ---------------------------------------------------------

    fun setForeground(foreground: Boolean) {
        if (foreground) {
            if (_uiState.value.phase == Phase.Pet) {
                refresh()
                restartPolling()
            }
        } else {
            pollJob?.cancel()
            pollJob = null
        }
    }

    private fun restartPolling() {
        pollJob?.cancel()
        pollJob = viewModelScope.launch {
            while (true) {
                delay(POLL_INTERVAL_MS)
                if (_uiState.value.phase != Phase.Pet) break
                pollOnce()
            }
        }
    }

    fun refresh() {
        if (_uiState.value.phase != Phase.Pet) return
        viewModelScope.launch { pollOnce() }
    }

    private suspend fun pollOnce() {
        try {
            val pet = io { client.fetchStatus() }
            _uiState.update { it.copy(pet = pet, online = true) }
            syncEvents()
        } catch (e: DrabbitError) {
            if (e is DrabbitError.BadToken) {
                // Token rotated on the desktop mid-session: back to the form.
                pollJob?.cancel()
                _uiState.update {
                    it.copy(phase = Phase.Connect, connectError = userMessage(e), online = false)
                }
            } else {
                _uiState.update { it.copy(online = false) }
            }
        } catch (e: Exception) {
            _uiState.update { it.copy(online = false) }
        }
    }

    /** First sync takes the whole retained window (since = 0, capped
     *  for display); later syncs are cursor deltas. */
    private suspend fun syncEvents() {
        try {
            val firstSync = eventCursor == null
            val page = io { client.fetchEvents(if (firstSync) 0L else eventCursor) }
            eventCursor = page.cursor
            if (page.events.isNotEmpty()) {
                _uiState.update { state ->
                    val merged = if (firstSync) page.events else state.events + page.events
                    state.copy(events = merged.takeLast(MAX_EVENTS_SHOWN))
                }
            }
        } catch (e: Exception) {
            // Events are decoration on the status; a failed sync just
            // retries on the next poll (the cursor is only advanced
            // on success, so nothing is skipped or duplicated).
        }
    }

    // -- actions ---------------------------------------------------------

    fun performAction(kind: ActionKind) {
        if (_uiState.value.actionInFlight) return
        _uiState.update { it.copy(actionInFlight = true) }
        viewModelScope.launch {
            try {
                val outcome = io { client.performAction(kind) }
                _uiState.update {
                    it.copy(pet = outcome.summary, online = true, actionInFlight = false)
                }
                // The action's events are NOT appended from the action
                // response — the events sync below fetches them via
                // the cursor, so every event reaches the list exactly
                // once even across polls.
                syncEvents()
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(actionInFlight = false, message = userMessage(e))
                }
            }
        }
    }

    fun consumeMessage() {
        _uiState.update { it.copy(message = null) }
    }

    private suspend fun <T> io(block: () -> T): T = withContext(Dispatchers.IO) { block() }

    private companion object {
        const val POLL_INTERVAL_MS = 15_000L
        const val MAX_EVENTS_SHOWN = 100
    }
}
