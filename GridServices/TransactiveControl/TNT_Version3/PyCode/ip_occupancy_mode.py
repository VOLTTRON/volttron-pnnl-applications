"""
OccupancyMode class
This class helps define the various occupancy modes available to the Islay Power node devices. A normal occupancy mode
should ALWAYS be defined to drive normal operations. These following occupancy modes are recommended to be instantiated:
{vacation, away, sleep, normal, party, and guest}. Of these, all but the vacation and guest modes may can be scheduled.
See class ModeSchedule concerning the means to schedule occupancy modes.
"""

from .ip_constants import Constant


class OccupancyMode(object):

    def __init__(self,
                 maximum_cooling=None,
                 maximum_heating=(130 - 32) / 1.8,
                 minimum_cooling=None,
                 minimum_heating=(110 - 32) / 1.8,
                 name='',
                 is_schedulable=True,
                 occupancy_cost_mode=0.5,
                 occupancy_risk_mode=0.5,
                 preferred_cooling=None,
                 preferred_heating=(120 - 32) / 1.8
                 ):
        self.name = name
        self._preferredCooling = preferred_cooling  # [deg.C]
        self._maximumCooling = maximum_cooling  # deg. C
        self._minimumCooling = minimum_cooling  # deg. C
        self._preferredHeating = preferred_heating  # deg. C
        self._maximumHeating = maximum_heating  # deg. C
        self._minimumHeating = minimum_heating  # deg. C
        self._occupancyCostMode = occupancy_cost_mode
        self._occupancyRiskMode = occupancy_risk_mode
        self.isSchedulable = is_schedulable

    def get_preferred_heating(self):
        return self._preferredHeating  # deg. C

    def set_preferred_heating(self, new_preferred_heating_temperature):
        if new_preferred_heating_temperature > Constant.MAXIMUM_ALLOWED_TEMPERATURE - 1:
            new_preferred_heating_temperature = Constant.MAXIMUM_ALLOWED_TEMPERATURE - 1
            Warning('The temperature was reduced to', new_preferred_heating_temperature)
        if new_preferred_heating_temperature < Constant.MINIMUM_ALLOWED_TEMPERATURE + 1:
            new_preferred_heating_temperature = Constant.MINIMUM_ALLOWED_TEMPERATURE + 1
            Warning('The temperature was increased to', new_preferred_heating_temperature)
        self._preferredHeating = new_preferred_heating_temperature
        if self._maximumHeating < self._preferredHeating + 1:
            self.maximumHeating = self._preferredHeating + 1
            Warning('The occupancy mode maximum temperature is increased to', self._maximumHeating)
        if self._minimumHeating > self._preferredHeating - 1:
            self.minimumHeating = self._preferredHeating - 1
            Warning('The occupancy mode minimum temperature is decreased to', self._minimumHeating)

    preferredHeating = property(get_preferred_heating, set_preferred_heating)

    def get_maximum_heating(self):
        return self._maximumHeating

    def set_maximum_heating(self, new_maximum_heating_temperature):
        if new_maximum_heating_temperature > Constant.MAXIMUM_ALLOWED_TEMPERATURE:
            new_maximum_heating_temperature = Constant.MAXIMUM_ALLOWED_TEMPERATURE
            Warning('The temperature was reduced to', new_maximum_heating_temperature)
        if new_maximum_heating_temperature < self._preferredHeating + 1:
            new_maximum_heating_temperature = self._preferredHeating + 1
            Warning('The temperature was increased to', new_maximum_heating_temperature)
        self._maximumHeating = new_maximum_heating_temperature

    maximumHeating = property(get_maximum_heating, set_maximum_heating)

    def get_minimum_heating(self):
        return self._minimumHeating

    def set_minimum_heating(self, new_minimum_heating_temperature):
        if new_minimum_heating_temperature < Constant.MINIMUM_ALLOWED_TEMPERATURE:
            new_minimum_heating_temperature = Constant.MINIMUM_ALLOWED_TEMPERATURE
            Warning('The temperature was increased to', new_minimum_heating_temperature)
        if new_minimum_heating_temperature > self._preferredHeating - 1:
            new_minimum_heating_temperature = self._preferredHeating - 1
            Warning('The temperature was reduced to', new_minimum_heating_temperature)
        self._minimumHeating = new_minimum_heating_temperature

    minimumHeating = property(get_minimum_heating, set_minimum_heating)

    def get_occupancy_cost_mode(self):
        return self._occupancyCostMode

    def set_occupancy_cost_mode(self, new_occupancy_cost_mode):
        if new_occupancy_cost_mode > 1.0:
            new_occupancy_cost_mode = 1.0
            Warning('The occupancy cost mode is constrained between 0 adn 1.')
        elif new_occupancy_cost_mode < 0.0:
            new_occupancy_cost_mode = 0.0
            Warning('The occupancy cost mode is constrained between 0 adn 1.')
        self._occupancyCostMode = new_occupancy_cost_mode

    occupancyCostMode = property(get_occupancy_cost_mode, set_occupancy_cost_mode)

    def get_occupancy_risk_mode(self):
        return self._occupancyRiskMode

    def set_occupancy_risk_mode(self, new_occupancy_risk_mode):
        if new_occupancy_risk_mode > 1.0:
            new_occupancy_risk_mode = 1.0
            Warning('The occupancy risk mode is constrained between 0 adn 1.')
        elif new_occupancy_risk_mode < 0.0:
            new_occupancy_risk_mode = 0.0
            Warning('The occupancy risk mode is constrained between 0 adn 1.')
        self._occupancyRiskMode = new_occupancy_risk_mode

    occupancyRiskMode = property(get_occupancy_risk_mode, set_occupancy_risk_mode)
