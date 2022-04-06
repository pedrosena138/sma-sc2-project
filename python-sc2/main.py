from sc2 import maps
from sc2.player import Bot, Computer
from sc2.main import run_game
from sc2.data import Race, Difficulty
from bots.zerg_bot import ExpandZergBot

# The map always will be AcropolisLE
_MAP = maps.get("AcropolisLE")

def main():
  players = [
    Bot(Race.Zerg, ExpandZergBot()),
    Computer(Race.Terran, Difficulty.VeryEasy)
  ]
  
  while True:
    run_game(
      map_settings=_MAP, 
      players=players, 
      realtime=False
    )

if __name__ == "__main__":
  main()