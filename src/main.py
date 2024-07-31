from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.data import Race
from sc2.main import run_game
from sc2.player import Bot, Computer

# The map always will be AcropolisLE
_MAP = maps.get("AcropolisLE")


class WorkerRushBot(BotAI):
    async def on_step(self, iteration: int):
        if iteration == 0:
            for worker in self.workers:
                worker.attack(self.enemy_start_locations[0])


def main():
    players = [Bot(Race.Zerg, WorkerRushBot()), Computer(Race.Random)]

    while True:
        run_game(
            map_settings=_MAP,
            players=players,
            realtime=False,
        )


if __name__ == "__main__":
    main()
