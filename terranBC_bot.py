import random

from sc2.constants import *
from sc2.bot_ai import BotAI
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
from sc2.data import Race, Difficulty
from sc2 import maps
from sc2.player import Bot, Computer
from sc2.main import run_game
from sc2.ids.upgrade_id import UpgradeId
from sc2.ids.unit_typeid import UnitTypeId

from typing import Set, List, Tuple

from enum import IntEnum

# The map always will be AcropolisLE
MAP = maps.get("AcropolisLE")

MAX_SCV_REPAIRING_PERCENTAGE: float = 0.2
WORKERS_PER_TOWNHALL: int = 16
HAVESTER_PER_TOWNHALL: int = 2

UPGRADE_ID_LIST: List[UpgradeId] = [
    UpgradeId.TERRANBUILDINGARMOR,
    UpgradeId.TERRANINFANTRYWEAPONSLEVEL1,
    UpgradeId.TERRANINFANTRYARMORSLEVEL1,
    UpgradeId.TERRANINFANTRYARMORSLEVEL2,
    UpgradeId.TERRANINFANTRYWEAPONSLEVEL2,
    UpgradeId.TERRANINFANTRYARMORSLEVEL3,
    UpgradeId.TERRANINFANTRYWEAPONSLEVEL3,
]

ARMY_UNITS = {
    UnitTypeId.HELLION: [8, 3],
    UnitTypeId.MARAUDER: [8, 3],
    UnitTypeId.SIEGETANK: [8, 3]
}

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


class EventTypes(IntEnum):
    EMPTY = 0,
    TRIGGER = 1,
    CONSTANT = 2,
    NEW_UNIT = 3,
    REMOVED_UNIT = 4,
    UPGRADE = 5


class TaskStatus(IntEnum):
    DONE = 1,
    RUNNING = 2,
    FAILED = 3


class States(IntEnum):
    IDLE = 1,
    WORKER_BUILDING = 2,
    WORKER_MINERALS = 3,
    WORKER_GAS = 4,
    ARMY_DEFENDING = 5


class Task(object):

    def __init__(self, start=None, step=None,
                 end=None, get_status=None):
        """
        Task class used for all game controls, added to a queue to take effect.
        :param start: Called once the first tick its added.
        :param step: Called once per tick.
        :param end: Called once the task has ended. This can be when completed, failed or any
                     other state that concludes the task.
        :param get_status: The returned state determine the lifetime of the task.
        """
        self.__start_func = start
        self.__step_func = step
        self.__end_func = end
        self.__get_status_func = get_status

        self.__start_called = False

    def on_start(self, bot):
        if self.__start_func:
            self.__start_func(bot)

    def on_step(self, bot):
        # Call start once
        if not self.__start_called:
            self.on_start(bot)
            self.__start_called = True

        if self.__step_func:
            self.__step_func(bot)

    def on_end(self, bot, status):
        if self.__end_func:
            self.__end_func(bot, status)

    def get_status(self, bot) -> TaskStatus:
        if self.__get_status_func:
            return self.__get_status_func(bot)
        return TaskStatus.RUNNING


class Event(object):
    """
    Not meant to be used by itself.
    Trigger event or Passive event should be used instead.
    """

    def __init__(self, on_event=None, get_status=None,
                 event_type: EventTypes = EventTypes.EMPTY, constant: bool = False, toggle: bool = False):
        self.__on_event = on_event
        self.__get_status = get_status
        self.event_type = event_type
        self.constant = constant
        self.toggle = toggle
        self.__has_toggled = False

    def trigger_event(self, bot, *args):
        """
        Call the on_event method associated with this event.
        :return:
        """
        if self.__on_event:
            self.__on_event(bot, *args)

    def should_trigger(self, bot):
        """
        Call the get_status method associated with this event.
        :return:
        """
        if self.__get_status:
            status = self.__get_status(bot)
            if status or (self.toggle and self.__has_toggled):
                self.__has_toggled = True
                return True
            return False
        return True


class PassiveEvent(Event):
    """
    Most commonly used on the global event dictionary.
    @param event_type should be any Event.TYPES except TRIGGER.
    """

    def __init__(self, on_event, event_type: EventTypes,
                 constant: bool = False, toggle: bool = False):
        Event.__init__(
            self,
            on_event=on_event,
            event_type=event_type,
            constant=constant,
            toggle=toggle)


class TriggerEvent(Event):
    """
    Most commonly used when registering a Task.
    """

    def __init__(self, trigger, constant: bool = False, toggle: bool = False):
        Event.__init__(
            self,
            get_status=trigger,
            event_type=EventTypes.TRIGGER,
            constant=constant,
            toggle=toggle)


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

    async def expand(self) -> None:
        """
        Check if can build another base
        """
        townhall_id = TOWNHALL_TYPE[self.race]

        if self.can_afford(
                townhall_id) and self.townhalls.first.surplus_harvesters > 0 and not self.already_pending(townhall_id):
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

    async def army_attack(self):
        for unit in self.army_units:
            if self.units(unit).amount > self.army_units[unit][0] and self.units(unit).amount > self.army_units[unit][1] and self.units(
                    unit).amount > self.army_units[unit][2] and self.units(unit).amount > self.army_units[unit][3]:
                for s in self.units(unit).idle:
                    self.do(s.attack(self.select_army_target(self.state)))

            elif self.units(unit).amount > self.army_units[unit][1]:
                if len(self.enemy_units) > 0:
                    for s in self.units(unit).idle:
                        self.do(s.attack(random.choice(self.enemy_units)))

    async def build_workers(self):
        worker_id = WORKER_TYPE[self.race]

        max_workers = self.townhalls.amount * WORKERS_PER_TOWNHALL
        workers_amount = self.supply_workers + self.already_pending(worker_id)
        if workers_amount < max_workers:
            for th in self.townhalls:
                if self.can_afford(worker_id) and th.is_idle:
                    self.do(th.train(worker_id))

    async def build_gas_harvester(self):
        harvester_id = VESPENE_GAS_HARVESTER_TYPE[self.race]
        max_harvester_amount = HAVESTER_PER_TOWNHALL * self.townhalls.amount

        for th in self.townhalls:
            if self.gas_buildings.amount < max_harvester_amount and self.can_afford(
                    harvester_id):
                vespene_geyser_list: Units = self.vespene_geyser.closer_than(
                    20, th)
                for vg in vespene_geyser_list:
                    if self.gas_buildings.filter(
                            lambda unit: unit.distance_to(vg) < 1):
                        break
                    worker: Unit = self.select_build_worker(vg.position)
                    if worker is None:
                        break

                    worker.build(harvester_id, vg)
                    break

        for gb in self.gas_buildings:
            if gb.assigned_harvesters < gb.ideal_harvesters:
                worker: Units = self.workers.closer_than(10, gb)
                if worker:
                    worker.random.gather(gb)

    def detect_changes(self) -> None:
        # --- Check all units ---
        # Extract the ids from the list of units and make them sets.
        units_by_id = {unit.tag: unit for unit in self.units + self.structures}
        units_ids = set(units_by_id.keys())
        # TODO: Add caching to reduce workload.
        world_units_ids = set(
            [unit.tag for unit in self.world["units"].keys()])

        # Calculate the difference and the intersection between the sets.
        new_ids = units_ids.difference(world_units_ids)

        # Add the new unit.
        for unit_id in new_ids:
            self.world["units"][units_by_id[unit_id]] = {
                "state": States.IDLE,
                "task_queue": [],
                "display_state": "",
                "target_location": None,
                "target_type": None
            }
            self.trigger_global_event(
                EventTypes.NEW_UNIT, units_by_id[unit_id])

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
                if (not item["trigger_event"].constant) or (
                        status != Task.STATUS.RUNNING):
                    self.global_queue.pop(self.global_queue.index(item))[
                        "task"].on_end(self, status)

    def select_army_target(self) -> None:
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

    def trigger_global_event(self, event_type, *args) -> None:
        """
        Used to trigger all events in the global event dictionary of a specified type.
        :param event_type:
        :param args:
        :return:
        """
        if event_type in self.global_events.keys():
            for event in self.global_events[event_type]:
                event.trigger_event(self, *args)


class TerranBot(BaseBot):

    async def on_start(self):
        self.army_units = {
            UnitTypeId.MARINE: [8, 3],
            UnitTypeId.HELLION: [8, 3],
            UnitTypeId.MARAUDER: [8, 3],
            UnitTypeId.SIEGETANK: [8, 3]
        }

        # Add global event to add engineeringbay logic to new engineeringbay.
        def engineeringbay_task_adder_logic(bot: TerranBot, unit: Unit):
            def engineeringbay_core_logic():
                if (len(UPGRADE_ID_LIST) == 0):
                    return

                upgrade_id = UPGRADE_ID_LIST[0]
                if self.research(upgrade_id):
                    UPGRADE_ID_LIST.pop(0)

            if unit.type_id == UnitTypeId.ENGINEERINGBAY:
                self.add_unit_task(
                    unit,
                    Task(step=bot.factory(engineeringbay_core_logic)),
                    TriggerEvent(lambda bot: self.structures.by_tag(unit.tag) and self.minerals > 100 and self.vespene > 100,
                                 constant=True,
                                 ),
                )

        self.register_global_event(
            PassiveEvent(
                engineeringbay_task_adder_logic,
                EventTypes.NEW_UNIT,
                True))

        if len(self.enemy_units) > 0:
            return random.choice(self.enemy_units)

        elif len(self.enemy_structures) > 0:
            return random.choice(self.enemy_structures)

        else:
            self.enemy_start_locations[0]

    async def on_step(self, iteration):
        self.iteration = iteration
        await self.expand()
        await self.distribute_workers()
        await self.build_workers()
        await self.build_depots()
        await self.build_gas_harvester()
        await self.build_barrack()
        await self.train_base_army()
        await self.build_engineering_bay()
        await self.build_factory()
        await self.build_starport()
        await self.build_starport_techlab()
        await self.build_fusion_core()
        await self.train_battlecruiser()
        await self.battlecruiser_attack()
        await self.army_attack()
        await self.reactive_depot()
        await self.build_tech_lab_barrack()
        await self.build_tech_lab_factory()

        self.detect_changes()
        self.exec_global_tasks()
        self.exec_all_units_tasks()

    async def build_depots(self):
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        else:
            cc: Unit = ccs.first

        if self.can_afford(UnitTypeId.SUPPLYDEPOT) and len(self.structures.of_type(
                {UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED})) < 3 and not self.already_pending(UnitTypeId.SUPPLYDEPOT):
            depot_placement_positions = self.main_base_ramp.corner_depots | {
                self.main_base_ramp.depot_in_middle}
            depots: Units = self.structures.of_type(
                {UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED})
            if depots:
                depot_placement_positions: Set[Point2] = {
                    d
                    for d in depot_placement_positions
                    if depots.closest_distance_to(d) > 1
                }
                if len(depot_placement_positions) == 0:
                    return
                # Choose any depot location
                target_depot_location: Point2 = depot_placement_positions.pop()
                workers: Units = self.workers.gathering
                if workers:  # if workers were found
                    worker: Unit = workers.random
                    self.do(
                        worker.build(
                            UnitTypeId.SUPPLYDEPOT,
                            target_depot_location))

        if (self.supply_left < 6 and self.supply_used >=
                14 and not self.already_pending(UnitTypeId.SUPPLYDEPOT)):
            if self.can_afford(UnitTypeId.SUPPLYDEPOT):
                workers: Units = self.workers.gathering
                if workers:  # if workers were found
                    worker: Unit = workers.random
                    depot_placement_positions = self.main_base_ramp.depot_in_middle
                    depot_position = await self.find_placement(UnitTypeId.SUPPLYDEPOT, near=depot_placement_positions)
                    self.do(
                        worker.build(
                            UnitTypeId.SUPPLYDEPOT,
                            depot_position))

    async def build_barrack(self):
        if self.townhalls:
            cc: Unit = self.townhalls.first
            if not self.structures(UnitTypeId.BARRACKS) and self.can_afford(
                    UnitTypeId.BARRACKS) and not self.already_pending(UnitTypeId.BARRACKS):
                await self.build(UnitTypeId.BARRACKS, near=cc.position.towards(self.game_info.map_center, 8), placement_step=6)

    async def train_base_army(self):
        for barrack in self.structures(UnitTypeId.BARRACKS):
            if self.can_afford(UnitTypeId.MARINE) and self.supply_army < 8 and not self.already_pending(
                    UnitTypeId.MARINE) and barrack.is_idle:
                self.train(UnitTypeId.MARINE, 1)

            elif self.can_afford(UnitTypeId.MARAUDER) and self.supply_army < 15 and not self.already_pending(UnitTypeId.MARAUDER) and barrack.is_idle and barrack.has_add_on:
                self.train(UnitTypeId.MARAUDER, 1)

        for factory in self.structures(UnitTypeId.FACTORY):
            if self.can_afford(UnitTypeId.HELLION) and self.supply_army < 12 and not self.already_pending(
                    UnitTypeId.HELLION):
                self.train(UnitTypeId.HELLION, 1)

            elif self.can_afford(UnitTypeId.SIEGETANK) and self.supply_army < 15 and not self.already_pending(UnitTypeId.SIEGETANK) and factory.has_add_on:
                self.train(UnitTypeId.SIEGETANK, 1)

    async def build_engineering_bay(self):
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        else:
            cc: Unit = ccs.first
        if self.can_afford(UnitTypeId.ENGINEERINGBAY) and not self.structures(
                UnitTypeId.ENGINEERINGBAY) and not self.already_pending(UnitTypeId.ENGINEERINGBAY):
            await self.build(UnitTypeId.ENGINEERINGBAY, near=cc.position.towards(self.game_info.map_center, 8))

    async def build_factory(self):
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        else:
            cc: Unit = ccs.first
        if self.structures(UnitTypeId.BARRACKS) and not self.structures(UnitTypeId.FACTORY) and self.can_afford(
                UnitTypeId.FACTORY) and not self.already_pending(UnitTypeId.FACTORY):
            await self.build(
                UnitTypeId.FACTORY,
                near=cc.position.towards(self.game_info.map_center, 8),
                placement_step=5
            )

    async def build_starport(self):
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        else:
            cc: Unit = ccs.first
        if self.structures(UnitTypeId.FACTORY) and len(self.structures(UnitTypeId.STARPORT)) < 2 and self.can_afford(
                UnitTypeId.STARPORT) and not self.already_pending(UnitTypeId.STARPORT):
            await self.build(UnitTypeId.STARPORT, near=cc.position.towards(self.game_info.map_center, 8), placement_step=5)

    async def build_fusion_core(self):
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        else:
            cc: Unit = ccs.first

        if self.structures(UnitTypeId.STARPORT) and not self.structures(UnitTypeId.FUSIONCORE) and self.can_afford(
                UnitTypeId.FUSIONCORE) and not self.already_pending(UnitTypeId.FUSIONCORE):
            await self.build(UnitTypeId.FUSIONCORE, near=cc.position.towards(self.game_info.map_center, 8), placement_step=5)

    async def train_battlecruiser(self):
        for sp in self.structures(UnitTypeId.STARPORT).idle:
            if sp.has_add_on and len(self.units(UnitTypeId.BATTLECRUISER)) < 8:
                if not self.can_afford(UnitTypeId.BATTLECRUISER):
                    break
                sp.train(UnitTypeId.BATTLECRUISER)

    async def starport_points_to_build_addon(self, sp_position: Point2) -> List[Point2]:
        """ Return all points that need to be checked when trying to build an addon. Returns 4 points. """
        addon_offset: Point2 = Point2((2.5, -0.5))
        addon_position: Point2 = sp_position + addon_offset
        addon_points = [
            (addon_position + Point2((x - 0.5, y - 0.5))).rounded
            for x in range(0, 2)
            for y in range(0, 2)
        ]
        return addon_points

    async def build_starport_techlab(self):
        sp: Unit
        for sp in self.structures(UnitTypeId.STARPORT).ready.idle:
            if not sp.has_add_on and self.can_afford(
                    UnitTypeId.STARPORTTECHLAB):
                addon_points = await self.starport_points_to_build_addon(sp.position)
                if all(
                    self.in_map_bounds(addon_point)
                    and self.in_placement_grid(addon_point)
                    and self.in_pathing_grid(addon_point)
                    for addon_point in addon_points
                ):
                    sp.build(UnitTypeId.STARPORTTECHLAB)

    async def battlecruiser_attack(self):
        bcs: Units = self.units(UnitTypeId.BATTLECRUISER)
        if bcs:
            target, target_is_enemy_unit = await self.battlecruiser_select_target()
            bc: Unit
            for bc in bcs:
                # Order the BC to attack-move the target
                if target_is_enemy_unit and (bc.is_idle or bc.is_moving):
                    bc.attack(target)
                # Order the BC to move to the target, and once the
                # battlecruiser_select_target returns an attack-target, change
                # it to attack-move
                elif bc.is_idle:
                    bc.move(target)

    async def reactive_depot(self):
        for depo in self.structures(UnitTypeId.SUPPLYDEPOT).ready:
            for unit in self.enemy_units:
                if unit.distance_to(depo) < 15:
                    break
            else:
                depo(AbilityId.MORPH_SUPPLYDEPOT_LOWER)

        # Lower depos when no enemies are nearby
        for depo in self.structures(UnitTypeId.SUPPLYDEPOTLOWERED).ready:
            for unit in self.enemy_units:
                if unit.distance_to(depo) < 10:
                    depo(AbilityId.MORPH_SUPPLYDEPOT_RAISE)
                    break

    def factory(self, func, *args):
        return lambda bot: func(*args)

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken):
        scvs = self.units(UnitTypeId.SCV)
        if len(scvs) == 0 or not unit.is_structure:
            return

        scvs_repairing = scvs.filter(lambda unit: unit.is_repairing)
        scvs_not_repairing = scvs.filter(lambda unit: not unit.is_repairing)

        repairing_percentage = len(scvs_repairing) / len(scvs)
        if repairing_percentage >= MAX_SCV_REPAIRING_PERCENTAGE:
            return

        if len(scvs_not_repairing) == 0:
            return

        scvs_not_repairing[0].repair(unit, queue=True)

    async def build_tech_lab_barrack(self):
        for barrack in self.structures(UnitTypeId.BARRACKS).ready.idle:
            if not barrack.has_add_on and self.can_afford(
                    UnitTypeId.BARRACKSTECHLAB):
                addon_points = await self.starport_points_to_build_addon(barrack.position)
                if all(
                    self.in_map_bounds(addon_point)
                    and self.in_placement_grid(addon_point)
                    and self.in_pathing_grid(addon_point)
                    for addon_point in addon_points
                ):
                    barrack.build(UnitTypeId.BARRACKSTECHLAB)

    async def battlecruiser_select_target(self) -> Tuple[Point2, bool]:
        targets: Units = self.enemy_units
        if targets:
            return targets.random.position, True

        """ Select an enemy target the units should attack. """
        targets: Units = self.enemy_structures
        if targets and len(self.units(UnitTypeId.BATTLECRUISER)) > 5:
            return targets.random.position, True

        if len(self.units(UnitTypeId.BATTLECRUISER)) > 5:
            return self.enemy_start_locations[0].position, False

        # retornar a posição de um cc randomico
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        else:
            cc: Unit = ccs.random

        return cc.position, False

    async def build_tech_lab_factory(self):
        for factory in self.structures(UnitTypeId.FACTORY).ready.idle:
            if not factory.has_add_on and self.can_afford(
                    UnitTypeId.FACTORYTECHLAB):
                addon_points = await self.starport_points_to_build_addon(factory.position)
                if all(
                    self.in_map_bounds(addon_point)
                    and self.in_placement_grid(addon_point)
                    and self.in_pathing_grid(addon_point)
                    for addon_point in addon_points
                ):
                    factory.build(UnitTypeId.FACTORYTECHLAB)


def main():
    players = [
        Bot(Race.Terran, TerranBot()),
        Computer(Race.Random, Difficulty.Hard)
    ]

    while True:
        run_game(
            map_settings=MAP,
            players=players,
        )


if __name__ == "__main__":
    main()
