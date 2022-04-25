from sc2 import maps
from sc2.player import Bot, Computer
from sc2.main import run_game
from sc2.data import Race, Difficulty
from bots.zerg_bot import BaseZergBot, BroodlordZergBot
from bots.terran_bot import TerranBot
from bots.base_bot import BaseBot

# The map always will be AcropolisLE
_MAP = maps.get("AcropolisLE")


def main():
    players = [
        Bot(Race.Terran, TerranBot()),
        Computer(Race.Random)
    ]

    while True:
        run_game(
            map_settings=_MAP,
            players=players,
            realtime=False,
        )


if __name__ == "__main__":
    main()
