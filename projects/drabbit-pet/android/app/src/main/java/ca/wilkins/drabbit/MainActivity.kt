package ca.wilkins.drabbit

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.viewmodel.compose.viewModel
import ca.wilkins.drabbit.ui.ConnectScreen
import ca.wilkins.drabbit.ui.PetScreen
import ca.wilkins.drabbit.ui.PetViewModel
import ca.wilkins.drabbit.ui.Phase
import ca.wilkins.drabbit.ui.theme.DrabbitTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            DrabbitTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    DrabbitApp()
                }
            }
        }
    }
}

@Composable
private fun DrabbitApp(viewModel: PetViewModel = viewModel()) {
    val state by viewModel.uiState.collectAsState()

    // Poll only while the screen is actually in front of the owner.
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner, viewModel) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> viewModel.setForeground(true)
                Lifecycle.Event.ON_PAUSE -> viewModel.setForeground(false)
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            viewModel.setForeground(false)
        }
    }

    when (state.phase) {
        Phase.Connect -> ConnectScreen(
            saved = state.savedSettings,
            connecting = state.connecting,
            error = state.connectError,
            onConnect = { host, port, token -> viewModel.connect(host, port, token) },
        )

        Phase.Pet -> {
            val pet = state.pet
            if (pet == null) {
                // Connecting straight into the pet phase happens only
                // with a pet already fetched; guard anyway.
                ConnectScreen(
                    saved = state.savedSettings,
                    connecting = true,
                    error = null,
                    onConnect = { host, port, token -> viewModel.connect(host, port, token) },
                )
            } else {
                PetScreen(
                    pet = pet,
                    events = state.events,
                    online = state.online,
                    actionInFlight = state.actionInFlight,
                    message = state.message,
                    onAction = { kind -> viewModel.performAction(kind) },
                    onRefresh = { viewModel.refresh() },
                    onEditConnection = { viewModel.backToConnect() },
                    onMessageShown = { viewModel.consumeMessage() },
                )
            }
        }
    }
}
