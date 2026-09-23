package edh.pilot;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import forge.LobbyPlayer;
import forge.ai.AiController;
import forge.ai.AiPlayDecision;
import forge.ai.ComputerUtilAbility;
import forge.ai.ComputerUtilCost;
import forge.ai.ComputerUtilMana;
import forge.ai.PlayerControllerAi;
import forge.game.Game;
import forge.game.GameObject;
import forge.game.card.Card;
import forge.game.card.CardCollection;
import forge.game.phase.PhaseType;
import forge.game.player.Player;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;

/**
 * Forge's AI with one decision handed to an external pilot: what to do with
 * priority during our own main phases while the stack is empty (cast, activate,
 * play a land, or move on). Everything else (combat, responses, targets of
 * spells the pilot picks, mana payment, trigger ordering) stays with Forge's AI.
 *
 * Candidates: Forge's own pick, every other play its evaluator approves, land
 * drops, and legal payable plays Forge *declines* (labelled with its reason),
 * targeted with Forge's mandatory-mode targeting. The last group is where engine
 * decks live: cards Forge's AI won't play or undervalues.
 */
public class PilotController extends PlayerControllerAi {
    private static final int MAX_OPTIONS = 40;
    private static Method canPlayAndPayFor;

    private final Sidecar sidecar;
    private final String gameTag;

    public PilotController(Game game, Player p, LobbyPlayer lp, Sidecar sidecar, String gameTag) {
        super(game, p, lp);
        this.sidecar = sidecar;
        this.gameTag = gameTag;
    }

    private AiPlayDecision evaluate(SpellAbility sa) {
        try {
            if (canPlayAndPayFor == null) {
                canPlayAndPayFor = AiController.class.getDeclaredMethod("canPlayAndPayFor", SpellAbility.class);
                canPlayAndPayFor.setAccessible(true);
            }
            Game game = getGame();
            sa.setActivatingPlayer(player);
            SpellAbility root = sa.getRootAbility();
            if (root.isSpell() || root.isTrigger() || root.isReplacementAbility()) {
                sa.setLastStateBattlefield(game.getLastStateBattlefield());
                sa.setLastStateGraveyard(game.getLastStateGraveyard());
            }
            AiPlayDecision d = (AiPlayDecision) canPlayAndPayFor.invoke(getAi(), sa);
            sa.clearLastState();
            return d;
        } catch (Exception e) {
            return AiPlayDecision.CantPlaySa;
        }
    }

    @Override
    public List<SpellAbility> chooseSpellAbilityToPlay() {
        List<SpellAbility> aiPick = super.chooseSpellAbilityToPlay();
        Game game = getGame();
        PhaseType phase = game.getPhaseHandler().getPhase();
        boolean ourMain = game.getPhaseHandler().getPlayerTurn() == player
                && (phase == PhaseType.MAIN1 || phase == PhaseType.MAIN2)
                && game.getStack().isEmpty();
        if (!ourMain || sidecar == null) {
            return aiPick;
        }

        // ---- candidate plays
        Map<String, List<SpellAbility>> options = new LinkedHashMap<>();
        Map<String, String> source = new LinkedHashMap<>();
        IdentityHashMap<SpellAbility, Boolean> seen = new IdentityHashMap<>();
        String forgeDefault = "pass";
        if (aiPick != null && !aiPick.isEmpty() && aiPick.get(0) != null) {
            options.put("o0", aiPick);
            source.put("o0", "forge");
            forgeDefault = "o0";
            for (SpellAbility sa : aiPick) seen.put(sa, true);
        }
        CardCollection cards = ComputerUtilAbility.getAvailableCards(game, player);
        List<SpellAbility> all;
        try {
            all = ComputerUtilAbility.getOriginalAndAltCostAbilities(ComputerUtilAbility.getSpellAbilities(cards, player), player);
        } catch (Exception e) {
            return aiPick;
        }
        Map<SpellAbility, AiPlayDecision> declined = new LinkedHashMap<>();
        for (SpellAbility sa : all) {
            if (options.size() >= MAX_OPTIONS) break;
            if (seen.containsKey(sa) || sa.getHostCard() == null || sa.isManaAbility()) continue;
            AiPlayDecision d;
            try {
                if (sa.isLandAbility()) {
                    sa.setActivatingPlayer(player);
                    if (!sa.canPlay()) continue;
                    d = AiPlayDecision.WillPlay;
                } else {
                    d = evaluate(sa);
                }
            } catch (Exception e) {
                continue;
            }
            if (d != AiPlayDecision.WillPlay) {
                declined.put(sa, d);
                continue;
            }
            seen.put(sa, true);
            String id = "o" + options.size();
            options.put(id, Collections.singletonList(sa));
            source.put(id, sa.isLandAbility() ? "land" : "ai-approved");
        }
        // Legal plays Forge declined: target them in mandatory mode and let the pilot decide.
        for (Map.Entry<SpellAbility, AiPlayDecision> e : declined.entrySet()) {
            if (options.size() >= MAX_OPTIONS) break;
            SpellAbility sa = e.getKey();
            try {
                sa.setActivatingPlayer(player);
                if (!sa.canPlay() || !ComputerUtilCost.canPayCost(sa, player, false)) continue;
                if (sa.usesTargeting() || sa.getApi() != null) {
                    boolean targeted = getAi().doTrigger(sa, true);
                    if (sa.usesTargeting() && (!targeted || !sa.isTargetNumberValid())) continue;
                }
            } catch (Exception ex) {
                continue;
            }
            seen.put(sa, true);
            String id = "o" + options.size();
            options.put(id, Collections.singletonList(sa));
            source.put(id, "forge-declined:" + e.getValue());
        }
        if (options.isEmpty()) {
            return aiPick;
        }

        // ---- ask the pilot
        JsonObject req = new JsonObject();
        req.addProperty("game", gameTag);
        req.addProperty("forge_default", forgeDefault);
        req.add("state", StateView.describe(game, player));
        JsonArray opts = new JsonArray();
        for (Map.Entry<String, List<SpellAbility>> e : options.entrySet()) {
            SpellAbility sa = e.getValue().get(0);
            JsonObject o = new JsonObject();
            o.addProperty("id", e.getKey());
            o.addProperty("source", source.get(e.getKey()));
            o.addProperty("card", sa.getHostCard().getName());
            o.addProperty("zone", sa.getHostCard().getZone() == null ? "?" : sa.getHostCard().getZone().getZoneType().name());
            o.addProperty("kind", sa.isLandAbility() ? "land" : sa.isSpell() ? "cast" : "activate");
            o.addProperty("text", StateView.clip(sa.toString(), 240));
            JsonArray tg = new JsonArray();
            try {
                if (sa.usesTargeting() && sa.getTargets() != null) {
                    for (GameObject t : sa.getTargets()) tg.add(StateView.describeTarget(t, player));
                }
            } catch (Exception ignored) { }
            o.add("targets", tg);
            opts.add(o);
        }
        req.add("options", opts);

        String choice = sidecar.decide(req, forgeDefault);
        if ("pass".equals(choice)) {
            return null;
        }
        List<SpellAbility> picked = options.get(choice);
        return picked != null ? picked : aiPick;
    }

    static int manaEstimate(Player p) {
        try {
            return ComputerUtilMana.getAvailableManaEstimate(p);
        } catch (Exception e) {
            return -1;
        }
    }

    static List<Card> zone(Player p, ZoneType z) {
        return new ArrayList<>(p.getCardsIn(z));
    }
}
