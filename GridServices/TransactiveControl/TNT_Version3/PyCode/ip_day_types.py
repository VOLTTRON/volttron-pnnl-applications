from ip_weekdays import Weekday
from ip_mode_schedules import ModeSchedule

DAY_INDEX = 0
SCHEDULE_INDEX = 1


class DayType(object):

    def __init__(self):
        self.dayType = [  # Assigns one ModeSchedule object to each weekday.
            [Weekday.Monday, None],
            [Weekday.Tuesday, None],
            [Weekday.Wednesday, None],
            [Weekday.Thursday, None],
            [Weekday.Friday, None],
            [Weekday.Saturday, None],
            [Weekday.Sunday, None]
        ]

    def set_day_type(self, day, mode_schedule):
        if not isinstance(mode_schedule, ModeSchedule):
            Warning('The argument must be a valid object of class ModeSchedule.')
        elif not isinstance(day, int):
            Warning('Parameter "day" must resolve to an integer value.')
        elif day < 0 or day > 6:
            Warning('Parameter "day" must be in the range from 0 to 6')
        else:
            self.dayType[day][SCHEDULE_INDEX] = mode_schedule
        return None

    def set_all(self, mode_schedule):
        if not isinstance(mode_schedule, ModeSchedule):
            Warning('The argument must be a valid object of class ModeSchedule.')
        else:
            for x in self.dayType:
                x[SCHEDULE_INDEX] = mode_schedule
        return None

    def report_day_types(self):
        day = {1: "Monday",
               2: "Tuesday",
               3: "Wednesday",
               4: "Thursday",
               5: "Friday",
               6: "Saturday",
               7: "Sunday"
               }
        print('The pairings of weekdays and mode schedules is:')
        for x in range(0, 6):
            print(day[x], self.dayType[x][SCHEDULE_INDEX])
