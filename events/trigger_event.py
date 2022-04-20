from helpers.enum import EventTypes
from .event import Event
class TriggerEvent(Event):
    """
    Most commonly used when registering a Task.
    """
    def __init__(self, trigger, constant: bool = False, toggle: bool = False):
        Event.__init__(self, get_status=trigger, event_type=EventTypes.TRIGGER, constant=constant, toggle=toggle)

