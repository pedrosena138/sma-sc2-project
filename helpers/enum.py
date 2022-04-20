from enum import IntEnum

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
