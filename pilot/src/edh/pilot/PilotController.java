package edh.pilot;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.apache.commons.lang3.tuple.ImmutablePair;

import forge.LobbyPlayer;
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
import forge.game.cost.CostDecisionMakerBase;
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
public class PilotController extends PlayerControllerAi {
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
            if (!sa.usesTargeting() || sa.getMinTargets() != 1 || sa.getMaxTargets() != 1) return null;
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
    private List<GameEntity> addTargetQuestion(Ask a, String qid, String prompt, SpellAbility sa) {
        List<GameEntity> cands = singleTargetCandidates(sa);
        if (cands == null) return null;
        GameObject current = null;
        try {
            if (sa.getTargets() != null && !sa.getTargets().isEmpty()) current = sa.getTargets().get(0);
        } catch (Exception ignored) { }
        String def = "t0";
        for (int i = 0; i < cands.size(); i++) {
            if (cands.get(i) == current) def = "t" + i;
        }
        a.question(qid, prompt, def);
        for (int i = 0; i < cands.size(); i++) a.option(qid, "t" + i, describe(cands.get(i)));
        return cands;
    }

    private void applyTarget(SpellAbility sa, List<GameEntity> cands, String answer) {
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

    /** Generic "pick one card" used by sacrifices and costs. */
    Card pickCard(String kind, String prompt, CardCollectionView cards, Card forgeChoice, boolean optional) {
        if (sidecar == null || cards.size() < 2) return forgeChoice;
        List<Card> list = new ArrayList<>(cards);
        if (list.size() > MAX_TARGETS) list = new ArrayList<>(list.subList(0, MAX_TARGETS));
        if (forgeChoice != null && !list.contains(forgeChoice)) list.set(list.size() - 1, forgeChoice);
        Ask a = ask(kind);
        String def = forgeChoice == null ? "none" : "c" + list.indexOf(forgeChoice);
        a.question("pick", prompt, def);
        for (int i = 0; i < list.size(); i++) a.option("pick", "c" + i, describe(list.get(i)));
        if (optional) a.option("pick", "none", "choose nothing");
        String ans = a.send(sidecar).get("pick");
        if (ans == null) return forgeChoice;
        if (ans.equals("none")) return optional ? null : forgeChoice;
        try {
            return list.get(Integer.parseInt(ans.substring(1)));
        } catch (Exception e) {
            return forgeChoice;
        }
    }

    static int manaEstimate(Player p) {
        try {
            return ComputerUtilMana.getAvailableManaEstimate(p);
        } catch (Exception e) {
            return -1;
        }
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
                    if (!ComputerUtilCost.canPayCost(sa, player, false)) continue;
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

            String window = main ? "our main phase, stack empty"
                    : oppOnStack ? "responding to an opponent's spell or ability on the stack"
                    : endOfOppTurn ? "end of an opponent's turn" : "instant-speed window (" + phase + ")";
            Ask a = ask("action").context("window", window);
            if (top != null) a.context("stack_top", StateView.clip(top.getStackDescription(), 200));
            a.question("action", "Which action do we take now?", forgeDefault);
            Map<String, List<GameEntity>> targetCands = new LinkedHashMap<>();
            for (Map.Entry<String, List<SpellAbility>> e : options.entrySet()) {
                SpellAbility sa = e.getValue().get(0);
                String zone = sa.getHostCard().getZone() == null ? "?" : sa.getHostCard().getZone().getZoneType().name();
                String kind = sa.isLandAbility() ? "play land" : sa.isSpell() ? "cast" : "activate";
                StringBuilder text = new StringBuilder(kind).append(' ').append(sa.getHostCard().getName())
                        .append(" (from ").append(zone).append("): ").append(StateView.clip(sa.toString(), 220));
                try {
                    if (sa.usesTargeting() && !sa.getTargets().isEmpty()) {
                        text.append(" → target: ").append(describe(sa.getTargets().get(0)));
                    }
                } catch (Exception ignored) { }
                String src = source.get(e.getKey());
                try {
                    if (!sa.isLandAbility() && sa.getPayCosts() != null && sa.getPayCosts().hasNoManaCost()) {
                        text.append(" [costs no mana]");
                    }
                } catch (Exception ignored) { }
                if (src.startsWith("forge-declined")) {
                    text.append(" [Forge's heuristic AI would not do this: ").append(src.substring(15)).append(']');
                }
                a.option("action", e.getKey(), text.toString());
                // speculative fan-out: the target for each targeted option, answered in the same call
                List<GameEntity> cands = addTargetQuestion(a, "tgt_" + e.getKey(),
                        "If we " + kind + " " + sa.getHostCard().getName() + " (" + StateView.clip(sa.toString(), 200)
                                + "), what should it target?", sa);
                if (cands != null) targetCands.put(e.getKey(), cands);
            }
            String skip = forgeWantsToAct ? " (this skips o0, the play Forge's AI would make now)" : "";
            a.option("action", "pass", (main
                    ? "Take no further action this phase: hold remaining mana and cards"
                    : "Do nothing now; let it resolve / let the turn pass") + skip);
            Map<String, String> ans = a.send(sidecar);
            String choice = ans.getOrDefault("action", forgeDefault);
            if ("pass".equals(choice)) return null;
            List<SpellAbility> picked = options.get(choice);
            if (picked == null) return aiPick;
            applyTarget(picked.get(0), targetCands.get(choice), ans.get("tgt_" + choice));
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
                            a.option(q, "d" + d, "attack " + describeDefender(defenders.get(d)));
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

    private String describeDefender(GameEntity d) {
        if (d instanceof Player p) return StateView.label(p) + " (" + p.getLife() + " life)";
        if (d instanceof Card c) {
            String extra = c.isPlaneswalker() ? " loyalty " + c.getCurrentLoyalty() : "";
            return describe(c) + extra;
        }
        return String.valueOf(d);
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
            List<Card> blockers = new ArrayList<>();
            for (Card c : player.getCreaturesInPlay()) {
                try {
                    if (CombatUtil.canBlock(c, combat)) blockers.add(c);
                } catch (Exception ignored) { }
            }
            if (blockers.isEmpty()) return;
            Map<Card, List<Card>> forgeBlocks = new LinkedHashMap<>();
            for (Card at : attackers) forgeBlocks.put(at, new ArrayList<>(combat.getBlockers(at)));

            Ask a = ask("block");
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
                    try {
                        if (CombatUtil.canBlock(at, b, combat)) {
                            a.option(q, "k" + j, "block with " + b.getName() + " " + b.getNetPower() + "/" + b.getNetToughness());
                        }
                    } catch (Exception ignored) { }
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
                for (Map.Entry<Card, List<Card>> fb : forgeBlocks.entrySet()) {
                    for (Card b : fb.getValue()) combat.addBlocker(fb.getKey(), b);
                }
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
            Ask a = ask("mulligan").context("cards_to_bottom_if_kept", String.valueOf(cardsToReturn));
            a.question("keep", "Keep this opening hand (then put " + cardsToReturn + " on the bottom) or mulligan?",
                    keep ? "keep" : "mulligan");
            a.option("keep", "keep", "keep the hand");
            a.option("keep", "mulligan", "mulligan for a new hand");
            String ans = a.send(sidecar).get("keep");
            return ans == null ? keep : ans.equals("keep");
        } catch (RuntimeException e) {
            hookFailed("mulligan", e);
            return keep;
        }
    }

    @Override
    public boolean confirmAction(SpellAbility sa, PlayerActionConfirmMode mode, String message, List<String> options,
                                 Card cardToShow, Map<String, Object> params) {
        boolean forge = super.confirmAction(sa, mode, message, options, cardToShow, params);
        if (sidecar == null) return forge;
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
        if (sidecar == null || min != 1 || max != 1 || validTargets.size() < 2 || forge == null || forge.size() != 1) {
            return forge;
        }
        try {
            String src = sa != null && sa.getHostCard() != null ? sa.getHostCard().getName() : "an effect";
            Card c = pickCard("sacrifice", src + " makes us sacrifice a permanent: which one?", validTargets, forge.get(0), false);
            return c == null ? forge : new CardCollection(c);
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
                            + StateView.clip(sa.toString(), 200) + "): what should it target?", sa);
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
            a.question("yes", StateView.clip((host == null ? "" : host.getName() + ": ") + sa.toString(), 300)
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
                a.option("pick", "c" + i, StateView.cardLine(c, 140));
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

    @Override
    public CostDecisionMakerBase getCostDecisionMaker(Player p, SpellAbility ability, boolean effect, String prompt) {
        if (sidecar == null) return super.getCostDecisionMaker(p, ability, effect, prompt);
        return new PilotCostDecision(p, ability, effect, this);
    }
}
