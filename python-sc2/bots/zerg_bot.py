from sc2.bot_ai import BotAI
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from contextlib import suppress
from typing import Set

import random

_MAX_DRONES: int = 22
_MAX_BROODLORDS_AMOUNT: int = 2
_MAX_ZERGLINGS_AMOUNT: int = 100
_QUEEN_ENERGY_AMOUNT: int = 25

# SUPPLY
_MIN_SUPPLY_AMOUNT: int = 2

_ARMY_UNITS: Set[UnitTypeId] = {
    UnitTypeId.ZERGLING, 
    UnitTypeId.CORRUPTOR, 
    UnitTypeId.BROODLORD
}

class BaseZergBot(BotAI):   
    """
    Base class for a zerg bot
    """
    def __init__(self):
        super(BaseZergBot, self).__init__()
        self.race = Race.Zerg
        self.headquarter: Unit = None
        self.army: Units = None

    def select_target(self) -> Point2:
        """
        Select enemy units or builds to attack
        """
        if self.enemy_structures:
            return random.choice(self.enemy_structures).position
        return self.enemy_start_locations[0]
    
    # Forces
    def can_train_drones(self) -> None:
        """
        Check if can train drones based on bases amount
        """
        max_drones_amount = (self.townhalls.amount + self.placeholders(UnitTypeId.HATCHERY).amount) * _MAX_DRONES
        drones_amount = self.supply_workers + self.already_pending(UnitTypeId.DRONE)
        return self.larva and self.can_afford(UnitTypeId.DRONE) and drones_amount - self.worker_en_route_to_build(UnitTypeId.HATCHERY) < max_drones_amount

    def build_queen(self) -> None:
        if self.structures(UnitTypeId.SPAWNINGPOOL).ready:
            if not self.units(UnitTypeId.QUEEN) and self.headquarter.is_idle:
                if self.can_afford(UnitTypeId.QUEEN):
                    self.headquarter.train(UnitTypeId.QUEEN)
    
    async def on_building_construction_complete(self, unit: Unit):
        """ Set rally point of new hatcheries. """
        if unit.type_id == UnitTypeId.HATCHERY and self.mineral_field:
            mf = self.mineral_field.closest_to(unit)
            unit.smart(mf)

    # Builds
    async def build_spawning_pool(self) -> None:
        """
        Build spawning pool
        """
        if self.structures(UnitTypeId.SPAWNINGPOOL).amount + self.already_pending(UnitTypeId.SPAWNINGPOOL) == 0:
            if self.can_afford(UnitTypeId.SPAWNINGPOOL):
                await self.build(UnitTypeId.SPAWNINGPOOL, near=self.headquarter)
    
    async def can_expand(self) -> None:
        """
        Check if can build another base
        """
        if self.can_afford(UnitTypeId.HATCHERY):
            planned_hatch_locations: Set[Point2] = {placeholder.position for placeholder in self.placeholders}
            my_structure_locations: Set[Point2] = {structure.position for structure in self.structures}
            enemy_structure_locations: Set[Point2] = {structure.position for structure in self.enemy_structures}
            blocked_locations: Set[Point2] = (
                my_structure_locations | planned_hatch_locations | enemy_structure_locations
            )

            exp_pos = await self.get_next_expansion()
            if exp_pos and exp_pos not in blocked_locations:
                await self.expand_now(building=UnitTypeId.HATCHERY)

    def build_extractor(self) -> None:
        """
        Build gas extractors
        """
        max_extractors_amount = self.townhalls.amount * 2
        extractors_amount = self.gas_buildings.amount + self.already_pending(UnitTypeId.EXTRACTOR)
        
        if extractors_amount < max_extractors_amount:
            if self.can_afford(UnitTypeId.EXTRACTOR):
                drone: Unit = self.workers.random
                target: Unit = self.vespene_geyser.closest_to(drone.position)
                drone.build_gas(target)


class CollectAndExpandBot(BaseZergBot):
    
    async def on_start(self):
        super(CollectAndExpandBot, self).on_start()
        self.client.game_step = 50
        await self.client.debug_show_map()

    async def on_step(self, iteration: int):

        # Expand
        await self.can_expand()

        # Train Overlords
        if self.supply_left < 2:
            if self.larva and self.can_afford(UnitTypeId.OVERLORD) and not self.already_pending(UnitTypeId.OVERLORD):
                self.train(UnitTypeId.OVERLORD)
                return
        
        # Train Drones
        if self.larva and self.can_train_drones():
            self.train(UnitTypeId.DRONE)
            return

        await self.distribute_workers()
        
        self.build_extractor()
        if self.enemy_units:
            await self.client.debug_kill_unit(self.enemy_units)       


class ZerglingBot(BaseZergBot):
    def __init__(self):
        super(ZerglingBot, self).__init__()

    async def on_step(self, iteration):
        self.headquarter: Unit = self.townhalls.first
        self.army: Units = self.units.of_type(_ARMY_UNITS)

        if self.units(UnitTypeId.BROODLORD).amount > _MAX_BROODLORDS_AMOUNT and iteration % 50 == 0:
            for unit in self.army:
                unit.attack(self.select_target())

        # Train Overlords
        if self.supply_left < _MIN_SUPPLY_AMOUNT:
            if self.larva and self.can_afford(UnitTypeId.OVERLORD) and not self.already_pending(UnitTypeId.OVERLORD):
                self.larva.random.train(UnitTypeId.OVERLORD)
                return
        
        if self.structures(UnitTypeId.GREATERSPIRE).ready:
            corruptors: Units = self.units(UnitTypeId.CORRUPTOR)

            # build half-and-half corruptors and broodlords
            if corruptors and corruptors.amount > self.units(UnitTypeId.BROODLORD).amount:
                if self.can_afford(UnitTypeId.BROODLORD):
                    corruptors.random.train(UnitTypeId.BROODLORD)
            elif self.larva and self.can_afford(UnitTypeId.CORRUPTOR):
                self.larva.random.train(UnitTypeId.CORRUPTOR)
                return
        
        # Make idle queens inject
        for queen in self.units(UnitTypeId.QUEEN).idle:
            if queen.energy >= 25:
                queen(AbilityId.EFFECT_INJECTLARVA, self.headquarter)

        # Build pool
        self.build_spawning_pool()

        # Upgrade to lair
        if self.structures(UnitTypeId.SPAWNINGPOOL).ready:
            if not self.townhalls(UnitTypeId.LAIR) and not self.townhalls(UnitTypeId.HIVE) and self.headquarter.is_idle:
                if self.can_afford(UnitTypeId.LAIR):
                    self.headquarter.build(UnitTypeId.LAIR)
        
        # Build infestation pit
        if self.townhalls(UnitTypeId.LAIR).ready:
            if self.structures(UnitTypeId.INFESTATIONPIT).amount + self.already_pending(UnitTypeId.INFESTATIONPIT) == 0:
                if self.can_afford(UnitTypeId.INFESTATIONPIT):
                    await self.build(UnitTypeId.INFESTATIONPIT, near=self.headquarter)

            # Build spire
            if self.structures(UnitTypeId.SPIRE).amount + self.already_pending(UnitTypeId.SPIRE) == 0:
                if self.can_afford(UnitTypeId.SPIRE):
                    await self.build(UnitTypeId.SPIRE, near=self.headquarter)

        # Upgrade to hive
        if self.structures(UnitTypeId.INFESTATIONPIT).ready and not self.townhalls(UnitTypeId.HIVE) and self.headquarter.is_idle:
            if self.can_afford(UnitTypeId.HIVE):
                self.headquarter.build(UnitTypeId.HIVE)
        
        # Upgrade to greater spire
        if self.townhalls(UnitTypeId.HIVE).ready:
            spires: Units = self.structures(UnitTypeId.SPIRE).ready
            if spires:
                spire: Unit = spires.random
                if self.can_afford(UnitTypeId.GREATERSPIRE) and spire.is_idle:
                    spire.build(UnitTypeId.GREATERSPIRE)
        
        self.build_extractor()

        # Train Drones
        if self.larva and self.can_train_drones():
            self.larva.random.train(UnitTypeId.DRONE)
            return

        # Build queen
        if self.structures(UnitTypeId.SPAWNINGPOOL).ready:
            if not self.units(UnitTypeId.QUEEN) and self.headquarter.is_idle:
                if self.can_afford(UnitTypeId.QUEEN):
                    self.headquarter.train(UnitTypeId.QUEEN)

        # Train Zerglings
        if self.units(UnitTypeId.ZERGLING).amount < _MAX_ZERGLINGS_AMOUNT and self.minerals > 1000:
            if self.larva and self.can_afford(UnitTypeId.ZERGLING):
                self.larva.random.train(UnitTypeId.ZERGLING)

class BroodlordBot(BaseZergBot):
    def __init__(self):
        super(BroodlordBot, self).__init__()

    async def on_step(self, iteration):            
        headquarter: Unit = self.townhalls.first
        army: Units = self.units.of_type(_ARMY_UNITS)

        if self.units(UnitTypeId.BROODLORD).amount > _MAX_BROODLORDS_AMOUNT and iteration % 50 == 0:
            for unit in army:
                unit.attack(self.select_target())

        # Train Overlord
        if self.supply_left < _MIN_SUPPLY_AMOUNT and not self.already_pending(UnitTypeId.OVERLORD):
            if self.larva and self.can_afford(UnitTypeId.OVERLORD):
                self.larva.random.train(UnitTypeId.OVERLORD)
                return

        if self.structures(UnitTypeId.GREATERSPIRE).ready:
            corruptors: Units = self.units(UnitTypeId.CORRUPTOR)
            # build half-and-half corruptors and broodlords
            if corruptors and corruptors.amount > self.units(UnitTypeId.BROODLORD).amount:
                if self.can_afford(UnitTypeId.BROODLORD):
                    corruptors.random.train(UnitTypeId.BROODLORD)
            elif self.larva and self.can_afford(UnitTypeId.CORRUPTOR):
                self.larva.random.train(UnitTypeId.CORRUPTOR)
                return

        # Make idle queens inject
        for queen in self.units(UnitTypeId.QUEEN).idle:
            if queen.energy >= _QUEEN_ENERGY_AMOUNT:
                queen(AbilityId.EFFECT_INJECTLARVA, headquarter)

        # Build pool
        if self.structures(UnitTypeId.SPAWNINGPOOL).amount + self.already_pending(UnitTypeId.SPAWNINGPOOL) == 0:
            if self.can_afford(UnitTypeId.SPAWNINGPOOL):
                await self.build(UnitTypeId.SPAWNINGPOOL, near=headquarter)

        # Upgrade to lair
        if self.structures(UnitTypeId.SPAWNINGPOOL).ready:
            if not self.townhalls(UnitTypeId.LAIR) and not self.townhalls(UnitTypeId.HIVE) and headquarter.is_idle:
                if self.can_afford(UnitTypeId.LAIR):
                    headquarter.build(UnitTypeId.LAIR)

        # Build infestation pit
        if self.townhalls(UnitTypeId.LAIR).ready:
            if self.structures(UnitTypeId.INFESTATIONPIT).amount + self.already_pending(UnitTypeId.INFESTATIONPIT) == 0:
                if self.can_afford(UnitTypeId.INFESTATIONPIT):
                    await self.build(UnitTypeId.INFESTATIONPIT, near=headquarter)

            # Build spire
            if self.structures(UnitTypeId.SPIRE).amount + self.already_pending(UnitTypeId.SPIRE) == 0:
                if self.can_afford(UnitTypeId.SPIRE):
                    await self.build(UnitTypeId.SPIRE, near=headquarter)

        # Upgrade to hive
        if self.structures(UnitTypeId.INFESTATIONPIT).ready and not self.townhalls(UnitTypeId.HIVE) and headquarter.is_idle:
            if self.can_afford(UnitTypeId.HIVE):
                headquarter.build(UnitTypeId.HIVE)

        # Upgrade to greater spire
        if self.townhalls(UnitTypeId.HIVE).ready:
            spires: Units = self.structures(UnitTypeId.SPIRE).ready
            if spires:
                spire: Unit = spires.random
                if self.can_afford(UnitTypeId.GREATERSPIRE) and spire.is_idle:
                    spire.build(UnitTypeId.GREATERSPIRE)

        # Build extractor
        self.build_extractor()

        # Assign drones to extractors
        for extractor in self.gas_buildings:
            if extractor.assigned_harvesters < extractor.ideal_harvesters:
                workers: Units = self.workers
                if workers:
                    workers.random.gather(extractor)

        await self.distribute_workers()
              
        # Build up to 22 drones
        if self.supply_workers + self.already_pending(UnitTypeId.DRONE) < _MAX_DRONES:
            if self.larva and self.can_afford(UnitTypeId.DRONE):
                larva: Unit = self.larva.random
                larva.train(UnitTypeId.DRONE)
                return

        # Build queen
        if self.structures(UnitTypeId.SPAWNINGPOOL).ready:
            if not self.units(UnitTypeId.QUEEN) and headquarter.is_idle:
                if self.can_afford(UnitTypeId.QUEEN):
                    headquarter.train(UnitTypeId.QUEEN)

        # Build zerglings if we have not enough gas to build corruptors and broodlords
        if self.units(UnitTypeId.ZERGLING).amount < _MAX_ZERGLINGS_AMOUNT and self.minerals > 1000:
            if self.larva and self.can_afford(UnitTypeId.ZERGLING):
                self.larva.random.train(UnitTypeId.ZERGLING)