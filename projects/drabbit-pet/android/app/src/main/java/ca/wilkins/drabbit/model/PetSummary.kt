package ca.wilkins.drabbit.model

/**
 * The wire model of the companion protocol (docs/DESIGN.md, "Companion
 * wire protocol (as implemented in P3)").
 *
 * [PetSummary] mirrors `desktop/src/shared/api-types.ts` exactly — the
 * same 16 fields the desktop sends over IPC and HTTP. It is a
 * presentation subset of the pet's full state: the app holds no
 * simulation and no authoritative state of its own.
 */

data class Needs(
    val hunger: Double,
    val happiness: Double,
    val energy: Double,
    val cleanliness: Double,
)

data class PetSummary(
    val id: String,
    val name: String,
    /** One of: ember, meadow, royal, sky, sunset, rainbow. */
    val fur: String,
    /** One of: egg, baby, child, teen, adult, dead. */
    val stage: String,
    /** radiant / content / scruffy once adult; null before that. */
    val adultForm: String?,
    /** waiting, joyful, content, okay, unhappy, miserable, frail, sick, asleep, gone. */
    val mood: String,
    val needs: Needs,
    val health: Double,
    val careScore: Double,
    /** Simulated ms since hatch (0 while an egg). */
    val ageMs: Long,
    val asleep: Boolean,
    val sick: Boolean,
    val messes: Int,
    val readyToHatch: Boolean,
    /** Lineage generation of this pet (1 = first of its line). */
    val generation: Int,
    val deathCause: String?,
)

/** One entry of the pet's event log, as sent by the server. */
data class PetEvent(
    /** Simulated timestamp (ms) at which the event occurred. */
    val t: Long,
    val kind: String,
    val detail: String,
)

/** The result of a successful POST /v1/actions. */
data class ActionOutcome(
    val summary: PetSummary,
    val events: List<PetEvent>,
)

/** One page of GET /v1/events: events plus the cursor to poll with next. */
data class EventsPage(
    val events: List<PetEvent>,
    val cursor: Long,
    val serverNow: Long,
)

/**
 * Care actions, using the server's `{ kind }` vocabulary (the same one
 * the desktop care panel uses). [NEW_EGG] is part of the vocabulary
 * but is deliberately not performable remotely — the server refuses it
 * with 403 `desktop_only` — and the app never offers it.
 */
enum class ActionKind(val wire: String, val label: String) {
    FEED_MEAL("feed-meal", "Feed meal"),
    FEED_SNACK("feed-snack", "Feed snack"),
    PLAY("play", "Play"),
    CLEAN("clean", "Clean up"),
    SLEEP("sleep", "Sleep"),
    WAKE("wake", "Wake"),
    MEDICINE("medicine", "Medicine"),
    HATCH("hatch", "Hatch"),
    NEW_EGG("new-egg", "New egg"),
}
