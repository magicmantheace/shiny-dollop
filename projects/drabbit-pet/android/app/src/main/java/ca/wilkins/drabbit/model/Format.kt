package ca.wilkins.drabbit.model

/** Small pure formatting helpers (unit-tested, no Android types). */
object Format {

    /**
     * Simulated age since hatch: "0m", "5m", "1h 5m", "1d 2h".
     * The summary reports ageMs = 0 while the pet is an egg.
     */
    fun age(ageMs: Long): String {
        val totalMinutes = (ageMs / 60_000L).coerceAtLeast(0)
        val days = totalMinutes / (24 * 60)
        val hours = (totalMinutes % (24 * 60)) / 60
        val minutes = totalMinutes % 60
        return when {
            days > 0 -> "${days}d ${hours}h"
            hours > 0 -> "${hours}h ${minutes}m"
            else -> "${minutes}m"
        }
    }

    /** "baby · joyful · gen 1" style subtitle pieces are built in the UI;
     *  this is the stage label on its own, title-cased for display. */
    fun stageLabel(stage: String): String = when (stage) {
        "egg" -> "Egg"
        "baby" -> "Baby"
        "child" -> "Child"
        "teen" -> "Teen"
        "adult" -> "Adult"
        "dead" -> "Gone"
        else -> stage
    }
}
