from agents.ml_agents.base_agents import BaseAgent
from pysc2.lib import actions, units, features
import random

# Builds
_BUILD_SPAWNING_POOL_ID = actions.FUNCTIONS.Build_SpawningPool_screen.id

# Functions


# Parameters


class SimpleZergAgent(BaseAgent):
  def __init__(self):
    super(SimpleZergAgent, self).__init__()

  def step(self, obs):
    super(SimpleZergAgent, self).step(obs)

    if obs.first():
      self.set_attack_coordinates(obs)
    
    zerglings = self.get_units_by_type(obs, units.Zerg.Zergling)
    if len(zerglings) >= 10:
      if self.unit_type_is_selected(obs, units.Zerg.Zergling):
        if self.can_do(obs, actions.FUNCTIONS.Attack_minimap.id):
          return actions.FUNCTIONS.Attack_minimap("now", self.attack_coordinates)

      if self.can_do(obs, actions.FUNCTIONS.select_army.id):
        return actions.FUNCTIONS.select_army("select")

    #Build Spawningpool
    

      drones = self.get_units_by_type(obs, units.Zerg.Drone)
      if len(drones) > 0:
        drone = random.choice(drones)

        # select_all_type parameter here acts like a CTRL+click, so all Drones on the screen will be selected.
        return actions.FUNCTIONS.select_point("select_all_type", (drone.x, drone.y))
    
    if self.unit_type_is_selected(obs, units.Zerg.Larva):
      free_supply = (obs.observation.player.food_cap - obs.observation.player.food_used)
      if free_supply == 0:
        # Train Overlords  
        if self.can_do(obs, actions.FUNCTIONS.Train_Overlord_quick.id):
          return actions.FUNCTIONS.Train_Overlord_quick("now")

      # Train Zerlings  
      if self.can_do(obs, actions.FUNCTIONS.Train_Zergling_quick.id):
        return actions.FUNCTIONS.Train_Zergling_quick("now")
    
    larvae = self.get_units_by_type(obs, units.Zerg.Larva)
    if len(larvae) > 0:
      larva = random.choice(larvae)
      return actions.FUNCTIONS.select_point("select_all_type", (larva.x, larva.y))
    
    return actions.FUNCTIONS.no_op()
  
  def build_spawning_pool(self, obs):
    """
    Spawning Pool
    """

    spawning_pools_list = self.get_units_by_type(obs, units.Zerg.SpawningPool)
    if len(spawning_pools_list) == 0:
      if self.unit_type_is_selected(obs, units.Zerg.Drone):
        if self.can_do(obs, _BUILD_SPAWNING_POOL_ID):
          position_x = random.randint(0, 50)
          position_y = random.randint(0, 50)

          return actions.FUNCTIONS.Build_SpawningPool_screen("now", (position_x, position_y))
      
      drones_list = self.get_units_by_type(obs, units.Zerg.Drone)
      if len(drones_list) > 0:
        drone = random.choice(drones_list)

        return actions.FUNCTIONS.select_point("select_all_type", (drone.x, drone.y))