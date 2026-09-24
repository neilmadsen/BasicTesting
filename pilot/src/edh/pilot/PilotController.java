package edh.pilot;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.apache.commons.lang3.tuple.ImmutablePair;

import forge.LobbyPlayer;
import forge.ai.AiCardMemory;
import forge.card.mana.ManaCost;
import forge.card.mana.ManaCostShard;
import forge.game.cost.Cost;
import forge.game.cost.CostPart;
import forge.game.cost.CostPartMana;
import forge.ai.AiController;
import forge.ai.AiPlayDecision;
import forge.ai.ComputerUtil;
import forge.ai.ComputerUtilAbility;
import forge.ai.ComputerUtilCost;
import forge.ai.ComputerUtilMana;
import forge.ai.PlayerControllerAi;
import forge.game.Game;
import forge.game.GameEntity;
import forge.game.GameObject;
import forge.game.card.Card;
import forge.game.card.CardCollection;
import forge.game.card.CardCollectionView;
import forge.game.combat.Combat;
import forge.game.combat.CombatUtil;
import forge.game.phase.PhaseHandler;
import forge.game.phase.PhaseType;
import forge.game.player.DelayedReveal;
import forge.game.player.Player;
import forge.game.player.PlayerActionConfirmMode;
import forge.game.spellability.SpellAbility;
import forge.game.spellability.SpellAbilityStackInstance;
import forge.game.trigger.WrappedAbility;
import forge.game.zone.ZoneType;
import forge.util.collect.FCollectionView;

/**
 * Forge's AI with most decisions routed through an external pilot (Jev, guided by
 * an LLM strategist). Each hook first computes Forge's own answer, then asks the
 * pilot to confirm or change it, validates the result with Forge's rules checks,
 * and falls back to Forge's answer whenever anything is off.
 *
 * Hooks: priority actions at any speed (with speculative target questions),
 * attacks, blocks, mulligans, "may" confirmations and optional triggers,
 * single-entity effect choices, library/graveyard searches (tutors, fetches),
 * discards, sacrifices (effects and costs), scry/surveil, trigger targets.
 */
public class PilotController extends CountingController {
    private static final int MAX_OPTIONS = 40;
    private static final int MAX_TARGETS = 40;
    private static final long SCAN_BUDGET_MS = 1500;
    private static final int MAX_SEARCH = 120;  // Jev takes up to 255 options per Choice
    private static Method canPlayAndPayFor;
    private static Method prepareSingleSa;

    private final Sidecar sidecar;
    private final String gameTag;

    public PilotController(Game game, Player p, LobbyPlayer lp, Sidecar sidecar, String gameTag) {
        super(game, p, lp);
        this.sidecar = sidecar;
        this.gameTag = gameTag;
        if (sidecar != null) {
            try {  // swap in a brain that routes our sacrifice costs to the pilot (see PilotAi)
                java.lang.reflect.Field brains = PlayerControllerAi.class.getDeclaredField("brains");
                brains.setAccessible(true);
                brains.set(this, new PilotAi(p, game, this));
            } catch (Exception e) {
                hookFailed("sacrifice-cost setup", new RuntimeException(e));
            }
        }
    }

    /** True while Forge plays and pays for an ability we chose, as opposed to the AI merely evaluating one. */
    private boolean paying = false;
    /** Activations the pilot cancelled at payment this turn; not offered again until next turn. */
    private final Set<String> cancelled = new HashSet<>();
    private int cancelledTurn = -1;

    private static String cancelKey(SpellAbility sa) {
        return sa.getHostCard().getId() + "|" + sa.getDescription();
    }

    private boolean cancelledThisTurn(SpellAbility sa) {
        if (cancelled.isEmpty()) return false;
        if (cancelledTurn != getGame().getPhaseHandler().getTurn()) {
            cancelled.clear();
            return false;
        }
        try {
            return cancelled.contains(cancelKey(sa));
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    public boolean playChosenSpellAbility(SpellAbility sa) {
        boolean was = paying;
        paying = true;
        try {
            return super.playChosenSpellAbility(sa);
        } finally {
            paying = was;
        }
    }

    /** Called by PilotAi for discard costs (Survival of the Fittest and the like) that we are actually paying. */
    CardCollection pickDiscardCost(int num, String[] types, SpellAbility ability, CardCollectionView exclude,
                                   CardCollection forgePick) {
        if (sidecar == null || !paying || forgePick == null || forgePick.size() != 1 || num != 1 || ability == null) return forgePick;
        try {
            CardCollection valid = forge.game.card.CardLists.getValidCards(player.getCardsIn(ZoneType.Hand), types, player,
                    ability.getHostCard(), ability);
            if (exclude != null) valid.removeAll(exclude);
            if (valid.size() < 2 || !valid.contains(forgePick.get(0))) return forgePick;
            String what = ability.getHostCard().getName() + " (" + StateView.clip(ability.toString(), 160) + ")";
            Card chosen = pickCard("discard-cost", "Paying a cost for " + what + ": which card do we discard?",
                    valid, forgePick.get(0), false);
            return chosen == null || chosen == forgePick.get(0) ? forgePick : new CardCollection(chosen);
        } catch (RuntimeException e) {
            hookFailed("discard-cost", e);
            return forgePick;
        }
    }

    /** Called by PilotAi for every sacrifice cost; the pilot re-picks single sacrifices we are actually paying. */
    CardCollectionView pickSacrificeCost(String type, SpellAbility ability, int amount, CardCollectionView exclude,
                                         CardCollectionView forgePick) {
        if (sidecar == null || !paying || forgePick == null || forgePick.size() != 1 || amount != 1 || ability == null) return forgePick;
        try {
            CardCollection valid = forge.game.card.CardLists.getValidCards(player.getCardsIn(ZoneType.Battlefield),
                    type.split(";"), player, ability.getHostCard(), ability);
            if (exclude != null) valid.removeAll(exclude);
            if (valid.size() < 2 || !valid.contains(forgePick.get(0))) return forgePick;
            String what = ability.getHostCard().getName() + " (" + StateView.clip(ability.toString(), 160) + ")";
            // Cancelling is offered because the activation itself is often the mistake: Jev activated Claws of Gix
            // ("sacrifice a permanent: gain 1 life") turn after turn and fed it lands. Forge's AI decides every cost
            // part before paying any, so returning null here aborts the activation with nothing spent.
            Card chosen = pickCard("sacrifice-cost", "Paying a cost for " + what + ": which permanent do we sacrifice?",
                    valid, forgePick.get(0), "cancel: don't activate " + ability.getHostCard().getName()
                            + " after all (nothing here is worth giving up for it)");
            if (chosen == null) {  // and don't offer it again this turn, or Jev re-picks it and cancels again
                cancelled.add(cancelKey(ability));
                cancelledTurn = getGame().getPhaseHandler().getTurn();
                return null;
            }
            return chosen == forgePick.get(0) ? forgePick : new CardCollection(chosen);
        } catch (RuntimeException e) {
            hookFailed("sacrifice-cost", e);
            return forgePick;
        }
    }

    // ------------------------------------------------------------------ helpers

    private Ask ask(String kind) {
        return new Ask(kind, gameTag, StateView.describe(getGame(), player));
    }

    private static final Map<String, Integer> HOOK_ERRORS = new java.util.concurrent.ConcurrentHashMap<>();

    /** A pilot hook failed: log the first few per hook, and the caller falls back to Forge's answer. */
    private static void hookFailed(String hook, Throwable e) {
        int n = HOOK_ERRORS.merge(hook, 1, Integer::sum);
        if (n <= 3) {
            StackTraceElement at = e.getStackTrace().length > 0 ? e.getStackTrace()[0] : null;
            System.err.println("[pilot] hook error in " + hook + " (#" + n + "), keeping Forge's choice: " + e
                    + (at == null ? "" : " at " + at));
        }
    }

    private String describe(Object o) {
        return StateView.describeTarget(o, player);
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

    /** Legal single-target candidates for sa (null if not a single-target ability or nothing to choose). */
    private List<GameEntity> singleTargetCandidates(SpellAbility sa) {
        try {
            // one target, or "up to one" (The Coming of Galactus chapter I was never asked before)
            if (!sa.usesTargeting() || sa.getMinTargets() > 1 || sa.getMaxTargets() != 1) return null;
            List<GameEntity> all = new ArrayList<>(sa.getTargetRestrictions().getAllCandidates(sa));
            all.removeIf(e -> !sa.canTarget(e));
            if (all.size() < 2) return null;
            // opponents' things first, so the cap never hides them
            all.sort((x, y) -> Boolean.compare(owner(x) == player, owner(y) == player));
            return all.size() > MAX_TARGETS ? new ArrayList<>(all.subList(0, MAX_TARGETS)) : all;
        } catch (Exception e) {
            return null;
        }
    }

    private Player owner(GameEntity e) {
        if (e instanceof Card c) return c.getController();
        if (e instanceof Player p) return p;
        return null;
    }

    /** Add a target question keyed qid; returns candidates in option order (t0..tn), or null. */
    /**
     * What an ability does, for a question. A trigger's inner ability often prints as "" (Soul-Guide Lantern,
     * Grist's -2), which left Jev choosing a target with no idea of the effect; fall back to the trigger's own
     * description, then the card's rules text.
     */
    static String abilityText(SpellAbility outer, SpellAbility inner, int chars) {
        for (SpellAbility sa : new SpellAbility[] {inner, outer}) {
            if (sa == null) continue;
            try {
                String t = sa.toString();
                if (t == null || t.isBlank()) t = sa.getDescription();
                if ((t == null || t.isBlank()) && sa.getTrigger() != null) t = sa.getTrigger().toString();
                if (t != null && !t.isBlank()) return StateView.clip(t, chars);
            } catch (Exception ignored) { }
        }
        try {
            Card h = (inner != null ? inner : outer).getHostCard();
            return StateView.clip(h.getOracleText().replace("\\n", " "), chars);
        } catch (Exception e) {
            return "";
        }
    }

    private List<GameEntity> addTargetQuestion(Ask a, String qid, String prompt, SpellAbility sa) {
        List<GameEntity> cands = singleTargetCandidates(sa);
        if (cands == null) return null;
        GameObject current = null;
        try {
            if (sa.getTargets() != null && !sa.getTargets().isEmpty()) current = sa.getTargets().get(0);
        } catch (Exception ignored) { }
        boolean upTo = sa.getMinTargets() == 0;
        String def = upTo && current == null ? "none" : "t0";
        for (int i = 0; i < cands.size(); i++) {
            if (cands.get(i) == current) def = "t" + i;
        }
        a.question(qid, prompt, def);
        for (int i = 0; i < cands.size(); i++) a.option(qid, "t" + i, describe(cands.get(i)));
        if (upTo) a.option(qid, "none", "no target (it is \"up to one\")");
        return cands;
    }

    private void applyTarget(SpellAbility sa, List<GameEntity> cands, String answer) {
        if (cands != null && "none".equals(answer) && sa.getMinTargets() == 0) {
            sa.resetTargets();
            return;
        }
        if (cands == null || answer == null || !answer.startsWith("t")) return;
        try {
            GameEntity t = cands.get(Integer.parseInt(answer.substring(1)));
            GameObject current = sa.getTargets().isEmpty() ? null : sa.getTargets().get(0);
            if (t != current && sa.canTarget(t)) {
                sa.resetTargets();
                sa.getTargets().add(t);
            }
        } catch (Exception ignored) { }
    }

    /** A card in a pick question: board cards as usual; cards in hand with their type, mana value and role. */
    private String pickLabel(Card c) {
        if (!c.isInZone(ZoneType.Hand)) return describe(c);
        StringBuilder b = new StringBuilder(c.getName());
        try {
            b.append(" [in hand; ").append(c.getType().toString());
            if (!c.isLand()) b.append(", mana value ").append(c.getCMC());
            if (c.isLand() || !c.getManaAbilities().isEmpty()) b.append("; makes mana");
            b.append(c.isPermanent() ? "; a permanent card" : "; an instant or sorcery").append(']');
        } catch (Exception ignored) { }
        return b.toString();
    }

    /** Generic "pick one card" used by sacrifices, discards and costs. */
    Card pickCard(String kind, String prompt, CardCollectionView cards, Card forgeChoice, boolean optional) {
        return pickCard(kind, prompt, cards, forgeChoice, optional ? "choose nothing" : null);
    }

    /** noneLabel: the text of a "none" option, or null for a mandatory pick. */
    Card pickCard(String kind, String prompt, CardCollectionView cards, Card forgeChoice, String noneLabel) {
        boolean optional = noneLabel != null;
        if (sidecar == null || cards.size() < 2) return forgeChoice;
        List<Card> list = new ArrayList<>(cards);
        if (list.size() > MAX_TARGETS) list = new ArrayList<>(list.subList(0, MAX_TARGETS));
        if (forgeChoice != null && !list.contains(forgeChoice)) list.set(list.size() - 1, forgeChoice);
        Ask a = ask(kind);
        String def = forgeChoice == null ? "none" : "c" + list.indexOf(forgeChoice);
        a.question("pick", prompt, def);
        for (int i = 0; i < list.size(); i++) a.option("pick", "c" + i, pickLabel(list.get(i)));
        if (optional) a.option("pick", "none", noneLabel);
        String ans = a.send(sidecar).get("pick");
        if (ans == null) return forgeChoice;
        if (ans.equals("none")) return optional ? null : forgeChoice;
        try {
            return list.get(Integer.parseInt(ans.substring(1)));
        } catch (Exception e) {
            return forgeChoice;
        }
    }

    /**
     * Mana our untapped sources can make right now. Forge's own estimate counts each colour of a
     * "Combo B G U" land as separate mana (a Triome read as 4), which misled the strategist's arithmetic.
     */
    static int manaEstimate(Player p) {
        int total = 0;
        try {
            for (Card c : p.getCardsIn(ZoneType.Battlefield)) {
                int best = 0;
                for (SpellAbility ma : c.getManaAbilities()) {
                    try {
                        ma.setActivatingPlayer(p);
                        if (!ma.canPlay()) continue;
                        String[] produced = ma.getParamOrDefault("Produced", "").trim().split(" ");
                        String first = produced.length > 0 ? produced[0] : "";
                        int kinds = first.equals("Combo") || first.equals("Any") || first.startsWith("Chosen")
                                || produced.length == 0 ? 1 : produced.length;
                        int amount;
                        try {
                            amount = Integer.parseInt(ma.getParamOrDefault("Amount", "1"));
                        } catch (NumberFormatException nfe) {
                            amount = 1;
                        }
                        int cost = ma.getPayCosts().getCostMana() != null ? ma.getPayCosts().getCostMana().convertAmount() : 0;
                        best = Math.max(best, kinds * amount - cost);
                    } catch (Exception ignored) { }
                }
                total += best;
            }
        } catch (Exception e) {
            return -1;
        }
        return total;
    }

    // ------------------------------------------------------------------ held mana and X

    /** Mana sources held open until our next turn for one instant-speed play (heldFor), via Forge's own
     *  reservation set, which its payment code refuses to spend. */
    private final Set<Card> heldSources = new HashSet<>();
    private Card heldFor = null;
    private int holdTurn = -1;   // turn the hold was decided on (-1: not decided this turn)

    /** Forge clears its next-spell reservation every time its AI evaluates priority; put ours back. */
    private void applyHold() {
        for (Card c : heldSources) {
            if (c.isInZone(ZoneType.Battlefield) && !c.isTapped()) {
                AiCardMemory.rememberCard(player, c, AiCardMemory.MemorySet.HELD_MANA_SOURCES_FOR_NEXT_SPELL);
            }
        }
    }

    private void releaseHold() {
        AiCardMemory.clearMemorySet(player, AiCardMemory.MemorySet.HELD_MANA_SOURCES_FOR_NEXT_SPELL);
        heldSources.clear();
        heldFor = null;
    }

    /** Can we pay for sa without the held sources? (The play the mana is held for always can.) */
    private boolean affordableUnderHold(SpellAbility sa) {
        if (heldSources.isEmpty() || sa == null || sa.isLandAbility() || sa.getHostCard() == heldFor) return true;
        try {
            return ComputerUtilMana.canPayManaCost(sa, player, 0, false);
        } catch (Exception e) {
            return true;
        }
    }

    private static String colorsProduced(Card c, Player p) {
        StringBuilder out = new StringBuilder();
        for (SpellAbility ma : c.getManaAbilities()) {
            try {
                ma.setActivatingPlayer(p);
                if (!ma.canPlay() || ma.getManaPart() == null) continue;
                if (ma.getManaPart().isAnyMana()) return "WUBRG";
                for (char ch : ma.getManaPart().getOrigProduced().toCharArray()) {
                    if ("WUBRGC".indexOf(ch) >= 0 && out.indexOf(String.valueOf(ch)) < 0) out.append(ch);
                }
            } catch (Exception ignored) { }
        }
        return out.toString();
    }

    private static int amountProduced(Card c) {
        int best = 1;
        for (SpellAbility ma : c.getManaAbilities()) {
            try {
                best = Math.max(best, Integer.parseInt(ma.getParamOrDefault("Amount", "1")));
            } catch (NumberFormatException ignored) { }
        }
        return best;
    }

    /** Untapped sources that could pay mc (colored shards first, fewest-colour sources first), or null. */
    private List<Card> coverCost(ManaCost mc, List<Card> sources) {
        List<Card> pool = new ArrayList<>(sources);
        List<Card> used = new ArrayList<>();
        for (ManaCostShard sh : mc) {
            if (sh.isGeneric() || sh == ManaCostShard.X) continue;
            String need = (sh.isWhite() ? "W" : "") + (sh.isBlue() ? "U" : "") + (sh.isBlack() ? "B" : "")
                    + (sh.isRed() ? "R" : "") + (sh.isGreen() ? "G" : "") + (sh.isColorless() ? "C" : "");
            Card best = null;
            for (Card c : pool) {
                String cols = colorsProduced(c, player);
                boolean fits = false;
                for (char ch : need.toCharArray()) fits |= cols.indexOf(ch) >= 0;
                if (fits && (best == null || cols.length() < colorsProduced(best, player).length())) best = c;
            }
            if (best == null) return null;
            pool.remove(best);
            used.add(best);
        }
        int generic = mc.getGenericCost();
        pool.sort((x, y) -> Integer.compare(colorsProduced(x, player).length(), colorsProduced(y, player).length()));
        for (Card c : pool) {
            if (generic <= 0) break;
            if (colorsProduced(c, player).isEmpty()) continue;
            used.add(c);
            generic -= amountProduced(c);
        }
        return generic > 0 ? null : used;
    }

    private static final class Hold {
        final String text;
        final Card host;
        final List<Card> sources;
        Hold(String text, Card host, List<Card> sources) {
            this.text = text;
            this.host = host;
            this.sources = sources;
        }
    }

    /** Instant-speed plays we could keep mana open for: instants and flash cards in hand, and activated
     *  abilities of our permanents that cost mana and aren't sorcery-speed. */
    private List<Hold> holdCandidates() {
        List<Card> sources = new ArrayList<>();
        for (Card c : player.getCardsIn(ZoneType.Battlefield)) {
            if (!c.isTapped() && !c.getManaAbilities().isEmpty() && !colorsProduced(c, player).isEmpty()) sources.add(c);
        }
        List<Hold> out = new ArrayList<>();
        Set<String> seenText = new HashSet<>();
        List<SpellAbility> sas = new ArrayList<>();
        for (Card c : player.getCardsIn(ZoneType.Hand)) {
            for (SpellAbility sa : c.getSpellAbilities()) {
                try {
                    sa.setActivatingPlayer(player);
                    if (sa.isSpell() && !c.isLand() && (c.isInstant() || sa.withFlash(c, player))) sas.add(sa);
                } catch (Exception ignored) { }
            }
        }
        for (Card c : player.getCardsIn(ZoneType.Battlefield)) {
            if (c.isLand()) continue;  // utility-land draws and the like aren't worth holding a turn for
            for (SpellAbility sa : c.getSpellAbilities()) {
                // interaction only: abilities that target something or counter a spell
                if (sa.isActivatedAbility() && !sa.isManaAbility() && !sa.hasParam("SorcerySpeed")
                        && (sa.usesTargeting() || sa.getApi() == forge.game.ability.ApiType.Counter)) {
                    sas.add(sa);
                }
            }
        }
        for (SpellAbility sa : sas) {
            if (out.size() >= 12) break;
            try {
                Cost cost = sa.getPayCosts();
                if (cost == null || !cost.hasManaCost() || cost.getTotalMana() == null) continue;
                ManaCost mc = cost.getTotalMana();
                List<Card> own = new ArrayList<>(sources);
                own.remove(sa.getHostCard());  // an ability that taps its own permanent can't also use it for mana
                List<Card> plan = coverCost(mc, own);
                if (plan == null || plan.isEmpty()) continue;
                String what = sa.getHostCard().getName() + ": " + StateView.clip(sa.toString(), 140);
                if (!seenText.add(what)) continue;
                StringBuilder names = new StringBuilder();
                for (Card c : plan) names.append(names.length() > 0 ? ", " : "").append(c.getName());
                out.add(new Hold("keep " + mc.getShortString() + " open (" + names + ") for " + what, sa.getHostCard(), plan));
            } catch (Exception ignored) { }
        }
        return out;
    }

    /** {min, max, xShards} for a play whose cost has X (mana X or e.g. "pay X life"), else null. */
    private int[] xRange(SpellAbility sa) {
        try {
            Cost c = sa.getPayCosts();
            if (c == null) return null;
            ManaCost mc = c.getTotalMana();
            int xs = mc == null ? 0 : mc.countX();
            boolean nonMana = false;
            for (CostPart part : c.getCostParts()) {
                if (!(part instanceof CostPartMana) && "X".equals(part.getAmount())) nonMana = true;
            }
            if (xs == 0 && !nonMana) return null;
            int max;
            if (xs > 0) {
                max = (manaEstimate(player) - (mc == null ? 0 : mc.getCMC())) / xs;
            } else {
                Integer m = c.getMaxForNonManaX(sa, player, false);
                max = m == null ? 0 : m;
            }
            max = Math.min(max, 20);
            return max < 1 ? null : new int[]{0, max, xs};
        } catch (Exception e) {
            return null;
        }
    }


    private static final java.util.regex.Pattern MAY_PLAY_BY = java.util.regex.Pattern.compile(" by [^\\[\\]]*?\\(\\d+\\)(?: \\(\\w+\\))?");

    /** The text Jev sees for one action option. */
    private String actionLabel(SpellAbility sa, String kind, String src, PhaseType phase, boolean ourTurn) {
        Card host = sa.getHostCard();
        String zone = host.getZone() == null ? "?" : host.getZone().getZoneType().name();
        String body = sa.toString();
        String permission = null;
        try {
            forge.game.staticability.StaticAbility may = sa.getMayPlay();
            if (may != null && may.hasParam("MayPlayText") && may.getHostCard() != host) {
                body = MAY_PLAY_BY.matcher(body).replaceAll("");
                permission = may.getHostCard().getName() + "'s " + may.getParam("MayPlayText").toLowerCase() + " permission";
            }
        } catch (Exception ignored) { }
        StringBuilder text = new StringBuilder(kind).append(' ').append(host.getName())
                .append(" (from ").append(zone).append("): ").append(StateView.clip(body, 220));
        if (permission != null) text.append(" [uses ").append(permission).append(" for this turn]");
        try {
            if (sa.usesTargeting() && !sa.getTargets().isEmpty()) {
                text.append(" → target: ").append(describe(sa.getTargets().get(0)));
            }
        } catch (Exception ignored) { }
        try {
            if (!sa.isLandAbility() && sa.getPayCosts() != null && sa.getPayCosts().hasNoManaCost()) {
                text.append(" [costs no mana]");
            }
        } catch (Exception ignored) { }
        if (src.startsWith("forge-declined")) {
            String why = src.substring(15);
            boolean waits = false;
            try {  // Forge's AI casts most permanents after combat; in main 1 that shows up as CantPlayAi
                waits = "CantPlayAi".equals(why) && sa.isSpell() && host.isPermanent() && ourTurn
                        && phase == PhaseType.MAIN1 && !ComputerUtil.castPermanentInMain1(player, sa);
            } catch (Exception ignored) { }
            text.append(waits ? " [Forge's AI would wait and cast this after combat]"
                    : " [Forge's AI would not do this now: " + why + "]");
        }
        return text.toString();
    }

    // ------------------------------------------------------------------ priority actions

    @Override
    public List<SpellAbility> chooseSpellAbilityToPlay() {
        List<SpellAbility> aiPick = super.chooseSpellAbilityToPlay();
        if (sidecar == null) return aiPick;
        try {
            Game game = getGame();
            PhaseHandler ph = game.getPhaseHandler();
            PhaseType phase = ph.getPhase();
            boolean ourTurn = ph.getPlayerTurn() == player;
            boolean main = ourTurn && (phase == PhaseType.MAIN1 || phase == PhaseType.MAIN2) && game.getStack().isEmpty();
            SpellAbilityStackInstance top = game.getStack().isEmpty() ? null : game.getStack().peek();
            boolean oppOnStack = top != null && top.getActivatingPlayer() != player;
            boolean endOfOppTurn = !ourTurn && phase == PhaseType.END_OF_TURN && game.getStack().isEmpty();
            int turn = ph.getTurn();
            if (ourTurn && holdTurn >= 0 && holdTurn != turn) {  // a hold lasts until our next turn
                releaseHold();
                holdTurn = -1;
            }
            applyHold();
            if (aiPick != null && !aiPick.isEmpty() && aiPick.get(0) != null && !affordableUnderHold(aiPick.get(0))) {
                aiPick = null;  // Forge's play would spend the mana we're holding
            }
            if (aiPick != null && !aiPick.isEmpty() && aiPick.get(0) != null && cancelledThisTurn(aiPick.get(0))) {
                aiPick = null;  // an activation the pilot already cancelled at payment this turn
            }
            boolean forgeWantsToAct = aiPick != null && !aiPick.isEmpty() && aiPick.get(0) != null;
            if (!main && !oppOnStack && !endOfOppTurn && !forgeWantsToAct) return aiPick;

            long t0 = System.currentTimeMillis();
            Map<String, List<SpellAbility>> options = new LinkedHashMap<>();
            Map<String, String> source = new LinkedHashMap<>();
            IdentityHashMap<SpellAbility, Boolean> seen = new IdentityHashMap<>();
            String forgeDefault = "pass";
            if (forgeWantsToAct) {
                options.put("o0", aiPick);
                source.put("o0", "forge");
                forgeDefault = "o0";
                for (SpellAbility sa : aiPick) seen.put(sa, true);
            }
            List<SpellAbility> all;
            try {
                all = ComputerUtilAbility.getOriginalAndAltCostAbilities(
                        ComputerUtilAbility.getSpellAbilities(ComputerUtilAbility.getAvailableCards(game, player), player), player);
            } catch (Exception e) {
                return aiPick;
            }
            Map<SpellAbility, AiPlayDecision> declined = new LinkedHashMap<>();
            for (SpellAbility sa : all) {
                if (options.size() >= MAX_OPTIONS || System.currentTimeMillis() - t0 > SCAN_BUDGET_MS) break;
                if (seen.containsKey(sa) || sa.getHostCard() == null || sa.isManaAbility()) continue;
                if (!affordableUnderHold(sa) || cancelledThisTurn(sa)) continue;
                AiPlayDecision d;
                try {
                    sa.setActivatingPlayer(player);
                    if (sa.isLandAbility()) {
                        if (!main || !sa.canPlay()) continue;
                        d = AiPlayDecision.WillPlay;
                    } else {
                        if (!sa.canPlay()) continue;
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
            for (Map.Entry<SpellAbility, AiPlayDecision> e : declined.entrySet()) {
                if (options.size() >= MAX_OPTIONS || System.currentTimeMillis() - t0 > SCAN_BUDGET_MS) break;
                SpellAbility sa = e.getKey();
                try {
                    if (!ComputerUtilCost.canPayCost(sa, player, false) || !affordableUnderHold(sa)) continue;
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
            if (options.isEmpty()) return aiPick;

            // In our own upkeep or draw step with nothing on the stack, whatever Forge's AI wants to fire could wait for
            // the main phase, where sorceries are also on offer; spending the mana now broke the memo's main-phase plan
            // in several reviewed games (Capsule before Toxic Deluge, Heroic Intervention with nothing to protect).
            boolean ownBeginning = ourTurn && !main && top == null && (phase == PhaseType.UPKEEP || phase == PhaseType.DRAW);
            if (ownBeginning && "o0".equals(forgeDefault)) forgeDefault = "pass";
            String window = main ? (phase == PhaseType.MAIN1 ? "our main phase 1 (before combat), stack empty"
                            : "our main phase 2 (after combat; no more combat this turn), stack empty")
                    : oppOnStack ? "responding to an opponent's spell or ability on the stack"
                    : endOfOppTurn ? "end of an opponent's turn"
                    : ownBeginning ? "our " + (phase == PhaseType.UPKEEP ? "upkeep" : "draw step")
                            + ", stack empty: mana spent now is not available in our main phase, where sorceries are also possible"
                    : "instant-speed window (" + phase + ")";
            Ask a = ask("action").context("window", window);
            if (top != null) a.context("stack_top", StateView.clip(top.getStackDescription(), 200));
            a.question("action", "Which action do we take now?", forgeDefault);
            Map<String, List<GameEntity>> targetCands = new LinkedHashMap<>();
            Map<String, int[]> xRanges = new LinkedHashMap<>();
            Set<String> labels = new HashSet<>();
            for (Map.Entry<String, List<SpellAbility>> e : options.entrySet()) {
                SpellAbility sa = e.getValue().get(0);
                String kind = sa.isLandAbility() ? "play land" : sa.isSpell() ? "cast" : "activate";
                String text = actionLabel(sa, kind, source.get(e.getKey()), phase, ourTurn);
                // Forge lists some plays several times (Muldrotha's permissions get re-applied to copies). Offering
                // identical options splits Jev's probability between them and makes overruling Forge harder.
                if (!labels.add(text)) continue;
                a.option("action", e.getKey(), text);
                // speculative fan-out: the target for each targeted option, answered in the same call
                List<GameEntity> cands = addTargetQuestion(a, "tgt_" + e.getKey(),
                        "If we " + kind + " " + sa.getHostCard().getName() + " (" + StateView.clip(sa.toString(), 200)
                                + "), what should it target?", sa);
                if (cands != null) targetCands.put(e.getKey(), cands);
                int[] xr = xRange(sa);
                if (xr != null) {  // speculative: X for this play, if it's the one we take
                    xRanges.put(e.getKey(), xr);
                    Integer cur = sa.getXManaCostPaid();
                    String q = "x_" + e.getKey();
                    String costText = sa.getPayCosts() == null ? "" : StateView.clip(sa.getPayCosts().toString(), 120);
                    a.question(q, "If we " + kind + " " + sa.getHostCard().getName() + " (" + StateView.clip(sa.toString(), 160)
                            + "; cost: " + costText + "), what should X be?", "auto");
                    a.option(q, "auto", "let Forge choose X" + (cur != null ? " (it has " + cur + ")" : ""));
                    for (int n = xr[0]; n <= xr[1]; n++) {
                        a.option(q, "x" + n, "X = " + n + (xr[2] > 0 ? " (" + n * xr[2] + " more mana)" : ""));
                    }
                }
            }
            List<Hold> holds = (ourTurn && main && holdTurn != turn) ? holdCandidates() : Collections.emptyList();
            if (!holds.isEmpty()) {
                a.question("hold", "Keep mana open until our next turn for an instant-speed play? Held mana is not spent "
                        + "on anything else, so it costs development now.", "none");
                a.option("hold", "none", "hold nothing: use our mana freely");
                for (int i = 0; i < holds.size(); i++) a.option("hold", "h" + i, holds.get(i).text);
            }
            String skip = forgeWantsToAct ? " (this skips o0, the play Forge's AI would make now)" : "";
            a.option("action", "pass", (main
                    ? "Take no further action this phase: hold remaining mana and cards"
                    : "Do nothing now; let it resolve / let the turn pass") + skip);
            Map<String, String> ans = a.send(sidecar);
            String choice = ans.getOrDefault("action", forgeDefault);
            List<SpellAbility> picked = "pass".equals(choice) ? null : options.get(choice);
            String h = ans.get("hold");
            if (h != null && h.startsWith("h")) {
                Hold ho = holds.get(Integer.parseInt(h.substring(1)));
                heldSources.addAll(ho.sources);
                heldFor = ho.host;
                holdTurn = turn;
                applyHold();
                if (picked != null && !affordableUnderHold(picked.get(0))) {  // the play needs that mana: play now, hold later
                    releaseHold();
                    holdTurn = -1;
                }
            } else if ("none".equals(h) && phase == PhaseType.MAIN2) {
                holdTurn = turn;  // last main phase: decided to hold nothing this turn
            }
            if ("pass".equals(choice)) return null;
            if (picked == null) return aiPick;
            SpellAbility sa = picked.get(0);
            if (sa.getHostCard() == heldFor) releaseHold();  // the play we held mana for: spend it now
            applyTarget(sa, targetCands.get(choice), ans.get("tgt_" + choice));
            String xa = ans.get("x_" + choice);
            int[] xr = xRanges.get(choice);
            if (xa != null && xa.startsWith("x") && xr != null) {
                Integer before = sa.getXManaCostPaid();
                int n = Integer.parseInt(xa.substring(1));
                sa.setXManaCostPaid(n);
                boolean ok = xr[2] > 0 ? ComputerUtilMana.canPayManaCost(sa, player, 0, false) : n <= xr[1];
                if (!ok) sa.setXManaCostPaid(before);
            }
            return picked;
        } catch (RuntimeException e) {
            hookFailed("action", e);
            return aiPick;
        }
    }

    // ------------------------------------------------------------------ combat

    @Override
    public void declareAttackers(Player attacker, Combat combat) {
        super.declareAttackers(attacker, combat);
        if (sidecar == null || attacker != player) return;
        try {
            List<Card> potential = new ArrayList<>();
            for (Card c : player.getCreaturesInPlay()) {
                try {
                    if (CombatUtil.canAttack(c)) potential.add(c);
                } catch (Exception ignored) { }
            }
            if (potential.isEmpty()) return;
            if (potential.size() > 30) potential = new ArrayList<>(potential.subList(0, 30));
            List<GameEntity> defenders = new ArrayList<>(combat.getDefenders());
            Map<Card, GameEntity> forgePlan = new LinkedHashMap<>();
            for (Card c : combat.getAttackers()) forgePlan.put(c, combat.getDefenderByAttacker(c));

            Ask a = ask("attack");
            for (int i = 0; i < potential.size(); i++) {
                Card c = potential.get(i);
                String q = "a" + i;
                GameEntity planned = forgePlan.get(c);
                String def = planned == null ? "hold" : "d" + defenders.indexOf(planned);
                a.question(q, "Attack with " + describe(c) + " " + c.getNetPower() + "/" + c.getNetToughness() + "?", def);
                a.option(q, "hold", "don't attack with it");
                for (int d = 0; d < defenders.size(); d++) {
                    try {
                        if (CombatUtil.canAttack(c, defenders.get(d))) {
                            a.option(q, "d" + d, "attack " + describeDefender(defenders.get(d)) + blockOutlook(c, defenders.get(d)));
                        }
                    } catch (Exception ignored) { }
                }
            }
            a.prune();
            Map<String, String> ans = a.send(sidecar);
            if (ans.isEmpty()) return;
            combat.clearAttackers();
            try {
                for (int i = 0; i < potential.size(); i++) {
                    Card c = potential.get(i);
                    String choice = ans.get("a" + i);
                    if (choice == null) {  // not asked (single option): keep Forge's plan for it
                        if (forgePlan.containsKey(c)) combat.addAttacker(c, forgePlan.get(c));
                    } else if (choice.startsWith("d")) {
                        combat.addAttacker(c, defenders.get(Integer.parseInt(choice.substring(1))));
                    }
                }
                for (Map.Entry<Card, GameEntity> e : forgePlan.entrySet()) {  // attackers beyond the cap
                    if (!potential.contains(e.getKey())) combat.addAttacker(e.getKey(), e.getValue());
                }
                if (!CombatUtil.validateAttackers(combat)) throw new IllegalStateException("invalid attack");
            } catch (Exception e) {
                combat.clearAttackers();
                for (Map.Entry<Card, GameEntity> p : forgePlan.entrySet()) combat.addAttacker(p.getKey(), p.getValue());
            }
        } catch (RuntimeException e) {
            hookFailed("attack", e);
        }
    }

    /** What the defending player could do to this attacker, by Forge's own combat evaluation: how many of
     *  their untapped creatures can block it, and how many of those would kill it. The blind audit's
     *  recurring reason for preferring Forge's attacks was exactly this ("seven ground blockers"). */
    private String blockOutlook(Card attacker, GameEntity defender) {
        try {
            Player dp = defender instanceof Player p ? p : defender instanceof Card dc ? dc.getController() : null;
            if (dp == null) return "";
            int can = 0, kill = 0, trade = 0;
            for (Card b : dp.getCreaturesInPlay()) {
                if (b.isTapped() || !CombatUtil.canBlock(attacker, b)) continue;
                can++;
                boolean kills = forge.ai.ComputerUtilCombat.canDestroyAttacker(dp, attacker, b, null, false);
                boolean dies = forge.ai.ComputerUtilCombat.canDestroyBlocker(dp, b, attacker, null, false);
                if (kills && !dies) kill++;
                else if (kills) trade++;
            }
            if (can == 0) return " [no untapped creature of theirs can block it]";
            return " [" + can + " of their untapped creatures can block it; " + kill + " would kill it and survive, "
                    + trade + " would trade]";
        } catch (Exception e) {
            return "";
        }
    }

    /** Forge's evaluation of one block: does our blocker kill the attacker, and does it survive? */
    private String blockResult(Card attacker, Card blocker) {
        try {
            Player ap = attacker.getController();
            boolean killsIt = forge.ai.ComputerUtilCombat.canDestroyAttacker(player, attacker, blocker, null, false);
            boolean dies = forge.ai.ComputerUtilCombat.canDestroyBlocker(ap, blocker, attacker, null, false);
            return " [" + (killsIt ? "kills it" : "doesn't kill it") + ", " + (dies ? "ours dies" : "ours survives") + "]";
        } catch (Exception e) {
            return "";
        }
    }

    private String describeDefender(GameEntity d) {
        if (d instanceof Player p) return StateView.label(p) + " (" + p.getLife() + " life)";
        if (d instanceof Card c) {
            String extra = c.isPlaneswalker() ? " loyalty " + c.getCurrentLoyalty() : "";
            return describe(c) + extra;
        }
        return String.valueOf(d);
    }

    private static void restoreBlocks(Combat combat, Map<Card, List<Card>> blocks) {
        for (Map.Entry<Card, List<Card>> fb : blocks.entrySet()) {
            for (Card b : fb.getValue()) {
                if (!combat.getBlockers(fb.getKey()).contains(b)) combat.addBlocker(fb.getKey(), b);
            }
        }
    }

    @Override
    public void declareBlockers(Player defender, Combat combat) {
        super.declareBlockers(defender, combat);
        if (sidecar == null || defender != player) return;
        try {
            List<Card> attackers = new ArrayList<>();
            for (Card at : combat.getAttackers()) {
                GameEntity d = combat.getDefenderByAttacker(at);
                if (d == player || (d instanceof Card dc && dc.getController() == player)) attackers.add(at);
            }
            if (attackers.isEmpty()) return;
            if (attackers.size() > 20) attackers = new ArrayList<>(attackers.subList(0, 20));
            Map<Card, List<Card>> forgeBlocks = new LinkedHashMap<>();
            for (Card at : attackers) forgeBlocks.put(at, new ArrayList<>(combat.getBlockers(at)));
            // Candidates are computed with Forge's blocks lifted: a creature already assigned by Forge fails
            // canBlock, so Forge's own blocker used to be missing from the options (default "k-1").
            List<Card> blockers = new ArrayList<>();
            Map<Card, Set<Card>> legal = new HashMap<>();  // attacker -> creatures that could block it
            for (Card c : player.getCreaturesInPlay()) combat.undoBlockingAssignment(c);
            try {
                for (Card c : player.getCreaturesInPlay()) {
                    try {
                        if (CombatUtil.canBlock(c, combat)) blockers.add(c);
                    } catch (Exception ignored) { }
                }
                for (List<Card> fb : forgeBlocks.values()) {
                    for (Card b : fb) if (!blockers.contains(b)) blockers.add(b);
                }
                for (Card at : attackers) {
                    Set<Card> ok = new HashSet<>(forgeBlocks.get(at));
                    for (Card b : blockers) {
                        try {
                            if (CombatUtil.canBlock(at, b, combat)) ok.add(b);
                        } catch (Exception ignored) { }
                    }
                    legal.put(at, ok);
                }
            } finally {
                restoreBlocks(combat, forgeBlocks);
            }
            if (blockers.isEmpty()) return;

            int incoming = 0;
            for (Card at : attackers) {
                if (combat.getDefenderByAttacker(at) == player) incoming += Math.max(0, at.getNetCombatDamage());
            }
            Ask a = ask("block").context("incoming", "Unblocked, the attackers at us deal " + incoming
                    + " combat damage; our life is " + player.getLife() + ". Blocks are asked one attacker at a time.");
            for (int i = 0; i < attackers.size(); i++) {
                Card at = attackers.get(i);
                String q = "b" + i;
                List<Card> fb = forgeBlocks.get(at);
                String def = fb.isEmpty() ? "none" : "k" + blockers.indexOf(fb.get(0));
                GameEntity target = combat.getDefenderByAttacker(at);
                a.question(q, describe(at) + " " + at.getNetPower() + "/" + at.getNetToughness() + " attacks "
                        + (target == player ? "us" : describe(target)) + ". Block it with what?", def);
                a.option(q, "none", "no block (take the damage)");
                for (int j = 0; j < blockers.size(); j++) {
                    Card b = blockers.get(j);
                    if (legal.get(at).contains(b)) {
                        a.option(q, "k" + j, "block with " + b.getName() + " " + b.getNetPower() + "/" + b.getNetToughness()
                                + blockResult(at, b));
                    }
                }
            }
            a.prune();
            Map<String, String> ans = a.send(sidecar);
            if (ans.isEmpty()) return;
            try {
                for (Card b : blockers) combat.undoBlockingAssignment(b);
                Set<Card> used = new HashSet<>();
                for (int i = 0; i < attackers.size(); i++) {
                    Card at = attackers.get(i);
                    String choice = ans.get("b" + i);
                    List<Card> fb = forgeBlocks.get(at);
                    String def = fb.isEmpty() ? "none" : "k" + blockers.indexOf(fb.get(0));
                    if (choice == null || choice.equals(def)) {  // keep Forge's (possibly multi-) block
                        for (Card b : fb) {
                            if (used.add(b)) combat.addBlocker(at, b);
                        }
                    } else if (choice.startsWith("k")) {
                        Card b = blockers.get(Integer.parseInt(choice.substring(1)));
                        if (used.add(b)) combat.addBlocker(at, b);
                    }
                }
                if (CombatUtil.validateBlocks(combat, player) != null) throw new IllegalStateException("invalid blocks");
            } catch (Exception e) {
                for (Card b : blockers) combat.undoBlockingAssignment(b);
                restoreBlocks(combat, forgeBlocks);
            }
        } catch (RuntimeException e) {
            hookFailed("block", e);
        }
    }

    // ------------------------------------------------------------------ other choices

    @Override
    public boolean mulliganKeepHand(Player firstPlayer, int cardsToReturn) {
        boolean keep = super.mulliganKeepHand(firstPlayer, cardsToReturn);
        if (sidecar == null) return keep;
        try {
            int size = player.getCardsIn(ZoneType.Hand).size();
            Ask a = ask("mulligan").context("cards_to_bottom_if_kept", String.valueOf(cardsToReturn));
            a.question("keep", "Opening hand of " + size + " cards: " + StateView.handSummary(player)
                    + ". Keep it (then put " + cardsToReturn + " on the bottom) or mulligan?", keep ? "keep" : "mulligan");
            a.option("keep", "keep", "keep the hand");
            a.option("keep", "mulligan", "mulligan for a new hand");
            String ans = a.send(sidecar).get("keep");
            return ans == null ? keep : ans.equals("keep");
        } catch (RuntimeException e) {
            hookFailed("mulligan", e);
            return keep;
        }
    }


    /** True if a triggered ability waiting to go on the stack will return this card to the battlefield. */
    private boolean pendingReturnToBattlefield(Card card) {
        List<SpellAbility> pending = new ArrayList<>();
        try {
            java.lang.reflect.Field f = forge.game.zone.MagicStack.class.getDeclaredField("simultaneousStackEntryList");
            f.setAccessible(true);
            @SuppressWarnings("unchecked")
            List<SpellAbility> sim = (List<SpellAbility>) f.get(getGame().getStack());
            pending.addAll(sim);
        } catch (Exception ignored) { }
        for (SpellAbilityStackInstance si : getGame().getStack()) pending.add(si.getSpellAbility());
        for (SpellAbility sa : pending) {
            try {
                SpellAbility inner = sa instanceof forge.game.trigger.WrappedAbility
                        ? ((forge.game.trigger.WrappedAbility) sa).getWrappedAbility() : sa;
                if (inner.getApi() != forge.game.ability.ApiType.ChangeZone
                        || !"Battlefield".equals(inner.getParam("Destination"))) continue;
                Player who = sa.getActivatingPlayer() != null ? sa.getActivatingPlayer() : sa.getHostCard().getController();
                if (who != player) continue;
                for (Object o : sa.getTriggeringObjects().values()) {
                    if (o instanceof Card && ((Card) o).getId() == card.getId()) return true;
                }
            } catch (Exception ignored) { }
        }
        try {  // still collected but not yet turned into abilities
            java.lang.reflect.Field f = forge.game.trigger.TriggerHandler.class.getDeclaredField("waitingTriggers");
            f.setAccessible(true);
            @SuppressWarnings("unchecked")
            List<forge.game.trigger.TriggerWaiting> waiting = (List<forge.game.trigger.TriggerWaiting>) f.get(getGame().getTriggerHandler());
            for (forge.game.trigger.TriggerWaiting w : waiting) {
                Object moved = w.getParams().get(forge.game.ability.AbilityKey.Card);
                if (!(moved instanceof Card) || ((Card) moved).getId() != card.getId()) continue;
                for (forge.game.trigger.Trigger t : w.getTriggers()) {
                    Card h = t.getHostCard();
                    if (h == null || h.getController() != player || !t.hasParam("Execute")) continue;
                    String exec = h.getSVar(t.getParam("Execute"));
                    if (exec != null && exec.contains("ChangeZone") && exec.contains("Destination$ Battlefield")) return true;
                }
            }
        } catch (Exception ignored) { }
        return false;
    }

    /**
     * "Pay N life or ...": shock lands entering, mostly. Forge's AI decided these silently, and the lands entered
     * tapped on turns the memo needed their mana (Muldrotha's 8th mana, a Massacre Wurm).
     */
    @Override
    public boolean payCostToPreventEffect(Cost cost, SpellAbility sa, boolean alreadyPaid,
                                          forge.util.collect.FCollectionView<Player> allPayers) {
        if (sidecar == null || cost == null || sa == null || cost.getCostParts().isEmpty()) {
            return super.payCostToPreventEffect(cost, sa, alreadyPaid, allPayers);
        }
        for (CostPart part : cost.getCostParts()) {
            if (!(part instanceof forge.game.cost.CostPayLife)) return super.payCostToPreventEffect(cost, sa, alreadyPaid, allPayers);
        }
        try {
            boolean forgeWill = forge.ai.SpellApiToAi.Converter.get(sa).willPayUnlessCost(player, sa, cost, alreadyPaid, allPayers);
            if (!ComputerUtilCost.canPayCost(cost, sa, player, true)) return false;
            String host = sa.getHostCard() == null ? "An effect" : sa.getHostCard().getName();
            String otherwise = StateView.clip(sa.getStackDescription() == null || sa.getStackDescription().isBlank()
                    ? sa.toString() : sa.getStackDescription(), 160);
            Ask a = ask("confirm");
            a.question("yes", host + ": " + cost.toSimpleString() + "? If we don't: " + otherwise.trim()
                    + " (we have " + player.getLife() + " life and " + manaEstimate(player) + " mana untapped now)",
                    forgeWill ? "yes" : "no");
            a.option("yes", "yes", "yes: " + cost.toSimpleString());
            a.option("yes", "no", "no");
            String ans = a.send(sidecar).get("yes");
            boolean pay = ans == null ? forgeWill : ans.equals("yes");
            if (!pay) return false;
            return new forge.game.cost.CostPayment(cost, sa).payComputerCosts(new forge.ai.AiCostDecision(player, sa, true));
        } catch (RuntimeException e) {
            hookFailed("pay-life", e);
            return super.payCostToPreventEffect(cost, sa, alreadyPaid, allPayers);
        }
    }

    @Override
    public boolean confirmAction(SpellAbility sa, PlayerActionConfirmMode mode, String message, List<String> options,
                                 Card cardToShow, Map<String, Object> params) {
        boolean forge = super.confirmAction(sa, mode, message, options, cardToShow, params);
        if (sidecar == null) return forge;
        try {
            // Our commander going to the command zone instead of the graveyard/exile: not a real choice
            // (the pilot declined it 5 times in 11 in one run, stranding Muldrotha).
            Card host = sa == null ? null : sa.getHostCard();
            if (mode == PlayerActionConfirmMode.ChangeZoneToAltDestination && host != null && host.isCommander()
                    && host.getOwner() == player) {
                // ...except when one of our triggers (Kaya's Ghostform) is about to return it to the battlefield:
                // moving it to the command zone makes that trigger fizzle.
                return forge && !pendingReturnToBattlefield(host);
            }
        } catch (RuntimeException ignored) { }
        try {
            String src = sa != null && sa.getHostCard() != null ? sa.getHostCard().getName() + ": " : "";
            Ask a = ask("confirm");
            a.question("yes", StateView.clip(src + (message == null ? String.valueOf(mode) : message), 300), forge ? "yes" : "no");
            a.option("yes", "yes", "yes, do it");
            a.option("yes", "no", "no");
            String ans = a.send(sidecar).get("yes");
            return ans == null ? forge : ans.equals("yes");
        } catch (RuntimeException e) {
            hookFailed("confirm", e);
            return forge;
        }
    }

    @Override
    public <T extends GameEntity> T chooseSingleEntityForEffect(FCollectionView<T> optionList, DelayedReveal delayedReveal,
            SpellAbility sa, String title, boolean isOptional, Player targetedPlayer, Map<String, Object> params) {
        T forge = super.chooseSingleEntityForEffect(optionList, delayedReveal, sa, title, isOptional, targetedPlayer, params);
        if (sidecar == null || optionList.size() < 2) return forge;
        try {
            List<T> list = new ArrayList<>(optionList);
            if (list.size() > MAX_TARGETS) list = new ArrayList<>(list.subList(0, MAX_TARGETS));
            if (forge != null && !list.contains(forge)) list.set(list.size() - 1, forge);
            Ask a = ask("choose");
            String def = forge == null ? "none" : "e" + list.indexOf(forge);
            String src = sa != null && sa.getHostCard() != null ? sa.getHostCard().getName() + ": " : "";
            a.question("pick", StateView.clip(src + (title == null ? "choose one" : title), 300), def);
            for (int i = 0; i < list.size(); i++) a.option("pick", "e" + i, describe(list.get(i)));
            if (isOptional) a.option("pick", "none", "choose nothing");
            String ans = a.send(sidecar).get("pick");
            if (ans == null) return forge;
            if (ans.equals("none")) return isOptional ? null : forge;
            try {
                return list.get(Integer.parseInt(ans.substring(1)));
            } catch (Exception e) {
                return forge;
            }
        } catch (RuntimeException e) {
            hookFailed("choose", e);
            return forge;
        }
    }

    @Override
    public CardCollectionView choosePermanentsToSacrifice(SpellAbility sa, int min, int max, CardCollectionView validTargets,
                                                          String message) {
        CardCollectionView forge = super.choosePermanentsToSacrifice(sa, min, max, validTargets, message);
        // one permanent, mandatory or optional ("you may sacrifice", e.g. Braids after its yes/no confirm)
        if (sidecar == null || max != 1 || min > 1 || validTargets.size() < 2 || forge == null || forge.size() > 1) {
            return forge;
        }
        try {
            boolean optional = min == 0;
            String src = sa != null && sa.getHostCard() != null ? sa.getHostCard().getName() : "an effect";
            Card c = pickCard("sacrifice", src + (optional ? " lets us sacrifice a permanent: which one?"
                    : " makes us sacrifice a permanent: which one?"), validTargets, forge.isEmpty() ? null : forge.get(0), optional);
            if (c == null) return optional ? CardCollection.EMPTY : forge;
            return new CardCollection(c);
        } catch (RuntimeException e) {
            hookFailed("sacrifice", e);
            return forge;
        }
    }

    @Override
    public ImmutablePair<CardCollection, CardCollection> arrangeForSurveil(CardCollection topN) {
        return arrangeTop(super.arrangeForSurveil(topN), "surveil", "graveyard");
    }

    @Override
    public ImmutablePair<CardCollection, CardCollection> arrangeForScry(CardCollection topN) {
        return arrangeTop(super.arrangeForScry(topN), "scry", "bottom");
    }

    private ImmutablePair<CardCollection, CardCollection> arrangeTop(ImmutablePair<CardCollection, CardCollection> forge,
                                                                     String kind, String away) {
        if (sidecar == null) return forge;
        try {
            List<Card> cards = new ArrayList<>(forge.getLeft());
            cards.addAll(forge.getRight());
            if (cards.isEmpty()) return forge;
            Ask a = ask(kind);
            for (int i = 0; i < cards.size(); i++) {
                Card c = cards.get(i);
                a.question("s" + i, kind + " " + c.getName() + ": keep it on top of our library, or put it into our " + away + "?",
                        forge.getLeft().contains(c) ? "top" : "away");
                a.option("s" + i, "top", "keep on top");
                a.option("s" + i, "away", "put into our " + away);
            }
            Map<String, String> ans = a.send(sidecar);
            if (ans.isEmpty()) return forge;
            CardCollection top = new CardCollection();
            CardCollection rest = new CardCollection();
            for (int i = 0; i < cards.size(); i++) {
                String choice = ans.getOrDefault("s" + i, forge.getLeft().contains(cards.get(i)) ? "top" : "away");
                (choice.equals("top") ? top : rest).add(cards.get(i));
            }
            return ImmutablePair.of(top, rest);
        } catch (RuntimeException e) {
            hookFailed("arrange", e);
            return forge;
        }
    }

    @Override
    public boolean playTrigger(Card host, WrappedAbility wrapper, boolean isMandatory) {
        if (sidecar == null) return super.playTrigger(host, wrapper, isMandatory);
        try {
            if (prepareSingleSa == null) {
                prepareSingleSa = PlayerControllerAi.class.getDeclaredMethod("prepareSingleSa", Card.class,
                        SpellAbility.class, boolean.class);
                prepareSingleSa.setAccessible(true);
            }
            if (!(Boolean) prepareSingleSa.invoke(this, host, wrapper, isMandatory)) return false;
        } catch (Exception e) {
            return super.playTrigger(host, wrapper, isMandatory);
        }
        retargetTrigger(host, wrapper);
        return ComputerUtil.playNoStack(wrapper.getActivatingPlayer(), wrapper, getGame(), true);
    }

    /** Let the pilot re-pick the single target Forge chose for one of our triggers. */
    private void retargetTrigger(Card host, SpellAbility wrapper) {
        try {
            SpellAbility sa = wrapper instanceof WrappedAbility w && w.getWrappedAbility() != null
                    ? w.getWrappedAbility() : wrapper;
            Ask a = ask("trigger-target");
            List<GameEntity> cands = addTargetQuestion(a, "tgt",
                    "Our triggered ability from " + (host == null ? "?" : host.getName()) + " ("
                            + abilityText(wrapper, sa, 200) + "): what should it target?", sa);
            if (cands != null) applyTarget(sa, cands, a.send(sidecar).get("tgt"));
        } catch (RuntimeException e) {
            hookFailed("trigger-target", e);
        }
    }

    /**
     * Ordinary (non-static) triggers go on the stack here, not through playTrigger.
     * Same as Forge's version, plus a target question for each of our triggers.
     */
    @Override
    public void orderAndPlaySimultaneousSa(List<SpellAbility> activePlayerSAs) {
        if (sidecar == null) {
            super.orderAndPlaySimultaneousSa(activePlayerSAs);
            return;
        }
        for (SpellAbility sa : orderSimultaneousSa(activePlayerSAs)) {
            if (!sa.isTrigger() || sa.isCopied()) {
                super.orderAndPlaySimultaneousSa(Collections.singletonList(sa));
                continue;
            }
            boolean ready;
            try {
                if (prepareSingleSa == null) {
                    prepareSingleSa = PlayerControllerAi.class.getDeclaredMethod("prepareSingleSa", Card.class,
                            SpellAbility.class, boolean.class);
                    prepareSingleSa.setAccessible(true);
                }
                ready = (Boolean) prepareSingleSa.invoke(this, sa.getHostCard(), sa, true);
            } catch (Exception e) {
                hookFailed("trigger-order", e);
                super.orderAndPlaySimultaneousSa(Collections.singletonList(sa));
                continue;
            }
            if (ready) {
                retargetTrigger(sa.getHostCard(), sa);
                ComputerUtil.playStack(sa, player, getGame());
            }
        }
    }

    /** Optional ("you may") triggers, asked on resolution. */
    @Override
    public boolean confirmTrigger(WrappedAbility wrapper) {
        boolean forge = super.confirmTrigger(wrapper);
        if (sidecar == null || wrapper.isMandatory()) return forge;
        try {
            SpellAbility sa = wrapper.getWrappedAbility() != null ? wrapper.getWrappedAbility() : wrapper;
            // saying yes to a targeted trigger Forge declined only works if targets were already chosen
            boolean canSayYes = forge || !sa.usesTargeting() || !sa.getTargets().isEmpty();
            if (!canSayYes) return forge;
            Card host = wrapper.getHostCard();
            Ask a = ask("optional-trigger");
            a.question("yes", StateView.clip((host == null ? "" : host.getName() + ": ") + abilityText(wrapper, sa, 280), 300)
                    + " — use this optional trigger?", forge ? "yes" : "no");
            a.option("yes", "yes", "yes, use it");
            a.option("yes", "no", "no, decline it");
            String ans = a.send(sidecar).get("yes");
            return ans == null ? forge : ans.equals("yes");
        } catch (RuntimeException e) {
            hookFailed("optional-trigger", e);
            return forge;
        }
    }

    /** Library/graveyard searches that pick one card: tutors, fetch lands, land ramp, "return a card". */
    @Override
    public Card chooseSingleCardForZoneChange(ZoneType destination, List<ZoneType> origin, SpellAbility sa,
            CardCollection fetchList, DelayedReveal delayedReveal, String selectPrompt, boolean isOptional, Player decider) {
        Card forge = super.chooseSingleCardForZoneChange(destination, origin, sa, fetchList, delayedReveal, selectPrompt,
                isOptional, decider);
        if (sidecar == null || decider != player || fetchList == null || fetchList.size() < 2) return forge;
        try {
            // one option per distinct name (a library search sees many copies of basics)
            Map<String, Card> byName = new LinkedHashMap<>();
            if (forge != null) byName.put(forge.getName(), forge);
            for (Card c : fetchList) {
                if (byName.size() >= MAX_SEARCH) break;
                byName.putIfAbsent(c.getName(), c);
            }
            if (byName.size() + (isOptional ? 1 : 0) < 2) return forge;
            List<Card> list = new ArrayList<>(byName.values());
            String src = sa != null && sa.getHostCard() != null ? sa.getHostCard().getName() : "an effect";
            String from = origin == null ? "?" : origin.toString().toLowerCase();
            Ask a = ask("search").context("search", src + ": " + from + " → " + String.valueOf(destination).toLowerCase());
            a.question("pick", StateView.clip(src + " (" + (sa == null ? "" : sa.toString()) + ")", 240)
                    + ": which card do we take from " + from + " to " + String.valueOf(destination).toLowerCase() + "?",
                    forge == null ? "none" : "c0");
            for (int i = 0; i < list.size(); i++) {
                Card c = list.get(i);
                a.option("pick", "c" + i, landEntry(c, destination) + StateView.cardLine(c, 140));
            }
            // "take nothing" only when Forge itself would fail to find: declining a search we already
            // paid for is almost never right, and Forge re-opens a declined search after a confirm.
            if (isOptional && forge == null) a.option("pick", "none", "take nothing");
            String ans = a.send(sidecar).get("pick");
            if (ans == null) return forge;
            if (ans.equals("none")) return forge == null ? null : forge;
            Card chosen = list.get(Integer.parseInt(ans.substring(1)));
            return fetchList.contains(chosen) ? chosen : forge;
        } catch (RuntimeException e) {
            hookFailed("search", e);
            return forge;
        }
    }

    private static final java.util.regex.Pattern PAY_OR_TAPPED =
            java.util.regex.Pattern.compile("(?i)you may pay (\\d+) life\\. if you don't, it enters (the battlefield )?tapped");
    private static final java.util.regex.Pattern ENTERS_TAPPED =
            java.util.regex.Pattern.compile("(?i)enters( the battlefield)? tapped");

    /** For a land fetched onto the battlefield: whether it can make mana this turn. */
    private static String landEntry(Card c, ZoneType destination) {
        if (!c.isLand() || destination != ZoneType.Battlefield) return "";
        String text = c.getOracleText() == null ? "" : c.getOracleText();
        java.util.regex.Matcher m = PAY_OR_TAPPED.matcher(text);
        if (m.find()) return "[untapped only if we pay " + m.group(1) + " life] ";
        if (ENTERS_TAPPED.matcher(text).find()) return "[enters tapped: no mana this turn] ";
        return "[enters untapped] ";
    }

    /** Our own single-card discards (effects and costs routed through the controller, and cleanup). */
    @Override
    public CardCollection chooseCardsToDiscardFrom(Player p, SpellAbility sa, CardCollection validCards, int min, int max,
                                                   CardCollectionView visibleToChooser) {
        CardCollection forge = super.chooseCardsToDiscardFrom(p, sa, validCards, min, max, visibleToChooser);
        if (sidecar == null || p != player || min != 1 || max != 1 || forge == null || forge.size() != 1
                || validCards.size() < 2) {
            return forge;
        }
        try {
            String src = sa != null && sa.getHostCard() != null ? sa.getHostCard().getName() : "an effect";
            Card c = pickCard("discard", src + " makes us discard a card: which one?", validCards, forge.get(0), false);
            return c == null ? forge : new CardCollection(c);
        } catch (RuntimeException e) {
            hookFailed("discard", e);
            return forge;
        }
    }

    @Override
    public CardCollectionView chooseCardsToDiscardToMaximumHandSize(int numDiscard) {
        CardCollectionView forge = super.chooseCardsToDiscardToMaximumHandSize(numDiscard);
        if (sidecar == null || numDiscard != 1 || forge == null || forge.size() != 1) return forge;
        try {
            CardCollectionView hand = player.getCardsIn(ZoneType.Hand);
            Card c = pickCard("discard", "Cleanup: we are over the hand size limit and must discard one card. Which?",
                    hand, forge.get(0), false);
            return c == null ? forge : new CardCollection(c);
        } catch (RuntimeException e) {
            hookFailed("discard", e);
            return forge;
        }
    }

}
