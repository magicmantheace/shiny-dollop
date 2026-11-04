package ca.wilkins.drabbit.net

import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/** A single blocking HTTP exchange, abstracted so the client can be
 *  unit-tested with a fake transport (no sockets, no Android). */
data class HttpRequest(
    val method: String,
    val url: String,
    val headers: Map<String, String>,
    val body: String?,
)

data class HttpResponse(
    val status: Int,
    val body: String,
)

interface HttpTransport {
    /** @throws IOException on any connectivity failure. */
    @Throws(IOException::class)
    fun execute(request: HttpRequest): HttpResponse
}

/** The production transport: plain [HttpURLConnection], no libraries. */
class HttpUrlConnectionTransport(
    private val connectTimeoutMs: Int = 5_000,
    private val readTimeoutMs: Int = 10_000,
) : HttpTransport {

    override fun execute(request: HttpRequest): HttpResponse {
        val connection = URL(request.url).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = request.method
            connection.connectTimeout = connectTimeoutMs
            connection.readTimeout = readTimeoutMs
            connection.instanceFollowRedirects = false
            for ((name, value) in request.headers) {
                connection.setRequestProperty(name, value)
            }
            val body = request.body
            if (body != null) {
                val bytes = body.toByteArray(Charsets.UTF_8)
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.setFixedLengthStreamingMode(bytes.size)
                connection.outputStream.use { it.write(bytes) }
            }
            val status = connection.responseCode
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
            return HttpResponse(status, text)
        } finally {
            connection.disconnect()
        }
    }
}
