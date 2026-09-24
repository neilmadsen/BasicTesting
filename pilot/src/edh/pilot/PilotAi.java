package edh.pilot;

import forge.ai.AiController;
import forge.game.Game;
import forge.game.card.CardCollectionView;
import forge.game.player.Player;
import forge.game.spellability.SpellAbility;

/**
 * Forge's AI brain, except that sacrifice costs we pay go to the pilot.
 *
 * Forge's AI pays its own costs with a fresh AiCostDecision (ComputerUtil.handlePlayingSpellAbility), never
 * through the controller's getCostDecisionMaker, so PilotCostDecision alone never fired for our own plays:
 * Barrin and Claws of Gix ate lands, Sol Ring and Kaya's Ghostform on Forge's pick. Both paths end here.
 */
final class PilotAi extends AiController {
    private final PilotController pilot;

    PilotAi(Player p, Game game, PilotController pilot) {
        super(p, game);
        this.pilot = pilot;
    }

    @Override
    public CardCollectionView chooseSacrificeType(String type, SpellAbility ability, boolean effect, int amount,
                                                  CardCollectionView exclude) {
        CardCollectionView forge = super.chooseSacrificeType(type, ability, effect, amount, exclude);
        return pilot.pickSacrificeCost(type, ability, amount, exclude, forge);
    }
}
