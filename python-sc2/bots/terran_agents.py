from sc2.bot_ai import BotAI
from sc2.ids.unit_typeid import UnitTypeId



class BaseAgent(BotAI):

  async def on_step(self, iteration: int):
    if self.townhalls: 
      nexus = self.townhalls.random
    else:
      if self.can_afford(UnitTypeId.SUPPLYDEPOT):
        await self.expand_now()