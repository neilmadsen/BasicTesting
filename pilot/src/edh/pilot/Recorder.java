package edh.pilot;

import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Observable;
import java.util.Observer;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;

import com.google.common.collect.Multimap;
import com.google.common.eventbus.Subscribe;
import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import forge.ai.ComputerUtilAbility;
import forge.ai.ComputerUtilCost;
import forge.game.Game;
import forge.game.GameEntityView;
import forge.game.GameLogEntry;
import forge.game.card.Card;
import forge.game.card.CardView;
import forge.game.combat.CombatUtil;
import forge.game.event.GameEvent;
import forge.game.event.GameEventAttackersDeclared;
import forge.game.event.GameEventBlockersDeclared;
import forge.game.event.GameEventGameOutcome;
import forge.game.event.GameEventLandPlayed;
import forge.game.event.GameEventMulligan;
import forge.game.event.GameEventPlayerPriority;
import forge.game.event.GameEventSpellAbilityCast;
import forge.game.phase.PhaseHandler;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.PlayerView;
import forge.game.spellability.SpellAbility;
import forge.game.spellability.SpellAbilityStackInstance;
import forge.game.spellability.StackItemView;
import forge.game.zone.ZoneType;

/**
 * Records one player's decisions in a Forge game: at each prompt, the board as the pilot sees it (StateView, so
 * hidden information stays hidden), the plays Forge says are legal and affordable, and what the player did. Records
 * use the pilot's decision format (`type: decision`, `questions`, `answers`, `state`), so the game digest, replays
 * and executor comparisons read a human's games like a piloted run's.
 *
 * Prompts come from the human controller's input queue (InputPassPriority, InputAttack, InputBlock, mulligans),
 * so a phase the GUI skips is not recorded as a decision. In `aiMode` (testing on an AI seat) priority events
 * stand in for prompts. Results come from game events: casts and activations, land drops, attackers, blockers,
 * mulligans. Choices made in dialogs (modes, scry, card names) are not decisions here; they show in the game log,
 * whose new lines ride along on every record. Nothing here may disturb the game: every hook swallows its errors.
 */
public final class Recorder implements Observer {
    static final String FILE = "human_decisions.jsonl";
    private static final Gson GSON = new Gson();
    private static final AtomicInteger GAMES = new AtomicInteger();
    private static final int MAX_OPTIONS = 40;
    private static final long SCAN_BUDGET_MS = 400;

    private final Game game;
    private final Player me;
    private final Path dir;
    private final boolean aiMode;
    final String gid;
    private Window open;
    private Object lastInput;
    private int logSeen;
    private boolean started, finished;
    int records, errors;

    private static final class Opt {
        final String id, text;
        final SpellAbility sa;
        final Card card;
        Opt(String id, String text, SpellAbility sa, Card card) { this.id = id; this.text = text; this.sa = sa; this.card = card; }
    }

    private static final class Window {
        String kind, phase, context;
        int turn;
        long t0;
        JsonObject state;
        JsonArray log, prompts = new JsonArray();
        List<Opt> opts = new ArrayList<>();
    }

    public Recorder(Game game, Player me, Path dir, boolean aiMode) {
        this.game = game;
        this.me = me;
        this.dir = dir;
        this.aiMode = aiMode;
        this.gid = new SimpleDateFormat("yyyyMMdd-HHmmss").format(new Date()) + "-g" + GAMES.incrementAndGet();
    }

    /** Subscribe to the game's events; the caller adds the input-queue observer for a human seat. */
    public Recorder attach() {
        game.subscribeToEvents(this);
        // Forge closed mid-game: the decisions are already on disk (each record is flushed); keep the game log too
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            synchronized (this) {
                if (finished || !started) return;
                try {
                    StringBuilder sb = new StringBuilder();
                    for (GameLogEntry e : game.getGameLog().getAllEntries()) sb.append(e).append('\n');
                    Files.writeString(dir.resolve(gid + ".log"), sb.toString(), StandardCharsets.UTF_8);
                } catch (Throwable ignored) { }
            }
        }, "edh-recorder-flush"));
        return this;
    }

    // ------------------------------------------------------------------ prompts (human seat)

    /** InputQueue notifications: a new input on top is a prompt the player sees now. */
    @Override
    public synchronized void update(Observable o, Object arg) {
        try {
            Object in = ((forge.gamemodes.match.input.InputQueue) o).getInput();
            if (in == null || in == lastInput) return;
            lastInput = in;
            onPrompt(in.getClass().getSimpleName(), in);
        } catch (Throwable t) {
            errors++;
        }
    }

    /** Process whatever input is already showing (the recorder attaches after the game has started). */
    public synchronized void primeFrom(forge.gamemodes.match.input.InputQueue q) {
        update(q, null);
    }

    private void onPrompt(String cls, Object in) {
        if (game.isGameOver()) return;
        switch (cls) {
            case "InputPassPriority":
                closeOpen(null, null);
                openAction();
                break;
            case "InputAttack":
                closeOpen(null, null);
                openCombat("attack");
                break;
            case "InputBlock":
                closeOpen(null, null);
                openCombat("block");
                break;
            case "InputConfirmMulligan":
            case "InputLondonMulligan":
            case "InputChooseStartingHand":
                if (open != null && "mulligan".equals(open.kind)) {
                    open.prompts.add(cls);
                } else {
                    closeOpen(null, null);
                    openMulligan();
                }
                break;
            default:
                // targets, mana payment, choosing cards from a list: steps inside the open decision
                if (open != null) {
                    open.prompts.add(cls + (in != null ? ": " + StateView.clip(String.valueOf(in), 160) : ""));
                } else {
                    JsonObject r = base("prompt");
                    r.addProperty("input", cls);
                    write(r);
                }
        }
    }

    // ------------------------------------------------------------------ events

    @Subscribe
    public synchronized void onEvent(GameEvent ev) {
        if (finished) return;
        try {
            if (ev instanceof GameEventPlayerPriority p) {
                closeOpen(null, null);  // whoever has priority now, the open decision was a pass
                if (aiMode && p.priority() == me.getView()) openAction();
            } else if (ev instanceof GameEventSpellAbilityCast c) {
                StackItemView si = c.si();
                if (si == null || si.getActivatingPlayer() != me.getView() || si.isTrigger()) return;
                String label = (si.isAbility() ? "activate " : "cast ") + StateView.clip(si.getText(), 220);
                ownAction(label, opt -> opt.sa != null && !opt.sa.isLandAbility()
                        && (opt.sa.getView() == c.sa() || sameHost(opt, si.getSourceCard()) && opt.sa.isSpell() == !si.isAbility()));
            } else if (ev instanceof GameEventLandPlayed l) {
                if (l.player() != me.getView()) return;
                ownAction("play land " + l.land().getName(),
                        opt -> opt.sa != null && opt.sa.isLandAbility() && sameHost(opt, l.land()));
            } else if (ev instanceof GameEventAttackersDeclared a) {
                if (a.player() != me.getView()) return;
                List<CardView> who = new ArrayList<>(a.attackersMap().values());
                combatDeclared("attack", who, attackLabels(a.attackersMap()));
            } else if (ev instanceof GameEventBlockersDeclared b) {
                if (b.defendingPlayer() != me.getView()) return;
                List<CardView> who = new ArrayList<>();
                combatDeclared("block", who, blockLabels(b.blockers(), who));
            } else if (ev instanceof GameEventMulligan m) {
                if (m.player() != me.getView()) return;
                if (open != null && "mulligan".equals(open.kind)) close(open, "mulligan", "mulligan for a new hand");
                else write(base("mulligan"));
                open = null;
            } else if (ev instanceof GameEventGameOutcome o) {
                finish(o);
            }
        } catch (Throwable t) {
            errors++;
        }
    }

    private interface Match { boolean test(Opt o); }

    private static boolean sameHost(Opt o, CardView cv) {
        return cv != null && o.card != null && o.card.getId() == cv.getId();
    }

    private void ownAction(String label, Match match) {
        if (open != null && "action".equals(open.kind)) {
            Opt hit = null;
            for (Opt o : open.opts) if (match.test(o)) { hit = o; break; }
            close(open, hit != null ? hit.id : "other", label);
            open = null;
        } else {
            // a play outside a priority prompt: a free cast during a resolution (Plargg and Nassari, cascade), or
            // an AI seat's second play in one priority loop
            Window w = window("action");
            w.context = "outside a priority prompt (a free or follow-up cast)";
            close(w, "other", label);
        }
        if (aiMode && !game.isGameOver()) openAction();  // the AI keeps priority without a new priority event
    }

    // ------------------------------------------------------------------ windows

    private Window window(String kind) {
        Window w = new Window();
        PhaseHandler ph = game.getPhaseHandler();
        w.kind = kind;
        w.turn = ph.getTurn();
        w.phase = String.valueOf(ph.getPhase());
        w.t0 = System.currentTimeMillis();
        try {
            w.state = StateView.describe(game, me);
        } catch (Throwable t) {
            errors++;
            w.state = new JsonObject();
        }
        w.log = newLog();
        return w;
    }

    private void openAction() {
        Window w = window("action");
        PhaseHandler ph = game.getPhaseHandler();
        PhaseType phase = ph.getPhase();
        boolean ourTurn = ph.getPlayerTurn() == me;
        boolean stackEmpty = game.getStack().isEmpty();
        boolean main = ourTurn && stackEmpty && (phase == PhaseType.MAIN1 || phase == PhaseType.MAIN2);
        SpellAbilityStackInstance top = stackEmpty ? null : game.getStack().peek();
        w.context = main ? (phase == PhaseType.MAIN1 ? "our main phase 1 (before combat), stack empty"
                        : "our main phase 2 (after combat), stack empty")
                : top != null ? (top.getActivatingPlayer() == me ? "our own spell or ability is on the stack: "
                        : "responding to an opponent's spell or ability: ") + StateView.clip(top.getStackDescription(), 200)
                : (ourTurn ? "our turn, " : "an opponent's turn (" + StateView.label(ph.getPlayerTurn()) + "), ")
                        + "stack empty (" + phase + ")";
        long t0 = System.currentTimeMillis();
        Set<String> labels = new HashSet<>();
        List<SpellAbility> all;
        try {
            all = ComputerUtilAbility.getSpellAbilities(ComputerUtilAbility.getAvailableCards(game, me), me);
        } catch (Throwable t) {
            errors++;
            all = new ArrayList<>();
        }
        for (SpellAbility sa : all) {
            if (w.opts.size() >= MAX_OPTIONS || System.currentTimeMillis() - t0 > SCAN_BUDGET_MS) {
                w.prompts.add("option scan truncated");
                break;
            }
            Card host = sa.getHostCard();
            if (host == null || sa.isManaAbility()) continue;
            String note = "";
            try {
                if (sa.getActivatingPlayer() == null) sa.setActivatingPlayer(me);
                if (sa.isLandAbility()) {
                    if (!main || !sa.canPlay()) continue;
                } else {
                    if (!sa.canPlay()) continue;
                    try {
                        if (!ComputerUtilCost.canPayCost(sa, me, false)) continue;
                    } catch (Throwable t) {
                        note = " [cost not checked]";
                    }
                }
            } catch (Throwable t) {
                continue;
            }
            String kind = sa.isLandAbility() ? "play land" : sa.isSpell() ? "cast" : "activate";
            ZoneType zone = host.getZone() == null ? null : host.getZone().getZoneType();
            String text = kind + " " + host.getName() + (zone != null && zone != ZoneType.Hand ? " (from " + zone + ")" : "")
                    + (sa.isLandAbility() ? "" : ": " + StateView.clip(sa.toString(), 180)) + note;
            if (!labels.add(text)) continue;
            w.opts.add(new Opt("o" + w.opts.size(), text, sa, host));
        }
        open = w;
    }

    private void openCombat(String kind) {
        Window w = window(kind);
        int i = 0;
        for (Card c : me.getCreaturesInPlay()) {
            boolean able;
            try {
                able = "attack".equals(kind) ? CombatUtil.canAttack(c) : CombatUtil.canBlock(c);
            } catch (Throwable t) {
                able = !c.isTapped();
            }
            if (able) w.opts.add(new Opt("o" + i++, c.getName() + " " + c.getNetPower() + "/" + c.getNetToughness(), null, c));
        }
        if ("block".equals(kind)) {
            try {
                if (game.getCombat() != null) {
                    JsonArray at = new JsonArray();
                    for (Card a : game.getCombat().getAttackers()) {
                        at.add(a.getName() + " " + a.getNetPower() + "/" + a.getNetToughness() + " ("
                                + StateView.label(a.getController()) + ") -> " + game.getCombat().getDefenderByAttacker(a));
                    }
                    w.context = "attackers: " + at;
                }
            } catch (Throwable ignored) { }
        }
        open = w;
    }

    private void openMulligan() {
        Window w = window("mulligan");
        w.opts.add(new Opt("keep", "keep the hand", null, null));
        w.opts.add(new Opt("mulligan", "mulligan for a new hand", null, null));
        open = w;
    }

    private void combatDeclared(String kind, List<CardView> who, List<String> labels) {
        Window w = open != null && kind.equals(open.kind) ? open : window(kind);
        if (w.opts.isEmpty()) {
            // no prompt came first (an AI seat): the options are the creatures declared plus the others that could have
            Set<Integer> seen = new HashSet<>();
            for (CardView cv : who) {
                if (!seen.add(cv.getId())) continue;
                Card c = game.findById(cv.getId());
                w.opts.add(new Opt("o" + w.opts.size(), c == null ? cv.getName() : c.getName() + " " + c.getNetPower() + "/" + c.getNetToughness(), null, c));
            }
            for (Card c : me.getCreaturesInPlay()) {
                if (!c.isTapped() && seen.add(c.getId())) w.opts.add(new Opt("o" + w.opts.size(), c.getName() + " " + c.getNetPower() + "/" + c.getNetToughness(), null, c));
            }
        }
        String label = labels.isEmpty() ? ("attack".equals(kind) ? "no attack" : "no blocks") : String.join("; ", labels);
        List<String> ids = new ArrayList<>();
        for (Opt o : w.opts) {
            for (CardView cv : who) if (o.card != null && o.card.getId() == cv.getId()) { ids.add(o.id); break; }
        }
        close(w, ids.isEmpty() ? "none" : String.join(",", ids), label);
        open = null;
    }

    private static List<String> attackLabels(Multimap<GameEntityView, CardView> m) {
        List<String> out = new ArrayList<>();
        for (Map.Entry<GameEntityView, CardView> e : m.entries()) {
            out.add(e.getValue().getName() + " -> " + defender(e.getKey()));
        }
        return out;
    }

    /** defender -> attacker -> blockers; Forge maps an unblocked attacker to itself. */
    private static List<String> blockLabels(Map<GameEntityView, Multimap<CardView, CardView>> m, List<CardView> who) {
        List<String> out = new ArrayList<>();
        for (Multimap<CardView, CardView> byAttacker : m.values()) {
            for (Map.Entry<CardView, CardView> e : byAttacker.entries()) {
                if (e.getValue().getId() == e.getKey().getId()) continue;
                out.add(e.getValue().getName() + " blocks " + e.getKey().getName());
                who.add(e.getValue());
            }
        }
        return out;
    }

    private static String defender(GameEntityView v) {
        if (v instanceof PlayerView pv) {
            String n = pv.getName();
            int i = n.indexOf(")-");
            return i >= 0 ? n.substring(i + 2) : n;
        }
        return v instanceof CardView cv ? cv.getName() : String.valueOf(v);
    }

    /** Close the open decision with no play: a pass, no attack, no blocks, or a kept hand. */
    private void closeOpen(String choice, String label) {
        if (open == null) return;
        Window w = open;
        open = null;
        switch (w.kind) {
            case "action": close(w, "pass", "pass priority"); break;
            case "attack": close(w, "none", "no attack"); break;
            case "block": close(w, "none", "no blocks"); break;
            case "mulligan": close(w, "keep", "keep the hand"); break;
            default: close(w, choice, label);
        }
    }

    private void close(Window w, String choice, String label) {
        JsonObject r = base("decision");
        r.addProperty("turn", w.turn);
        r.addProperty("phase", w.phase);
        r.addProperty("kind", w.kind);
        r.addProperty("ms", System.currentTimeMillis() - w.t0);
        String qid = "action".equals(w.kind) ? "action" : "mulligan".equals(w.kind) ? "keep"
                : "attack".equals(w.kind) ? "attackers" : "blockers";
        String dflt = "action".equals(w.kind) ? "pass" : "mulligan".equals(w.kind) ? "keep" : "none";
        String prompt = "action".equals(w.kind) ? "Which action do we take now?"
                : "mulligan".equals(w.kind) ? "Keep this hand or mulligan?"
                : "attack".equals(w.kind) ? "Which creatures attack, and whom?" : "Which creatures block, and what?";
        JsonObject ctx = new JsonObject();
        if (w.context != null) ctx.addProperty("window", w.context);
        if (!w.prompts.isEmpty()) ctx.add("prompts", w.prompts);
        r.add("context", ctx);
        JsonObject q = new JsonObject();
        q.addProperty("id", qid);
        q.addProperty("prompt", prompt);
        q.addProperty("default", dflt);
        JsonArray opts = new JsonArray();
        for (Opt o : w.opts) opts.add(option(o.id, o.text));
        if ("action".equals(w.kind)) opts.add(option("pass", "pass priority: take no action now"));
        if ("attack".equals(w.kind) || "block".equals(w.kind)) opts.add(option("none", "attack".equals(w.kind) ? "no attack" : "no blocks"));
        q.add("options", opts);
        JsonArray qs = new JsonArray();
        qs.add(q);
        r.add("questions", qs);
        JsonObject a = new JsonObject();
        a.addProperty("q", qid);
        a.addProperty("default", dflt);
        a.addProperty("choice", choice);
        a.addProperty("label", label);
        JsonArray as = new JsonArray();
        as.add(a);
        r.add("answers", as);
        r.add("state", w.state);
        if (w.log != null && !w.log.isEmpty()) r.add("log", w.log);
        write(r);
    }

    private static JsonObject option(String id, String text) {
        JsonObject o = new JsonObject();
        o.addProperty("id", id);
        o.addProperty("text", text);
        return o;
    }

    // ------------------------------------------------------------------ output

    private JsonObject base(String type) {
        JsonObject r = new JsonObject();
        r.addProperty("type", type);
        r.addProperty("game", gid);
        r.addProperty("by", aiMode ? "ai-test" : "human");
        if (!"decision".equals(type)) {
            r.addProperty("turn", game.getPhaseHandler().getTurn());
            r.addProperty("phase", String.valueOf(game.getPhaseHandler().getPhase()));
        }
        return r;
    }

    private JsonArray newLog() {
        JsonArray out = new JsonArray();
        try {
            List<GameLogEntry> all = game.getGameLog().getAllEntries();
            for (int i = logSeen; i < all.size(); i++) out.add(String.valueOf(all.get(i)));
            logSeen = all.size();
        } catch (Throwable t) {
            errors++;
        }
        return out;
    }

    private void write(JsonObject r) {
        try {
            Files.createDirectories(dir);
            if (!started) {
                started = true;
                JsonObject s = new JsonObject();
                s.addProperty("type", "game_start");
                s.addProperty("game", gid);
                s.addProperty("by", aiMode ? "ai-test" : "human");
                s.addProperty("me", StateView.label(me));
                s.addProperty("me_name", me.getName());
                JsonArray ps = new JsonArray();
                for (Player p : game.getRegisteredPlayers()) {
                    JsonObject o = new JsonObject();
                    o.addProperty("name", StateView.label(p));
                    o.addProperty("is_me", p == me);
                    JsonArray cmd = new JsonArray();
                    try { for (Card c : p.getCommanders()) cmd.add(c.getName()); } catch (Throwable ignored) { }
                    o.add("commanders", cmd);
                    ps.add(o);
                }
                s.add("players", ps);
                append(s);
            }
            append(r);
            records++;
        } catch (Throwable t) {
            errors++;
        }
    }

    private void append(JsonObject r) throws IOException {
        try (Writer w = Files.newBufferedWriter(dir.resolve(FILE), StandardCharsets.UTF_8,
                StandardOpenOption.CREATE, StandardOpenOption.APPEND)) {
            w.write(GSON.toJson(r));
            w.write("\n");
        }
    }

    private void finish(GameEventGameOutcome o) throws IOException {
        if (finished) return;
        if (open != null) closeOpen(null, null);
        JsonObject r = base("outcome");
        // a draw still carries a "winning" player name; Forge's own outcome says whether it was a draw
        boolean draw = o.winningPlayerName() == null;
        try {
            draw |= game.getOutcome() != null && (game.getOutcome().isDraw()
                    || game.getOutcome().getWinCondition() == forge.game.GameEndReason.Draw);
        } catch (Throwable ignored) { }
        r.addProperty("winner", draw ? "none (draw)" : o.winningPlayerName());
        r.addProperty("we_won", !draw && o.winningPlayerName().equals(me.getName()));
        JsonArray lines = new JsonArray();
        if (o.outcomeStrings() != null) for (String s : o.outcomeStrings()) lines.add(s);
        r.add("outcome", lines);
        r.addProperty("records", records + 1);
        r.addProperty("recorder_errors", errors);
        JsonArray rest = newLog();
        if (!rest.isEmpty()) r.add("log", rest);
        write(r);
        finished = true;
        // the whole game log, oldest first, in the format sim pod logs use
        StringBuilder sb = new StringBuilder();
        for (GameLogEntry e : game.getGameLog().getAllEntries()) sb.append(e).append('\n');
        Files.writeString(dir.resolve(gid + ".log"), sb.toString(), StandardCharsets.UTF_8);
        System.out.println("[recorder] " + gid + ": " + records + " records, " + errors + " recorder errors -> " + dir);
    }
}
