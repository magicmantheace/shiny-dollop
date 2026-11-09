package ca.wilkins.drabbit.model

import org.junit.Assert.assertEquals
import org.junit.Test

class FormatTest {

    @Test
    fun age_minutesOnly() {
        assertEquals("0m", Format.age(0))
        assertEquals("5m", Format.age(5 * 60_000L))
        assertEquals("59m", Format.age(59 * 60_000L))
    }

    @Test
    fun age_hoursAndMinutes() {
        assertEquals("1h 0m", Format.age(60 * 60_000L))
        assertEquals("1h 5m", Format.age(65 * 60_000L))
        assertEquals("23h 59m", Format.age(23 * 3_600_000L + 59 * 60_000L))
    }

    @Test
    fun age_daysAndHours() {
        assertEquals("1d 2h", Format.age(26 * 3_600_000L))
        assertEquals("3d 0h", Format.age(3 * 24 * 3_600_000L))
    }

    @Test
    fun stageLabels() {
        assertEquals("Egg", Format.stageLabel("egg"))
        assertEquals("Baby", Format.stageLabel("baby"))
        assertEquals("Adult", Format.stageLabel("adult"))
        assertEquals("Gone", Format.stageLabel("dead"))
    }
}
