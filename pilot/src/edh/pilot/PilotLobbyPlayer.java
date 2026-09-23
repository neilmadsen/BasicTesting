package edh.pilot;

import forge.ai.LobbyPlayerAi;
import forge.game.Game;
import forge.game.player.Player;

/** An AI lobby player whose in-game controller is the external pilot. */
public class PilotLobbyPlayer extends LobbyPlayerAi {
    private final Sidecar sidecar;
    private final String tagPrefix;
    private int gameNo = 0;

    public PilotLobbyPlayer(String name, Sidecar sidecar, String tagPrefix) {
        super(name, null);
        this.sidecar = sidecar;
        this.tagPrefix = tagPrefix;
        setAiProfile("Default");
    }

    @Override
    public Player createIngamePlayer(Game game, final int id) {
        Player p = new Player(getName(), game, id);
        gameNo++;
        p.setFirstController(new PilotController(game, p, this, sidecar, tagPrefix + "-g" + gameNo));
        return p;
    }
}
