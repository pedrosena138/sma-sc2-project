from pysc2.agents import base_agent
from pysc2.lib import actions, features


class BaseAgent(base_agent.BaseAgent):
  def __init__(self):
    super(BaseAgent, self).__init__()

    self.attack_coordinates = None
    self.safe_coordinates = None
  
  def unit_type_is_selected(self, obs, unit_type):
    if (len(obs.observation.single_select) > 0 and obs.observation.single_select[0].unit_type == unit_type):
      return True
    
    if (len(obs.observation.multi_select) > 0 and obs.observation.multi_select[0].unit_type == unit_type):
      return True
    
    return False
  
  def get_units_by_type(self, obs, unit_type):
    return [unit for unit in obs.observation.feature_units if unit.unit_type == unit_type]
  
  def can_do(self, obs, action):
    return action in obs.observation.available_actions

  def set_attack_coordinates(self, obs):
    """
    Scripted attack coordinates
    """

    #Check self postion
    player_y, player_x = (obs.observation.feature_minimap.player_relative == features.PlayerRelative.SELF).nonzero()
    x_mean = player_x.mean()
    y_mean = player_y.mean()
    
    # Check enemy position
    if x_mean <= 31 and y_mean <= 31:
      self.attack_coordinates = (49, 49)
      self.safe_coordinates = (12, 16)
    else:
      self.attack_coordinates = (12, 16)
      self.safe_coordinates = (49, 49)