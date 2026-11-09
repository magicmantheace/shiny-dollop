package ca.wilkins.drabbit.data

import android.content.Context

/**
 * Where the phone should knock: the desktop PC's address on the LAN or
 * its Tailscale address, the companion port, and the pairing token.
 */
data class ConnectionSettings(
    val host: String,
    val port: Int,
    val token: String,
) {
    val baseUrl: String get() = "http://$host:$port"

    /** Everything needed to attempt a connection. */
    val isComplete: Boolean
        get() = host.isNotBlank() && token.isNotBlank() && port in 1..65535

    companion object {
        const val DEFAULT_PORT = 8931

        /**
         * Forgiving input cleanup for the connect form: trims
         * whitespace, strips a pasted scheme ("http://…") and anything
         * after the host ("/", ":port" pasted as part of the host is
         * left to the port field), and falls back to the default port
         * for blank/unparsable port text.
         */
        fun normalize(hostRaw: String, portRaw: String, tokenRaw: String): ConnectionSettings {
            var host = hostRaw.trim()
            if (host.startsWith("http://", ignoreCase = true)) host = host.substring(7)
            if (host.startsWith("https://", ignoreCase = true)) host = host.substring(8)
            host = host.substringBefore('/').trim()
            val port = portRaw.trim().toIntOrNull()
                ?.takeIf { it in 1..65535 }
                ?: DEFAULT_PORT
            return ConnectionSettings(host = host, port = port, token = tokenRaw.trim())
        }
    }
}

/**
 * Persists [ConnectionSettings] in app-private SharedPreferences.
 * The token lives only there — no account, no cloud, nothing leaves
 * the phone except the requests to the owner's own PC.
 */
class SettingsStore(context: Context) {

    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun load(): ConnectionSettings = ConnectionSettings(
        host = prefs.getString(KEY_HOST, "") ?: "",
        port = prefs.getInt(KEY_PORT, ConnectionSettings.DEFAULT_PORT),
        token = prefs.getString(KEY_TOKEN, "") ?: "",
    )

    fun save(settings: ConnectionSettings) {
        prefs.edit()
            .putString(KEY_HOST, settings.host)
            .putInt(KEY_PORT, settings.port)
            .putString(KEY_TOKEN, settings.token)
            .apply()
    }

    private companion object {
        const val PREFS_NAME = "drabbit-companion"
        const val KEY_HOST = "host"
        const val KEY_PORT = "port"
        const val KEY_TOKEN = "token"
    }
}
