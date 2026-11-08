package ca.wilkins.drabbit.model

import ca.wilkins.drabbit.net.DrabbitError
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/**
 * JSON → model parsing for the companion protocol, kept separate from
 * the transport so unit tests can drive it (via the client) with
 * fixtures captured from the real P3 server.
 *
 * Field names and types match the server exactly; unknown extra
 * fields are ignored so a newer desktop stays readable. A missing or
 * mistyped required field is a [DrabbitError.MalformedResponse] —
 * never a guess.
 */

internal fun parsePetSummary(json: JSONObject): PetSummary {
    try {
        val needs = json.getJSONObject("needs")
        return PetSummary(
            id = json.getString("id"),
            name = json.getString("name"),
            fur = json.getString("fur"),
            stage = json.getString("stage"),
            adultForm = json.optNullableString("adultForm"),
            mood = json.getString("mood"),
            needs = Needs(
                hunger = needs.getDouble("hunger"),
                happiness = needs.getDouble("happiness"),
                energy = needs.getDouble("energy"),
                cleanliness = needs.getDouble("cleanliness"),
            ),
            health = json.getDouble("health"),
            careScore = json.getDouble("careScore"),
            ageMs = json.getLong("ageMs"),
            asleep = json.getBoolean("asleep"),
            sick = json.getBoolean("sick"),
            messes = json.getInt("messes"),
            readyToHatch = json.getBoolean("readyToHatch"),
            generation = json.getInt("generation"),
            deathCause = json.optNullableString("deathCause"),
        )
    } catch (e: JSONException) {
        throw DrabbitError.MalformedResponse("pet summary: ${e.message}")
    }
}

internal fun parsePetEvent(json: JSONObject): PetEvent {
    try {
        return PetEvent(
            t = json.getLong("t"),
            kind = json.getString("kind"),
            detail = json.getString("detail"),
        )
    } catch (e: JSONException) {
        throw DrabbitError.MalformedResponse("pet event: ${e.message}")
    }
}

internal fun parsePetEvents(array: JSONArray): List<PetEvent> {
    val events = ArrayList<PetEvent>(array.length())
    for (i in 0 until array.length()) {
        val item = array.optJSONObject(i)
            ?: throw DrabbitError.MalformedResponse("event #$i is not an object")
        events.add(parsePetEvent(item))
    }
    return events
}

/** String field that is JSON-null or absent → null; present → its value. */
private fun JSONObject.optNullableString(name: String): String? =
    if (isNull(name)) null else optString(name, null)
