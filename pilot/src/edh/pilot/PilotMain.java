package edh.pilot;

import java.io.File;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Random;

import forge.GuiDesktop;
import forge.LobbyPlayer;
import forge.deck.Deck;
import forge.deck.io.DeckSerializer;
import forge.game.GameRules;
import forge.game.GameType;
import forge.game.Match;
import forge.game.player.RegisteredPlayer;
import forge.gui.GuiBase;
import forge.model.FModel;
import forge.player.GamePlayerUtil;
import forge.util.MyRandom;
import forge.view.SimulateMatch;

/**
 * Headless Commander match with one seat piloted externally. Output matches
 * `forge sim` (full game logs), so edhkit's log parser works unchanged.
 *
 *   java -cp forge.jar:pilot.jar edh.pilot.PilotMain --pilot-seat 2 --sidecar http://127.0.0.1:8765 \
 *        --games 5 --seed 42 --clock 600 --tag pod03 deck1.dck deck2.dck deck3.dck deck4.dck
 */
public final class PilotMain {
    public static void main(String[] args) {
        System.setProperty("java.awt.headless", "true");
        System.setProperty("java.util.Arrays.useLegacyMergeSort", "true");
        int seat = 1, games = 1, clock = 600;
        long seed = 1;
        String sidecarUrl = null, tag = "pod";
        List<String> decks = new ArrayList<>();
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--pilot-seat": seat = Integer.parseInt(args[++i]); break;
                case "--games": games = Integer.parseInt(args[++i]); break;
                case "--seed": seed = Long.parseLong(args[++i]); break;
                case "--clock": clock = Integer.parseInt(args[++i]); break;
                case "--sidecar": sidecarUrl = args[++i]; break;
                case "--tag": tag = args[++i]; break;
                default: decks.add(args[i]);
            }
        }
        GuiBase.setInterface(new GuiDesktop());
        FModel.initialize(null, null);
        MyRandom.setRandom(new Random(seed));

        GameRules rules = new GameRules(GameType.Commander);
        rules.setAppliedVariants(EnumSet.of(GameType.Commander));
        rules.setSimTimeout(clock);

        // "--sidecar count": our seat runs PilotController with no pilot, so Forge answers everything but
        // the counting layer still tallies every decision (to measure what the pilot never sees).
        boolean countOnly = "count".equals(sidecarUrl);
        Sidecar sidecar = sidecarUrl == null || countOnly ? null : new Sidecar(sidecarUrl);
        List<RegisteredPlayer> players = new ArrayList<>();
        StringBuilder header = new StringBuilder();
        for (int i = 0; i < decks.size(); i++) {
            Deck d = DeckSerializer.fromFile(new File(decks.get(i)));
            if (d == null) {
                System.out.println("Could not load deck - " + decks.get(i));
                return;
            }
            String name = "Ai(" + (i + 1) + ")-" + d.getName();
            LobbyPlayer lp = (i + 1 == seat && (sidecar != null || countOnly))
                    ? new PilotLobbyPlayer(name, sidecar, tag)
                    : GamePlayerUtil.createAiPlayer(name, i, "");
            RegisteredPlayer rp = RegisteredPlayer.forCommander(d);
            rp.setPlayer(lp);
            players.add(rp);
            header.append(i > 0 ? " vs " : "").append(name).append(i + 1 == seat && (sidecar != null || countOnly) ? " [pilot]" : "");
        }
        System.out.println("Simulation mode");
        System.out.println(header + " - " + games + " games of Commander seed " + seed);
        Match mc = new Match(rules, players, "Pilot");
        for (int g = 0; g < games; g++) {
            CountingController.drain();
            SimulateMatch.simulateSingleMatch(mc, g, true);
            System.out.println("[pilot] controller-calls " + tag + "-g" + g + " " + CountingController.drain());
        }
        System.out.flush();
        System.exit(0);
    }
}
