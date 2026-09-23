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
            return clip(c.getName(), 50) + " [" + (ctl == me ? "ours" : ctl == null ? "?" : label(ctl)) + "]";
        }
        if (t instanceof Player p) {
            return p == me ? "us" : label(p);
        }
        return clip(String.valueOf(t), 60);
    }

    static String label(Player p) {
        String n = p.getName();
        int i = n.indexOf(")-");
        return i >= 0 ? n.substring(i + 2) : n;
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
        s.addProperty("my_mana_available", PilotController.manaEstimate(me));
        s.addProperty("my_lands_played_this_turn", me.getLandsPlayedThisTurn());
        s.add("my_hand", names(me.getCardsIn(ZoneType.Hand)));
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
        return s;
    }
}
