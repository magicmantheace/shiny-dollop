package ca.wilkins.drabbit.net

/**
 * Everything that can go wrong talking to the companion server, mapped
 * from the wire (docs/DESIGN.md: errors are
 * `{ ok: false, error: { code, message } }` with a matching HTTP
 * status). The UI turns these into plain language; nothing here
 * carries UI copy.
 */
sealed class DrabbitError(message: String) : Exception(message) {

    /** HTTP 401 `unauthorized` — the token is missing or wrong
     *  (e.g. it was regenerated on the desktop). */
    object BadToken : DrabbitError("The server rejected the token.")

    /** HTTP 403 `desktop_only` — the action exists but is a
     *  desktop-side decision (starting the next generation). */
    class DesktopOnly(val serverMessage: String) :
        DrabbitError(serverMessage.ifBlank { "That action is desktop-only." })

    /** HTTP 409 — the action is invalid for the pet's current state;
     *  [serverMessage] is the core's own explanation, kept verbatim. */
    class StateError(val code: String, val serverMessage: String) :
        DrabbitError(serverMessage)

    /** Any other non-200 HTTP status (400s, 404, 413, 500…). */
    class ServerError(val httpStatus: Int, val code: String?) :
        DrabbitError("Server answered HTTP $httpStatus" + (code?.let { " ($it)" } ?: ""))

    /** No answer at all: connection refused, timed out, no route. */
    class Unreachable(val detail: String?) :
        DrabbitError("Unreachable" + (detail?.let { ": $it" } ?: ""))

    /** A 200 response whose body is not the protocol shape. */
    class MalformedResponse(val detail: String) :
        DrabbitError("Malformed response: $detail")
}
