package ca.wilkins.drabbit.net

import ca.wilkins.drabbit.Fixtures
import ca.wilkins.drabbit.data.ConnectionSettings
import ca.wilkins.drabbit.model.ActionKind
import java.io.IOException
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Client behaviour against fixtures captured from the REAL P3 server
 * (see Fixtures.kt). The transport is faked; everything above it —
 * URLs, auth header, body shape, parsing, error mapping — is the
 * production code.
 */
class DrabbitClientTest {

    private class FakeTransport(var handler: (HttpRequest) -> HttpResponse) : HttpTransport {
        val requests = mutableListOf<HttpRequest>()
        override fun execute(request: HttpRequest): HttpResponse {
            requests += request
            return handler(request)
        }
    }

    private val settings = ConnectionSettings(host = "192.168.1.20", port = 8931, token = "test-token")

    private fun clientReturning(status: Int, body: String): Pair<DrabbitClient, FakeTransport> {
        val transport = FakeTransport { HttpResponse(status, body) }
        return DrabbitClient(transport) { settings } to transport
    }

    private inline fun <reified T : Throwable> expectError(block: () -> Unit): T {
        val caught = try {
            block()
            null
        } catch (e: Throwable) {
            e
        }
        assertTrue("expected ${T::class.java.name} but got $caught", caught is T)
        return caught as T
    }

    // -- status ---------------------------------------------------------

    @Test
    fun fetchStatus_parsesBabyFixture_andSendsAuthHeader() {
        val (client, transport) = clientReturning(200, Fixtures.text("status_baby.json"))
        val pet = client.fetchStatus()
        assertEquals("Pip", pet.name)
        assertEquals("royal", pet.fur)
        assertEquals("baby", pet.stage)
        assertNull(pet.adultForm)
        assertNull(pet.deathCause)
        assertEquals("joyful", pet.mood)
        assertEquals(80.0, pet.needs.hunger, 0.001)
        assertEquals(100.0, pet.needs.energy, 0.001)
        assertEquals(100.0, pet.health, 0.001)
        assertEquals(70.0, pet.careScore, 0.001)
        assertEquals(0L, pet.ageMs)
        assertFalse(pet.asleep)
        assertFalse(pet.sick)
        assertEquals(0, pet.messes)
        assertTrue(pet.readyToHatch)
        assertEquals(1, pet.generation)

        val request = transport.requests.single()
        assertEquals("GET", request.method)
        assertEquals("http://192.168.1.20:8931/v1/status", request.url)
        assertEquals("Bearer test-token", request.headers["Authorization"])
        assertNull(request.body)
    }

    @Test
    fun fetchStatus_parsesDeadFixture() {
        val (client, _) = clientReturning(200, Fixtures.text("status_dead.json"))
        val pet = client.fetchStatus()
        assertEquals("dead", pet.stage)
        assertEquals("neglect", pet.deathCause)
        assertEquals("ember", pet.fur)
    }

    @Test
    fun fetchStatus_parsesEggReadyFixture() {
        val (client, _) = clientReturning(200, Fixtures.text("status_egg_ready.json"))
        val pet = client.fetchStatus()
        assertEquals("egg", pet.stage)
        assertTrue(pet.readyToHatch)
    }

    // -- actions ----------------------------------------------------------

    @Test
    fun performAction_feedMeal_returnsOutcome_andPostsKindVocabulary() {
        val (client, transport) = clientReturning(200, Fixtures.text("action_feed_meal_ok.json"))
        val outcome = client.performAction(ActionKind.FEED_MEAL)
        assertEquals(100.0, outcome.summary.needs.hunger, 0.001)
        assertEquals(98.0, outcome.summary.needs.cleanliness, 0.001)
        assertEquals(1, outcome.events.size)
        assertEquals("fed", outcome.events[0].kind)
        assertEquals("Ate a proper meal.", outcome.events[0].detail)
        assertEquals(1_700_000_600_000L, outcome.events[0].t)

        val request = transport.requests.single()
        assertEquals("POST", request.method)
        assertEquals("http://192.168.1.20:8931/v1/actions", request.url)
        assertEquals("feed-meal", JSONObject(request.body!!).getString("kind"))
    }

    @Test
    fun performAction_hatch_returnsHatchedEvent() {
        val (client, _) = clientReturning(200, Fixtures.text("action_hatch_ok.json"))
        val outcome = client.performAction(ActionKind.HATCH)
        assertEquals("baby", outcome.summary.stage)
        assertTrue(outcome.events.any { it.kind == "hatched" })
    }

    // -- error mapping ------------------------------------------------------

    @Test
    fun http401_mapsToBadToken() {
        val (client, _) = clientReturning(401, Fixtures.text("error_401.json"))
        expectError<DrabbitError.BadToken> { client.fetchStatus() }
    }

    @Test
    fun http403_mapsToDesktopOnly() {
        val (client, _) = clientReturning(403, Fixtures.text("error_403_desktop_only.json"))
        val error = expectError<DrabbitError.DesktopOnly> {
            client.performAction(ActionKind.NEW_EGG)
        }
        assertTrue(error.serverMessage.contains("desktop-only"))
    }

    @Test
    fun http409_mapsToStateError_withServerCodeAndMessage() {
        val (client, _) = clientReturning(409, Fixtures.text("error_409_not_sick.json"))
        val error = expectError<DrabbitError.StateError> {
            client.performAction(ActionKind.MEDICINE)
        }
        assertEquals("not_sick", error.code)
        assertTrue(error.serverMessage.contains("Not sick"))
    }

    @Test
    fun http404_mapsToServerError() {
        val (client, _) = clientReturning(404, Fixtures.text("error_404.json"))
        val error = expectError<DrabbitError.ServerError> { client.fetchStatus() }
        assertEquals(404, error.httpStatus)
        assertEquals("not_found", error.code)
    }

    @Test
    fun http500_mapsToServerError() {
        val (client, _) = clientReturning(
            500,
            """{"ok":false,"error":{"code":"internal","message":"boom"}}""",
        )
        val error = expectError<DrabbitError.ServerError> { client.fetchStatus() }
        assertEquals(500, error.httpStatus)
        assertEquals("internal", error.code)
    }

    @Test
    fun transportFailure_mapsToUnreachable() {
        val transport = FakeTransport { throw IOException("Connection refused") }
        val client = DrabbitClient(transport) { settings }
        expectError<DrabbitError.Unreachable> { client.fetchStatus() }
    }

    @Test
    fun malformedJson_mapsToMalformedResponse() {
        val (client, _) = clientReturning(200, "<html>not the server</html>")
        expectError<DrabbitError.MalformedResponse> { client.fetchStatus() }
    }

    @Test
    fun jsonWithoutPet_mapsToMalformedResponse() {
        val (client, _) = clientReturning(200, """{"ok":true,"serverNow":1}""")
        expectError<DrabbitError.MalformedResponse> { client.fetchStatus() }
    }

    // -- events ---------------------------------------------------------------

    @Test
    fun fetchEvents_bootstrap_returnsNoEventsAndCursor_andOmitsSince() {
        val (client, transport) = clientReturning(200, Fixtures.text("events_bootstrap.json"))
        val page = client.fetchEvents(null)
        assertTrue(page.events.isEmpty())
        assertEquals(4L, page.cursor)
        assertFalse(transport.requests.single().url.contains("since"))
    }

    @Test
    fun fetchEvents_delta_returnsOnlyNewerEvents() {
        val (client, transport) = clientReturning(200, Fixtures.text("events_delta.json"))
        val page = client.fetchEvents(4L)
        assertEquals(1, page.events.size)
        assertEquals("played", page.events[0].kind)
        assertEquals(5L, page.cursor)
        assertTrue(transport.requests.single().url.endsWith("/v1/events?since=4"))
    }

    @Test
    fun fetchEvents_caughtUp_returnsEmptyWithSameCursor() {
        val (client, _) = clientReturning(200, Fixtures.text("events_caught_up.json"))
        val page = client.fetchEvents(5L)
        assertTrue(page.events.isEmpty())
        assertEquals(5L, page.cursor)
    }

    @Test
    fun fetchEvents_sinceZero_returnsWholeRetainedWindow() {
        val (client, _) = clientReturning(200, Fixtures.text("events_all.json"))
        val page = client.fetchEvents(0L)
        assertEquals(5, page.events.size)
        assertEquals("created", page.events.first().kind)
        assertEquals("played", page.events.last().kind)
        assertEquals(5L, page.cursor)
    }
}
