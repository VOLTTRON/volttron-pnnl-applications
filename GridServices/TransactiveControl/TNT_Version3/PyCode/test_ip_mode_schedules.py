from ip_weekdays import Weekday
from ip_mode_schedules import ModeSchedule
from ip_day_types import DayType
from ip_occupancy_mode import OccupancyMode
from ip_constants import Constant
from datetime import time, datetime


# Test methods of class OccupancyMode in ip_occupancy_mode.py **********************************************************
def test_get_maximum_heating():
    print('Running test_get_maximum_heating().')

    print('**Case 1: Normal retrieval of attribute _maximumHeating.')
    normal = OccupancyMode()
    test_value = 10
    normal._maximumHeating = test_value
    try:
        value = normal.get_maximum_heating()
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS ENCOUNTERED:', warning)
        value = None
    assert value == test_value, 'The method returned an unexpected value.'

    print('test_get_maximum_heating() ran to completion.\n')


def test_set_maximum_heating():
    print('Running test_set_maximum_heating().')

    print('**Case 1: Normal assignment in allowed range.')
    normal = OccupancyMode()
    normal._preferredHeating = (120 - 32) / 1.8
    test_value = (140 - 32) / 1.8
    assert test_value <= Constant.MAXIMUM_ALLOWED_TEMPERATURE, 'The test value must be less than the allowed maximum.'
    assert test_value >= normal._preferredHeating + 1, \
        'The test value must be greater then the preferred temperature + 1.'
    try:
        normal.set_maximum_heating(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._maximumHeating == test_value, 'The attribute is not as expected.'

    print('**Case 2: Attempt to set value higher than allowed.')
    normal = OccupancyMode()
    test_value = Constant.MAXIMUM_ALLOWED_TEMPERATURE + 10
    assert test_value > Constant.MAXIMUM_ALLOWED_TEMPERATURE, \
        'In this case, the test value must be greater than the allowed maximum.'
    try:
        normal.set_maximum_heating(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._maximumHeating == Constant.MAXIMUM_ALLOWED_TEMPERATURE, 'The attribute is not as expected.'

    print('**Case 3: Attempt to set value lower than the preferred state, plus 1.')
    normal = OccupancyMode()
    test_value = normal._preferredHeating  # We must access protected attributes to perform these unit tests.
    assert test_value < normal._preferredHeating + 1, \
        'In this case, the test value must be less than the preferred temperature plus 1.'
    try:
        normal.set_maximum_heating(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._maximumHeating == normal._preferredHeating + 1, 'The attribute is not as expected.'

    print('test_set_maximum_heating() ran to completion.\n')


def test_get_minimum_heating():
    print('Running test_get_minimum_heating().')

    print('**Case 1: Normal retrieval of attribute _minimumHeating.')
    normal = OccupancyMode()
    test_value = 112
    normal._minimumHeating = test_value
    try:
        value = normal.get_minimum_heating()
        print('  - The case ran without errors.')
    except RuntimeError as error:
        print('  - ERRORS ENCOUNTERED:', error)
        value = None
    assert value == test_value, 'The method returned an unexpected value.'

    print('test_get_minimum_heating() ran to completion.\n')


def test_set_minimum_heating():
    print('Running test_set_minimum_heating().')

    print('**Case 1: Normal assignment in allowed range.')
    normal = OccupancyMode()
    normal._preferredHeating = (120 - 32) / 1.8
    test_value = (110 - 32) / 1.8
    assert test_value >= Constant.MINIMUM_ALLOWED_TEMPERATURE, \
        'The test value must be greater than the allowed minimum.'
    assert test_value <= normal._preferredHeating - 1, \
        'The test value must be less then the preferred temperature - 1.'
    try:
        normal.set_minimum_heating(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._minimumHeating == test_value, 'The attribute is not as expected.'

    print('**Case 2: Attempt to set value lower than allowed.')
    normal = OccupancyMode()
    test_value = Constant.MINIMUM_ALLOWED_TEMPERATURE - 10
    assert test_value < Constant.MINIMUM_ALLOWED_TEMPERATURE, \
        'In this case, the test value must be less than the allowed minimum.'
    try:
        normal.set_minimum_heating(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._minimumHeating == Constant.MINIMUM_ALLOWED_TEMPERATURE, 'The attribute is not as expected.'

    print('**Case 3: Attempt to set value higher than the preferred state, minus 1.')
    normal = OccupancyMode()
    test_value = normal._preferredHeating  # We must access protected attributes to perform these unit tests.
    assert test_value > normal._preferredHeating - 1, \
        'In this case, the test value must be greater than the preferred temperature minus 1.'
    try:
        normal.set_minimum_heating(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._minimumHeating == normal._preferredHeating - 1, 'The attribute is not as expected.'

    print('test_set_minimum_heating() ran to completion.\n')


def test_get_preferred_heating():
    print('Running test_get_preferred_heating().')

    print('**Case 1: Normal retrieval of attribute _preferredHeating.')
    normal = OccupancyMode()
    test_value = 12
    normal._preferredHeating = test_value
    try:
        value = normal.get_preferred_heating()
        print('  - The case ran without errors.')
    except RuntimeError as error:
        print('  - ERRORS ENCOUNTERED:', error)
        value = None
    assert value == test_value, 'The method returned an unexpected value.'

    print('test_get_preferred_heating() ran to completion.\n')


def test_set_preferred_heating():
    print('Running test_set_preferred_heating().')

    print('**Case 1: Normal assignment in allowed range.')
    normal = OccupancyMode()
    test_value = normal._preferredHeating
    try:
        normal.set_preferred_heating(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._preferredHeating == test_value, 'The attribute is not as expected.'

    print('**Case 2: Attempt to set value above allowed range.')
    normal = OccupancyMode()
    test_value = Constant.MAXIMUM_ALLOWED_TEMPERATURE + 1
    try:
        normal.set_preferred_heating(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._preferredHeating == Constant.MAXIMUM_ALLOWED_TEMPERATURE - 1, 'The attribute is not as expected.'

    print('**Case 3: Attempt to set value below allowed range.')
    normal = OccupancyMode()
    test_value = Constant.MINIMUM_ALLOWED_TEMPERATURE - 1
    try:
        normal.set_preferred_heating(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._preferredHeating == Constant.MINIMUM_ALLOWED_TEMPERATURE + 1, 'The attribute is not as expected.'

    print('**Case 4: Attempt to set value below current comfort range.')
    normal = OccupancyMode()
    test_value = normal._minimumHeating
    try:
        normal.set_preferred_heating(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._minimumHeating == normal._preferredHeating - 1, 'The minimum comfort range is not as expected.'

    print('**Case 5: Attempt to set value above current comfort range.')
    normal = OccupancyMode()
    test_value = normal._maximumHeating
    try:
        normal.set_preferred_heating(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._maximumHeating == normal._preferredHeating + 1, 'The maximum comfort range is not as expected.'

    print('test_set_preferred_heating() ran to completion.\n')


def test_get_occupancy_cost_mode():
    print('Running test_get_occupancy_cost_mode().')

    print('**Case 1: Normal retrieval of attribute _occupancyCostMode.')
    normal = OccupancyMode()
    test_value = 13
    normal._occupancyCostMode = test_value
    try:
        value = normal.get_occupancy_cost_mode()
        print('  - The case ran without errors.')
    except RuntimeError as error:
        print('  - ERRORS ENCOUNTERED:', error)
        value = None
    assert value == test_value, 'The method returned an unexpected value.'

    print('test_get_occupancy_cost_mode() ran to completion.\n')


def test_set_occupancy_cost_mode():
    print('Running test_set_occupancy_risk_mode().')

    print('**Case 1: Normal assignment in allowed range.')
    normal = OccupancyMode()
    test_value = 0.5
    try:
        normal.set_occupancy_cost_mode(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._occupancyCostMode == test_value, 'The attribute is not as expected.'

    print('**Case 2: Attempt to assign value above the allowed range.')
    normal = OccupancyMode()
    test_value = 1.1
    try:
        normal.set_occupancy_cost_mode(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._occupancyCostMode == 1.0, 'The attribute is not as expected.'

    print('**Case 3: Attempt to assign value below the allowed range.')
    normal = OccupancyMode()
    test_value = -1
    try:
        normal.set_occupancy_cost_mode(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._occupancyCostMode == 0.0, 'The attribute is not as expected.'

    print('test_set_occupancy_risk_mode() ran to completion.\n')


def test_get_occupancy_risk_mode():
    print('Running test_get_occupancy_risk_mode().')

    print('**Case 1: Normal retrieval of attribute _occupancyRiskMode.')
    normal = OccupancyMode()
    test_value = 12
    normal._occupancyRiskMode = test_value
    try:
        value = normal.get_occupancy_risk_mode()
        print('  - The case ran without errors.')
    except RuntimeError as error:
        print('  - ERRORS ENCOUNTERED:', error)
        value = None
    assert value == test_value, 'The method returned an unexpected value.'

    print('test_get_occupancy_risk_mode() ran to completion.\n')


def test_set_occupancy_risk_mode():
    print('Running test_set_occupancy_risk_mode().')

    print('**Case 1: Normal assignment in allowed range.')
    normal = OccupancyMode()
    test_value = 0.5
    try:
        normal.set_occupancy_risk_mode(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._occupancyRiskMode == test_value, 'The attribute is not as expected.'

    print('**Case 2: Attempt to assign value above the allowed range.')
    normal = OccupancyMode()
    test_value = 1.1
    try:
        normal.set_occupancy_risk_mode(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._occupancyRiskMode == 1.0, 'The attribute is not as expected.'

    print('**Case 3: Attempt to assign value below the allowed range.')
    normal = OccupancyMode()
    test_value = -1
    try:
        normal.set_occupancy_risk_mode(test_value)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert normal._occupancyRiskMode == 0.0, 'The attribute is not as expected.'

    print('test_set_occupancy_risk_mode() ran to completion.\n')


# Test methods of class ModeSchedules in ip_mode_schedules.py: *********************************************************
def test_add_event():
    print('Running test_add_event().')

    print('**Case 1: Normal addition of an event to a schedule.')
    weekdays = ModeSchedule()
    normal = OccupancyMode()
    normal.isSchedulable = True
    start_time = time(hour=1, minute=2)
    assert isinstance(weekdays, ModeSchedule), 'The method belongs to a mode schedule'
    assert isinstance(normal, OccupancyMode), 'The method must be provided an occupancy mode.'
    assert isinstance(start_time, time), 'The method must be provided a time class object.'
    assert weekdays.eventCount == 0, 'The schedule starts with no scheduled events.'
    assert normal.isSchedulable == True, 'The occupancy mode must be schedulable.'
    try:
        weekdays.add_event(start_time=start_time, mode=normal)
        print(' - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert len(weekdays.schedule) == 1, 'The event should have been scheduled'
    assert weekdays.eventCount == 1, 'The event count should have been incremented.'
    assert weekdays.schedule[0][0] == start_time, 'The event start time is unexpected.'
    assert weekdays.schedule[0][1] == normal, 'The event not assigned the expected occupancy mode.'

    print('**Case 2: Improper time parameter supplied.')
    weekdays = ModeSchedule()
    normal = OccupancyMode()
    normal.isSchedulable = True
    start_time = datetime.now()
    assert isinstance(weekdays, ModeSchedule), 'The method belongs to a mode schedule'
    assert isinstance(normal, OccupancyMode), 'The method must be provided an occupancy mode.'
    assert not isinstance(start_time, time), 'The method must be provided a time class object.'
    assert weekdays.eventCount == 0, 'The schedule starts with no scheduled events.'
    assert normal.isSchedulable == True, 'The occupancy mode must be schedulable.'
    try:
        weekdays.add_event(start_time=start_time, mode=normal)
        print(' - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert len(weekdays.schedule) == 0, 'The event should not have been scheduled'
    assert weekdays.eventCount == 0, 'The event count should not have been incremented.'

    print('**Case 3: Improper opccupancy mode parameter supplied.')
    weekdays = ModeSchedule()
    normal = 'Normal'
    start_time = time(hour=1)
    assert isinstance(weekdays, ModeSchedule), 'The method belongs to a mode schedule'
    assert not isinstance(normal, OccupancyMode), 'The method must be provided an occupancy mode.'
    assert isinstance(start_time, time), 'The method must be provided a time class object.'
    assert weekdays.eventCount == 0, 'The schedule starts with no scheduled events.'
    try:
        weekdays.add_event(start_time=start_time, mode=normal)
        print(' - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert len(weekdays.schedule) == 0, 'The event should not have been scheduled'
    assert weekdays.eventCount == 0, 'The event count should not have been incremented.'

    print('**Case 4: The occupancy mode is not schedulable.')
    weekdays = ModeSchedule()
    normal = OccupancyMode()
    normal.isSchedulable = False
    start_time = time(hour=1, minute=2)
    assert isinstance(weekdays, ModeSchedule), 'The method belongs to a mode schedule'
    assert isinstance(normal, OccupancyMode), 'The method must be provided an occupancy mode.'
    assert isinstance(start_time, time), 'The method must be provided a time class object.'
    assert weekdays.eventCount == 0, 'The schedule starts with no scheduled events.'
    assert normal.isSchedulable != True, 'The occupancy mode must be schedulable.'
    try:
        weekdays.add_event(start_time=start_time, mode=normal)
        print(' - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert len(weekdays.schedule) == 0, 'The event should not have been scheduled'
    assert weekdays.eventCount == 0, 'The event count should not have been incremented.'

    print('**Case 5: The time has already has a scheduled occupancy mode event.')
    weekdays = ModeSchedule()
    normal = OccupancyMode()
    normal.isSchedulable = True
    start_time = time(hour=1, minute=2)
    weekdays.add_event(start_time=start_time, mode=normal)  # Add the event, as per Case #1.
    assert isinstance(weekdays, ModeSchedule), 'The method belongs to a mode schedule'
    assert isinstance(normal, OccupancyMode), 'The method must be provided an occupancy mode.'
    assert isinstance(start_time, time), 'The method must be provided a time class object.'
    assert weekdays.eventCount == 1, 'The schedule starts with one scheduled event.'
    assert normal.isSchedulable == True, 'The occupancy mode must be schedulable.'
    try:
        weekdays.add_event(start_time=start_time, mode=normal)
        print(' - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert len(weekdays.schedule) == 1, 'The second event should not have been scheduled'
    assert weekdays.eventCount == 1, 'The event count should not have been incremented.'

    print('test_add_event() ran to completion.\n')


def test_remove_event():
    print('Running test_remove_event().')

    print('**Case 1: Normal removal of existing event.')
    weekdays = ModeSchedule()
    normal = OccupancyMode()
    normal.isSchedulable = True
    start_time = time(hour=1, minute=2)
    weekdays.add_event(start_time=start_time, mode=normal)  # Add an event, as per add_event() Case #1.
    assert isinstance(weekdays, ModeSchedule), 'The method belongs to a mode schedule'
    assert isinstance(normal, OccupancyMode), 'The method must be provided an occupancy mode.'
    assert isinstance(start_time, time), 'The method must be provided a time class object.'
    assert weekdays.eventCount == 1, 'The schedule starts with one scheduled event.'
    assert normal.isSchedulable == True, 'The occupancy mode must be schedulable.'
    try:
        weekdays.remove_event(start_time=start_time)
        print(' - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert len(weekdays.schedule) == 0, 'The scheduled event should have been removed'
    assert weekdays.eventCount == 0, 'The event count should have been decremented.'

    print('**Case 2: The time parameter is not of class "time".')
    weekdays = ModeSchedule()
    normal = OccupancyMode()
    normal.isSchedulable = True
    start_time = time(hour=1, minute=2)
    weekdays.add_event(start_time=start_time, mode=normal)  # Add an event, as per add_event() Case #1.
    assert isinstance(weekdays, ModeSchedule), 'The method belongs to a mode schedule'
    assert isinstance(normal, OccupancyMode), 'The method must be provided an occupancy mode.'
    assert isinstance(start_time, time), 'The method must be provided a time class object.'
    assert weekdays.eventCount == 1, 'The schedule starts with one scheduled event.'
    assert normal.isSchedulable == True, 'The occupancy mode must be schedulable.'
    try:
        weekdays.remove_event(start_time=datetime.now())
        print(' - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert len(weekdays.schedule) == 1, 'The scheduled event should not have been removed'
    assert weekdays.eventCount == 1, 'The event count should not have been decremented.'

    print('**Case 3: The time parameter is improper, not a member of class "time".')
    weekdays = ModeSchedule()
    normal = OccupancyMode()
    normal.isSchedulable = True
    original_start_time = time(hour=1, minute=2)  # time of first event must differ from the requested removal.
    start_time = time(hour=1)
    weekdays.add_event(start_time=start_time, mode=normal)  # Add an event, as per add_event() Case #1.
    assert isinstance(weekdays, ModeSchedule), 'The method belongs to a mode schedule'
    assert isinstance(normal, OccupancyMode), 'The method must be provided an occupancy mode.'
    assert isinstance(start_time, time), 'The method must be provided a time class object.'
    assert weekdays.eventCount == 1, 'The schedule starts with one scheduled event.'
    assert normal.isSchedulable == True, 'The occupancy mode must be schedulable.'
    assert start_time != original_start_time, \
        'The time of the requested removal should not match that of an existing event.'
    weekdays.add_event(start_time=original_start_time, mode=normal)
    try:
        weekdays.remove_event(start_time=start_time)
        print(' - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
    assert len(weekdays.schedule) == 1, 'The scheduled event should not have been removed'
    assert weekdays.eventCount == 1, 'The event count should have not been decremented.'

    print('test_remove_event() ran to completion.\n')


def test_get_occupancy_mode():
    print('Running test_get_occupancy_mode().')

    print('**Case 1: Normal retrieval of currently scheduled occupancy mode from event schedule.')
    weekdays = ModeSchedule()
    normal = OccupancyMode()
    normal.isSchedulable = True
    start_time = time(hour=0)
    weekdays.add_event(start_time=start_time, mode=normal)
    assert isinstance(weekdays, ModeSchedule), 'The method belongs to a mode schedule'
    assert isinstance(normal, OccupancyMode), 'The method must be provided an occupancy mode.'
    assert isinstance(start_time, time), 'The method must be provided a time class object.'
    assert weekdays.eventCount == 1, 'An event should be scheduled.'
    assert weekdays.schedule[0][0] == start_time, 'The existing event time was not scheduled right.'
    assert normal.isSchedulable is True, 'The occupancy mode must be schedulable.'
    time_of_interest = time(hour=23)
    try:
        current_mode = weekdays.get_occupancy_mode(time_of_interest)
        print(' - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
        current_mode = None
    assert len(weekdays.schedule) == 1, 'The event should be unchanged'
    assert weekdays.eventCount == 1, 'The event count should be unchanged.'
    assert current_mode == normal, 'The current mode should have been assigned.'

    print('**Case 2: No events have been scheduled.')
    weekdays = ModeSchedule()
    assert isinstance(weekdays, ModeSchedule), 'The method belongs to a mode schedule'
    assert weekdays.eventCount == 0, 'In this case, no events should be scheduled.'
    assert len(weekdays.schedule) == 0, 'In this case, no events should be scheduled.'
    time_of_interest = time(hour=23)
    try:
        current_mode = weekdays.get_occupancy_mode(time_of_interest)
        print(' - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
        current_mode = None
    assert len(weekdays.schedule) == 0, 'The event count should be unchanged'
    assert weekdays.eventCount == 0, 'The event count should be unchanged.'
    assert current_mode is None, 'The current mode should not have been assigned.'

    print('**Case 3: There exist no events that earlier in the day than the time of interest.')
    weekdays = ModeSchedule()
    normal = OccupancyMode()
    normal.isSchedulable = True
    start_time = time(hour=20)
    weekdays.add_event(start_time=start_time, mode=normal)
    time_of_interest = time(hour=10)
    assert time_of_interest < start_time, "In this case, no event start time can precede the time of interest."
    assert isinstance(weekdays, ModeSchedule), 'The method belongs to a mode schedule'
    assert isinstance(normal, OccupancyMode), 'The method must be provided an occupancy mode.'
    assert isinstance(start_time, time), 'The method must be provided a time class object.'
    assert weekdays.eventCount == 1, 'An event should be scheduled.'
    assert weekdays.schedule[0][0] == start_time, 'The existing event time was not scheduled right.'
    assert normal.isSchedulable is True, 'The occupancy mode must be schedulable.'
    try:
        current_mode = weekdays.get_occupancy_mode(time_of_interest)
        print(' - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
        current_mode = None
    assert len(weekdays.schedule) == 1, 'The event should be unchanged'
    assert weekdays.eventCount == 1, 'The event count should be unchanged.'
    assert current_mode is None, 'The current mode should not have been assigned.'

    print('test_get_occupancy_mode() ran to completion.\n')


# These test methods of class DayTypes in ip_day_types.py: *************************************************************
def test_set_day_type():
    print('Running test_set_day_type().')

    print('**Case 1: Normal case. Set Wednesday calendar as a weekday schedule.')
    my_days = DayType()
    weekdays = ModeSchedule()
    assert my_days.dayType[Weekday.Monday] != weekdays, "The day schedule is not already as assigned."
    try:
        my_days.set_day_type(Weekday.Monday, weekdays)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERROR WERE ENCOUNTERED:', warning)
    assert my_days.dayType[Weekday.Monday][1] == weekdays, "The day schedule was not assigned properly"

    print('test_set_day_type() ran to completion.\n')


def test_set_all():
    print('Running test_set_all().')
    print('**Case 1:')
    print('test_set_all() ran to completion.\n')


if __name__ == '__main__':
    print('Running tests in test_ip_mode_schedules.py:\n')

    print('These tests pertain to ip_occupancy_mode.py:\n')
    test_get_maximum_heating()
    test_set_maximum_heating()
    test_get_minimum_heating()
    test_set_minimum_heating()
    test_get_preferred_heating()
    test_set_preferred_heating()
    test_get_occupancy_cost_mode()
    test_set_occupancy_cost_mode()
    test_get_occupancy_risk_mode()
    test_set_occupancy_risk_mode()
    print('Tests of ip_occupancy_mode.py ran to completion.\n')

    print('These tests pertain to ip_mode_schedules.py:\n')
    test_add_event()
    test_remove_event()
    test_get_occupancy_mode()
    print('Tests of ip_mode_schedules.py ran to completion.\n')

    print('These tests pertain to ip_day_types.py:\n')
    test_set_day_type()
    test_set_all()
    print('Tests of ip_day_types.py ran to completion.\n')

    print('Tests in test_ip_mode_schedules.py ran to completion.\n')
