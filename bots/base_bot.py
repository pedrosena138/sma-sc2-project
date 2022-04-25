from sc2.bot_ai import BotAI
from sc2.ids.unit_typeid import UnitTypeId
from sc2.units import Units
from sc2.unit import Unit
from sc2.data import Race
from sc2.position import Point2
from helpers.task import Task
from helpers.enum import States, EventTypes, TaskStatus
from events.trigger_event import TriggerEvent
from events.passive_event import PassiveEvent
from typing import Set, Tuple

import random



TOWNHALL_TYPE: Set[UnitTypeId] = {
    Race.Protoss: UnitTypeId.NEXUS,
    Race.Terran: UnitTypeId.COMMANDCENTER,
    Race.Zerg: UnitTypeId.HATCHERY,
}

WORKER_TYPE: Set[UnitTypeId] = {
    Race.Protoss: UnitTypeId.PROBE,
    Race.Terran: UnitTypeId.SCV,
    Race.Zerg: UnitTypeId.DRONE,
}

VESPENE_GAS_HARVESTER_TYPE: Set[UnitTypeId] = {
    Race.Protoss: UnitTypeId.ASSIMILATOR,
    Race.Terran: UnitTypeId.REFINERY,
    Race.Zerg: UnitTypeId.EXTRACTOR,    
}

MAX_WORKERS: int = 65
HAVESTER_PER_TOWNHALL: int = 2
# ITERATIONS_PER_MINUTE: int = 165


class BaseBot(BotAI):
    def __init__(self):
        # Contains all the information available about the game world.
        self.world = { 
            "locations": {},
            "units": {},
        }
        self.global_queue = [] 
        self.global_events = {}
        self.army_units = {}
        self.WORKERS_PER_TOWNHALL: int = 16
        self.MIN_SUPPLY_AMOUNT: int = 2

    async def expand(self) -> None:
        """
        Check if can build another base
        """
        townhall_id = TOWNHALL_TYPE[self.race]
        if self.can_afford(townhall_id):
            planned_hatch_locations: Set[Point2] = {
                placeholder.position for placeholder in self.placeholders}
            my_structure_locations: Set[Point2] = {
                structure.position for structure in self.structures}
            enemy_structure_locations: Set[Point2] = {
                structure.position for structure in self.enemy_structures}
            blocked_locations: Set[Point2] = (
                my_structure_locations | planned_hatch_locations | enemy_structure_locations
            )

        
            location = await self.get_next_expansion()
            if location and location not in blocked_locations:
                workers: Units = self.workers.gathering
                
                # if workers were found
                if workers:  
                    worker: Unit = workers.random
                    self.do(worker.build(townhall_id, location))
    
    async def select_target(self) -> Tuple[Point2, bool]:
        targets: Units = {self.enemy_units, self.enemy_structures}
        if targets:
            return targets.random.position, True

    async def army_attack(self):
        for unit in self.army_units:
            if self.units(unit).amount > self.army_units[unit][0] and self.units(unit).amount > self.army_units[unit][1] and self.units(unit).amount > self.army_units[unit][2] and self.units(unit).amount > self.army_units[unit][3]:
                for s in self.units(unit).idle:
                    self.do(s.attack(self.select_army_target(self.state)))

            elif self.units(unit).amount > self.army_units[unit][1]:
                if len(self.enemy_units) > 0:
                    for s in self.units(unit).idle:
                        self.do(s.attack(random.choice(self.enemy_units)))

    def build_gas_havester(self) -> None:
        townhall_id = TOWNHALL_TYPE[self.race]
        vespene_gas_havester_id = VESPENE_GAS_HARVESTER_TYPE[self.race]

        for hq in self.townhalls(townhall_id):
            if self.gas_buildings.amount < HAVESTER_PER_TOWNHALL*len(self.townhalls(townhall_id)) and self.can_afford(vespene_gas_havester_id):
                vespene_geyser_list: Units = self.vespene_geyser.closer_than(20, hq)
                for vespene_geyser in vespene_geyser_list:
                    if self.gas_buildings.filter(lambda unit: unit.distance_to(vespene_geyser) < 1):
                        break
                    worker: Unit = self.select_build_worker(vespene_geyser.position)
                    if worker is None: 
                        break

                    worker.build(vespene_gas_havester_id, vespene_geyser)
                    break

        for havester in self.gas_buildings:
            if havester.assigned_harvesters < havester.ideal_harvesters:
                worker: Units = self.workers.closer_than(10, havester)
                if worker:
                    worker.random.gather(havester)
                    
    def detect_changes(self) -> None:
        # --- Check all units ---
        # Extract the ids from the list of units and make them sets.
        units_by_id = {unit.tag: unit for unit in self.units + self.structures}
        units_ids = set(units_by_id.keys())
        world_units_ids = set([unit.tag for unit in self.world["units"].keys()])  # TODO: Add caching to reduce workload.

        # Calculate the difference and the intersection between the sets.
        new_ids = units_ids.difference(world_units_ids)
        removed_ids = world_units_ids.difference(units_ids)
        comm_ids = units_ids.intersection(world_units_ids)

        # Add the new unit.
        for unit_id in new_ids:
            self.world["units"][units_by_id[unit_id]] = {
                "state": States.IDLE,
                "task_queue": [],
                "display_state": "",
                "target_location": None,
                "target_type": None
            }
            self.__trigger_global_event(EventTypes.NEW_UNIT, units_by_id[unit_id])
            
            # Remove the missing unit.
            for unit_id in removed_ids:
                # Trigger global event for removed unit and pop the unit from the registry.
                # self.trigger_global_event(EventTypes.REMOVED_UNIT, self.world["units"].pop(units_by_id[unit_id]))  # TODO: Why does this crash?
                pass

            # Check if states are correct.
            for unit_id in comm_ids:
                # TODO: Add check for if the state is correct.
                unit = units_by_id[unit_id]

                # Check if workers are done building. # TODO: Think this is the root of a problem
                """  
                if self.get_unit_state(unit) == States.WORKER_BUILDING and unit.is_idle:
                    self.set_unit_state(unit, States.IDLE)
                """
    
    def exec_all_units_tasks(self) -> None:
        for unit in self.units + self.structures:
            if self.world["units"][unit]["task_queue"]:
                item = self.world["units"][unit]["task_queue"][0]
                self.world["units"][unit]["task_queue"].sort(
                    key=lambda i: i["priority"], reverse=True
                )

                if item["trigger_event"].should_trigger(self):
                    item["task"].on_step(self)
                    status = item["task"].get_status(self)
                    if (not item["trigger_event"].constant) or (
                        status != TaskStatus.RUNNING
                    ):
                        self.world["units"][unit]["task_queue"].pop(0)["task"].on_end(
                            self, status
                        )
    
    def exec_global_tasks(self) -> None:
        self.global_queue.sort(key=lambda i: i["priority"], reverse=True)

        for i, item in enumerate(self.global_queue[:]):
            if item["trigger_event"].should_trigger(self):
                item["task"].on_step(self)
                status = item["task"].get_status(self)
                if (not item["trigger_event"].constant) or (status != Task.STATUS.RUNNING):
                    self.global_queue.pop(self.global_queue.index(item))["task"].on_end(self, status)
    
    def select_army_target(self,state) -> None:
        if len(self.enemy_units) > 0:
            return random.choice(self.enemy_units)
        elif len(self.enemy_structures) > 0:
            return random.choice(self.enemy_structures)
        else: 
            self.enemy_start_locations[0]
    
    def add_unit_task(
        self,
        unit: Unit,
        task: Task,
        trigger_event: TriggerEvent,
        priority: int = 0,
        tag: str = "",
    ) -> None:
        self.world["units"][unit]["task_queue"].append(
            {
                "priority": priority,
                "task": task,
                "trigger_event": trigger_event,
                "tag": tag,
                "time": self.time,
            }
        )

    def register_global_event(self, event: PassiveEvent) -> None:
        if event.event_type in self.global_events.keys():
            self.global_events[event.event_type].append(event)
        else:
            self.global_events[event.event_type] = [event]

    def __trigger_global_event(self, event_type, *args) -> None:
        """
        Used to trigger all events in the global event dictionary of a specified type.
        :param event_type:
        :param args:
        :return:
        """
        if event_type in self.global_events.keys():
            for event in self.global_events[event_type]:
                event.trigger_event(self, *args)
