package ca.wilkins.drabbit.net

import ca.wilkins.drabbit.data.ConnectionSettings
import ca.wilkins.drabbit.model.ActionKind
import ca.wilkins.drabbit.model.ActionOutcome
import ca.wilkins.drabbit.model.EventsPage
import ca.wilkins.drabbit.model.PetSummary
import ca.wilkins.drabbit.model.parsePetEvents
import ca.wilkins.drabbit.model.parsePetSummary
import java.io.IOException
import org.json.JSONException
import org.json.JSONObject

/**
 * The companion-protocol client (docs/DESIGN.md, as built in P3).
 *
 * Blocking calls — invoke from a background dispatcher. Settings are
 * read through [settingsProvider] on every call, so edits take effect
 * without rebuilding the client. Every request carries
 * `Authorization: Bearer <token>`; every failure is a [DrabbitError].
 */
class DrabbitClient(
    private val transport: HttpTransport,
    private val settingsProvider: () -> ConnectionSettings,
) {

    /** GET /v1/status — the pet's current summary (server advances first). */
    fun fetchStatus(): PetSummary {
        val body = request("GET", "/v1/status", body = null)
        val pet = body.optJSONObject("pet")
            ?: throw DrabbitError.MalformedResponse("status response has no \"pet\" object")
        return parsePetSummary(pet)
    }

    /** POST /v1/actions with the panel's `{ kind }` vocabulary. */
    fun performAction(kind: ActionKind): ActionOutcome {
        val payload = JSONObject().put("kind", kind.wire).toString()
        val body = request("POST", "/v1/actions", payload)
        val pet = body.optJSONObject("pet")
            ?: throw DrabbitError.MalformedResponse("action response has no \"pet\" object")
        val events = body.optJSONArray("events")
            ?: throw DrabbitError.MalformedResponse("action response has no \"events\" array")
        return ActionOutcome(summary = parsePetSummary(pet), events = parsePetEvents(events))
    }

    /**
     * GET /v1/events. Pass null to bootstrap (no backlog, just the
     * cursor), 0 for the whole retained window, or the last cursor to
     * poll for only newer events.
     */
    fun fetchEvents(since: Long?): EventsPage {
        val path = if (since == null) "/v1/events" else "/v1/events?since=$since"
        val body = request("GET", path, body = null)
        val events = body.optJSONArray("events")
            ?: throw DrabbitError.MalformedResponse("events response has no \"events\" array")
        val cursor = try {
            body.getLong("cursor")
        } catch (e: JSONException) {
            throw DrabbitError.MalformedResponse("events response has no numeric \"cursor\"")
        }
        val serverNow = body.optLong("serverNow", 0L)
        return EventsPage(events = parsePetEvents(events), cursor = cursor, serverNow = serverNow)
    }

    // -- plumbing ------------------------------------------------------

    /** Performs one request and returns the success envelope, or throws the mapped error. */
    private fun request(method: String, path: String, body: String?): JSONObject {
        val settings = settingsProvider()
        val response = try {
            transport.execute(
                HttpRequest(
                    method = method,
                    url = settings.baseUrl + path,
                    headers = mapOf("Authorization" to "Bearer ${settings.token}"),
                    body = body,
                )
            )
        } catch (e: IOException) {
            throw DrabbitError.Unreachable(e.message)
        }
        if (response.status != 200) throw mapHttpError(response)
        val json = try {
            JSONObject(response.body)
        } catch (e: JSONException) {
            throw DrabbitError.MalformedResponse("body is not a JSON object")
        }
        if (!json.optBoolean("ok", false)) {
            // A 200 that says ok:false is not a shape the server
            // produces; treat it as malformed rather than success.
            throw DrabbitError.MalformedResponse("success status without ok:true")
        }
        return json
    }

    private fun mapHttpError(response: HttpResponse): DrabbitError {
        val (code, serverMessage) = parseErrorBody(response.body)
        return when (response.status) {
            401 -> DrabbitError.BadToken
            403 -> DrabbitError.DesktopOnly(serverMessage ?: "")
            409 -> DrabbitError.StateError(code ?: "conflict", serverMessage ?: "That action isn't possible right now.")
            else -> DrabbitError.ServerError(response.status, code)
        }
    }

    /** Best-effort read of `{ error: { code, message } }`; nulls if absent. */
    private fun parseErrorBody(body: String): Pair<String?, String?> {
        return try {
            val error = JSONObject(body).optJSONObject("error")
            Pair(error?.optString("code", null), error?.optString("message", null))
        } catch (e: JSONException) {
            Pair(null, null)
        }
    }
}
