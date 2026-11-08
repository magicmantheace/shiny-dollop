package ca.wilkins.drabbit.model

import ca.wilkins.drabbit.Fixtures
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The CareRules matrix, exercised over summaries parsed from the real
 * server fixtures plus data-class variants of them (asleep, sick,
 * tired, not-ready). Expected behaviour mirrors core/src/actions.ts.
 */
class CareRulesTest {

    private fun summary(fixture: String): PetSummary =
        parsePetSummary(JSONObject(Fixtures.text(fixture)).getJSONObject("pet"))

    private fun states(pet: PetSummary): Map<ActionKind, ActionState> =
        CareRules.actionsFor(pet).associateBy { it.kind }

    @Test
    fun awakeHealthyBaby_coreActionsEnabled() {
        val s = states(summary("status_baby.json"))
        assertTrue(s.getValue(ActionKind.FEED_MEAL).enabled)
        assertTrue(s.getValue(ActionKind.FEED_SNACK).enabled)
        assertTrue(s.getValue(ActionKind.PLAY).enabled)
        assertTrue(s.getValue(ActionKind.CLEAN).enabled)
        assertTrue(s.getValue(ActionKind.SLEEP).enabled)
        assertFalse(s.getValue(ActionKind.WAKE).enabled)
        assertEquals("Not asleep.", s.getValue(ActionKind.WAKE).reason)
        assertFalse(s.getValue(ActionKind.MEDICINE).enabled)
        assertEquals("Not sick.", s.getValue(ActionKind.MEDICINE).reason)
        assertNull(s[ActionKind.HATCH]) // hatch is offered only for eggs
    }

    @Test
    fun enabledActions_haveNoReason() {
        val s = states(summary("status_baby.json"))
        for (state in s.values) {
            if (state.enabled) assertNull(state.reason)
            if (!state.enabled) assertNotNull(state.reason)
        }
    }

    @Test
    fun asleep_wakeAndCleanEnabled_feedAndPlayDisabled() {
        val pet = summary("status_baby.json").copy(asleep = true)
        val s = states(pet)
        assertTrue(s.getValue(ActionKind.WAKE).enabled)
        assertTrue(s.getValue(ActionKind.CLEAN).enabled) // core allows clean while asleep
        assertFalse(s.getValue(ActionKind.FEED_MEAL).enabled)
        assertFalse(s.getValue(ActionKind.FEED_SNACK).enabled)
        assertFalse(s.getValue(ActionKind.PLAY).enabled)
        assertFalse(s.getValue(ActionKind.SLEEP).enabled)
        assertEquals("Already asleep.", s.getValue(ActionKind.SLEEP).reason)
    }

    @Test
    fun sick_medicineEnabled_evenAsleep() {
        val pet = summary("status_baby.json").copy(sick = true)
        assertTrue(states(pet).getValue(ActionKind.MEDICINE).enabled)
        val sleepingSick = pet.copy(asleep = true)
        assertTrue(states(sleepingSick).getValue(ActionKind.MEDICINE).enabled)
    }

    @Test
    fun tooTired_playDisabled() {
        val baby = summary("status_baby.json")
        val tired = baby.copy(needs = baby.needs.copy(energy = CareRules.PLAY_MIN_ENERGY - 1))
        val play = states(tired).getValue(ActionKind.PLAY)
        assertFalse(play.enabled)
        assertTrue(play.reason!!.contains("Too tired"))
        val rested = baby.copy(needs = baby.needs.copy(energy = CareRules.PLAY_MIN_ENERGY))
        assertTrue(states(rested).getValue(ActionKind.PLAY).enabled)
    }

    @Test
    fun eggReady_onlyHatchEnabled() {
        val s = states(summary("status_egg_ready.json"))
        assertTrue(s.getValue(ActionKind.HATCH).enabled)
        val enabledOthers = s.filterKeys { it != ActionKind.HATCH }.values.count { it.enabled }
        assertEquals(0, enabledOthers)
        assertEquals(
            "Still an egg — hatch it first.",
            s.getValue(ActionKind.FEED_MEAL).reason,
        )
    }

    @Test
    fun eggNotReady_hatchDisabledWithReason() {
        val pet = summary("status_egg_ready.json").copy(readyToHatch = false)
        val hatch = states(pet).getValue(ActionKind.HATCH)
        assertFalse(hatch.enabled)
        assertTrue(hatch.reason!!.contains("isn't ready"))
    }

    @Test
    fun dead_everythingDisabled() {
        val s = states(summary("status_dead.json"))
        assertTrue(s.isNotEmpty())
        for (state in s.values) {
            assertFalse("${state.kind} should be disabled", state.enabled)
            assertNotNull(state.reason)
        }
    }

    @Test
    fun newEgg_isNeverOffered() {
        val scenarios = listOf(
            summary("status_baby.json"),
            summary("status_egg_ready.json"),
            summary("status_dead.json"),
            summary("status_baby.json").copy(asleep = true, sick = true),
        )
        for (pet in scenarios) {
            assertFalse(
                "NEW_EGG must never be offered (stage=${pet.stage})",
                CareRules.actionsFor(pet).any { it.kind == ActionKind.NEW_EGG },
            )
        }
    }
}
