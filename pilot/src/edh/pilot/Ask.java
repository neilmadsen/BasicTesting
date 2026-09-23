package edh.pilot;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

/**
 * One request to the pilot: a kind ("action", "attack", "block", ...), the board,
 * and one or more choice questions, each with Forge's own answer as the default.
 * The sidecar turns every question into a Jev Choice and answers all of them in
 * one call. Any failure returns an empty map, so callers keep Forge's choices.
 */
final class Ask {
    private final JsonObject req = new JsonObject();
    private final JsonArray questions = new JsonArray();
    private final Map<String, JsonObject> byId = new LinkedHashMap<>();

    Ask(String kind, String game, JsonObject state) {
        req.addProperty("kind", kind);
        req.addProperty("game", game);
        req.add("state", state);
        req.add("questions", questions);
    }

    Ask context(String key, String value) {
        req.addProperty(key, value);
        return this;
    }

    /** Start a question; add options with {@link #option}. */
    Ask question(String id, String prompt, String defaultOption) {
        JsonObject q = new JsonObject();
        q.addProperty("id", id);
        q.addProperty("prompt", prompt);
        q.addProperty("default", defaultOption);
        q.add("options", new JsonArray());
        questions.add(q);
        byId.put(id, q);
        return this;
    }

    Ask option(String questionId, String optionId, String text) {
        JsonObject o = new JsonObject();
        o.addProperty("id", optionId);
        o.addProperty("text", text);
        byId.get(questionId).getAsJsonArray("options").add(o);
        return this;
    }

    int size() {
        return questions.size();
    }

    /** Drop questions with fewer than two options: nothing to decide. */
    Ask prune() {
        for (int i = questions.size() - 1; i >= 0; i--) {
            JsonObject q = questions.get(i).getAsJsonObject();
            if (q.getAsJsonArray("options").size() < 2) {
                byId.remove(q.get("id").getAsString());
                questions.remove(i);
            }
        }
        return this;
    }

    Map<String, String> send(Sidecar sidecar) {
        Map<String, String> out = new HashMap<>();
        if (sidecar == null || questions.isEmpty()) return out;
        JsonObject resp = sidecar.ask(req);
        if (resp == null || !resp.has("answers")) return out;
        for (Map.Entry<String, JsonElement> e : resp.getAsJsonObject("answers").entrySet()) {
            out.put(e.getKey(), e.getValue().getAsString());
        }
        return out;
    }
}
