from datetime import time
from ip_occupancy_mode import OccupancyMode


class ModeSchedule(object):
    TIME_INDEX = 0
    MODE_INDEX = 1

    def __init__(self):
        self.schedule = []
        self.eventCount = 0
        self.name = ''
        self.isDefault = False

    def add_event(self, start_time, mode):
        if not isinstance(start_time, time):
            Warning('ABORTED: The start time must be of type "time"')
        elif not isinstance(mode, OccupancyMode):
            Warning('ABORTED: The mode must be of class "OccupancyMode')
        elif mode.isSchedulable is not True:
            Warning('ABORTED: This mode does not appear to be schedulable.')
        elif any([x[0] == start_time for x in self.schedule]):
            Warning('ABORTED: The start time is already assigned to an event.')
        else:
            new_event = [start_time, mode]
            self.schedule.append(new_event)
            self.schedule.sort(key=lambda x: x[ModeSchedule.TIME_INDEX])
            self.eventCount = len(self.schedule)
        return None

    def remove_event(self, start_time=None):
        if not isinstance(start_time, time):
            Warning('ABORTED: The start time must be of type "time"')
        elif all([x[0] != start_time for x in self.schedule]):
            Warning('ABORTED: The start time is not, in fact, scheduled.')
        for x in range(len(self.schedule)):
            if start_time == self.schedule[x][ModeSchedule.TIME_INDEX]:
                del self.schedule[x]
                self.eventCount = len(self.schedule)
                break

    def report_schedule(self):
        print(self.name, 'schedule is:')
        for x in self.schedule:
            print(x[ModeSchedule.TIME_INDEX].isoformat(), x[ModeSchedule.MODE_INDEX].name)

    def get_occupancy_mode(self, time_of_interest):
        if len(self.schedule) == 0:
            Warning("No events have been scheduled.")
            return None
        elif not isinstance(time_of_interest, time):
            Warning("A proper time must be supplied.")
            return None
        else:
            days_events = self.schedule
            prior_events = [x for x in days_events if x[ModeSchedule.TIME_INDEX] <= time_of_interest]
            if len(prior_events) == 0:
                Warning("The day has no events prior to the provided time.")
                return None
            else:
                prior_events.sort(key=lambda x: x[0])
                prior_event = prior_events[-1]
                return prior_event[ModeSchedule.MODE_INDEX]
