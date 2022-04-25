import random

from sc2.constants import *
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from sc2.ids.upgrade_id import UpgradeId
from sc2.ids.unit_typeid import UnitTypeId

from typing import List, Tuple
from helpers.task import Task
from events.trigger_event import TriggerEvent
from events.passive_event import PassiveEvent
from helpers.enum import EventTypes
from .base_bot import BaseBot

MAX_SCV_REPAIRING_PERCENTAGE = 0.2
MAX_WORKERS: int = 65

upgrade_ids = [
    UpgradeId.TERRANBUILDINGARMOR,
    UpgradeId.TERRANINFANTRYWEAPONSLEVEL1,
    UpgradeId.TERRANINFANTRYARMORSLEVEL1,
    UpgradeId.TERRANINFANTRYARMORSLEVEL2,
    UpgradeId.TERRANINFANTRYWEAPONSLEVEL2,
    UpgradeId.TERRANINFANTRYARMORSLEVEL3,
    UpgradeId.TERRANINFANTRYWEAPONSLEVEL3,
]

class TerranBot(BaseBot):

    async def on_start(self):
        self.army_units =  {
            UnitTypeId.MARINE: [8, 3],
            UnitTypeId.HELLION: [8, 3],
            UnitTypeId.MARAUDER: [8,3],
            UnitTypeId.SIEGETANK: [8,3]
        }
         # Add global event to add engineeringbay logic to new engineeringbay.
        def engineeringbay_task_adder_logic(bot: TerranBot, unit: Unit):
            def engineeringbay_core_logic():
                if (len(upgrade_ids) == 0):
                    return

                upgrade_id = upgrade_ids[0]
                if self.research(upgrade_id):
                    upgrade_ids.pop(0)

            if unit.type_id == UnitTypeId.ENGINEERINGBAY:
                self.add_unit_task(
                    unit,
                    Task(step=bot.factory(engineeringbay_core_logic)),
                    TriggerEvent(lambda bot: self.structures.by_tag(unit.tag) and self.minerals > 100 and self.vespene > 100,
                        constant=True,
                    ),
                )
        
        self.register_global_event(PassiveEvent(engineeringbay_task_adder_logic, EventTypes.NEW_UNIT, True))

        if len(self.enemy_units) > 0:
            return random.choice(self.enemy_units)

        elif len(self.enemy_structures) > 0:
            return random.choice(self.enemy_structures)

        else: 
            self.enemy_start_locations[0]

    async def on_step(self, iteration):
        self.iteration = iteration
        await self.distribute_workers()
        await self.build_workers()
        await self.build_depots()
        await self.build_refinary()
        await self.build_barrack()
        await self.build_base_army()
        await self.build_engineering_bay()
        await self.build_factory()
        await self.build_starport()
        await self.build_starport_techlab()
        await self.build_fusion_core()
        await self.train_BC()
        await self.BC_attack()
        await self.army_attack()
        await self.expand()
        await self.reactive_depot()
        await self.build_tech_lab_barrack()
        await self.build_tech_lab_factory()

        self.detect_changes()
        self.exec_global_tasks()
        self.exec_all_units_tasks()
        
        barracks_placement_position = self.main_base_ramp.barracks_correct_placement
        worker = self.select_build_worker(barracks_placement_position)

        if (
            worker
            and (
                await self.can_place(UnitTypeId.BARRACKS, [barracks_placement_position])
            )[0]
        ):
            worker.build(UnitTypeId.BARRACKS, barracks_placement_position)

    async def build_workers(self):
        if len(self.townhalls(UnitTypeId.COMMANDCENTER))*16 > len(self.units(UnitTypeId.SCV)):
            if len(self.units(UnitTypeId.SCV)) < MAX_WORKERS:
                for cc in self.townhalls(UnitTypeId.COMMANDCENTER):
                    if self.can_afford(UnitTypeId.SCV) and cc.is_idle:
                        self.do(cc.train(UnitTypeId.SCV))

    async def build_depots(self):
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        else:
            cc: Unit = ccs.first

        if self.can_afford(UnitTypeId.SUPPLYDEPOT) and len(self.structures.of_type({UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED})) < 3 and not self.already_pending(UnitTypeId.SUPPLYDEPOT):
            depot_placement_positions = self.main_base_ramp.corner_depots | {self.main_base_ramp.depot_in_middle}
            depots: Units = self.structures.of_type({UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED})
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
                    self.do(worker.build(UnitTypeId.SUPPLYDEPOT, target_depot_location))

        if (
            self.supply_left < 6
            and self.supply_used >= 14
            and not self.already_pending(UnitTypeId.SUPPLYDEPOT)
        ):
            if self.can_afford(UnitTypeId.SUPPLYDEPOT):
                workers: Units = self.workers.gathering
                if workers:  # if workers were found
                    worker: Unit = workers.random
                    depot_placement_positions = self.main_base_ramp.depot_in_middle
                    depot_position = await self.find_placement(UnitTypeId.SUPPLYDEPOT, near=depot_placement_positions)
                    self.do(worker.build(UnitTypeId.SUPPLYDEPOT, depot_position))
    
    async def build_refinary(self):
        for cc in self.townhalls(UnitTypeId.COMMANDCENTER):
            if self.gas_buildings.amount < 2*len(self.townhalls(UnitTypeId.COMMANDCENTER)) and self.can_afford(UnitTypeId.REFINERY):
                vgs: Units = self.vespene_geyser.closer_than(20, cc)
                for vg in vgs:
                    if self.gas_buildings.filter(lambda unit: unit.distance_to(vg) < 1):
                        break
                    worker: Unit = self.select_build_worker(vg.position)
                    if worker is None: 
                        break

                    worker.build(UnitTypeId.REFINERY, vg)
                    break
        for refinery in self.gas_buildings:
            if refinery.assigned_harvesters < refinery.ideal_harvesters:
                worker: Units = self.workers.closer_than(10, refinery)
                if worker:
                    worker.random.gather(refinery)

    async def build_barrack(self):
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        else:
            cc: Unit = ccs.first
        if not self.structures(UnitTypeId.BARRACKS) and self.can_afford(UnitTypeId.BARRACKS) and not self.already_pending(UnitTypeId.BARRACKS):
            await self.build(UnitTypeId.BARRACKS, near=cc.position.towards(self.game_info.map_center, 8), placement_step=6)

    async def build_base_army(self):
        for barrack in self.structures(UnitTypeId.BARRACKS):
            if  self.can_afford(UnitTypeId.MARINE) and self.supply_army < 8 and not self.already_pending(UnitTypeId.MARINE) and barrack.is_idle:
                self.train(UnitTypeId.MARINE, 1)

            elif self.can_afford(UnitTypeId.MARAUDER) and self.supply_army < 15 and not self.already_pending(UnitTypeId.MARAUDER) and barrack.is_idle and barrack.has_add_on:
                self.train(UnitTypeId.MARAUDER, 1)

        for factory in self.structures(UnitTypeId.FACTORY):
            if  self.can_afford(UnitTypeId.HELLION) and self.supply_army < 12 and not self.already_pending(UnitTypeId.HELLION):
                self.train(UnitTypeId.HELLION, 1)

            elif self.can_afford(UnitTypeId.SIEGETANK) and self.supply_army < 15 and not self.already_pending(UnitTypeId.SIEGETANK) and factory.has_add_on:
                self.train(UnitTypeId.SIEGETANK, 1)

    async def build_engineering_bay(self):
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        else:
            cc: Unit = ccs.first
        if self.can_afford(UnitTypeId.ENGINEERINGBAY) and not self.structures(UnitTypeId.ENGINEERINGBAY) and not self.already_pending(UnitTypeId.ENGINEERINGBAY):
            await self.build(UnitTypeId.ENGINEERINGBAY, near=cc.position.towards(self.game_info.map_center, 8))

    async def build_factory(self):
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        else:
            cc: Unit = ccs.first
        if self.structures(UnitTypeId.BARRACKS) and not self.structures(UnitTypeId.FACTORY) and self.can_afford(UnitTypeId.FACTORY) and not self.already_pending(UnitTypeId.FACTORY):
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
        if self.structures(UnitTypeId.FACTORY) and len(self.structures(UnitTypeId.STARPORT)) < 2 and self.can_afford(UnitTypeId.STARPORT) and not self.already_pending(UnitTypeId.STARPORT):
            await self.build(UnitTypeId.STARPORT, near=cc.position.towards(self.game_info.map_center, 8), placement_step=5)

    async def build_fusion_core(self):
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        else:
            cc: Unit = ccs.first
        
        if self.structures(UnitTypeId.STARPORT) and not self.structures(UnitTypeId.FUSIONCORE) and self.can_afford(UnitTypeId.FUSIONCORE) and not self.already_pending(UnitTypeId.FUSIONCORE):
            await self.build(UnitTypeId.FUSIONCORE, near=cc.position.towards(self.game_info.map_center, 8), placement_step=5)

    async def train_BC(self):
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
            if not sp.has_add_on and self.can_afford(UnitTypeId.STARPORTTECHLAB):
                addon_points = await self.starport_points_to_build_addon(sp.position)
                if all(
                    self.in_map_bounds(addon_point)
                    and self.in_placement_grid(addon_point)
                    and self.in_pathing_grid(addon_point)
                    for addon_point in addon_points
                ):
                    sp.build(UnitTypeId.STARPORTTECHLAB)

    async def BC_attack(self):
        bcs: Units = self.units(UnitTypeId.BATTLECRUISER)
        if bcs:
            target, target_is_enemy_unit = await self.select_target()
            bc: Unit
            for bc in bcs:
                # Order the BC to attack-move the target
                if target_is_enemy_unit and (bc.is_idle or bc.is_moving):
                    bc.attack(target)
                # Order the BC to move to the target, and once the select_target returns an attack-target, change it to attack-move
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
            if not barrack.has_add_on and self.can_afford(UnitTypeId.BARRACKSTECHLAB):
                addon_points = await self.starport_points_to_build_addon(barrack.position)
                if all(
                    self.in_map_bounds(addon_point)
                    and self.in_placement_grid(addon_point)
                    and self.in_pathing_grid(addon_point)
                    for addon_point in addon_points
                ):
                    barrack.build(UnitTypeId.BARRACKSTECHLAB)

    async def select_target(self) -> Tuple[Point2, bool]:
        targets: Units = self.enemy_units
        if targets:
            return targets.random.position, True

        """ Select an enemy target the units should attack. """
        targets: Units = self.enemy_structures
        if targets and len(self.units(UnitTypeId.BATTLECRUISER)) > 5 :
            return targets.random.position, True

        # if ( self.units and min([u.position.distance_to(self.enemy_start_locations[0])for u in self.units]) < 5) :
            # return self.enemy_start_locations[0].position, False
        if len(self.units(UnitTypeId.BATTLECRUISER)) > 5:
            return self.enemy_start_locations[0].position, False

        #retornar a posição de um cc randomico 
        ccs: Units = self.townhalls(UnitTypeId.COMMANDCENTER)
        if not ccs:
            return
        else:
            cc: Unit = ccs.random

        return cc.position, False

    async def build_tech_lab_factory(self):
        for factory in self.structures(UnitTypeId.FACTORY).ready.idle:
            if not factory.has_add_on and self.can_afford(UnitTypeId.FACTORYTECHLAB):
                addon_points = await self.starport_points_to_build_addon(factory.position)
                if all(
                    self.in_map_bounds(addon_point)
                    and self.in_placement_grid(addon_point)
                    and self.in_pathing_grid(addon_point)
                    for addon_point in addon_points
                ):
                    factory.build(UnitTypeId.FACTORYTECHLAB)
            