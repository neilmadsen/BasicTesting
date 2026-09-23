package edh.pilot;

import forge.ai.AiCostDecision;
import forge.game.card.Card;
import forge.game.card.CardCollection;
import forge.game.card.CardLists;
import forge.game.cost.CostSacrifice;
import forge.game.cost.PaymentDecision;
import forge.game.player.Player;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;

/** Forge's cost payment, except the pilot picks which permanent to sacrifice (single sacrifices). */
final class PilotCostDecision extends AiCostDecision {
    private final PilotController pilot;

    PilotCostDecision(Player p, SpellAbility sa, boolean effect, PilotController pilot) {
        super(p, sa, effect);
        this.pilot = pilot;
    }

    @Override
    public PaymentDecision visit(CostSacrifice cost) {
        PaymentDecision forge = super.visit(cost);
        if (forge == null || cost.payCostFromSource() || "All".equals(cost.getAmount())
                || cost.getType().equals("OriginalHost") || forge.cards.size() != 1) {
            return forge;
        }
        CardCollection valid;
        try {
            valid = CardLists.getValidCards(player.getCardsIn(ZoneType.Battlefield), cost.getType().split(";"),
                    player, source, ability);
        } catch (Exception e) {
            return forge;
        }
        if (valid.size() < 2) return forge;
        Card chosen = pilot.pickCard("sacrifice-cost",
                "Paying a cost for " + source.getName() + ": which permanent do we sacrifice?",
                valid, forge.cards.get(0), false);
        return chosen == null ? forge : PaymentDecision.card(chosen);
    }
}
