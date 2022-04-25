from sc2.bot_ai import BotAI
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from contextlib import suppress
from typing import Set
from .base_bot import BaseBot

import random

_MAX_BROODLORDS_AMOUNT: int = 2
_MAX_ZERGLINGS_AMOUNT: int = 100
_QUEEN_ENERGY_AMOUNT: int = 25

TOWNHALLS_ID: Set[UnitTypeId] = {
    UnitTypeId.HATCHERY, 
    UnitTypeId.LAIR, 
    UnitTypeId.HIVE
}

_ARMY_UNITS: Set[UnitTypeId] = {
    UnitTypeId.ZERGLING,
    UnitTypeId.CORRUPTOR,
    UnitTypeId.BROODLORD
}


class BaseZergBot(BaseBot):
    """
    Base class for a zerg bot
    """

    async def on_step(self, iteration):
        self.iteration = iteration

        await self.distribute_workers()
        self.train_overlord()
        self.build_gas_havester()
        self.train_drone()
        await self.build_spawning_pool()

        await self.expand()

        self.detect_changes()
        self.exec_global_tasks()
        self.exec_all_units_tasks()

    # Units
    def train_queen(self) -> None:
        if self.structures(UnitTypeId.SPAWNINGPOOL).ready:
            if not self.units(UnitTypeId.QUEEN) and self.headquarter.is_idle:
                if self.can_afford(UnitTypeId.QUEEN):
                    self.headquarter.train(UnitTypeId.QUEEN)
    
    def train_drone(self) -> None:
        """
        Train drones
        """
        max_drones_amount = len(self.townhalls(TOWNHALLS_ID)) * self.WORKERS_PER_TOWNHALL
        drones_amount = self.supply_workers + self.already_pending(UnitTypeId.DRONE)

        if drones_amount < max_drones_amount:
            for hq in self.townhalls(TOWNHALLS_ID):
                if self.larva and self.can_afford(UnitTypeId.DRONE) and hq.is_idle:
                    larva: Unit = self.larva.random
                    larva.train(UnitTypeId.DRONE)
    
    def train_overlord(self):
        if self.supply_left < self.MIN_SUPPLY_AMOUNT and not self.already_pending(
                UnitTypeId.OVERLORD):
            if self.larva and self.can_afford(UnitTypeId.OVERLORD):
                self.larva.random.train(UnitTypeId.OVERLORD)
    
    # Builds
    async def build_spawning_pool(self) -> None:
        """
        Build spawning pool
        """
        townhall_builds: Units = self.townhalls(TOWNHALLS_ID)
        if townhall_builds:
            headquarter: Unit = townhall_builds.first
            if not self.structures(UnitTypeId.SPAWNINGPOOL) and self.can_afford(UnitTypeId.SPAWNINGPOOL) and not self.already_pending(UnitTypeId.SPAWNINGPOOL):
                await self.build(UnitTypeId.SPAWNINGPOOL, near=headquarter.position.towards(self.game_info.map_center, 8), placement_step=6)


class BroodlordZergBot(BaseZergBot):

    async def on_step(self, iteration):
        self.headquarter: Unit = self.townhalls.first
        self.army: Units = self.units.of_type(_ARMY_UNITS)

        if self.headquarter and self.headquarter.surplus_harvesters > 0 and not self.already_pending(
                UnitTypeId.HATCHERY):
            await self.can_expand()

        if self.units(
                UnitTypeId.BROODLORD).amount > _MAX_BROODLORDS_AMOUNT and iteration % 50 == 0:
            for unit in self.army:
                unit.attack(self.select_target())

        # Train Overlord
        if self.supply_left < self.MIN_SUPPLY_AMOUNT and not self.already_pending(
                UnitTypeId.OVERLORD):
            if self.larva and self.can_afford(UnitTypeId.OVERLORD):
                self.larva.random.train(UnitTypeId.OVERLORD)
                return

        if self.structures(UnitTypeId.GREATERSPIRE).ready:
            corruptors: Units = self.units(UnitTypeId.CORRUPTOR)
            # build half-and-half corruptors and broodlords
            if corruptors and corruptors.amount > self.units(
                    UnitTypeId.BROODLORD).amount:
                if self.can_afford(UnitTypeId.BROODLORD):
                    corruptors.random.train(UnitTypeId.BROODLORD)
            elif self.larva and self.can_afford(UnitTypeId.CORRUPTOR):
                self.larva.random.train(UnitTypeId.CORRUPTOR)
                return

        # Make idle queens inject
        for queen in self.units(UnitTypeId.QUEEN).idle:
            if queen.energy >= _QUEEN_ENERGY_AMOUNT:
                queen(AbilityId.EFFECT_INJECTLARVA, self.headquarter)

        # Build pool
        await self.build_spawning_pool()

        # Upgrade to lair
        if self.structures(UnitTypeId.SPAWNINGPOOL).ready:
            if not self.townhalls(UnitTypeId.LAIR) and not self.townhalls(
                    UnitTypeId.HIVE) and self.headquarter.is_idle:
                if self.can_afford(UnitTypeId.LAIR):
                    self.headquarter.build(UnitTypeId.LAIR)

        # Build infestation pit
        if self.townhalls(UnitTypeId.LAIR).ready:
            if self.structures(UnitTypeId.INFESTATIONPIT).amount + \
                    self.already_pending(UnitTypeId.INFESTATIONPIT) == 0:
                if self.can_afford(UnitTypeId.INFESTATIONPIT):
                    await self.build(UnitTypeId.INFESTATIONPIT, near=self.headquarter)

            # Build spire
            if self.structures(UnitTypeId.SPIRE).amount + \
                    self.already_pending(UnitTypeId.SPIRE) == 0:
                if self.can_afford(UnitTypeId.SPIRE):
                    await self.build(UnitTypeId.SPIRE, near=self.headquarter)

        # Upgrade to hive
        if self.structures(UnitTypeId.INFESTATIONPIT).ready and not self.townhalls(
                UnitTypeId.HIVE) and self.headquarter.is_idle:
            if self.can_afford(UnitTypeId.HIVE):
                self.headquarter.build(UnitTypeId.HIVE)

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
            if extractor.surplus_harvesters < 0:
                drones: Units = self.get_drones().filter(
                    lambda d: d.distance_to(extractor) < 8
                )
                if drones:
                    drones.random.gather(extractor)

        # TODO: distribute drones better
        await self.distribute_workers()

        # Build up to 22 drones
        if self.supply_workers + \
                self.already_pending(UnitTypeId.DRONE) < _MAX_DRONES:
            if self.larva and self.can_afford(UnitTypeId.DRONE):
                larva: Unit = self.larva.random
                larva.train(UnitTypeId.DRONE)
                return

        # Build queen
        if self.structures(UnitTypeId.SPAWNINGPOOL).ready:
            if not self.units(UnitTypeId.QUEEN) and self.headquarter.is_idle:
                if self.can_afford(UnitTypeId.QUEEN):
                    self.headquarter.train(UnitTypeId.QUEEN)

        # Build zerglings if we have not enough gas to build corruptors and
        # broodlords
        if self.units(
                UnitTypeId.ZERGLING).amount < _MAX_ZERGLINGS_AMOUNT and self.minerals > 1000:
            if self.larva and self.can_afford(UnitTypeId.ZERGLING):
                self.larva.random.train(UnitTypeId.ZERGLING)