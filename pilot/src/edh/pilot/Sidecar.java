package edh.pilot;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

/** Blocking JSON-over-HTTP bridge to the Python pilot sidecar. Any failure falls back to Forge's pick. */
public final class Sidecar {
    private final String url;
    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .proxy(HttpClient.Builder.NO_PROXY)
            .build();

    public Sidecar(String url) {
        this.url = url;
    }

    public String decide(JsonObject request, String fallback) {
        try {
            HttpRequest req = HttpRequest.newBuilder(URI.create(url + "/decide"))
                    .timeout(Duration.ofSeconds(300))  // a strategist memo can take a while
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(request.toString()))
                    .build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() != 200) return fallback;
            JsonObject o = JsonParser.parseString(resp.body()).getAsJsonObject();
            return o.has("choice") ? o.get("choice").getAsString() : fallback;
        } catch (Exception e) {
            System.err.println("[pilot] sidecar error, using Forge's pick: " + e);
            return fallback;
        }
    }

    public void event(JsonObject body) {
        try {
            HttpRequest req = HttpRequest.newBuilder(URI.create(url + "/event"))
                    .timeout(Duration.ofSeconds(10))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body.toString()))
                    .build();
            http.send(req, HttpResponse.BodyHandlers.discarding());
        } catch (Exception ignored) { }
    }
}
