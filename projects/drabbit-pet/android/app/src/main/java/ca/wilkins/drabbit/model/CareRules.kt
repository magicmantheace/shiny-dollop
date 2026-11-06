package ca.wilkins.drabbit.model

/** One care button's state: offered, tappable, and if not, why not. */
data class ActionState(
    val kind: ActionKind,
    val enabled: Boolean,
    /** Plain-language reason when [enabled] is false; null when enabled. */
    val reason: String?,
)

/**
 * Which care actions make sense for a given summary — a pure function
 * of the summary, mirroring the guards in `core/src/actions.ts` so the
 * UI disables a button for the same reason the server would refuse it
 * (a refusal can still happen if the state moved on; the server is
 * the authority, this is presentation).
 *
 * The mirror, from the core:
 * - every care action needs a hatched, living pet (`is_egg` / `is_dead`);
 * - feed and play also need it awake (`asleep`);
 * - play needs energy >= [PLAY_MIN_ENERGY] (`too_tired`;
 *   core ACTION.playMinEnergy = 10);
 * - clean and medicine work on a sleeping pet (no awake guard in core);
 * - medicine needs the pet sick (`not_sick`);
 * - hatch needs an egg that is ready (`not_ready`);
 * - sleep/wake are complementary (`already_asleep` / `not_asleep`).
 */
object CareRules {

    /** Mirrors ACTION.playMinEnergy in core/src/constants.ts. */
    const val PLAY_MIN_ENERGY = 10.0

    /** Buttons the pet screen offers, in display order. NEW_EGG is
     *  deliberately absent: it is a desktop-only action. */
    private val OFFERED: List<ActionKind> = listOf(
        ActionKind.FEED_MEAL,
        ActionKind.FEED_SNACK,
        ActionKind.PLAY,
        ActionKind.CLEAN,
        ActionKind.SLEEP,
        ActionKind.WAKE,
        ActionKind.MEDICINE,
    )

    fun actionsFor(pet: PetSummary): List<ActionState> = when (pet.stage) {
        "dead" -> (listOf(ActionKind.HATCH) + OFFERED).map { kind ->
            ActionState(kind, enabled = false, reason = "${pet.name} has died.")
        }

        "egg" -> (listOf(ActionKind.HATCH) + OFFERED).map { kind ->
            when (kind) {
                ActionKind.HATCH -> ActionState(
                    kind,
                    enabled = pet.readyToHatch,
                    reason = if (pet.readyToHatch) null else "The egg isn't ready to hatch yet.",
                )
                else -> ActionState(kind, enabled = false, reason = "Still an egg — hatch it first.")
            }
        }

        else -> OFFERED.map { kind -> awakeOrAsleep(pet, kind) }
    }

    private fun awakeOrAsleep(pet: PetSummary, kind: ActionKind): ActionState {
        fun state(enabled: Boolean, reason: String?) =
            ActionState(kind, enabled, if (enabled) null else reason)
        return when (kind) {
            ActionKind.FEED_MEAL, ActionKind.FEED_SNACK, ActionKind.PLAY -> when {
                pet.asleep -> state(false, "The drabbit is asleep.")
                kind == ActionKind.PLAY && pet.needs.energy < PLAY_MIN_ENERGY ->
                    state(false, "Too tired to play — needs rest.")
                else -> state(true, null)
            }
            ActionKind.CLEAN -> state(true, null) // allowed while asleep (core)
            ActionKind.SLEEP ->
                if (pet.asleep) state(false, "Already asleep.") else state(true, null)
            ActionKind.WAKE ->
                if (pet.asleep) state(true, null) else state(false, "Not asleep.")
            ActionKind.MEDICINE ->
                if (pet.sick) state(true, null) else state(false, "Not sick.")
            ActionKind.HATCH -> state(false, "Already hatched.")
            ActionKind.NEW_EGG -> state(false, "Starting a new egg is done on the desktop.")
        }
    }

    /** True when the pet is gone and the next generation is a desktop decision. */
    fun isDead(pet: PetSummary): Boolean = pet.stage == "dead"
}
