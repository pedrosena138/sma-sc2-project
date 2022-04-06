from agents.ml_agents.base_agents import BaseAgent
from pysc2.lib import actions, units

import time
import random

# Builds
_BUILD_REFINERY_ID = actions.FUNCTIONS.Build_Refinery_screen.id
_BUILD_SUPPLY_DEPOT_ID = actions.FUNCTIONS.Build_SupplyDepot_screen.id
_BUILD_BARRACKS_ID = actions.FUNCTIONS.Build_Barracks_screen.id

# Functions
_HARVEST_GATHER_ID = actions.FUNCTIONS.Harvest_Gather_screen.id
_TRAIN_MARINE_QUICK_ID = actions.FUNCTIONS.Train_Marine_quick.id
_ATTACK_MINIMAP_ID = actions.FUNCTIONS.Attack_minimap.id
_SELECT_ARMY_ID = actions.FUNCTIONS.select_army.id

# Parameters
_BARRACKS_QUANTITY = 3
_BARRACKS_MINERALS = 150

_SUPPLY_DEPOTS_QUANTITY = 3
_SUPPLY_DEPOTS_MINERALS = 100

_MARINES_QUANTITY = 15


class SimpleTerranAgent(BaseAgent):
    def __init__(self):
        super(SimpleTerranAgent, self).__init__()
    
    def step(self, obs):
        try: 
            super(SimpleTerranAgent, self).step(obs)
            
            if obs.first():
                self.set_attack_coordinates(obs)
            
            minerals = obs.observation.player.minerals

            supply_depot_list = self.get_units_by_type(obs, units.Terran.SupplyDepot)
            if len(supply_depot_list) < _SUPPLY_DEPOTS_QUANTITY and minerals >= _SUPPLY_DEPOTS_MINERALS:
                if self.unit_type_is_selected(obs, units.Terran.SCV):
                    if self.can_do(obs, _BUILD_SUPPLY_DEPOT_ID):
                        position_x = random.randint(0, 83)
                        position_y = random.randint(0, 83)
                        return actions.FUNCTIONS.Build_SupplyDepot_screen("now", (position_x, position_y))
            
            barracks_list = self.get_units_by_type(obs, units.Terran.Barracks)
            if len(barracks_list) < _BARRACKS_QUANTITY and minerals >= _BARRACKS_MINERALS:
                if self.unit_type_is_selected(obs, units.Terran.SCV):
                    if self.can_do(obs, _BUILD_BARRACKS_ID):
                        position_x = random.randint(0, 83)
                        position_y = random.randint(0, 83)
                        return actions.FUNCTIONS.Build_Barracks_screen("now", (position_x, position_y))
            
            #Attack - Marines (15 group)
            marines_list = self.get_units_by_type(obs, units.Terran.Marine)
            if len(marines_list) >= _MARINES_QUANTITY:
                if self.unit_type_is_selected(obs, units.Terran.Marine):
                    if self.can_do(obs, _ATTACK_MINIMAP_ID):
                        return actions.FUNCTIONS.Attack_minimap("now", self.attack_coordinates)
                if self.can_do(obs, _SELECT_ARMY_ID):
                    return actions.FUNCTIONS.select_army("select")

            #Train Marines
            if len(barracks_list) >= _BARRACKS_QUANTITY:
                marines_list = self.get_units_by_type(obs, units.Terran.Marine)
                if len(marines_list) <= _MARINES_QUANTITY:
                    if self.can_do(obs, _TRAIN_MARINE_QUICK_ID):
                        return actions.FUNCTIONS.Train_Marine_quick("now")
                
                barrack = random.choice(barracks_list)
                return actions.FUNCTIONS.select_point("select_all_type", (barrack.x, barrack.y))

            build_refinery = self.build_refinery(obs)
            if build_refinery:
                return build_refinery

            recolectors_list = self.get_units_by_type(obs, units.Terran.SCV)
            if len(recolectors_list) > 0:
                scv = random.choice(recolectors_list)
                return actions.FUNCTIONS.select_point("select_all_type", (scv.x, scv.y))
            
            gas_refinery = self.gather_vespene_gas(obs)
            if gas_refinery:
                return gas_refinery
            
            return actions.FUNCTIONS.no_op()
        except ValueError:
            pass
    
    def build_refinery(self, obs):
        neutral_vespene_geysers = self.get_units_by_type(obs, units.Neutral.VespeneGeyser)
        refineries = self.get_units_by_type(obs, units.Terran.Refinery)

        if len(refineries) < 1 and len(neutral_vespene_geysers) > 0:
            if self.unit_type_is_selected(obs, units.Terran.SCV):
                if self.can_do(obs, _BUILD_REFINERY_ID):
                    geyser = random.choice(neutral_vespene_geysers)
                    return actions.FUNCTIONS.Build_Refinery_screen("now", (geyser.x, geyser.y))
            
            scv_list = self.get_units_by_type(obs, units.Terran.SCV)
            if len(scv_list) > 0:
                scv_position = random.choice(scv_list)
                return actions.FUNCTIONS.select_point("select_all_type", (scv_position.x, scv_position.y))
    
    def gather_vespene_gas(self, obs):
        refinery = self.get_units_by_type(obs, units.Terran.Refinery)
        if len(refinery) > 0:
            refinery = random.choice(refinery)
            if refinery['assigned_harvesters'] < 3:
                if self.unit_type_is_selected(obs, units.Terran.SCV):
                    if len(obs.observation.single_select) < 2 and len(obs.observation.multi_select) < 2:
                        if self.can_do(obs, _HARVEST_GATHER_ID):
                            return actions.FUNCTIONS.Harvest_Gather_screen("now", (refinery.x, refinery.y))
                
                scv_list = self.get_units_by_type(obs, units.Terran.SCV)
                if len(scv_list) > 0:
                    scv_position = random.choice(scv_list)
                    return actions.FUNCTIONS.select_point("select", (scv_position.x, scv_position.y))