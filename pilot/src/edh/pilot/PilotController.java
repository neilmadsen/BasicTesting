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
import forge.game.spellability.AbilityManaPart;
import forge.game.ability.AbilityUtils;
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
    // Scanning what we can play asks Forge's AI about each ability. With 16 Forge JVMs sharing the machine that
    // took longer than the old 1.5 s budget, and cards scanned last (Niv-Mizzet, Parun on a full board) silently
    // dropped out of the options. Spells are scanned first and a cut is recorded in the request.
    private static final long SCAN_BUDGET_MS = 6000;
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
        Card host = sa.getHostCard();
        ZoneType from = host != null && host.getZone() != null ? host.getZone().getZoneType() : null;
        boolean ok = false;
        boolean frozenByUs = false;
        try {
            // A failed payment leaves the stack frozen with the failed spell as its primary ability; every later
            // spell of the phase then waits in the frozen stack, in the stack zone but off the stack, until the next
            // phase unfreezes it. We only get priority on an unfrozen stack, so a freeze here is stale.
            if (getGame().getStack().isFrozen()) {
                System.out.println("[pilot] stale stack freeze cleared before casting " + (host == null ? sa : host.getName()));
                getGame().getStack().unfreezeStack();
            }
            clearForgeReservations();
            ok = super.playChosenSpellAbility(sa);
            frozenByUs = getGame().getStack().isFrozen();
            return ok;
        } finally {
            paying = was;
            // Forge's AI returns true even when payment failed. Its failure path marks the ability skipped (but on
            // its own copy for a commander cast, so Vivi stayed stranded for a whole game) and leaves the stack
            // frozen. Either sign means this cast failed; a card merely waiting in a frozen stack is not rescued
            // (moving it back duplicated Jeska's Will).
            if (sa.isSpell() && (sa.isSkip() || frozenByUs) && from != null && from != ZoneType.Stack) {
                dumpPayment(sa);
                if (frozenByUs) getGame().getStack().unfreezeStack();
                rescueStranded(sa, host, from);
            }
        }
    }

    /** Forge's AI reserves mana sources as a side effect of evaluating plays (a damage spell it could chain
     *  reserves the next spell's mana; a creature it predicts casting after combat, or a block trick, reserves
     *  theirs), and its payment then refuses those sources for the play actually chosen: Ponder and Hullbreaker
     *  Horror failed with "Didn't find what to pay for {U}" while the lands were untapped. Clear Forge's
     *  reservations and keep only the pilot's own hold. */
    private void clearForgeReservations() {
        clearReservationSets();
        applyHold();
    }

    private void clearReservationSets() {
        AiCardMemory.clearMemorySet(player, AiCardMemory.MemorySet.HELD_MANA_SOURCES_FOR_MAIN2);
        AiCardMemory.clearMemorySet(player, AiCardMemory.MemorySet.HELD_MANA_SOURCES_FOR_DECLBLK);
        AiCardMemory.clearMemorySet(player, AiCardMemory.MemorySet.HELD_MANA_SOURCES_FOR_ENEMY_DECLBLK);
        AiCardMemory.clearMemorySet(player, AiCardMemory.MemorySet.HELD_MANA_SOURCES_FOR_NEXT_SPELL);
    }

    /** One line per mana source when a payment fails: what was untapped and which reservation held it. */
    private void dumpPayment(SpellAbility sa) {
        try {
            StringBuilder b = new StringBuilder("[pilot] payment failed for " + sa.getHostCard().getName()
                    + " cost=" + sa.getPayCosts().toSimpleString() + " pool=" + player.getManaPool().totalMana() + " sources:");
            for (Card c : player.getCardsIn(ZoneType.Battlefield)) {
                if (c.getManaAbilities().isEmpty()) continue;
                b.append(" ").append(c.getName()).append(c.isTapped() ? "(tapped" : "(");
                for (AiCardMemory.MemorySet m : AiCardMemory.MemorySet.values()) {
                    if (AiCardMemory.isRememberedCard(player, c, m)) b.append(" ").append(m.name());
                }
                b.append(")");
            }
            System.out.println(b);
        } catch (RuntimeException e) {
            hookFailed("dump-payment", e);
        }
    }

    /**
     * A cast whose payment failed: Forge's AI leaves the card in the stack zone for the rest of the game (its own
     * recovery only runs for cards cast from the stack), so Niv-Mizzet, Parun and Rhystic Study vanished from our
     * hand after one failed cast each. Put the card back where it came from, playable again, and don't offer that
     * cast again this turn.
     */
    private void rescueStranded(SpellAbility sa, Card host, ZoneType from) {
        try {
            Game game = getGame();
            Card now = game.getCardState(host, null);
            if (now == null || !now.isInZone(ZoneType.Stack) || game.getStack().isFrozen()) return;
            for (SpellAbilityStackInstance si : game.getStack()) {
                if (si.getSpellAbility() != null && si.getSpellAbility().getHostCard() != null
                        && si.getSpellAbility().getHostCard().getId() == now.getId()) return;  // really on the stack
            }
            Card back = game.getAction().moveTo(from, now, null, null);
            // the colours may be what failed: with an unused big mana source, make it (split for this card) and let
            // the card be offered again
            if (back != null && !bigManaAbilities(player).isEmpty()) {
                for (SpellAbility ma : bigManaAbilities(player)) if (activateBigMana(ma, back)) {
                    for (SpellAbility csa : back.getSpellAbilities()) csa.setSkip(false);
                    System.out.println("[pilot] cast failed at payment; returned " + now.getName() + " and made " + ma.getHostCard().getName() + "'s mana");
                    return;
                }
            }
            if (back != null) {
                if (cancelledTurn != game.getPhaseHandler().getTurn()) cancelled.clear();
                cancelledTurn = game.getPhaseHandler().getTurn();
                for (SpellAbility csa : back.getSpellAbilities()) {
                    csa.setSkip(false);
                    if (csa.getDescription().equals(sa.getDescription())) cancelled.add(cancelKey(csa));
                }
            }
            System.out.println("[pilot] cast failed at payment, returned " + now.getName() + " to " + from);
        } catch (RuntimeException e) {
            hookFailed("rescue-stranded", e);
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

    private static int scanRank(SpellAbility sa) {
        if (sa.isLandAbility()) return 0;
        if (sa.isSpell()) return 1;
        return 2;
    }

    /** Legal single-target candidates for sa (null if not a single-target ability or nothing to choose). */
    private List<GameEntity> singleTargetCandidates(SpellAbility sa) {
        try {
            // one target, or "up to one" (The Coming of Galactus chapter I was never asked before)
            if (!sa.usesTargeting() || sa.getMinTargets() > 1 || sa.getMaxTargets() != 1) return null;
            List<GameEntity> all = new ArrayList<>(sa.getTargetRestrictions().getAllCandidates(sa));
            // a card "in the stack zone" is only a target if it is a spell actually on the stack (an Aura stranded
            // there by a failed resolution is not), and it is targeted as that spell, not as the card
            all.removeIf(e -> e instanceof Card c && c.isInZone(ZoneType.Stack) ? stackSpell(sa, c) == null : !sa.canTarget(e));
            if (all.size() < 2) return null;
            // opponents' things first, so the cap never hides them
            all.sort((x, y) -> Boolean.compare(owner(x) == player, owner(y) == player));
            return all.size() > MAX_TARGETS ? new ArrayList<>(all.subList(0, MAX_TARGETS)) : all;
        } catch (Exception e) {
            return null;
        }
    }

    /** The spell on the stack whose card is c, if sa can target it; counterspells target spells, not cards. */
    private SpellAbility stackSpell(SpellAbility sa, Card c) {
        for (SpellAbilityStackInstance si : getGame().getStack()) {
            SpellAbility s = si.getSpellAbility();
            if (s != null && s.isSpell() && s.getHostCard() != null && s.getHostCard().getId() == c.getId() && sa.canTarget(s))
                return s;
        }
        return null;
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
        return addTargetQuestion(a, qid, prompt, sa, Collections.emptySet());
    }

    /** pending: what other triggers from the same card on the stack already target (labelled on those options). */
    private List<GameEntity> addTargetQuestion(Ask a, String qid, String prompt, SpellAbility sa, Set<Object> pending) {
        List<GameEntity> cands = singleTargetCandidates(sa);
        if (cands == null) return null;
        GameObject current = null;
        try {
            if (sa.getTargets() != null && !sa.getTargets().isEmpty()) current = sa.getTargets().get(0);
            if (current instanceof SpellAbility s) current = s.getHostCard();  // a spell target, listed as its card
        } catch (Exception ignored) { }
        boolean upTo = sa.getMinTargets() == 0;
        String def = upTo && current == null ? "none" : "t0";
        for (int i = 0; i < cands.size(); i++) {
            if (cands.get(i) == current) def = "t" + i;
        }
        a.question(qid, prompt, def);
        for (int i = 0; i < cands.size(); i++) {
            GameEntity c = cands.get(i);
            a.option(qid, "t" + i, describe(c) + (pending.contains(c) ? " [already the target of our spell or trigger on the stack: aiming here too can fizzle one]" : ""));
        }
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
            GameObject target = t instanceof Card c && c.isInZone(ZoneType.Stack) ? stackSpell(sa, c) : t;
            if (target != null && target != current && sa.canTarget(target)) {
                sa.resetTargets();
                sa.getTargets().add(target);
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
        if (forgeChoice != null && !list.contains(forgeChoice)) {
            if (list.size() < MAX_TARGETS) list.add(forgeChoice);  // a short list keeps every card
            else list.set(list.size() - 1, forgeChoice);
        }
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
    /** What in hand the extra mana could pay for now: "; with it we could cast X, Y", or a warning that there is
     *  nothing to spend it on (Vivi's 12 mana drained away with only a counterspell in hand). */
    private String spendableWith(int extra) {
        try {
            // the estimate already counts the big mana ability being offered: adding it again made every play look
            // affordable, and the "nothing needs this mana" veto never fired (3 of 4 wasted Vivi activations in round 8)
            int counted = 0;
            Set<Card> hosts = new HashSet<>();
            for (SpellAbility ma : bigManaAbilities(player)) if (hosts.add(ma.getHostCard())) counted += cardMana(ma.getHostCard(), player);
            int total = manaEstimate(player) - counted + extra;
            List<String> names = new ArrayList<>();
            // everything we could play now, not only the hand: a flashback Faithless Looting and Fiery Islet's draw
            // were vetoed as "nothing needs this mana"
            for (SpellAbility sa : ComputerUtilAbility.getSpellAbilities(ComputerUtilAbility.getAvailableCards(getGame(), player), player)) {
                Card c = sa.getHostCard();
                if (c == null || sa.isManaAbility() || sa.isLandAbility() || sa.getPayCosts() == null) continue;
                ManaCost mc = sa.getPayCosts().getTotalMana();
                int cost = mc == null ? 0 : mc.getCMC();
                if (cost == 0 || cost > total || names.contains(c.getName())) continue;
                boolean fast = sa.isAbility() || c.isInstant() || c.hasKeyword(forge.game.keyword.Keyword.FLASH);
                if (!fast || cost > manaEstimate(player)) names.add(c.getName());
            }
            return names.isEmpty() ? ". NOTHING in hand needs this mana now: taking it wastes it"
                    : ". With it we could cast: " + String.join(", ", names.subList(0, Math.min(6, names.size())));
        } catch (RuntimeException e) {
            return "";
        }
    }

    /** The most mana one permanent's abilities can make now (a Combo or Any ability counts once per mana). */
    static int cardMana(Card c, Player p) {
        int best = 0;
        for (SpellAbility ma : c.getManaAbilities()) {
            try {
                ma.setActivatingPlayer(p);
                if (!ma.canPlay() || !ma.checkRestrictions(p)) continue;
                String[] produced = ma.getParamOrDefault("Produced", "").trim().split(" ");
                String first = produced.length > 0 ? produced[0] : "";
                int kinds = first.equals("Combo") || first.equals("Any") || first.startsWith("Chosen")
                        || produced.length == 0 ? 1 : produced.length;
                int amount;
                try {  // "X" amounts (Vivi Ornitier: her power) were counted as 1
                    amount = AbilityUtils.calculateAmount(c, ma.getParamOrDefault("Amount", "1"), ma);
                } catch (Exception nfe) {
                    amount = 1;
                }
                int cost = ma.getPayCosts().getCostMana() != null ? ma.getPayCosts().getCostMana().getMana().getCMC() : 0;
                best = Math.max(best, kinds * amount - cost);
            } catch (Exception ignored) { }
        }
        return best;
    }

    static int manaEstimate(Player p) {
        int total = 0;
        try {
            for (Card c : p.getCardsIn(ZoneType.Battlefield)) total += cardMana(c, p);
            total += p.getManaPool().totalMana();  // mana already floating
        } catch (Exception e) {
            return -1;
        }
        return total;
    }

    /** Free, untapped-cost mana abilities that make several mana at once (Vivi Ornitier: {0}: add X, once a turn,
     *  our turn only). Forge's payment and affordability code barely uses them: in the Vivi runs an overloaded
     *  Cyclonic Rift was never on offer with 3 lands and a 10-power Vivi, although the memo planned exactly that.
     *  The pilot offers them as explicit actions instead. */
    static List<SpellAbility> bigManaAbilities(Player p) {
        List<SpellAbility> out = new ArrayList<>();
        try {
            for (Card c : p.getCardsIn(ZoneType.Battlefield)) {
                if (c.isLand()) continue;
                for (SpellAbility ma : c.getManaAbilities()) {
                    try {
                        ma.setActivatingPlayer(p);
                        Cost cost = ma.getPayCosts();
                        debugMana(c.getName() + " cost=" + cost + " tap=" + (cost != null && cost.hasTapCost())
                                + " manaPart=" + (cost == null || cost.getCostMana() == null ? "none" : cost.getCostMana().convertAmount())
                                + " canPlay=" + ma.canPlay() + " amount=" + AbilityUtils.calculateAmount(c, ma.getParamOrDefault("Amount", "1"), ma));
                        // a {0} cost has a mana part that convertAmount() counts as 1; its mana value is 0
                        if (cost == null || cost.hasTapCost() || (cost.getCostMana() != null && cost.getCostMana().getMana().getCMC() > 0)) continue;
                        // canPlay() skips static bans: Vivi made mana under Linvala, Keeper of Silence
                        if (!ma.canPlay() || !ma.checkRestrictions(p)) continue;
                        int amount = AbilityUtils.calculateAmount(c, ma.getParamOrDefault("Amount", "1"), ma);
                        if (amount >= 1) out.add(ma);  // a 1-power Vivi's single mana paid for Niv-Mizzet's last pip
                    } catch (Exception e) {
                        debugMana(c.getName() + " error " + e);
                    }
                }
            }
        } catch (Exception ignored) { }
        return out;
    }

    private static void debugMana(String line) {
        String path = System.getenv("EDH_PILOT_DEBUG_MANA");
        if (path == null) return;
        try (java.io.FileWriter w = new java.io.FileWriter(path, true)) {
            w.write(line + "\n");
        } catch (Exception ignored) { }
    }

    /** Colours for a combo mana ability: split by the coloured pips of the spells in hand (U/R for Vivi). */
    private String comboSplit(SpellAbility ma, int amount) {
        return comboSplit(ma, amount, null);
    }

    /** forCard: a spell being cast with this mana; its coloured pips are covered first. */
    private String comboSplit(SpellAbility ma, int amount, Card forCard) {
        AbilityManaPart mp = ma.getManaPart();
        String[] colors = mp.getComboColors(ma).trim().split(" ");
        if (forCard != null && forCard.getManaCost() != null) {
            Map<String, Integer> need = new LinkedHashMap<>();
            int left = amount;
            for (String col : colors) {
                int n = 0;
                for (ManaCostShard sh : forCard.getManaCost()) {
                    if (!sh.isGeneric() && sh.canBePaidWithManaOfColor(forge.card.MagicColor.fromName(col))) n++;
                }
                n = Math.min(n, left);
                need.put(col, n);
                left -= n;
            }
            String rest = left > 0 ? comboSplit(ma, left, null) : "";
            StringBuilder sb = new StringBuilder(rest);
            for (String col : colors) {
                for (int i = 0; i < need.get(col); i++) sb.append(sb.length() > 0 ? " " : "").append(col);
            }
            return sb.toString();
        }
        Map<String, Integer> pips = new LinkedHashMap<>();
        Map<String, Integer> most = new LinkedHashMap<>();
        for (String col : colors) { pips.put(col, 0); most.put(col, 0); }
        for (Card c : player.getCardsIn(ZoneType.Hand)) {
            if (c.isLand() || c.getManaCost() == null) continue;
            for (String col : colors) {
                int n = 0;
                for (ManaCostShard sh : c.getManaCost()) {
                    if (sh.canBePaidWithManaOfColor(forge.card.MagicColor.fromName(col))
                            && !sh.isGeneric()) n++;
                }
                pips.put(col, pips.get(col) + n);
                most.put(col, Math.max(most.get(col), n));
            }
        }
        // colours no other untapped source makes come first, enough for the most demanding card that needs them: a
        // 1-mana Vivi split by hand pips came out red, and the planned Sigil of Sleep ({U}) couldn't be cast
        StringBuilder lands = new StringBuilder();
        for (Card c : player.getCardsIn(ZoneType.Battlefield)) {
            if (c != ma.getHostCard() && !c.isTapped()) lands.append(colorsProduced(c, player));
        }
        String first = "";
        int firstN = 0;
        for (String col : colors) {
            if (most.get(col) > 0 && lands.indexOf(col) < 0 && most.get(col) > firstN) { first = col; firstN = most.get(col); }
        }
        if (!first.isEmpty()) {
            int n = Math.min(firstN, amount);
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < n; i++) sb.append(sb.length() > 0 ? " " : "").append(first);
            if (amount - n > 0) {
                most.put(first, 0);
                pips.put(first, Math.max(0, pips.get(first) - n));
            }
            String rest = amount - n > 0 ? splitByPips(colors, pips, most, amount - n) : "";
            return rest.isEmpty() ? sb.toString() : sb + " " + rest;
        }
        return splitByPips(colors, pips, most, amount);
    }

    /** amount mana spread over colors in proportion to the pips in hand. */
    private static String splitByPips(String[] colors, Map<String, Integer> pips, Map<String, Integer> most, int amount) {
        int total = 0;
        for (int v : pips.values()) total += v;
        Map<String, Integer> share = new LinkedHashMap<>();
        int given = 0;
        for (String col : colors) {
            int n = total == 0 ? amount / colors.length : Math.round((float) amount * pips.get(col) / total);
            n = Math.max(n, Math.min(most.get(col), amount));
            share.put(col, n);
            given += n;
        }
        // fix rounding: trim from or add to the largest share
        String big = colors[0];
        for (String col : colors) if (share.get(col) > share.get(big)) big = col;
        share.put(big, Math.max(0, share.get(big) + amount - given));
        StringBuilder sb = new StringBuilder();
        for (String col : colors) {
            for (int i = 0; i < share.get(col); i++) sb.append(sb.length() > 0 ? " " : "").append(col);
        }
        return sb.toString();
    }

    private boolean activateBigMana(SpellAbility ma) {
        return activateBigMana(ma, null);
    }

    private boolean activateBigMana(SpellAbility ma, Card forCard) {
        try {
            if (!ma.checkRestrictions(player)) return false;  // a static ban (Linvala)
            int amount = AbilityUtils.calculateAmount(ma.getHostCard(), ma.getParamOrDefault("Amount", "1"), ma);
            AbilityManaPart mp = ma.getManaPart();
            if (mp != null && mp.isComboMana()) mp.setExpressChoice(comboSplit(ma, amount, forCard));
            if (!ComputerUtil.playNoStack(player, ma, getGame(), true)) return false;
            // Forge counts an activation only when it goes through the stack code; without this, "once each turn"
            // wasn't enforced and a smoke run activated Vivi three times in one turn.
            getGame().getStack().addAbilityActivatedThisTurn(ma, ma.getHostCard());
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    /** Forge's affordability check ignores Vivi's {0} mana: a play the other sources can't cover but they plus her
     *  mana can is kept on offer (autoBigMana makes her mana first when it's chosen). */
    private boolean payableWithBigMana(SpellAbility sa) {
        try {
            if (bigManaAbilities(player).isEmpty() || sa.getPayCosts() == null) return false;
            ManaCost mc = adjustedCost(sa);
            return mc != null && mc.getCMC() <= manaEstimate(player);
        } catch (RuntimeException e) {
            return false;
        }
    }

    /**
     * Forge's affordability check counts a {0} mana ability like Vivi's as a source, but its AI payment doesn't use it,
     * so a spell only Vivi's mana could pay for was offered, chosen, and failed at payment (Lightning Greaves, Izzet
     * Signet, Blasphemous Act). When the other sources can't cover the spell, make the mana first, split for it.
     */
    private void autoBigMana(SpellAbility sa) {
        autoBigMana(sa, 0);
    }

    /** Payable once the filters are activated from floating mana (autoFilterMana does it before payment): Forge's
     *  affordability check can't see that chain, so such plays were never offered. */
    private boolean payableWithFilters(SpellAbility sa) {
        try {
            ManaCost mc = adjustedCost(sa);
            if (mc == null) return false;
            int pool = player.getManaPool().totalMana(), plain = 0, filters = 0;
            for (Card c : player.getCardsIn(ZoneType.Battlefield)) {
                if (heldSources.contains(c)) continue;
                if (filterAbility(c, player) != null) filters++;
                else if (!c.isTapped()) plain += cardMana(c, player);
            }
            return filters > 0 && pool + plain > 0 && mc.getCMC() <= pool + plain + filters;
        } catch (RuntimeException e) {
            return false;
        }
    }

    /** A mana ability that costs mana and a tap (Izzet Signet: {1}, {T}: add {U}{R}). */
    private static SpellAbility filterAbility(Card c, Player p) {
        if (c.isTapped()) return null;
        for (SpellAbility ma : c.getManaAbilities()) {
            try {
                ma.setActivatingPlayer(p);
                Cost cost = ma.getPayCosts();
                if (cost != null && cost.hasTapCost() && cost.getCostMana() != null
                        && cost.getCostMana().getMana().getCMC() > 0 && ma.canPlay() && ma.checkRestrictions(p)) return ma;
            } catch (Exception ignored) { }
        }
        return null;
    }

    /**
     * Forge's payment can't pay a filter's cost from floating mana and then spend its output (ledger J: Jeska's Will,
     * Chaos Warp and Fire Magic failed at payment with 2 floating and an untapped Izzet Signet). When the floating mana
     * and the plain sources fall short, activate the filters first; Forge then pays from the pool.
     */
    private void autoFilterMana(int needed) {
        try {
            int direct = player.getManaPool().totalMana() - heldUntapped();
            List<SpellAbility> filters = new ArrayList<>();
            Set<Card> bigHosts = new HashSet<>();
            for (SpellAbility ma : bigManaAbilities(player)) bigHosts.add(ma.getHostCard());
            for (Card c : player.getCardsIn(ZoneType.Battlefield)) {
                if (bigHosts.contains(c) || heldSources.contains(c)) continue;
                SpellAbility f = filterAbility(c, player);
                if (f != null) filters.add(f);
                else if (!c.isTapped()) direct += cardMana(c, player);
            }
            for (SpellAbility f : filters) {
                if (needed <= direct) return;
                if (player.getManaPool().totalMana() + direct < 1) return;  // nothing to pay its cost with
                if (ComputerUtil.playNoStack(player, f, getGame(), true)) {
                    direct += 1;  // a filter nets one mana
                    System.out.println("[pilot] activated " + f.getHostCard().getName() + " before paying (filter mana)");
                }
            }
        } catch (RuntimeException e) {
            hookFailed("filter-mana", e);
        }
    }

    private void autoBigMana(SpellAbility sa, int extra) {
        try {
            ManaCost mc0 = sa.getPayCosts() == null ? null : sa.getPayCosts().getTotalMana();
            if (mc0 != null) {
                int x0 = sa.getXManaCostPaid() == null ? 0 : sa.getXManaCostPaid();
                autoFilterMana(mc0.getCMC() + mc0.countX() * x0 + extra);
            }
            List<SpellAbility> big = bigManaAbilities(player);
            if (big.isEmpty()) return;
            int bigTotal = 0;
            for (SpellAbility ma : big) bigTotal += AbilityUtils.calculateAmount(ma.getHostCard(), ma.getParamOrDefault("Amount", "1"), ma);
            ManaCost mc = sa.getPayCosts() == null ? null : sa.getPayCosts().getTotalMana();
            if (mc == null) return;
            int x = sa.getXManaCostPaid() == null ? 0 : sa.getXManaCostPaid();
            int needed = mc.getCMC() + mc.countX() * x + extra;
            if (needed <= manaEstimate(player) - bigTotal - heldUntapped() && coloursCovered(mc, big)) return;
            for (SpellAbility ma : big) {
                if (activateBigMana(ma, sa.getHostCard())) {
                    System.out.println("[pilot] made " + ma.getHostCard().getName() + "'s mana to pay for " + sa.getHostCard().getName());
                    return;
                }
            }
        } catch (RuntimeException e) {
            hookFailed("auto-mana", e);
        }
    }

    /** Whether our untapped sources other than the big mana abilities can make each coloured pip of mc (Ponder's {U}
     *  when the only blue source was Vivi: Forge counted her, its payment couldn't use her, the cast failed). */
    private boolean coloursCovered(ManaCost mc, List<SpellAbility> big) {
        Map<String, Integer> need = new LinkedHashMap<>(), have = new LinkedHashMap<>();
        for (ManaCostShard sh : mc) {
            if (sh.isGeneric()) continue;  // generic covers X
            for (String col : new String[] {"W", "U", "B", "R", "G"}) {
                if (sh.canBePaidWithManaOfColor(forge.card.MagicColor.fromName(col)) && !sh.isOr2Generic()) {
                    need.merge(col, 1, Integer::sum);
                    break;
                }
            }
        }
        if (need.isEmpty()) return true;
        IdentityHashMap<SpellAbility, Boolean> skip = new IdentityHashMap<>();
        for (SpellAbility b : big) skip.put(b, true);
        for (Card c : player.getCardsIn(ZoneType.Battlefield)) {
            if (c.isTapped()) continue;
            Set<String> cols = new HashSet<>();
            for (SpellAbility ma : c.getManaAbilities()) {
                if (skip.containsKey(ma) || ma.getManaPart() == null) continue;
                // a filter's colours (Izzet Signet) aren't Forge's to pay with: Sink into Stupor's {U}{U} failed with
                // the Signet counted as blue and Vivi's mana not made
                Cost fc = ma.getPayCosts();
                if (fc != null && fc.getCostMana() != null && fc.getCostMana().getMana().getCMC() > 0) continue;
                for (String col : need.keySet()) {
                    try {
                        if (ma.getManaPart().canProduce(col, ma)) cols.add(col);
                    } catch (RuntimeException ignored) { }
                }
            }
            for (String col : cols) have.merge(col, 1, Integer::sum);
        }
        // mana already floating counts (a filter activated before paying left its {U}{R} there, and Vivi's once-a-turn
        // mana was made early anyway)
        for (String col : need.keySet()) {
            try {
                int n = player.getManaPool().getAmountOfColor(forge.card.MagicColor.fromName(col));
                if (n > 0) have.merge(col, n, Integer::sum);
            } catch (RuntimeException ignored) { }
        }
        for (Map.Entry<String, Integer> e : need.entrySet()) {
            if (have.getOrDefault(e.getKey(), 0) < e.getValue()) return false;
        }
        return true;
    }

    // ------------------------------------------------------------------ held mana and X

    /** Mana sources held open until our next turn for one instant-speed play (heldFor), via Forge's own
     *  reservation set, which its payment code refuses to spend. */
    private final Set<Card> heldSources = new HashSet<>();
    private Card heldFor = null;
    private int holdTurn = -1;   // turn the hold was decided on (-1: not decided this turn)
    private int landsAtHold = -1;  // our land drops that turn when the hold was decided

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
            // the mana outside the hold must cover it: Forge's check passed Opt with only the held lands untapped
            // and Vivi's mana spent, and the payment failed
            ManaCost mc = adjustedCost(sa);
            if (mc != null && mc.getCMC() > manaEstimate(player) - heldUntapped()) return false;
            if (ComputerUtilMana.canPayManaCost(sa, player, 0, false)) return true;
            // Forge's check leaves out Vivi's {0} mana: the hold for An Offer You Can't Refuse was dropped for a
            // play her mana could pay, the lands paid instead, and no counter mana stayed open for three turns
            return mc != null && payableWithBigMana(sa);
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
            if (!c.isTapped() && !c.getManaAbilities().isEmpty() && !colorsProduced(c, player).isEmpty()
                    && !ourTurnOnly(c)) sources.add(c);
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
                ManaCost mc = adjustedCost(sa);
                List<Card> own = new ArrayList<>(sources);
                own.remove(sa.getHostCard());  // an ability that taps its own permanent can't also use it for mana
                List<Card> plan = coverCost(mc, own);
                if (plan == null || plan.isEmpty()) continue;
                String what = sa.getHostCard().getName() + ": " + StateView.clip(sa.toString(), 140);
                if (!seenText.add(what)) continue;
                StringBuilder names = new StringBuilder();
                for (Card c : plan) names.append(names.length() > 0 ? ", " : "").append(c.getName());
                out.add(new Hold("keep " + mc.getSimpleString() + " open (" + names + ") for " + what, sa.getHostCard(), plan));
            } catch (Exception ignored) { }
        }
        return out;
    }

    /** The mana cost after reductions: holds priced at the printed cost ignored Stormcatch Mentor's {1} off, so a
     *  Mana Sculpt hold wasn't offered when the lands could cover it. */
    private ManaCost adjustedCost(SpellAbility sa) {
        ManaCost printed = sa.getPayCosts() == null ? null : sa.getPayCosts().getTotalMana();
        try {
            sa.setActivatingPlayer(player);
            // reductions (Stormcatch Mentor) and increases (commander tax: Vivi offered at her printed 3 with 5 mana
            // and a tax of 4 failed at payment)
            ManaCost adj = ComputerUtilMana.calculateManaCost(sa.getPayCosts(), sa, player, true, 0, false).toManaCost();
            return adj != null ? adj : printed;
        } catch (RuntimeException e) {
            return printed;
        }
    }

    /** For an opponent's combat step with attackers at us and an instant or flash card in our hand: who attacks,
     *  blocked or not, and the damage that gets through (double strike counted). Null when there's nothing to ask. */
    private String oppCombatNote(boolean ourTurn, SpellAbilityStackInstance top, PhaseType phase) {
        try {
            forge.game.combat.Combat combat = getGame().getCombat();
            if (ourTurn || top != null || combat == null
                    || (phase != PhaseType.COMBAT_DECLARE_ATTACKERS && phase != PhaseType.COMBAT_DECLARE_BLOCKERS)) return null;
            boolean instant = false;
            for (Card c : player.getCardsIn(ZoneType.Hand)) {
                if (c.isInstant() || c.hasKeyword(forge.game.keyword.Keyword.FLASH)) { instant = true; break; }
            }
            if (!instant) return null;
            int through = 0, n = 0;
            List<String> parts = new ArrayList<>();
            for (Card a : combat.getAttackers()) {
                if (combat.getDefenderByAttacker(a) != player) continue;
                n++;
                int dmg = Math.max(0, a.getNetCombatDamage()) * (a.hasDoubleStrike() ? 2 : 1);
                boolean blocked = combat.isBlocked(a);
                if (!blocked) through += dmg;
                parts.add(a.getName() + " " + a.getNetPower() + "/" + a.getNetToughness()
                        + (a.hasDoubleStrike() ? " double strike" : "")
                        + (blocked ? " (blocked by " + combat.getBlockers(a).size() + ")" : " (unblocked)"));
            }
            if (n == 0) return null;
            return String.join("; ", parts) + ". Unblocked damage to us: " + through + "; our life is " + player.getLife();
        } catch (RuntimeException e) {
            return null;
        }
    }

    /** A mana source usable only during our turn (Vivi Ornitier): no use for mana held until the next one. */
    private static boolean ourTurnOnly(Card c) {
        for (SpellAbility ma : c.getManaAbilities()) {
            if (ma.getRestrictions() == null || !ma.getRestrictions().isPlayerTurn()) return false;
        }
        return true;
    }

    /** Mana our hold keeps open: what the held untapped sources can make (a Resonating Lute land makes two). */
    private int heldUntapped() {
        int n = 0;
        for (Card c : heldSources) if (c.isInZone(ZoneType.Battlefield) && !c.isTapped()) n += cardMana(c, player);
        return n;
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
    /** The name of the face a play uses: a double-faced card's back face was offered under the front's name, so
     *  "cast Birgi, God of Storytelling (from Hand): Harnfel, Horn of Bounty" took the memo's "Cast Birgi" tag and
     *  we cast the artifact instead of the creature. */
    static String faceName(SpellAbility sa) {
        Card host = sa.getHostCard();
        try {
            forge.game.card.CardState st = sa.getCardState();
            if (st != null && st.getName() != null && !st.getName().isEmpty()) return st.getName();
        } catch (RuntimeException ignored) { }
        return host.getName();
    }

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
        String face = faceName(sa);
        StringBuilder text = new StringBuilder(kind).append(' ').append(face)
                .append(" (from ").append(zone).append("): ")
                .append(face.equals(host.getName()) ? "" : "[the other face of " + host.getName() + "] ")
                .append(StateView.clip(body, 220));
        if (permission != null) text.append(" [uses ").append(permission).append(" for this turn]");
        // Jeska's Will and Expressive Iteration exile cards we may play only this turn: no MayPlayText, so the pass
        // guard never saw them and Sol Ring from exile was lost on a kill turn
        else if ("Exile".equals(zone) && sa.getMayPlay() != null) text.append(" [an exiled card we may play now: the permission may end this turn]");
        try {
            if (sa.usesTargeting() && !sa.getTargets().isEmpty()) {
                // an Aura spell's target is the permanent it enchants, not what its effect hits (Twisted Embrace
                // read "→ target: Muldrotha [ours]" and was cast once in 24 offers)
                boolean aura = sa.isSpell() && host.isAura();
                text.append(aura ? " → enchanting: " : " → target: ").append(describe(sa.getTargets().get(0)));
                // a counterspell aimed at a spell that can't be countered does nothing (a Hexing Squelcher copy on the
                // opponent's side made their spells uncounterable, and Negate went on one anyway)
                if (sa.getApi() == forge.game.ability.ApiType.Counter && sa.getTargets().get(0) instanceof SpellAbility t
                        && t.isSpell() && !t.isCounterableBy(sa)) {
                    text.append(" [THE TARGET CAN'T BE COUNTERED: this does nothing]");
                }
                if (aura) text.append(" (what its own effect hits is chosen when it resolves; see its text)");
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
        if (sidecar == null || !Ask.allowed("action")) return aiPick;
        try {
            Game game = getGame();
            PhaseHandler ph = game.getPhaseHandler();
            PhaseType phase = ph.getPhase();
            boolean ourTurn = ph.getPlayerTurn() == player;
            boolean main = ourTurn && (phase == PhaseType.MAIN1 || phase == PhaseType.MAIN2) && game.getStack().isEmpty();
            SpellAbilityStackInstance top = game.getStack().isEmpty() ? null : game.getStack().peek();
            boolean oppOnStack = top != null && top.getActivatingPlayer() != player;
            boolean endOfOppTurn = !ourTurn && phase == PhaseType.END_OF_TURN && game.getStack().isEmpty();
            // our own spell on top of the stack: the memo sometimes plans a response to it (An Offer You Can't Refuse
            // on our own Swiftfoot Boots for the triggers; a counterspell chain for storm), and we were never asked
            boolean ownSpellOnStack = top != null && top.getActivatingPlayer() == player && top.isSpell();
            int turn = ph.getTurn();
            if (ourTurn && holdTurn >= 0 && holdTurn != turn) {  // a hold lasts until our next turn
                releaseHold();
                holdTurn = -1;
            }
            // a land played since the hold was decided (a draw spell found it): decide again with the new mana. A hold
            // chosen before Faithless Looting drew lands made the planned Vivi cast read as spending held mana.
            if (ourTurn && holdTurn == turn && landsAtHold >= 0 && player.getLandsPlayedThisTurn() > landsAtHold) {
                releaseHold();
                holdTurn = -1;
                landsAtHold = -1;
            }
            clearForgeReservations();  // Forge's own evaluation just reserved sources for its pick's follow-ups
            if (aiPick != null && !aiPick.isEmpty() && aiPick.get(0) != null && !affordableUnderHold(aiPick.get(0))) {
                aiPick = null;  // Forge's play would spend the mana we're holding
            }
            if (aiPick != null && !aiPick.isEmpty() && aiPick.get(0) != null && cancelledThisTurn(aiPick.get(0))) {
                aiPick = null;  // an activation the pilot already cancelled at payment this turn
            }
            boolean forgeWantsToAct = aiPick != null && !aiPick.isEmpty() && aiPick.get(0) != null;
            // An opponent's combat at us, with an instant or flash card in hand: asked even when Forge's AI would do
            // nothing (the memo's "after attackers are declared, cast Slip Out the Back" window never came, and the
            // attack killed us). The note says who attacks, what is blocked and what gets through.
            String combatNote = oppCombatNote(ourTurn, top, phase);
            if (!main && !oppOnStack && !endOfOppTurn && !forgeWantsToAct && !ownSpellOnStack && combatNote == null) return aiPick;

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
            // Plays that would spend mana we're holding stay on offer, labelled, instead of vanishing: hidden, the
            // memo's main play could never be weighed against the hold (a hold for Lightning Bolt chosen before the
            // land drop removed Vivi from every option of a turn whose plan was to cast her). So note which plays need
            // the held mana, then lift the reservation while listing what can be played.
            IdentityHashMap<SpellAbility, Boolean> holdBreakers = new IdentityHashMap<>();
            if (!heldSources.isEmpty()) {
                for (SpellAbility sa : all) {
                    if (sa.getHostCard() != null && !sa.isManaAbility() && !affordableUnderHold(sa)) holdBreakers.put(sa, true);
                }
                AiCardMemory.clearMemorySet(player, AiCardMemory.MemorySet.HELD_MANA_SOURCES_FOR_NEXT_SPELL);
            }
            Map<SpellAbility, AiPlayDecision> declined = new LinkedHashMap<>();
            all = new ArrayList<>(all);
            all.sort((x, y) -> Integer.compare(scanRank(x), scanRank(y)));  // lands, then spells, then activations
            int scanned = 0;
            for (SpellAbility sa : all) {
                if (options.size() >= MAX_OPTIONS || System.currentTimeMillis() - t0 > SCAN_BUDGET_MS) break;
                scanned++;
                if (seen.containsKey(sa) || sa.getHostCard() == null || sa.isManaAbility()) continue;
                if (cancelledThisTurn(sa)) continue;
                AiPlayDecision d;
                try {
                    sa.setActivatingPlayer(player);
                    if (sa.isLandAbility()) {
                        if (!main || !sa.canPlay()) continue;
                        d = AiPlayDecision.WillPlay;
                    } else {
                        if (!sa.canPlay()) continue;
                        // an earlier option's evaluation may have reserved the mana this one needs (a chainable damage
                        // spell reserves the next spell's): each option is judged on the whole untapped board
                        clearReservationSets();
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
                    // an X Forge's AI stored on this spell in an earlier evaluation makes it look unaffordable now:
                    // Crackle with Power was offered in every main phase until the AI stored X=2, then never again
                    if (sa.costHasManaX()) sa.setXManaCostPaid(0);
                    // a stale target with ward (Sauron) made Snap look unaffordable; aim again below
                    if (sa.usesTargeting()) sa.resetTargets();
                    clearReservationSets();
                    if (!ComputerUtilCost.canPayCost(sa, player, false) && !payableWithBigMana(sa) && !payableWithFilters(sa)) continue;
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
            clearForgeReservations();  // drop what the evaluations reserved; put our hold back for Forge's payment
            IdentityHashMap<SpellAbility, Integer> manaOptions = new IdentityHashMap<>();
            if (main) {
                debugMana("main phase " + phase + " turn " + turn);
                for (SpellAbility ma : bigManaAbilities(player)) {
                    int amount = AbilityUtils.calculateAmount(ma.getHostCard(), ma.getParamOrDefault("Amount", "1"), ma);
                    String id = "o" + options.size();
                    options.put(id, Collections.singletonList(ma));
                    source.put(id, "mana");
                    manaOptions.put(ma, amount);
                }
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
                    : ownSpellOnStack ? "our own spell is on the stack, not yet resolved: respond to it only if the plan "
                            + "needs a play before it resolves"
                    : endOfOppTurn ? "end of an opponent's turn"
                    : combatNote != null ? "an opponent's combat against us, stack empty (" + phase + "): " + combatNote
                    : ownBeginning ? "our " + (phase == PhaseType.UPKEEP ? "upkeep" : "draw step")
                            + ", stack empty: mana spent now is not available in our main phase, where sorceries are also possible"
                    // whose turn: plays the memo timed for an opponent's combat went off in our own
                    : ourTurn ? "our turn, instant-speed window (" + phase + ")"
                    : "an opponent's turn, instant-speed window (" + phase + ")";
            Ask a = ask("action").context("window", window);
            if (scanned < all.size()) a.context("scan_truncated", (all.size() - scanned) + " of " + all.size()
                    + " abilities not scanned after " + (System.currentTimeMillis() - t0) + " ms");
            if (top != null) a.context("stack_top", StateView.clip(top.getStackDescription(), 200));
            a.question("action", "Which action do we take now?", forgeDefault);
            Map<String, List<GameEntity>> targetCands = new LinkedHashMap<>();
            Map<String, int[]> xRanges = new LinkedHashMap<>();
            Set<String> labels = new HashSet<>();
            for (Map.Entry<String, List<SpellAbility>> e : options.entrySet()) {
                SpellAbility sa = e.getValue().get(0);
                String kind = sa.isLandAbility() ? "play land" : sa.isSpell() ? "cast" : "activate";
                String text = manaOptions.containsKey(sa)
                        ? "activate " + sa.getHostCard().getName() + " (from Battlefield): add " + manaOptions.get(sa)
                          + " mana (" + sa.getManaPart().getComboColors(sa).trim().replace(" ", "/") + ") to our mana pool now,"
                          + " without tapping it. Once per turn. Mana left unspent empties at the end of this phase, so"
                          + " take this right before the plays that need it" + spendableWith(manaOptions.get(sa))
                        : actionLabel(sa, kind, source.get(e.getKey()), phase, ourTurn);
                if (holdBreakers.containsKey(sa) && heldFor != null) {
                    text += " [spends the mana held open for " + heldFor.getName() + "]";
                }
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
            // Ask about holding mana only once the land drop is made (or there is none to make): asked before it, a
            // hold was decided on a turn's worth of mana that didn't exist yet.
            boolean landOnOffer = false;
            for (List<SpellAbility> l : options.values()) {
                if (!l.isEmpty() && l.get(0) != null && l.get(0).isLandAbility()) landOnOffer = true;
            }
            List<Hold> holds = (ourTurn && main && holdTurn != turn && !landOnOffer) ? holdCandidates()
                    : Collections.emptyList();
            if (!holds.isEmpty()) {
                a.question("hold", "Keep mana open until our next turn for an instant-speed play? Held mana is not spent "
                        + "on anything else, so it costs development now.", "none");
                a.option("hold", "none", "hold nothing: use our mana freely");
                for (int i = 0; i < holds.size(); i++) a.option("hold", "h" + i, holds.get(i).text);
            }
            String skip = forgeWantsToAct ? " (this skips o0, the play Forge's AI would make now)" : "";
            int floating = player.getManaPool().totalMana();
            if (main && floating > 0) skip += ". The " + floating + " mana floating in our pool is lost if we pass now";
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
                landsAtHold = player.getLandsPlayedThisTurn();
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
            if (manaOptions.containsKey(sa)) {  // make the mana, then ask again with it in our pool
                if (activateBigMana(sa)) return chooseSpellAbilityToPlay();
                return aiPick;
            }
            if (holdBreakers.containsKey(sa)) {  // Jev chose to spend the held mana on this play: the hold is off
                releaseHold();
                holdTurn = -1;
            }
            if (sa.getHostCard() == heldFor) releaseHold();  // the play we held mana for: spend it now
            applyTarget(sa, targetCands.get(choice), ans.get("tgt_" + choice));
            String xa = ans.get("x_" + choice);
            int[] xr = xRanges.get(choice);
            if (xa != null && xa.startsWith("x") && xr != null) {
                Integer before = sa.getXManaCostPaid();
                int n = Integer.parseInt(xa.substring(1));
                sa.setXManaCostPaid(n);
                // Forge's check can't see mana it doesn't model (Resonating Lute's 2-mana lands): it put back Forge's X=3
                // when Jev chose X=5 for a lethal Crackle with Power. The pilot's own estimate is enough (a payment
                // that fails anyway is rescued).
                ManaCost xmc = sa.getPayCosts() == null ? null : sa.getPayCosts().getTotalMana();
                boolean ok = xr[2] > 0 ? ComputerUtilMana.canPayManaCost(sa, player, 0, false)
                        || (xmc != null && xmc.getCMC() + xr[2] * n <= manaEstimate(player) - heldUntapped())
                        : n <= xr[1];
                if (!ok) {
                    System.out.println("[pilot] X=" + n + " for " + sa.getHostCard().getName() + " not payable; X stays " + before);
                    sa.setXManaCostPaid(before);
                }
            }
            askMoreTargets(sa);
            if (sa.isSpell()) autoBigMana(sa);
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
        if (sidecar == null || attacker != player || !Ask.allowed("attack")) return;
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
        if (sidecar == null || defender != player || !Ask.allowed("block")) return;
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
                    + " combat damage; our life is " + player.getLife() + ". Blocks are asked one attacker at a time;"
                    + " each of our creatures can block only one attacker, so don't pick the same blocker twice.");
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
                        if (used.add(b)) {
                            combat.addBlocker(at, b);
                        } else {  // picked twice: this attacker gets Forge's blocker if it's still free, not silence
                            System.out.println("[pilot] blocker " + b.getName() + " picked for two attackers; "
                                    + at.getName() + " keeps Forge's block");
                            for (Card f : fb) if (used.add(f)) combat.addBlocker(at, f);
                        }
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
        if (sidecar == null || cost == null || sa == null || cost.getCostParts().isEmpty() || !Ask.allowed("confirm")) {
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
                    && host.getOwner() == player && Ask.allowed("confirm")) {
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
            boolean yes = ans == null ? forge : ans.equals("yes");
            confirmedYes = yes && !forge && sa != null ? sa.getHostCard() : null;  // a "yes" Forge wouldn't have given: its follow-up is ours
            return yes;
        } catch (RuntimeException e) {
            hookFailed("confirm", e);
            return forge;
        }
    }

    /** The host of a confirm the pilot turned to "yes" against Forge's "no" (Braids: "you may sacrifice ..."): Forge's
     *  own follow-up choice then declined it again, sacrificing nothing with one candidate. */
    private Card confirmedYes = null;

    @Override
    public <T extends GameEntity> T chooseSingleEntityForEffect(FCollectionView<T> optionList, DelayedReveal delayedReveal,
            SpellAbility sa, String title, boolean isOptional, Player targetedPlayer, Map<String, Object> params) {
        T forge = super.chooseSingleEntityForEffect(optionList, delayedReveal, sa, title, isOptional, targetedPlayer, params);
        // Forge's AI can answer nothing to a mandatory choice: its Curiosity aura logic rates any creature with 0 power
        // at -100, so an Ophidian Eye cast on Vivi (0/3 base) never picked its own target at resolution and stayed
        // stranded in the stack zone. A mandatory choice takes the first option instead.
        if (forge == null && !isOptional && !optionList.isEmpty()) forge = optionList.iterator().next();
        if (sidecar == null || optionList.size() < 2) return forge;
        // "untap up to N lands" (Snap, Frantic Search): asked blind as "choose one" over every tapped land on the table,
        // 3 of 6 untaps untapped nothing and one untapped an opponent's land. Untap our own, the most colours first.
        if (sa != null && "Untap".equals(String.valueOf(sa.getApi())) && sa.getActivatingPlayer() == player) {
            T best = null;
            int bestColours = -1;
            for (T e : optionList) {
                if (e instanceof Card c && c.getController() == player && c.isTapped()) {
                    int n = colorsProduced(c, player).length();
                    if (n > bestColours) { best = e; bestColours = n; }
                }
            }
            return best != null ? best : isOptional ? null : forge;
        }
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
        Card yesHost = confirmedYes;
        confirmedYes = null;
        boolean saidYes = yesHost != null && sa != null && sa.getHostCard() == yesHost;
        if (saidYes && min == 0 && (forge == null || forge.isEmpty()) && validTargets.size() == 1) {
            return new CardCollection(validTargets.get(0));  // we said yes; the one candidate goes
        }
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
            // a modal trigger ("choose up to one", Hullbreaker Horror) carries its target on the chosen mode, which
            // Forge's AI has already appended as a sub-ability; the root itself targets nothing
            while (sa != null && !sa.usesTargeting()) sa = sa.getSubAbility();
            if (sa == null) return;
            // what the card's other triggers on the stack already aim at: Hullbreaker's triggers repeated each other's
            // targets 4 times in one game, and 3 fizzled
            // ... and what our own spells there aim at: Sigil of Sleep's bounce took Chaos Warp's target and fizzled it
            Set<Object> pending = new HashSet<>();
            for (SpellAbilityStackInstance si : getGame().getStack()) {
                SpellAbility s2 = si.getSpellAbility();
                if (s2 == null || s2.getHostCard() == null) continue;
                boolean sibling = host != null && s2.getHostCard().getId() == host.getId();
                boolean ourSpell = si.getActivatingPlayer() == player && s2.isSpell();
                if (!sibling && !ourSpell) continue;
                if (s2 instanceof WrappedAbility w && w.getWrappedAbility() != null) s2 = w.getWrappedAbility();
                for (SpellAbility sub = s2; sub != null; sub = sub.getSubAbility()) {
                    if (sub.usesTargeting()) for (Object t : sub.getTargets()) if (t instanceof Card) pending.add(t);  // players take repeated pings fine
                }
            }
            Ask a = ask("trigger-target");
            List<GameEntity> cands = addTargetQuestion(a, "tgt",
                    "Our triggered ability from " + (host == null ? "?" : host.getName()) + " ("
                            + abilityText(wrapper, sa, 200) + "): what should it target?", sa, pending);
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
            if (sa.isCopied() && sa.isSpell() && sa.isMayChooseNewTargets()) {
                playCopy(sa);
                continue;
            }
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

    private java.lang.reflect.Method chooseNewTargetsForCopy;
    private final Map<String, List<String>> copyTargets = new HashMap<>();

    /**
     * A copy of our spell (storm, Twincast): placed like Forge's own AI places it, then each copy's target is asked.
     * Forge's AI aims every copy at the board as it stands, so all five Grapeshot copies went at one 1/1 token and four
     * fizzled; the question lists what earlier copies of the same spell already target.
     */
    private void playCopy(SpellAbility sa) {
        Game game = getGame();
        if (!sa.getHostCard().isInZone(ZoneType.Stack)) sa.setHostCard(game.getAction().moveToStack(sa.getHostCard(), sa));
        else game.getStackZone().add(sa.getHostCard());
        try {
            if (chooseNewTargetsForCopy == null) {
                chooseNewTargetsForCopy = PlayerControllerAi.class.getDeclaredMethod("chooseNewTargetsForCopy", SpellAbility.class);
                chooseNewTargetsForCopy.setAccessible(true);
            }
            chooseNewTargetsForCopy.invoke(this, sa);
            SpellAbility t = sa;
            while (t != null && !t.usesTargeting()) t = t.getSubAbility();
            if (t != null) {
                String name = sa.getHostCard().getName();
                List<String> earlier = copyTargets.computeIfAbsent(game.getPhaseHandler().getTurn() + "|" + name,
                        k -> new ArrayList<>());
                if (earlier.isEmpty()) {  // the original spell's own target counts too
                    for (SpellAbilityStackInstance si : game.getStack()) {
                        SpellAbility o = si.getSpellAbility();
                        if (o != null && !o.isCopied() && o.getHostCard() != null && name.equals(o.getHostCard().getName())) {
                            for (SpellAbility x = o; x != null; x = x.getSubAbility())
                                if (x.usesTargeting() && !x.getTargets().isEmpty()) earlier.add(String.valueOf(x.getTargets().get(0)));
                        }
                    }
                }
                Ask a = ask("trigger-target");
                List<GameEntity> cands = addTargetQuestion(a, "tgt", "A copy of our " + name + " ("
                        + abilityText(sa, t, 160) + ")" + (earlier.isEmpty() ? "" : "; earlier copies already target: "
                        + String.join(", ", earlier)) + ". What should this copy target?", t);
                if (cands != null) applyTarget(t, cands, a.send(sidecar).get("tgt"));
                if (!t.getTargets().isEmpty()) earlier.add(String.valueOf(t.getTargets().get(0)));
            }
        } catch (Exception e) {
            hookFailed("copy-target", e);
        }
        game.getStack().add(sa);
    }

    /**
     * "Up to N targets" (Crackle with Power at X=2): after X is set, ask target by target, starting from Forge's
     * picks. Forge's AI aimed a lethal X=2 Crackle at one opponent only when a second target would also have died.
     */
    private void askMoreTargets(SpellAbility sa) {
        try {
            if (sidecar == null || !sa.usesTargeting()) return;
            // targets Forge's AI set for its own X: Jev's X=1 Crackle with Power kept Forge's four targets for X=4 and
            // failed to target. Trim to the new maximum; with one target left, ask it.
            int maxT = sa.getMaxTargets();
            if (sa.getTargets().size() > maxT) {
                List<GameObject> keep = new ArrayList<>(sa.getTargets()).subList(0, Math.max(0, maxT));
                List<GameObject> kept = new ArrayList<>(keep);
                sa.resetTargets();
                for (GameObject o : kept) sa.getTargets().add(o);
            }
            if (maxT == 1) {
                Ask a = ask("action");
                List<GameEntity> cands = addTargetQuestion(a, "tgt_x", "Our " + sa.getHostCard().getName() + " ("
                        + abilityText(sa, sa, 160) + ") with X = 1: what should it target?", sa);
                if (cands != null) applyTarget(sa, cands, a.send(sidecar).get("tgt_x"));
                return;
            }
            if (maxT < 2) return;
            int max = Math.min(sa.getMaxTargets(), 5), min = sa.getMinTargets();
            List<GameEntity> all = new ArrayList<>(sa.getTargetRestrictions().getAllCandidates(sa));
            all.removeIf(e -> e instanceof Card c && c.isInZone(ZoneType.Stack) || !sa.canTarget(e));
            if (all.size() < 2) return;
            all.sort((x, y) -> Boolean.compare(owner(x) == player, owner(y) == player));
            if (all.size() > MAX_TARGETS) all = new ArrayList<>(all.subList(0, MAX_TARGETS));
            List<GameObject> forge = new ArrayList<>(sa.getTargets());
            List<GameEntity> chosen = new ArrayList<>();
            for (int i = 0; i < max; i++) {
                Ask a = ask("action");
                String qid = "tgt_m" + i;
                GameObject f = i < forge.size() ? forge.get(i) : null;
                List<GameEntity> left = new ArrayList<>(all);
                left.removeAll(chosen);
                if (left.isEmpty()) break;
                String def = f instanceof GameEntity ge && left.contains(ge) ? "t" + left.indexOf(ge) : (i >= min ? "none" : "t0");
                a.question(qid, "Our " + sa.getHostCard().getName() + " (" + abilityText(sa, sa, 160) + ") can have up to "
                        + max + " targets: target " + (i + 1) + (chosen.isEmpty() ? "" : " (already chosen: "
                        + chosen.stream().map(this::describe).reduce((x, y) -> x + "; " + y).orElse("") + ")") + "?", def);
                for (int j = 0; j < left.size(); j++) a.option(qid, "t" + j, describe(left.get(j)));
                if (i >= min) a.option(qid, "none", "no more targets");
                String ans = a.send(sidecar).get(qid);
                if (ans == null) ans = def;
                if (ans.equals("none")) break;
                chosen.add(left.get(Integer.parseInt(ans.substring(1))));
            }
            if (chosen.size() >= Math.max(min, 1)) {
                sa.resetTargets();
                for (GameEntity e : chosen) if (sa.canTarget(e)) sa.getTargets().add(e);
            }
        } catch (RuntimeException e) {
            hookFailed("multi-target", e);
        }
    }

    /**
     * Modal spells and triggers ("choose one", Tiered): the mode is asked. Forge's AI answered nothing for Fire Magic's
     * tiers and 3 of 4 Fire Magics resolved with no effect; a mandatory choice with no answer takes the first mode.
     */
    @Override
    public List<forge.game.spellability.AbilitySub> chooseModeForAbility(SpellAbility sa,
            List<forge.game.spellability.AbilitySub> possible, int min, int num, boolean allowRepeat) {
        List<forge.game.spellability.AbilitySub> forge = super.chooseModeForAbility(sa, possible, min, num, allowRepeat);
        if ((forge == null || forge.size() < min) && possible != null && !possible.isEmpty() && min >= 1) {
            forge = new ArrayList<>(possible.subList(0, Math.min(min, possible.size())));
        }
        if (sidecar != null && possible != null && num == 2 && possible.size() >= 2 && possible.size() <= 4
                && !allowRepeat && sa.getActivatingPlayer() == player) {
            List<forge.game.spellability.AbilitySub> two = chooseTwoModes(sa, possible, min, forge);
            if (two != null) return two;
        }
        if (sidecar == null || possible == null || possible.size() < 2 || num != 1 || sa.getActivatingPlayer() != player) {
            // one legal mode: no mode question, but its target is still ours to choose
            if (sidecar != null && sa.isSpell() && sa.getActivatingPlayer() == player && forge != null && forge.size() == 1) {
                aimMode(sa, forge.get(0), sa.getHostCard() != null ? sa.getHostCard().getName() : "spell");
                fundMode(sa, forge.get(0));
            }
            return forge;
        }
        // a mode with an additional cost we can't pay fails the whole cast (Fira with 2 mana for Fire Magic's {R}+{2})
        int base = sa.getPayCosts() != null && sa.getPayCosts().getTotalMana() != null ? sa.getPayCosts().getTotalMana().getCMC() : 0;
        List<forge.game.spellability.AbilitySub> ok = new ArrayList<>();
        for (forge.game.spellability.AbilitySub m : possible) {
            int extra = 0;
            try {
                if (m.hasParam("ModeCost")) extra = new forge.game.cost.Cost(m.getParam("ModeCost"), false).getTotalMana().getCMC();
            } catch (RuntimeException ignored) { }
            if (base + extra <= manaEstimate(player)) ok.add(m);
        }
        if (!ok.isEmpty() && ok.size() < possible.size()) {
            possible = ok;
            if (forge != null && !forge.isEmpty() && !ok.contains(forge.get(0))) forge = new ArrayList<>(ok.subList(0, 1));
            if (possible.size() < 2) return forge;
        }
        try {
            Ask a = ask("choose");
            forge.game.spellability.AbilitySub f = forge != null && !forge.isEmpty() ? forge.get(0) : null;
            String def = f == null ? "none" : "m" + possible.indexOf(f);
            String host = sa.getHostCard() != null ? sa.getHostCard().getName() : "a modal ability";
            a.question("mode", StateView.clip(host + ": choose " + (min == 0 ? "up to one mode" : "one mode"), 200), def);
            for (int i = 0; i < possible.size(); i++) {
                forge.game.spellability.AbilitySub m = possible.get(i);
                String cost = m.hasParam("ModeCost") ? " (additional cost {" + m.getParam("ModeCost") + "})" : "";
                a.option("mode", "m" + i, StateView.clip((m.hasParam("PrecostDesc") ? m.getParam("PrecostDesc") + ": " : "")
                        + m.getDescription().replace("CARDNAME", host) + cost, 200));
            }
            if (min == 0) a.option("mode", "none", "choose no mode");
            String ans = a.send(sidecar).get("mode");
            if (ans == null) return forge;
            if (ans.equals("none")) return min == 0 ? new ArrayList<>() : forge;
            forge.game.spellability.AbilitySub m = possible.get(Integer.parseInt(ans.substring(1)));
            if (sa.isSpell()) aimMode(sa, m, host);
            fundMode(sa, m);
            return new ArrayList<>(Collections.singletonList(m));
        } catch (RuntimeException e) {
            hookFailed("mode", e);
            return forge;
        }
    }

    /** "Choose one or both" (Jeska's Will with our commander out, Flame of Anor with a Wizard): the choice went to
     *  Forge, and 3 of 7 such casts went against the memo (7 {R} of Jeska's Will lost). Asked as one question over the
     *  single modes and the pairs; each chosen mode is then aimed and funded. */
    private List<forge.game.spellability.AbilitySub> chooseTwoModes(SpellAbility sa,
            List<forge.game.spellability.AbilitySub> possible, int min, List<forge.game.spellability.AbilitySub> forge) {
        try {
            String host = sa.getHostCard() != null ? sa.getHostCard().getName() : "a modal spell";
            List<List<forge.game.spellability.AbilitySub>> combos = new ArrayList<>();
            if (min <= 1) for (forge.game.spellability.AbilitySub m : possible) combos.add(Collections.singletonList(m));
            for (int i = 0; i < possible.size(); i++)
                for (int j = i + 1; j < possible.size(); j++) combos.add(java.util.Arrays.asList(possible.get(i), possible.get(j)));
            Ask a = ask("choose");
            String def = "c0";
            for (int k = 0; k < combos.size(); k++) {
                if (forge != null && forge.size() == combos.get(k).size() && forge.containsAll(combos.get(k))) def = "c" + k;
            }
            a.question("mode", StateView.clip(host + ": choose " + (min <= 1 ? "one or both" : "both") + " modes", 200), def);
            for (int k = 0; k < combos.size(); k++) {
                StringBuilder t = new StringBuilder();
                for (forge.game.spellability.AbilitySub m : combos.get(k)) {
                    t.append(t.length() > 0 ? " AND " : "").append(m.getDescription().replace("CARDNAME", host));
                }
                a.option("mode", "c" + k, StateView.clip(t.toString(), 240));
            }
            String ans = a.send(sidecar).get("mode");
            if (ans == null || !ans.startsWith("c")) return null;
            List<forge.game.spellability.AbilitySub> chosen = new ArrayList<>(combos.get(Integer.parseInt(ans.substring(1))));
            for (forge.game.spellability.AbilitySub m : chosen) {
                if (sa.isSpell()) aimMode(sa, m, host);
                fundMode(sa, m);
            }
            return chosen;
        } catch (RuntimeException e) {
            hookFailed("two-modes", e);
            return null;
        }
    }

    /** A mode's additional cost (Fira's {2}) wasn't counted when deciding to make Vivi's or a filter's mana before
     *  paying, and the cast failed at payment. The mode is chosen during the cast, so fund it here. */
    private void fundMode(SpellAbility sa, forge.game.spellability.AbilitySub m) {
        try {
            if (!sa.isSpell() || sa.getActivatingPlayer() != player || !m.hasParam("ModeCost")) return;
            int extra = new forge.game.cost.Cost(m.getParam("ModeCost"), false).getTotalMana().getCMC();
            if (extra > 0) autoBigMana(sa, extra);
        } catch (RuntimeException e) {
            hookFailed("mode-mana", e);
        }
    }

    /** Forge's AI aims only the mode it would pick; another mode is cast with no target and never reaches the stack
     *  ("Abrade - [Couldn't add to stack, failed to target]", 3 times in round 6). Ask the chosen mode's target;
     *  Forge's AI aims it if the answer can't be applied. The target is copied along with the mode. */
    private void aimMode(SpellAbility sa, forge.game.spellability.AbilitySub m, String host) {
        try {
            // asked even when Forge's AI already aimed the mode: all 3 Abrades of round 7 hit a target the memo didn't
            // name (Forge's aim is the default)
            if (!m.usesTargeting()) return;
            m.setActivatingPlayer(player);
            Ask t = ask("trigger-target");
            List<GameEntity> cands = addTargetQuestion(t, "tgt", "Our " + host + " (" + StateView.clip(
                    m.getDescription().replace("CARDNAME", host), 160) + "): what should it target?", m);
            if (cands != null) applyTarget(m, cands, t.send(sidecar).get("tgt"));
            if (m.getTargets().isEmpty() || !m.isTargetNumberValid()) getAi().doTrigger(m, true);
        } catch (RuntimeException e) {
            hookFailed("mode-target", e);
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
        // Forge's AI sorts validCards and removes its own picks from it: options built from it afterwards lacked
        // 1-3 cards in every multi-card discard of round 5, among them the memo's discard target
        CardCollection all = new CardCollection(validCards);
        CardCollection forge = super.chooseCardsToDiscardFrom(p, sa, validCards, min, max, visibleToChooser);
        if (sidecar == null || p != player || min != max || min < 1 || min > 3 || forge == null
                || forge.size() != min || all.size() <= min) {
            return forge;
        }
        try {
            // one question per card: Frantic Search and Faithless Looting discard two, and those went to Forge
            String src = sa != null && sa.getHostCard() != null ? sa.getHostCard().getName() : "an effect";
            CardCollection pool = new CardCollection(all), chosen = new CardCollection();
            for (int i = 0; i < min; i++) {
                Card def = null;
                for (Card f : forge) if (!chosen.contains(f)) { def = f; break; }
                String which = min == 1 ? "a card" : "card " + (i + 1) + " of " + min;
                Card c = pickCard("discard", src + " makes us discard " + which + ": which one?", pool, def, false);
                if (c == null) return forge;
                chosen.add(c);
                pool.remove(c);
            }
            return chosen;
        } catch (RuntimeException e) {
            hookFailed("discard", e);
            return forge;
        }
    }

    @Override
    public CardCollectionView chooseCardsToDiscardToMaximumHandSize(int numDiscard) {
        CardCollectionView forge = super.chooseCardsToDiscardToMaximumHandSize(numDiscard);
        if (sidecar == null || numDiscard < 1 || numDiscard > 4 || forge == null || forge.size() != numDiscard) return forge;
        try {
            // card by card: discards of more than one went to Forge (Shivan Reef, Veyran and Swan Song at once)
            CardCollection pool = new CardCollection(player.getCardsIn(ZoneType.Hand)), chosen = new CardCollection();
            for (int i = 0; i < numDiscard; i++) {
                Card def = null;
                for (Card f : forge) if (!chosen.contains(f)) { def = f; break; }
                String which = numDiscard == 1 ? "one card" : "card " + (i + 1) + " of " + numDiscard;
                Card c = pickCard("discard", "Cleanup: we are over the hand size limit and must discard " + which + ". Which?",
                        pool, def, false);
                if (c == null) return forge;
                chosen.add(c);
                pool.remove(c);
            }
            return chosen;
        } catch (RuntimeException e) {
            hookFailed("discard", e);
            return forge;
        }
    }

}
