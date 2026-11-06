package ca.wilkins.drabbit.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The pure half of settings: input normalization and completeness.
 * (SettingsStore itself needs an Android Context for SharedPreferences
 * and is owner-device territory; it is a three-field read/write with
 * no logic beyond what is tested here via ConnectionSettings.)
 */
class ConnectionSettingsTest {

    @Test
    fun normalize_stripsSchemeWhitespaceAndTrailingSlash() {
        val s = ConnectionSettings.normalize("  http://192.168.1.20/ ", "", "  tok  ")
        assertEquals("192.168.1.20", s.host)
        assertEquals(ConnectionSettings.DEFAULT_PORT, s.port)
        assertEquals("tok", s.token)
    }

    @Test
    fun normalize_keepsTailscaleStyleNames() {
        val s = ConnectionSettings.normalize("adam-pc.tailnet-name.ts.net", "8931", "abc")
        assertEquals("adam-pc.tailnet-name.ts.net", s.host)
        assertEquals(8931, s.port)
        assertEquals("http://adam-pc.tailnet-name.ts.net:8931", s.baseUrl)
    }

    @Test
    fun normalize_badPortFallsBackToDefault() {
        assertEquals(
            ConnectionSettings.DEFAULT_PORT,
            ConnectionSettings.normalize("pc", "not-a-port", "t").port,
        )
        assertEquals(
            ConnectionSettings.DEFAULT_PORT,
            ConnectionSettings.normalize("pc", "70000", "t").port,
        )
        assertEquals(
            ConnectionSettings.DEFAULT_PORT,
            ConnectionSettings.normalize("pc", "0", "t").port,
        )
        assertEquals(1234, ConnectionSettings.normalize("pc", "1234", "t").port)
    }

    @Test
    fun isComplete_requiresHostTokenAndValidPort() {
        assertTrue(ConnectionSettings("192.168.1.20", 8931, "tok").isComplete)
        assertFalse(ConnectionSettings("", 8931, "tok").isComplete)
        assertFalse(ConnectionSettings("192.168.1.20", 8931, "").isComplete)
        assertFalse(ConnectionSettings("192.168.1.20", 0, "tok").isComplete)
    }

    @Test
    fun baseUrl_combinesHostAndPort() {
        assertEquals(
            "http://100.64.0.5:8931",
            ConnectionSettings("100.64.0.5", 8931, "t").baseUrl,
        )
    }
}
