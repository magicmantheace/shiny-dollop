package ca.wilkins.drabbit

/**
 * Test fixtures in src/test/resources/fixtures are RAW RESPONSE BODIES
 * captured from the real P3 companion server running headlessly on the
 * build VM (compiled desktop/dist, temp-dir PetService, dummy token
 * "android-fixture-token" — responses never contain the token).
 * They are the wire truth the client is tested against; see
 * android/README.md ("Verification") for how they were produced.
 */
object Fixtures {
    fun text(name: String): String {
        val stream = Fixtures::class.java.getResourceAsStream("/fixtures/$name")
            ?: throw AssertionError("missing test fixture: $name")
        return stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
    }
}
