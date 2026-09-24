package edh.pilot;

import java.util.LinkedHashMap;
import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import forge.game.Game;
import forge.game.card.Card;
import forge.game.player.Player;
import forge.game.spellability.SpellAbilityStackInstance;
import forge.game.zone.ZoneType;

/** Compact, hidden-information-respecting board summary for the pilot. */
final class StateView {
    private StateView() { }

    static String clip(String s, int n) {
        if (s == null) return "";
        s = s.replace('\n', ' ');
        return s.length() <= n ? s : s.substring(0, n - 1) + "…";
    }

    /** "Name [ours]" / "Name [P3]" / "P2", so the pilot can see whose thing a target is. */
    static String describeTarget(Object t, Player me) {
        if (t instanceof Card c) {
            Player ctl = c.getController();
            StringBuilder b = new StringBuilder(clip(c.getName(), 50));
            b.append(" [").append(ctl == me ? "ours" : ctl == null ? "?" : label(ctl));
            try {
                if (c.isCreature()) {
                    b.append(", ").append(c.getNetPower()).append('/').append(c.getNetToughness());
                    if (c.getDamage() > 0) b.append(" with ").append(c.getDamage()).append(" damage");
                }
                if (c.isPlaneswalker()) b.append(", loyalty ").append(c.getCurrentLoyalty());
                if (c.isToken()) b.append(", token");
                if (c.isCommander()) b.append(", commander");
                if (c.isTapped()) b.append(", tapped");
                if (!c.isInZone(forge.game.zone.ZoneType.Battlefield) && c.getZone() != null) {
                    b.append(", in ").append(c.getZone().getZoneType().name().toLowerCase());
                }
            } catch (Exception ignored) { }
            return b.append(']').toString();
        }
        if (t instanceof Player p) {
            return p == me ? "us (" + p.getLife() + " life)" : label(p) + " (" + p.getLife() + " life)";
        }
        return clip(String.valueOf(t), 60);
    }

    static String label(Player p) {
        if (p == null) return "none";
        String n = p.getName();
        int i = n.indexOf(")-");
        return i >= 0 ? n.substring(i + 2) : n;
    }

    /** "Name — Type line — rules text", for cards Jev can't see elsewhere (e.g. in a library search). */
    static String cardLine(Card c, int textChars) {
        StringBuilder b = new StringBuilder(c.getName());
        try {
            b.append(" — ").append(c.getType().toString());
            String text = c.getOracleText();
            if (text != null && !text.isBlank()) {
                b.append(" — ").append(clip(text.replace("\\n", " ").replaceAll("\\s+", " "), textChars));
            }
        } catch (Exception ignored) { }
        return b.toString();
    }

    private static JsonArray battlefield(Player p) {
        // group identical permanents (tokens especially) as "Name P/T xN (tapped k)"
        Map<String, int[]> groups = new LinkedHashMap<>();
        for (Card c : p.getCardsIn(ZoneType.Battlefield)) {
            StringBuilder key = new StringBuilder(c.getName());
            if (c.isCreature()) key.append(' ').append(c.getNetPower()).append('/').append(c.getNetToughness());
            if (c.isToken()) key.append(" [token]");
            if (c.isLand()) key.append(" [land]");
            try {
                if (!c.getCounters().isEmpty()) key.append(" {").append(c.getCounters()).append('}');
            } catch (Exception ignored) { }
            int[] g = groups.computeIfAbsent(key.toString(), k -> new int[2]);
            g[0]++;
            if (c.isTapped()) g[1]++;
        }
        JsonArray arr = new JsonArray();
        for (Map.Entry<String, int[]> e : groups.entrySet()) {
            int n = e.getValue()[0], t = e.getValue()[1];
            arr.add(e.getKey() + (n > 1 ? " x" + n : "") + (t > 0 ? " (tapped " + t + ")" : ""));
        }
        return arr;
    }

    /**
     * "3 lands (Bayou, Zagoth Triome, Swamp); mana rocks/dorks: Sol Ring; spells by mana value: 2: X; 6: Y".
     * The hand is otherwise a list of names, and the executor can't be expected to know that Verdant
     * Catacombs or Zagoth Triome is a land: before this, every mulligan it overruled was backwards.
     */
    static String handSummary(Player me) {
        java.util.List<String> lands = new java.util.ArrayList<>();
        java.util.List<String> ramp = new java.util.ArrayList<>();
        java.util.TreeMap<Integer, java.util.List<String>> byMv = new java.util.TreeMap<>();
        for (Card c : me.getCardsIn(ZoneType.Hand)) {
            if (c.isLand()) {
                lands.add(c.getName());
                continue;
            }
            if (!c.getManaAbilities().isEmpty()) ramp.add(c.getName());
            byMv.computeIfAbsent(c.getCMC(), k -> new java.util.ArrayList<>()).add(c.getName());
        }
        StringBuilder b = new StringBuilder();
        b.append(lands.size()).append(lands.size() == 1 ? " land" : " lands");
        if (!lands.isEmpty()) b.append(" (").append(String.join(", ", lands)).append(')');
        if (!ramp.isEmpty()) b.append("; mana rocks/dorks: ").append(String.join(", ", ramp));
        if (!byMv.isEmpty()) {
            b.append("; spells by mana value: ");
            boolean first = true;
            for (java.util.Map.Entry<Integer, java.util.List<String>> e : byMv.entrySet()) {
                b.append(first ? "" : "; ").append(e.getKey()).append(": ").append(String.join(", ", e.getValue()));
                first = false;
            }
        }
        return b.toString();
    }

    private static JsonArray names(Iterable<Card> cards) {
        JsonArray arr = new JsonArray();
        for (Card c : cards) arr.add(c.getName());
        return arr;
    }

    static JsonObject describe(Game game, Player me) {
        JsonObject s = new JsonObject();
        s.addProperty("turn", game.getPhaseHandler().getTurn());
        s.addProperty("phase", String.valueOf(game.getPhaseHandler().getPhase()));
        s.addProperty("me", label(me));
        s.addProperty("active", label(game.getPhaseHandler().getPlayerTurn()));
        s.addProperty("my_mana_available", PilotController.manaEstimate(me));
        s.addProperty("my_lands_played_this_turn", me.getLandsPlayedThisTurn());
        s.add("my_hand", names(me.getCardsIn(ZoneType.Hand)));
        s.addProperty("my_hand_summary", handSummary(me));
        s.add("my_graveyard", names(me.getCardsIn(ZoneType.Graveyard)));
        s.add("my_command_zone", names(me.getCardsIn(ZoneType.Command)));
        JsonArray players = new JsonArray();
        for (Player p : game.getPlayers()) {
            JsonObject o = new JsonObject();
            o.addProperty("name", label(p));
            o.addProperty("is_me", p == me);
            o.addProperty("life", p.getLife());
            if (p.getPoisonCounters() > 0) o.addProperty("poison", p.getPoisonCounters());
            o.addProperty("lost", p.hasLost());
            o.addProperty("hand_size", p.getCardsIn(ZoneType.Hand).size());
            o.addProperty("library_size", p.getCardsIn(ZoneType.Library).size());
            o.addProperty("graveyard_size", p.getCardsIn(ZoneType.Graveyard).size());
            try {
                JsonArray cmd = new JsonArray();
                for (Card c : p.getCommanders()) cmd.add(c.getName());
                o.add("commanders", cmd);
            } catch (Exception ignored) { }
            o.add("battlefield", battlefield(p));
            players.add(o);
        }
        s.add("players", players);
        JsonArray stack = new JsonArray();
        for (SpellAbilityStackInstance si : game.getStack()) {
            stack.add(clip(si.getStackDescription(), 120));
        }
        s.add("stack", stack);
        s.add("card_text", cardText(game, me));
        addGameFacts(s, game, me);
        return s;
    }

    private static final java.util.regex.Pattern AI_LABEL = java.util.regex.Pattern.compile("Ai\\(\\d+\\)-(P\\d+)");

    /** Public facts a player tracks that the board alone doesn't show. */
    private static void addGameFacts(JsonObject s, Game game, Player me) {
        try {
            JsonObject tax = new JsonObject();
            for (Card c : me.getCommanders()) {
                int n = me.getCommanderCast(c);
                if (n > 0) tax.addProperty(c.getName(), 2 * n);
            }
            if (tax.size() > 0) s.add("commander_tax", tax);
        } catch (Exception ignored) { }
        try {
            JsonArray stolen = new JsonArray();
            for (Player p : game.getPlayers()) {
                for (Card c : p.getCardsIn(ZoneType.Battlefield)) {
                    if (c.getOwner() != null && c.getOwner() != c.getController()) {
                        stolen.add(c.getName() + " (owned by " + (c.getOwner() == me ? "us" : label(c.getOwner()))
                                + ", controlled by " + (c.getController() == me ? "us" : label(c.getController())) + ")");
                    }
                }
            }
            if (!stolen.isEmpty()) s.add("stolen", stolen);
        } catch (Exception ignored) { }
        try {
            Player m = game.getMonarch();
            if (m != null) s.addProperty("monarch", m == me ? "us" : label(m));
        } catch (Exception ignored) { }
        try {
            java.util.List<forge.game.GameLogEntry> casts =
                    game.getGameLog().getLogEntriesExact(forge.game.GameLogEntryType.STACK_ADD);  // newest first
            JsonArray recent = new JsonArray();
            for (int i = Math.min(casts.size(), 24) - 1; i >= 0; i--) {
                String msg = AI_LABEL.matcher(casts.get(i).message()).replaceAll("$1");
                recent.add(clip(msg.replace(label(me) + " ", "us "), 160));
            }
            if (!recent.isEmpty()) s.add("recent_casts", recent);
        } catch (Exception ignored) { }
    }

    private static final int MAX_TEXTS = 80;

    /**
     * Oracle text, once per distinct name, for everything whose rules matter to the
     * decision: non-land permanents on every battlefield (opponents' first), our
     * hand and command zone, and the stack. Lands and vanilla tokens are skipped.
     */
    private static JsonObject cardText(Game game, Player me) {
        Map<String, String> out = new LinkedHashMap<>();
        java.util.List<Card> cards = new java.util.ArrayList<>();
        for (Player p : game.getPlayers()) {
            if (p != me) cards.addAll(p.getCardsIn(ZoneType.Battlefield));
        }
        cards.addAll(me.getCardsIn(ZoneType.Battlefield));
        cards.addAll(me.getCardsIn(ZoneType.Hand));
        cards.addAll(me.getCardsIn(ZoneType.Command));
        for (SpellAbilityStackInstance si : game.getStack()) {
            if (si.getSourceCard() != null) cards.add(si.getSourceCard());
        }
        for (Card c : cards) {
            if (out.size() >= MAX_TEXTS) break;
            if (c.isLand() && !c.isCreature()) continue;
            String name = c.getName();
            if (out.containsKey(name)) continue;
            String text;
            try {
                text = c.getOracleText();
                if ((text == null || text.isBlank()) && c.isToken()) text = c.getAbilityText();
            } catch (Exception e) {
                continue;
            }
            if (text == null || text.isBlank()) continue;
            out.put(name, clip(text.replace("\\n", " ").replaceAll("\\s+", " "), 260));
        }
        JsonObject o = new JsonObject();
        for (Map.Entry<String, String> e : out.entrySet()) o.addProperty(e.getKey(), e.getValue());
        return o;
    }
}
