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

    // Loop breaker: some Forge effects re-ask after an answer (a declined search reopens after a confirm).
    // If the same decision repeats too often in one phase, stop asking and let Forge answer.
    // Counts each distinct decision within one game phase (loops can alternate, e.g. search/confirm).
    private static final int MAX_REPEATS = 8;
    private static String phaseKey = "";
    private static final Map<String, Integer> seen = new HashMap<>();

    private static synchronized boolean looping(String phase, String key) {
        if (!phase.equals(phaseKey)) {
            phaseKey = phase;
            seen.clear();
        }
        int n = seen.merge(key, 1, Integer::sum);
        if (n == MAX_REPEATS + 1) System.err.println("[pilot] loop breaker: repeated decision, deferring to Forge: " + key);
        return n > MAX_REPEATS;
    }

    /**
     * Decision kinds the pilot may answer (env EDH_PILOT_KINDS, comma-separated; unset = all). For ablations:
     * every other kind is left to Forge's own AI, exactly as if there were no pilot for it.
     */
    private static final java.util.Set<String> KINDS = kinds();

    private static java.util.Set<String> kinds() {
        String env = System.getenv("EDH_PILOT_KINDS");
        if (env == null || env.isBlank()) return null;
        java.util.Set<String> out = new java.util.HashSet<>();
        for (String k : env.split(",")) if (!k.isBlank()) out.add(k.trim());
        return out;
    }

    static boolean allowed(String kind) {
        return KINDS == null || KINDS.contains(kind);
    }

    Map<String, String> send(Sidecar sidecar) {
        Map<String, String> out = new HashMap<>();
        if (sidecar == null || questions.isEmpty() || !allowed(req.get("kind").getAsString())) return out;
        JsonObject st = req.getAsJsonObject("state");
        String phase = req.get("game").getAsString() + "|" + (st.has("turn") ? st.get("turn").getAsString() : "")
                + "|" + (st.has("phase") ? st.get("phase").getAsString() : "");
        if (looping(phase, req.get("kind").getAsString() + "|" + questions.toString().hashCode())) return out;
        JsonObject resp = sidecar.ask(req);
        if (resp == null || !resp.has("answers")) return out;
        for (Map.Entry<String, JsonElement> e : resp.getAsJsonObject("answers").entrySet()) {
            out.put(e.getKey(), e.getValue().getAsString());
        }
        return out;
    }
}
