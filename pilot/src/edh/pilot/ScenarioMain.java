package edh.pilot;

import java.io.File;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumSet;
import java.util.List;
import java.util.Random;

import forge.GuiDesktop;
import forge.LobbyPlayer;
import forge.deck.Deck;
import forge.deck.io.DeckSerializer;
import forge.game.Game;
import forge.game.GameEndReason;
import forge.game.GameLogEntry;
import forge.game.GameRules;
import forge.game.GameState;
import forge.game.GameType;
import forge.game.Match;
import forge.game.player.RegisteredPlayer;
import forge.gui.GuiBase;
import forge.model.FModel;
import forge.player.GamePlayerUtil;
import forge.util.MyRandom;

/**
 * One board, loaded from a Forge game-state file, played forward a few turns. For testing a single
 * interaction in seconds instead of finding it in a 40-minute sim.
 *
 *   java -cp forge.jar:pilot.jar edh.pilot.ScenarioMain --state s.txt [--pilot-seat 1 --sidecar URL]
 *        [--turns 1] [--seed 1] deck1.dck deck2.dck ...
 *
 * The state file uses Forge's puzzle syntax (p0battlefield=Vivi Ornitier|Id:1;Ophidian Eye|AttachedTo:1,
 * activeplayer=p0, activephase=MAIN1, turn=5 ...). Players are p0.. in deck order. The game stops once
 * `--turns` turns have begun after the state's own turn, and the full game log is printed.
 */
public final class ScenarioMain {
    /** Applies the state on the calling thread: applyToGame() queues it on Forge's game thread pool, which races
     *  the game loop when the match runs on our own thread. */
    static final class SyncState extends GameState {
        void applyNow(Game game) {
            applyGameOnThread(game);
            // cards the state creates have no activating player on their mana abilities, so Forge's AI can't pay
            // with them ("Did not have activator set"): lands in a scenario were unusable
            for (forge.game.card.Card c : game.getCardsIn(forge.game.zone.ZoneType.Battlefield)) {
                for (forge.game.spellability.SpellAbility sa : c.getManaAbilities()) sa.setActivatingPlayer(c.getController());
                for (forge.game.spellability.SpellAbility sa : c.getSpellAbilities()) if (sa.getActivatingPlayer() == null) sa.setActivatingPlayer(c.getController());
            }
        }
    }

    static void dumpAttachments(Game game) {
        for (forge.game.card.Card c : game.getCardsInGame()) {
            if (c.getName().equals("Ophidian Eye") || c.getName().equals("Sigil of Sleep"))
                System.out.println("[attach] where: " + c + " zone=" + c.getZone() + " controller=" + c.getController()
                        + " attachedTo=" + c.getEntityAttachedTo());
        }
        // attachment identity: an attachment whose host object isn't the live card is a stale-object bug
        for (forge.game.card.Card c : game.getCardsIn(forge.game.zone.ZoneType.Battlefield)) {
            forge.game.GameEntity to = c.getEntityAttachedTo();
            System.out.println("[attach] on battlefield: " + c + " attachedTo=" + to + " attachments=" + c.getAttachedCards());
            if (to instanceof forge.game.card.Card host) {
                forge.game.card.Card live = game.getCardState(host, null);
                System.out.println("[attach] " + c + " -> " + host + " live=" + (live == host)
                        + " hostHasIt=" + host.hasCardAttachment(c) + " liveHasIt=" + (live != null && live.hasCardAttachment(c)));
            }
        }
    }

    public static void main(String[] args) throws Exception {
        System.setProperty("java.awt.headless", "true");
        System.setProperty("java.util.Arrays.useLegacyMergeSort", "true");
        int seat = 0, turns = 1;
        long seed = 1;
        String sidecarUrl = null, statePath = null;
        List<String> decks = new ArrayList<>();
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--pilot-seat": seat = Integer.parseInt(args[++i]); break;
                case "--turns": turns = Integer.parseInt(args[++i]); break;
                case "--seed": seed = Long.parseLong(args[++i]); break;
                case "--sidecar": sidecarUrl = args[++i]; break;
                case "--state": statePath = args[++i]; break;
                default: decks.add(args[i]);
            }
        }
        GuiBase.setInterface(new GuiDesktop());
        FModel.initialize(null, null);
        MyRandom.setRandom(new Random(seed));
        GameRules rules = new GameRules(GameType.Commander);
        rules.setAppliedVariants(EnumSet.of(GameType.Commander));
        rules.setSimTimeout(120);

        Sidecar sidecar = sidecarUrl == null || "none".equals(sidecarUrl) ? null : new Sidecar(sidecarUrl);
        List<RegisteredPlayer> players = new ArrayList<>();
        for (int i = 0; i < decks.size(); i++) {
            Deck d = DeckSerializer.fromFile(new File(decks.get(i)));
            String name = "Ai(" + (i + 1) + ")-P" + (i + 1);
            LobbyPlayer lp = i + 1 == seat && sidecar != null ? new PilotLobbyPlayer(name, sidecar, "scenario")
                    : GamePlayerUtil.createAiPlayer(name, i, "");
            RegisteredPlayer rp = RegisteredPlayer.forCommander(d);
            rp.setPlayer(lp);
            players.add(rp);
        }
        SyncState state = new SyncState();
        state.parse(Files.readAllLines(new File(statePath).toPath()));

        Match mc = new Match(rules, players, "Scenario");
        Game game = mc.createGame();
        game.setNoGUIUser();
        final int limit = turns;
        final int[] start = {-1};
        Thread watch = new Thread(() -> {
            while (!game.isGameOver()) {
                // counts from the state's own turn, once the hook has applied it
                if (start[0] >= 0 && game.getPhaseHandler().getTurn() - start[0] >= limit) {
                    dumpAttachments(game);
                    game.setGameOver(GameEndReason.Draw);
                    break;
                }
                try { Thread.sleep(20); } catch (InterruptedException e) { return; }
            }
        });
        watch.setDaemon(true);
        Thread run = new Thread(() -> {
            try {
                mc.startGame(game, () -> {
                    state.applyNow(game);
                    start[0] = game.getPhaseHandler().getTurn();
                });
            } catch (Throwable e) {
                if (!game.isGameOver()) e.printStackTrace();
            }
        });
        run.setDaemon(true);
        run.start();
        watch.start();
        run.join(120_000);
        if (!game.isGameOver()) game.setGameOver(GameEndReason.Draw);
        List<GameLogEntry> log = game.getGameLog().getLogEntries(null);
        Collections.reverse(log);
        for (GameLogEntry l : log) System.out.println(l);
        System.out.flush();
        System.exit(0);
    }
}
