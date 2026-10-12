package edh.pilot;

import java.awt.Rectangle;
import java.awt.Robot;
import java.awt.Toolkit;
import java.awt.image.BufferedImage;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.WeakHashMap;

import javax.imageio.ImageIO;

import forge.GuiDesktop;
import forge.Singletons;
import forge.deck.Deck;
import forge.deck.io.DeckSerializer;
import forge.game.Game;
import forge.game.GameEndReason;
import forge.game.GameRules;
import forge.game.GameType;
import forge.game.Match;
import forge.game.card.Card;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.player.RegisteredPlayer;
import forge.game.zone.ZoneType;
import forge.gamemodes.match.HostedMatch;
import forge.gamemodes.match.input.Input;
import forge.gamemodes.match.input.InputPassPriority;
import forge.gamemodes.match.input.InputQueue;
import forge.gui.FThreads;
import forge.gui.GuiBase;
import forge.gui.interfaces.IGuiGame;
import forge.localinstance.properties.ForgeConstants;
import forge.model.FModel;
import forge.player.GamePlayerUtil;
import forge.player.PlayerControllerHuman;
import forge.util.MyRandom;

/**
 * Forge's desktop UI with the decision recorder attached to every game a human plays in it.
 *
 *   java -cp forge.jar:pilot.jar edh.pilot.RecorderMain --out DIR [--decks DIR]
 *
 * --decks copies the .dck files there into Forge's Commander deck folder first, so they show up in the deck
 * lists. Each game the human plays appends to DIR/human_decisions.jsonl and writes DIR/<game>.log.
 *
 * Two test modes, for checking the recorder without a person at the keyboard:
 *   --headless-test --turns N --seed S deck1.dck ... : AI-only game, recorder on seat 1 (driven by priority events)
 *   --gui-test --turns N [--screenshot f.png] deck1.dck ... : the real desktop UI (run under Xvfb); seat 1 is a
 *        human controller whose prompts a driver answers (play a land, cast what the OK button allows, pass)
 */
public final class RecorderMain {
    private static final Map<Game, Boolean> ATTACHED = Collections.synchronizedMap(new WeakHashMap<>());

    public static void main(String[] args) throws Exception {
        System.setProperty("java.util.Arrays.useLegacyMergeSort", "true");
        Path out = Paths.get("human-games");
        String decksDir = null, screenshot = null;
        boolean headlessTest = false, guiTest = false;
        int turns = 6;
        long seed = 1;
        List<String> decks = new ArrayList<>();
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--out": out = Paths.get(args[++i]); break;
                case "--decks": decksDir = args[++i]; break;
                case "--headless-test": headlessTest = true; break;
                case "--gui-test": guiTest = true; break;
                case "--turns": turns = Integer.parseInt(args[++i]); break;
                case "--seed": seed = Long.parseLong(args[++i]); break;
                case "--screenshot": screenshot = args[++i]; break;
                default: decks.add(args[i]);
            }
        }
        if (headlessTest) {
            headless(out, decks, turns, seed);
            return;
        }
        // the deck folder is only known once Forge's GUI interface is set; Main sets it again, harmlessly
        GuiBase.setInterface(new GuiDesktop());
        if (decksDir != null) installDecks(Paths.get(decksDir));
        startWatcher(out);
        if (guiTest) startGuiTest(decks, turns, screenshot);
        System.out.println("[recorder] writing human games to " + out.toAbsolutePath());
        forge.view.Main.main(new String[0]);
    }

    static void installDecks(Path from) throws Exception {
        Path to = Paths.get(ForgeConstants.DECK_COMMANDER_DIR);
        Files.createDirectories(to);
        int n = 0;
        try (var files = Files.list(from)) {
            for (Path p : (Iterable<Path>) files::iterator) {
                if (!p.toString().endsWith(".dck")) continue;
                Files.copy(p, to.resolve(p.getFileName()), StandardCopyOption.REPLACE_EXISTING);
                n++;
            }
        }
        System.out.println("[recorder] installed " + n + " decks into " + to);
    }

    /** Attach a recorder to each new GUI game, for each human seat in it. */
    static void startWatcher(Path out) {
        Thread t = new Thread(() -> {
            while (true) {
                try {
                    if (Singletons.getControl() != null) {
                        for (HostedMatch hm : new ArrayList<>(Singletons.getControl().getCurrentMatches())) {
                            Game g = hm.getGame();
                            if (g != null && !g.isGameOver() && ATTACHED.putIfAbsent(g, true) == null) attach(g, out);
                        }
                    }
                    Thread.sleep(50);
                } catch (InterruptedException e) {
                    return;
                } catch (Throwable ignored) {
                    // the match list changes under us while games start and end; look again next tick
                }
            }
        }, "edh-recorder-watch");
        t.setDaemon(true);
        t.start();
    }

    static void attach(Game g, Path out) {
        for (Player p : g.getPlayers()) {
            if (p.getController() instanceof PlayerControllerHuman h) {
                Recorder r = new Recorder(g, p, out, false).attach();
                InputQueue q = h.getInputQueue();
                q.addObserver(r);
                r.primeFrom(q);  // a prompt already showing (the mulligan) before we attached
                System.out.println("[recorder] recording " + p.getName() + " in " + r.gid);
            }
        }
    }

    // ------------------------------------------------------------------ headless test

    static void headless(Path out, List<String> decks, int turns, long seed) throws Exception {
        System.setProperty("java.awt.headless", "true");
        GuiBase.setInterface(new GuiDesktop());
        FModel.initialize(null, null);
        MyRandom.setRandom(new Random(seed));
        GameRules rules = new GameRules(GameType.Commander);
        rules.setAppliedVariants(EnumSet.of(GameType.Commander));
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < decks.size(); i++) {
            Deck d = DeckSerializer.fromFile(new File(decks.get(i)));
            RegisteredPlayer rp = RegisteredPlayer.forCommander(d);
            rp.setPlayer(GamePlayerUtil.createAiPlayer("Ai(" + (i + 1) + ")-P" + (i + 1), i, ""));
            players.add(rp);
        }
        Match mc = new Match(rules, players, "Recorder test");
        Game game = mc.createGame();
        game.setNoGUIUser();
        Recorder rec = new Recorder(game, game.getPlayers().get(0), out, true).attach();
        Thread run = new Thread(() -> {
            try {
                mc.startGame(game, null);
            } catch (Throwable e) {
                if (!game.isGameOver()) e.printStackTrace();
            }
        });
        run.setDaemon(true);
        run.start();
        long deadline = System.currentTimeMillis() + 900_000L;
        while (!game.isGameOver() && System.currentTimeMillis() < deadline) {
            if (game.getPhaseHandler().getTurn() > turns) game.setGameOver(GameEndReason.Draw);
            Thread.sleep(20);
        }
        if (!game.isGameOver()) game.setGameOver(GameEndReason.Draw);
        run.join(10_000);
        System.out.println("[recorder-test] " + rec.gid + " turns=" + game.getPhaseHandler().getTurn()
                + " records=" + rec.records + " errors=" + rec.errors);
        System.out.flush();
        System.exit(0);
    }

    // ------------------------------------------------------------------ GUI test

    /** Host a Commander match in the real desktop UI with seat 1 human, and answer its prompts. */
    static void startGuiTest(List<String> deckPaths, int turns, String screenshot) {
        Thread t = new Thread(() -> {
            try {
                while (Singletons.getControl() == null || Singletons.getView() == null
                        || Singletons.getControl().getCurrentScreen() == null) Thread.sleep(200);
                Thread.sleep(3000);
                // a blank player name makes Forge ask for one in a dialog when the match starts
                FModel.getPreferences().setPref(forge.localinstance.properties.ForgePreferences.FPref.PLAYER_NAME, "Tester");
                FModel.getPreferences().save();
                List<RegisteredPlayer> players = new ArrayList<>();
                RegisteredPlayer human = null;
                for (int i = 0; i < deckPaths.size(); i++) {
                    Deck d = DeckSerializer.fromFile(new File(deckPaths.get(i)));
                    RegisteredPlayer rp = RegisteredPlayer.forCommander(d);
                    rp.setPlayer(i == 0 ? GamePlayerUtil.getGuiPlayer() : GamePlayerUtil.createAiPlayer("Opponent " + (i + 1), i));
                    if (i == 0) human = rp;
                    players.add(rp);
                }
                final RegisteredPlayer h0 = human;
                final HostedMatch[] hm = new HostedMatch[1];
                FThreads.invokeInEdtAndWait(() -> {
                    hm[0] = GuiBase.getInterface().hostMatch();
                    IGuiGame gui = GuiBase.getInterface().getNewGuiGame();
                    hm[0].startMatch(GameType.Constructed, EnumSet.of(GameType.Commander), players, Map.of(h0, gui));
                });
                drive(hm[0], turns, screenshot);
            } catch (Throwable e) {
                e.printStackTrace();
                System.exit(3);
            }
        }, "edh-gui-test");
        t.setDaemon(true);
        t.start();
    }

    /** Stand in for a person: keep the hand, play a land each turn, cast a cheap permanent when one is
     *  affordable, otherwise press OK (pass, no attack, no blocks). Keyboard Enter clears any dialog. */
    static void drive(HostedMatch hm, int turns, String screenshot) throws Exception {
        Robot robot = new Robot();
        Game game = null;
        PlayerControllerHuman hc = null;
        long deadline = System.currentTimeMillis() + 600_000L;
        Object lastInput = null;
        long since = System.currentTimeMillis();
        boolean shot = false;
        while (System.currentTimeMillis() < deadline) {
            Thread.sleep(150);
            if (game == null) {
                game = hm.getGame();
                if (game == null || hm.getHumanControllers().isEmpty()) { game = null; continue; }
                hc = hm.getHumanControllers().get(0);
            }
            if (game.isGameOver()) break;
            int turn = game.getPhaseHandler().getTurn();
            if (turn > turns) {
                game.setGameOver(GameEndReason.Draw);
                break;
            }
            if (!shot && screenshot != null && turn >= 3) {
                shot = true;
                Thread.sleep(800);
                BufferedImage img = robot.createScreenCapture(new Rectangle(Toolkit.getDefaultToolkit().getScreenSize()));
                ImageIO.write(img, "png", new File(screenshot));
                System.out.println("[gui-test] screenshot " + screenshot);
            }
            Input in = hc.getInputQueue().getInput();
            if (in != lastInput) {
                lastInput = in;
                since = System.currentTimeMillis();
                if (in == null) continue;
                final Input cur = in;
                final Player me = hc.getPlayer();
                final Game g = game;
                FThreads.invokeInEdtLater(() -> answer(cur, me, g));
            } else if (System.currentTimeMillis() - since > 2500) {
                // a modal dialog (play or draw, a choice list) or an input our answer didn't clear
                // a payment we can't complete stays open: cancel it, as a person would
                if (!clickDialog() && in != null) {
                    boolean pay = in.getClass().getSimpleName().startsWith("InputPayMana");
                    FThreads.invokeInEdtLater(pay ? in::selectButtonCancel : in::selectButtonOK);
                }
                since = System.currentTimeMillis();
            }
        }
        if (game != null && !game.isGameOver()) game.setGameOver(GameEndReason.Draw);  // out of time
        Thread.sleep(3000);  // let the outcome event and the recorder's log write finish
        System.out.println("[gui-test] done at turn " + (game == null ? -1 : game.getPhaseHandler().getTurn()));
        System.out.flush();
        System.exit(0);
    }

    /** Click the first button of a visible dialog (Xvfb has no window manager to focus it for a key press). */
    static boolean clickDialog() {
        for (java.awt.Window w : java.awt.Window.getWindows()) {
            if (!(w instanceof java.awt.Dialog) || !w.isVisible()) continue;
            javax.swing.AbstractButton b = null;
            for (String want : new String[] {"OK", "Yes", "Keep", "Play", "Continue", "Not now", "Later", "No", "Cancel", "Close"}) {
                b = findButton(w, want);
                if (b != null) break;
            }
            if (b == null) b = findButton(w, null);
            if (b != null) {
                System.out.println("[gui-test] dialog '" + ((java.awt.Dialog) w).getTitle() + "': clicking " + b.getText());
                javax.swing.SwingUtilities.invokeLater(b::doClick);
                return true;
            }
        }
        return false;
    }

    /** A visible, enabled button whose text starts with `want` (any labelled button when null). */
    static javax.swing.AbstractButton findButton(java.awt.Container c, String want) {
        for (java.awt.Component k : c.getComponents()) {
            if (k instanceof javax.swing.AbstractButton b && b.isEnabled() && b.isShowing() && b.getText() != null
                    && !b.getText().isBlank() && (want == null || b.getText().trim().startsWith(want))) return b;
            if (k instanceof java.awt.Container cc) {
                javax.swing.AbstractButton b = findButton(cc, want);
                if (b != null) return b;
            }
        }
        return null;
    }

    private static final Set<String> CHEAP = Set.of("Sol Ring", "Arcane Signet", "Fellwar Stone", "Dimir Signet",
            "Talisman of Creativity", "Talisman of Dominance", "Talisman of Indulgence", "Swiftfoot Boots");

    static int untappedManaSources(Player me) {
        int n = 0;
        for (Card c : me.getCardsIn(ZoneType.Battlefield)) if (!c.isTapped() && !c.getManaAbilities().isEmpty()) n++;
        return n;
    }

    private static int mulligans;

    static void answer(Input in, Player me, Game game) {
        try {
            String cls = in.getClass().getSimpleName();
            if (cls.equals("InputConfirmMulligan")) {  // OK keeps, Cancel mulligans; ship a hand with under 2 lands once
                long lands = me.getCardsIn(ZoneType.Hand).stream().filter(Card::isLand).count();
                if (lands < 2 && mulligans++ < 1) { in.selectButtonCancel(); return; }
            }
            if (cls.equals("InputSelectEntitiesFromList")) {  // who starts (we won the roll): pick ourselves first
                in.selectPlayer(me, null);
            }
            if (cls.equals("InputAttack")) {  // everything that can attack, at the default defender
                for (Card c : me.getCreaturesInPlay()) {
                    if (forge.game.combat.CombatUtil.canAttack(c)) in.selectCard(c, null, null);
                }
            }
            if (in instanceof InputPassPriority) {
                boolean main = game.getPhaseHandler().getPlayerTurn() == me && game.getStack().isEmpty()
                        && (game.getPhaseHandler().getPhase() == PhaseType.MAIN1 || game.getPhaseHandler().getPhase() == PhaseType.MAIN2);
                if (main) {
                    if (me.getLandsPlayedThisTurn() == 0) {
                        for (Card c : me.getCardsIn(ZoneType.Hand)) {
                            if (c.isLand() && in.selectCard(c, null, null)) return;
                        }
                    }
                    for (Card c : me.getCardsIn(ZoneType.Hand)) {
                        if (CHEAP.contains(c.getName()) && c.getCMC() <= untappedManaSources(me)
                                && in.selectCard(c, null, null)) return;
                    }
                    for (Card c : me.getCardsIn(ZoneType.Command)) {  // the commander, once there's mana for her
                        if (c.isCommander() && c.getCMC() <= untappedManaSources(me) && in.selectCard(c, null, null)) return;
                    }
                }
            }
            in.selectButtonOK();
        } catch (Throwable e) {
            System.out.println("[gui-test] answer failed: " + e);
        }
    }
}
