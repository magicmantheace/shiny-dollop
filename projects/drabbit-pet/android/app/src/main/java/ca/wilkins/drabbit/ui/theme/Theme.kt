package ca.wilkins.drabbit.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Renfaire-meadow palette, kept close to the desktop pet's fur tones.
private val MeadowGreen = Color(0xFF3E8F3E)
private val EmberRed = Color(0xFFCF4433)
private val RoyalPurple = Color(0xFF67409C)

private val LightColors = lightColorScheme(
    primary = MeadowGreen,
    secondary = RoyalPurple,
    tertiary = EmberRed,
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF7CC47F),
    secondary = Color(0xFFB79CE0),
    tertiary = Color(0xFFE88A7A),
)

@Composable
fun DrabbitTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
