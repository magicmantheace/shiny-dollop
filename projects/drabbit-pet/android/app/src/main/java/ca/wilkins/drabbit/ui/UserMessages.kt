package ca.wilkins.drabbit.ui

import ca.wilkins.drabbit.net.DrabbitError

/** DrabbitError → the sentence the owner actually reads. */
fun userMessage(error: Throwable): String = when (error) {
    is DrabbitError.Unreachable ->
        "Couldn't reach the PC — check the address, that this phone is on the " +
            "same Wi-Fi (or Tailscale), and that the companion is enabled in the " +
            "desktop care panel."
    is DrabbitError.BadToken ->
        "The server rejected the token — copy the current one from the Companion " +
            "section of the desktop care panel."
    is DrabbitError.DesktopOnly ->
        "That one's a desktop-side decision — it can only be done on the PC."
    is DrabbitError.StateError -> error.serverMessage
    is DrabbitError.ServerError ->
        "The desktop answered with an error (HTTP ${error.httpStatus})."
    is DrabbitError.MalformedResponse ->
        "The desktop's answer couldn't be understood — the apps may be out of sync."
    else -> error.message ?: "Something went wrong."
}
