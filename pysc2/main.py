#PySC2 game

from pysc2.env import run_loop
from pysc2.env.sc2_env import SC2Env, Agent, Bot, Race, Difficulty
from pysc2.lib import features
from absl import app

from agents.zerg_agents import SimpleZergAgent
from agents.terran_agents import SimpleTerranAgent

def main(unused_argv):
  # agent = SimpleZergAgent()
  agent1 = SimpleTerranAgent()
  agent2 = SimpleTerranAgent()

  try:
    players = [
      Agent(Race.terran),
      Agent(Race.terran)
    ]
    
    with SC2Env(
      map_name="Simple64",
      players= players,
      agent_interface_format=features.AgentInterfaceFormat(
        feature_dimensions=features.Dimensions(screen=84, minimap=64),
        use_feature_units=True 
      ),
      step_mul=16, # 150 APM
      visualize=True,
      disable_fog=True
    ) as env:
      run_loop.run_loop(agents=[agent1, agent2], env=env)
      
  except KeyboardInterrupt:
    pass

if __name__ == "__main__":
  app.run(main)