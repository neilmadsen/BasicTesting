package edh.pilot;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

/** Blocking JSON-over-HTTP bridge to the Python pilot sidecar. Any failure means "keep Forge's choice". */
public final class Sidecar {
    private final String url;
    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .proxy(HttpClient.Builder.NO_PROXY)
            .build();

    public Sidecar(String url) {
        this.url = url;
    }

    /** POST /ask; returns the parsed response or null. */
    public JsonObject ask(JsonObject request) {
        try {
            HttpRequest req = HttpRequest.newBuilder(URI.create(url + "/ask"))
                    .timeout(Duration.ofSeconds(300))  // a strategist re-plan can take a while
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(request.toString()))
                    .build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() != 200) return null;
            return JsonParser.parseString(resp.body()).getAsJsonObject();
        } catch (Exception e) {
            System.err.println("[pilot] sidecar error, keeping Forge's choice: " + e);
            return null;
        }
    }
}
