from .enum import TaskStatus

class Task(object):

    def __init__(self, start = None, step = None,
                end = None, get_status = None):
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
