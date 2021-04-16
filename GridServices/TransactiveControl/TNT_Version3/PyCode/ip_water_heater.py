"""
Islay Power Water Heater
This class manages the properties and energy behaviors of a water heater controller that is being developed for Islay
Power by Pacific Northwest National Laboratory, which is operated by Battelle Memorial Institute for the U.S. Department
of Energy.
Business sensitive to Islay Power.
Developed by Donald Hammerstom at Pacific Northwest National Laboratory, Richland, WA, USA, for Islay Power.
Copyright 2019 Don Hammerstrom, Battlle, PNNL
This class represents an Islay Power water heater that is responsive to forecasted prices and water usages.
"""

# This node is extends class LocalAsset and is responsive to class Market within the Transactive Network Template
# Metamodel. See report PNNL-28420 Rev. 1.
from local_asset_model import LocalAsset
# from market import Market
from datetime import datetime, timedelta, time
from vertex import Vertex
# from time_interval import TimeInterval
import numpy as np
import math
from ip_constants import Constant
from ip_occupancy_modes import OccupancyMode
from ip_occupancy_settings import OccupancySetting
from ip_weekdays import Weekday
from ip_cost_modes import CostMode
from ip_strategies import Strategy


class IpWaterHeater(LocalAsset):

    def __init__(self,
                 ambient_air_temperature=(50 - 32) / 1.8,  # [deg. C] = ([deg. F] - 32) / 1.8
                 cost_mode_setting=CostMode.BalancedEconomy,  # in range (0, 1)
                 default_power=0,  # [kW]
                 description='Islay Power water heater',  # [text]
                 element_power=4.5,  # [kW]
                 factor=3.6,  # [$/h]
                 gamma=2,  # [dimensionless]
                 inflow_temperature=(50 - 32) / 1.8,  # [deg. C] = ([deg. F) - 32) / 1.8
                 is_mpn=False,  # [Boolean]
                 location=None,  # [text]
                 lower_loss_rate=0.0159,  # [W / deg. C]
                 lower_temperature_set_point=(140 - 32) / 1.8,  # [deg. C] = ([deg. F] - 32) / 1.8
                 maximum_comfortable_temperature=(130 - 32) / 1.8,  # [deg. C]
                 maximum_power=0,  # [kW]
                 minimum_comfortable_temperature=(110 - 32) / 1.8,  # [deg. C]
                 minimum_power=-4.50,  # [kW]
                 name='Islay Power water heater',  # [text]
                 occupancy_mode=OccupancyMode.Occupied,  # See enumeration [OccupancyMode]
                 occupancy_setting=OccupancySetting.Scheduled,  # See enumeration [OccupancySetting]
                 preferred_delivery_temperature=(120 - 32) / 1.8,  # [deg. C]
                 risk_mode_setting=0.5,  # in range (0, 1)
                 scheduling_horizon=timedelta(hours=24),  # [time duration]
                 tank_volume=40 * 3.7,  # [liters] = [gallons] * 3.7
                 upper_loss_rate=0.00797,  # [W / deg. C]
                 upper_temperature_set_point=(120 - 32) / 1.8  # [deg. C] = ([deg. F] - 32) / 1.8
                 ):

        # Use initializations from base parent class:
        super(IpWaterHeater, self).__init__()

        # Redefine existing static class attributes:
        self.schedulingHorizon = scheduling_horizon  # [time duration] See LocalAsset.schedulingHorizon.
        self.defaultPower = default_power  # [kW] See LocalAsset.defaultPower.
        self.defaultVertices = Vertex(0, 0, 0)  # [IntervalValue:Vertex] See LocalAsset.defaultVertices.
        #                                                         See classes IntervalValue and Vertex.
        self.description = description  # [text]
        self.location = location  # [text]
        self.maximumPower = maximum_power  # [kW] See LocalAsset.maximumPower.
        self.minimumPower = minimum_power  # [kW] See LocalAsset.maximumPower.
        self.name = name  # [text]

        # Define new mode attributes:
        self.costModeSetting = cost_mode_setting  # [0, 1]: Ratio of utility cost to electricity cost.
        #                                                         Specifically, the ratio is:
        #                                                               costModeSetting : (1 - costModeSetting).
        self.occupancyMode = occupancy_mode  # See enumeration [OccupancyMode].
        self.occupancySetting = occupancy_setting  # See enumeration [OccupancySetting].
        self.riskModeSetting = risk_mode_setting  # [0, 1]: Relative prices to be chosen from their
        #                                                         positions in a cumulative distribution.

        # Define new configurable constant attributes:
        self.tankVolume = tank_volume  # [liters]
        self.upperVolume = self.tankVolume / 3  # [liters] Volume of top water slug (typically 1/3 of
        #                                                         tank)
        self.lowerVolume = 2 * self.tankVolume / 3  # [liters] Volume of bottom water slug (typically 2/3 of tank)
        self.upperLossRate = upper_loss_rate  # [W / deg. C] Heat loss rate function of wall temperature
        #                                             differential for upper water slug.
        self.lowerLossRate = lower_loss_rate  # [W / deg. C] Heat loss rate as a function of wall temperature
        #                                             differential for lower water slug.

        self.elementPower = element_power  # [kW] = [kJ/s]: upper and lower heating element power rating
        self.elementPower = 60 * self.elementPower  # [kJ/minute]
        self.elementPower = self.elementPower / 4.18  # [kCal/min] = [deg.C-l/min]

        self.upperHeatRate = element_power / self.upperVolume  # [deg. C/min] Maximum rate of upper slug heating
        #                                                         (typically 1.31 for a 40 gallon tank)
        self.lowerHeatRate = element_power / self.lowerVolume  # [deg. C/min] Maximum rate of lower slug heating
        #                                                         (typically 0.654 for a 40 gallon tank)
        self.upperTemperatureSetPoint = upper_temperature_set_point  # [deg. C] Setting of the upper thermostat.
        #                                                              This is not re-configurable on a conventional
        #                                                              tank water heater.
        self.lowerTemperatureSetPoint = lower_temperature_set_point  # [deg. C] Setting of the lower thermostat. This is
        #                                                              not re-configurable on a conventional tank water
        #                                                              heater.
        self.factor = factor  # [$/h] Multiplier that calibrates the comfort costs (see calculate_comfort_cost) to be
        #                       comparable with electricity costs. An acceptable strategy is to make the disutility cost
        #                       at minimum and maximum comfort temperatures about 10 times the electricity cost upon
        #                       operating the water heater full on (i.e., 4.5 kW). This value is about
        #                                             10 * $0.08 / kW * 4.5 kW = $3.6 / h
        #                       in the northwest U.S. If this calibration is successful, the water heater's cost mode
        #                       can meaningfully compare electricity and disutility costs.
        self.gamma = gamma  # [dimensionless] The exponential degree to which disutility cost increases as temperatures
        #                     vary around the preferred delivery temperature and approach. If gamma=1, there is a linear
        #                     change in disutility cost from the preferred delivery temperature (disutility cost = 0) to
        #                     either the minimum or maximum confortable temperatures, as which the disutility cost is
        #                     equal to property "factor." As gamma is increased, the costs become flatter near the
        #                     preferred delivery temperature and increase faster near the minimum and maximum
        #                     comfortable temperatures.
        self.maximumComfortableTemperature = maximum_comfortable_temperature  # [deg. C] A configurable, soft constraint
        #                                                                       on the maximum water delivery
        #                                                                       temperature. Comfort cost penalty
        #                                                                       increases rapidly as water delivery
        #                                                                       temperature approaches this maximum. The
        #                                                                       maximum may be modified by occupancy
        #                                                                       mode.
        self.minimumComfortableTemperature = minimum_comfortable_temperature  # [deg. C] A configurable, soft constraint
        #                                                                       on the minimum water delivery
        #                                                                       temperature. Comfort cost penalty
        #                                                                       increases rapidly as water delivery
        #                                                                       temperature approaches this maximum. The
        #                                                                       minimum may be modified by occupancy
        #                                                                       mode.
        self.preferredDeliveryTemperature = preferred_delivery_temperature  # [deg. C] Ideal heated water temperature.
        #                                                                     This preference may be affected by
        #                                                                     occupancy mode.
        # These functions check and may refine the minimum, preferred, and maximum temperatures to be self consistent.
        self.set_maximum_comfortable_temperature(self.maximumComfortableTemperature)
        self.set_minimum_comfortable_temperature(self.minimumComfortableTemperature)
        self.set_preferred_delivery_temperature(self.preferredDeliveryTemperature)

        # Define temperature measurements and predictions:
        self.ambientAirTemperature = ambient_air_temperature  # [deg. C] Air temperature surrounding water tank
        self.inflowTemperature = inflow_temperature  # [deg. C] Temperature of inflow water--measured or presumed
        self.currentUpperTemperature = self.upperTemperatureSetPoint  # [deg. C] Initialized. (Should be measured)
        self.currentLowerTemperature = self.lowerTemperatureSetPoint  # [deg. C] Initialized. (Probably inferred)
        self.modeledUpperTemperatures = []  # [deg. C] [IntervalValue] ... from model predictive control
        self.modeledLowerTemperatures = []  # [deg. C] [IntervalValue] ... from model predictive control

        # Other interval states and values to be tracked:
        self.waterUseModel = [0, 0] * 24  # [l/m] learned predicted hourly water use [average, std. dev]
        self.electricityUseMatrix = []
        self.modeledControlActionMatrix = []
        self.priceHorizon = []
        self.priorStateMatrix = []
        self.comfortCostMatrix = []
        self.cumulativeCostMatrix = []

        # New properties of Islay Power node devices:
        self._isMPN = is_mpn
        self.PPRNodeIds = []
        self.PPRPrices = []  # [IntervalValue:Float] [$/kWh] Local copy of markets' current marginal prices.
        # TODO: Consider whether class 'OccupancyMode' could be established to make this more elegant.
        self.daySets = []
        self._daySet1 = [Weekday.Monday, Weekday.Tuesday, Weekday.Wednesday, Weekday.Thursday, Weekday.Friday]
        #                                   A list of days that might be scheduled as workdays.
        self._daySet2 = [Weekday.Saturday, Weekday.Sunday]
        #                                   A list of days that might be scheduled as non-workday or weekend days.
        self.awayTimes = {  # Dictionary of start and end times for scheduled away occupancy mode.
            'weekday_start_time': time(hour=8),  # 'weekday' refers to day set #1
            'weekday_end_time': time(hour=17),
            'weekend_start_time': None,  # 'weekend' refers to day set #2
            'weekend_end_time': None
        }
        self.partyTimes = {  # Dictionary of start and end times for scheduled party occupancy mode.
            'weekday_start_time': None,  # 'weekday' refers to day set #1
            'weekday_end_time': None,
            'weekend_start_time': None,  # 'weekend' refers to day set #2
            'weekend_end_time': None
        }
        self.sleepTimes = {  # Dictionary of start and end times for scheduled sleep occupancy mode.
            'weekday_start_time': time(hour=22),  # 'weekday' refers to day set #1
            'weekday_end_time': time(hour=6),
            'weekend_start_time': time(hour=22),  # 'weekend' refers to day set #2
            'weekend_end_time': time(hour=6)
        }
        self.awaySetPoint = {  # Dictionary of away mode set point temperatures.
            'weekday_set_point': (120 - 32) / 1.8,  # 'weekday' refers to day set #1
            'weekend_set_point': (120 - 32) / 1.8  # 'weekend' refers to day set #2
        }
        self.guestSetPoint = {  # Dictionary of guest mode set point temperatures.
            'weekday_set_point': (120 - 32) / 1.8,  # 'weekday' refers to day set #1
            'weekend_set_point': (120 - 32) / 1.8  # 'weekend' refers to day set #2
        }
        self.occupiedSetPoint = {  # Dictionary of occupied mode set point temperatures.
            'weekday_set_point': (120 - 32) / 1.8,  # 'weekday' refers to day set #1
            'weekend_set_point': (120 - 32) / 1.8  # 'weekend' refers to day set #2
        }
        self.partySetPoint = {  # Dictionary of party mode set point temperatures.
            'weekday_set_point': (120 - 32) / 1.8,  # 'weekday' refers to day set #1
            'weekend_set_point': (120 - 32) / 1.8  # 'weekend' refers to day set #2
        }
        self.sleepSetPoint = {  # Dictionary of sleep mode set point temperatures.
            'weekday_set_point': (120 - 32) / 1.8,  # 'weekday' refers to day set #1
            'weekend_set_point': (120 - 32) / 1.8  # 'weekend' refers to day set #2
        }
        self.vacationSetPoint = {  # Dictionary of sleep mode set point temperatures.
            'weekday_set_point': (120 - 32) / 1.8,  # 'weekday' refers to day set #1
            'weekend_set_point': (120 - 32) / 1.8  # 'weekend' refers to day set #2
        }
        self.awayRange = {  # Dictionary of away mode high and low set points in cooling and heating modes.
            'cooling_low': None,
            'cooling_high': None,
            'heating_low': (110 - 32) / 1.8,
            'heating_high': (110 - 32) / 1.8
        }
        self.guestRange = {  # Dictionary of guest mode high and low set points in cooling and heating modes.
            'cooling_low': None,
            'cooling_high': None,
            'heating_low': (110 - 32) / 1.8,
            'heating_high': (110 - 32) / 1.8
        }
        self.occupiedRange = {  # Dictionary of occupied mode high and low set points in cooling and heating modes.
            'cooling_low': None,
            'cooling_high': None,
            'heating_low': (110 - 32) / 1.8,
            'heating_high': (110 - 32) / 1.8
        }
        self.partyRange = {  # Dictionary of party mode high and low set points in cooling and heating modes.
            'cooling_low': None,
            'cooling_high': None,
            'heating_low': (110 - 32) / 1.8,
            'heating_high': (110 - 32) / 1.8
        }
        self.sleepRange = {  # Dictionary of sleep mode high and low set points in cooling and heating modes.
            'cooling_low': None,
            'cooling_high': None,
            'heating_low': (110 - 32) / 1.8,
            'heating_high': (110 - 32) / 1.8
        }
        self.vacationRange = {  # Dictionary of vacation mode high and low set points in cooling and heating modes.
            'cooling_low': None,
            'cooling_high': None,
            'heating_low': (110 - 32) / 1.8,
            'heating_high': (110 - 32) / 1.8
        }
        self.strategy = Strategy.Heating

    def calculate_comfort_cost(self, water_delivery_temperatures):
        """
        This function calculates an average disutility penalty cost that is based on a water heater's delivery
        temperatures. The cost is zero at the preferred water delivery temperature and increases as the forecasted
        delivery temperature becomes farther from the user's preferred temperature. The parameters reflect the
        sensitivity of the user to diversions from the preferred temperature. The average disutility [$/h] should be
        scaled to be comparable comparable with electricity cost [$/h]. If this is accomplished, a comfort mode
        parameter can meaningfully trade off the values of electricity and disutility costs.

        :param water_delivery_temperatures: [list] [deg. C] One or more forecasted water delivery temperatures. Equal to
                                            the predicted or actual temperature of the upper water volume.
        :return: [avg. $ / h] Average disutility cost penalty for the list of forecasted water delivery temperatures

        January 2020: Recoded in Python from Matlab code.
        Donald J. Hammerstrom, Ph.D.
        Battelle Memorial Institute
        Contract 73346 for Islay Power.
        """

        # Raise a warning if any of the forecasted water delivery temperatures is outside the allowable temperature
        # range.
        if any([x < Constant.MINIMUM_ALLOWED_TEMPERATURE or x > Constant.MAXIMUM_ALLOWED_TEMPERATURE
                for x in water_delivery_temperatures]):
            Warning('Water delivery temperatures exceed the allowed range.')

        # Calculate the sum disutility costs for the water delivery temperatures, based on the stated preferences. This
        # calculation has a sign convention and potential asymmetry, so it must be performed separately for delivery
        # temperatures that are above and below the preferred water delivery temperature.
        cost = 0  # initialize cost
        for x in range(len(water_delivery_temperatures)):
            if water_delivery_temperatures[x] >= self.preferredDeliveryTemperature:
                cost = cost + self.factor * (
                        (water_delivery_temperatures[x] - self.preferredDeliveryTemperature)
                        / (self.maximumComfortableTemperature - self.preferredDeliveryTemperature)
                ) ** self.gamma
            else:
                cost = cost + self.factor * (
                        (water_delivery_temperatures[x] - self.preferredDeliveryTemperature)
                        / (self.minimumComfortableTemperature - self.preferredDeliveryTemperature)
                ) ** self.gamma

        # Take the average of the individual costs.
        cost = cost / len(water_delivery_temperatures)

        return cost

    # @property
    def get_cost_mode(self):
        # TODO: Use @property
        return self.costModeSetting

    # @property
    def get_current_ambient_temperature(self):
        # TODO: Use @property
        """
        This method should measure or estimate or infer the ambient temperature to which the water heater loses heat.
        The water heater's thermal model uses this temperature to forecast the effect of losses on water heater
        performance.
        These are viable strategies:
        1) Directly measure the ambient temperature. (preferred)
        2) Use a weather service and seasons to estimate ambient temperature
        3) Use a static configured temperature, which could work perfectly well for a water heater that resides in a
           conditioned indoor space.
        :return ambient temperature:
        """
        try:  # to directly measure the ambient temperature.
            raise RuntimeError

        except RuntimeError('The ambient temperature could not be directly measured.'):
            pass

        return (50 - 32) / 1.8  # = 10 deg. Celsius

    # @property
    def get_current_lower_temperature(self):
        # TODO: Use @property
        """
        The temperature of the lower water heater slug might be measured at the lower thermostat, but it is more likely
        that the current lower water heater temperature will be inferred from the water heater model over time.
        If it is measured, this value corrects the models initial lower slug water temperature.
        This method tries first to measure the lower slug temperature, if that fails, it tries to infer the lower slug
        temperature from the model. If neither approach works, a warning occurs, and the last value, possibly the
        initialized temperature, is returned.
        :return: current lower temperature [deg. C]
        """

        now = datetime.now()

        try:  # to measure the current lower slug temperature
            # TODO: Code the measurement of current lower slug temperature.
            pass

        except RuntimeWarning('Could not measure the lower water slug temperature'):

            try:  # ... to use the modeled current lower slug temperature from model predictive control.

                modeled_lower_temperatures = self.modeledLowerTemperatures

                if modeled_lower_temperatures is None or len(modeled_lower_temperatures) == 0:
                    raise RuntimeWarning('No lower temperatures have been modeled.')

                for x in range(len(modeled_lower_temperatures)):
                    interval_start = modeled_lower_temperatures[x].timeInterval.startTime
                    interval_end = interval_start + modeled_lower_temperatures[x].market.intervalDuration

                    if interval_start <= now < interval_end:
                        self.currentLowerTemperature = modeled_lower_temperatures[x].value
                        break  # out of for loop if a suitable temperature has been found.

            except RuntimeWarning('The lower slug temperature can neither be measured nor inferred from the model.'):
                # As last resort, use the current initialized lower slug temperature value and raise a warning.
                pass

        return self.currentLowerTemperature

    # @property
    def get_current_upper_temperature(self):
        # TODO: Use @property
        """
         The temperature of the upper water heater slug might be measured at the outflow or pressure relief valve.
         Alternatively, the upper water temperature may be inferred from model predictive control, but using a modeled
         value is much less desirable than using an actual measurement.
         If it is measured, this value corrects the models initial upper slug water temperature.
         This method tries first to measure the upper slug temperature, if that fails, it tries to infer the upper slug
         temperature from the model. If neither approach works, an error is raised, and the last value, possibly the
         initialized temperature, is returned.
         :return: current upper temperature [deg. C]
         """

        now = datetime.now()

        try:  # to measure the current upper slug temperature
            # TODO: Code the measurement of the current upper slug temperature.
            raise RuntimeError

        except RuntimeError('Failed to measure upper slug temperature'):

            try:  # ... to use the modeled current upper slug temperature from model predictive control.

                modeled_upper_temperatures = self.modeledUpperTemperatures

                if modeled_upper_temperatures is None or len(modeled_upper_temperatures) == 0:
                    # modeled_upper_temperatures = []
                    raise RuntimeWarning('Upper temperatures have not been modeled.')

                for x in range(len(modeled_upper_temperatures)):
                    interval_start = modeled_upper_temperatures[x].timeInterval.startTime
                    interval_end = interval_start + modeled_upper_temperatures[x].market.intervalDuration

                    if interval_start <= now < interval_end:
                        self.currentUpperTemperature = modeled_upper_temperatures[x].value
                        break  # out of for loop

            except RuntimeWarning('The upper slug temperature can neither be measured nor inferred from the model.'):
                # As last resort, use the current initialized upper slug temperature value.
                pass

        return self.currentUpperTemperature

    def get_daySet1(self):
        return self._daySet1

    def set_daySet1(self, values):
        # This method receives a list of integers, tests its members, replaces property _daySet1 with members that pass
        # tests while ignoring others, and reorders the protected list _daySet1.
        # NOTE: Built-in methods like append() should not be used directly here (e.g., object.daySet1.append(0)) because
        # doing so fails to invoke this setter. Instead, invoke by
        #                           temp = object.daySet1.append(0)
        #                           object.daySet1 = temp
        if not isinstance(values, list):
            values = [values]
        temp = []
        for x in values:
            if not isinstance(x, int):
                Warning('Days are stored as integers in the range from 0 to 6.')
            elif x not in range(7):
                Warning('Days must be in range 0 to 6.')
            elif x in self.daySet2:
                Warning('A day in day set 2 cannot be in day set 1.')
            elif x in temp:
                Warning('Days will not be duplicated.')
            else:
                temp.append(x)
        self._daySet1 = temp
        self._daySet1.sort()

    daySet1 = property(get_daySet1, set_daySet1)

    def get_daySet2(self):
        return self._daySet2

    def set_daySet2(self, values):
        # This method receives a list of integers, tests its members, replaces property _daySet2 with members that pass
        # tests while ignoring others, and reorders the protected list _daySet2.
        # NOTE: Built-in methods like append() should not be used directly here (e.g., object.daySet2.append(0)) because
        # doing so fails to invoke this setter. Instead, invoke by
        #                           temp = object.daySet2.append(0)
        #                           object.daySet2 = temp
        # NOTE: A day must be removed from daySet1 before it can be added to daySet2.
        if not isinstance(values, list):
            values = [values]
        temp = []
        for x in values:
            if not isinstance(x, int):
                Warning('Days are stored as integers in the range from 0 to 6.')
            elif x not in range(7):
                Warning('Days must be in the range 0 to 6.')
            elif x in self.daySet1:
                Warning('A day in day set 1 cannot be added to day set 2.')
            elif x in temp:
                Warning('Days will not be duplicated.')
            else:
                temp.append(x)
        self._daySet2 = temp
        self._daySet2.sort()

    daySet2 = property(get_daySet2, set_daySet2)

    # @property
    def get_inflow_temperature(self):
        # TODO: Use @property
        """
        The temperature of water entering the water heater may be measured. However, at many locations it is often
        constant enough that a constant initialization value may be used, e.g., 50 F [= 10 C].
        This method should measure the inlet temperature, represent it in deg. C, save it into property
        'inletTemperature,' and return the value, as well.
        :return: inlet temperature [deg. C]
        """
        try:  # to measure the inlet water temperature
            # TODO: Add code to measure the inlet water temperature
            pass

        except RuntimeWarning('Inlet water temperature could not be measured'):
            # Current initialized inlet temperature will be used.
            pass

        return self.inflowTemperature

    def get_isMPN(self):
        return self._isMPN

    def set_isMPN(self, value):
        # Receives a Boolean value, tests it, and replaces the property _isMPN.
        if not isinstance(value, bool):
            Warning('Property "isMPN" must be Boolean.')
        else:
            self._isMPN = value

    isMPN = property(get_isMPN, set_isMPN)

    # @property
    def get_maximum_comfortable_temperature(self):
        # TODO: Use @property
        return self.maximumComfortableTemperature

    # @property
    def get_minimum_comfortable_temperature(self):
        # TODO: Use @property
        return self.minimumComfortableTemperature

    # @property
    def get_occupancy_mode(self):
        # TODO: Use @property
        return self.occupancyMode

    # @property
    def get_preferred_delivery_temperature(self):
        # TODO: Use @property
        return self.preferredDeliveryTemperature

    # @property
    def get_risk_mode(self):
        # TODO: Use @property
        return self.riskModeSetting

    def model_water_use(self, datetime_item, new_water_use=None, k=14):
        """
        This method returns its best forcasted average and standard deviation water use [l/m] in the hour of the
        supplied datetime parameter. If additionally, a new water use datum is provided, the method also updates the
        simple model of water use by hour.
        :return: forecast average and standard deviation water use in hour [l/m]
        """
        # TODO: Refine this method to infer and model water usage. This is a candidate for AI.
        avg_water_use = None
        sd_water_use = None

        try:
            if type(datetime_item) == datetime:
                h = int(datetime_item.hour)
            else:
                raise RuntimeError('A datetime item must be supplied as a parameter.')

            avg_water_use = self.waterUseModel[2 * h]
            sd_water_use = self.waterUseModel[2 * h + 1]

            if new_water_use is not None:
                avg_water_use = ((k - 1.0) * avg_water_use + new_water_use) / k
                sd_water_use = (((k - 1.0) * sd_water_use ** 2 + (avg_water_use - new_water_use) ** 2) / k) ** 0.5
                self.waterUseModel[2 * h] = avg_water_use
                self.waterUseModel[2 * h + 1] = sd_water_use

        except NameError("Could not use the water use model to determine or set a water use"):
            pass

        return avg_water_use, sd_water_use

    def predict_temperatures(self, number_of_minutes, initial_upper_temperature, initial_lower_temperature,
                             average_water_use, power_fraction):
        """
        This method forecasts upper and lower water heater slug temperatures for a time interval having a discrete
        number of included minutes. Initial upper and lower temperatures are passed to this method as initial
        condictions. The simulation is forecasted water usage, the fraction of electrical heating element power that is
        applied, and many properties of the water heater like upper and lower volumes and lossiness and thermostat set
        points.
        :param number_of_minutes: [whole number] A discrete number of minutes. The model currently works for discrete
                                  numbers of minutes. For example, an hour-long time interval would have precisely 60
                                  minutes.
        :param initial_upper_temperature: [deg. C] The initial measured or modeled temperature of the water heater's
                                          upper volume.
        :param initial_lower_temperature: [deg. C] The initial measured or modeled temperature of the water heater's
                                          lower volume.
        :param average_water_use: [avg. l / mimute] Agerage forecasted water consumption during the interval.
        :param power_fraction: [dimensionless] Controlled fraction or duty cycle of maximum electrical heating element
                               power that is to be applied during the time interval.
        :return upper_temperatures: [deg. C] Representative upper volume water temperature during each minute of the
                                    simulation.
        :return lower_temperatures: [deg. C] Representative lower volume water temperature during each minute of the
                                    simulation.
        :return upper_control_states: [Boolean] For each simulation minute, the state of the upper water heater
                                      thermostat:
                                      ON:  Conducting: 1
                                      OFF: Open:       0
        :return lower_control_states: [Boolean] For each simulation minute, the state of the lower water heater
                                      thermostat:
                                      ON:  Conducting: 1
                                      OFF: Open:       0
        """

        upper_temperature = initial_upper_temperature
        lower_temperature = initial_lower_temperature

        inflow_temperature = self.inflowTemperature
        ambient_air_temperature = self.ambientAirTemperature
        upper_loss_rate = self.upperLossRate
        lower_loss_rate = self.lowerLossRate
        upper_heat_rate = self.upperHeatRate
        lower_heat_rate = self.lowerHeatRate
        upper_volume = self.upperVolume
        lower_volume = self.lowerVolume
        upper_temperature_set_point = self.upperTemperatureSetPoint
        lower_temperature_set_point = self.lowerTemperatureSetPoint

        # Initialize output vectors.
        upper_temperatures = np.zeros(number_of_minutes)
        lower_temperatures = np.zeros(number_of_minutes)
        upper_control_states = np.zeros(number_of_minutes)
        lower_control_states = np.zeros(number_of_minutes)

        interval = 0

        while interval < number_of_minutes:
            lower_thermostat_state = Constant.OFF  # = 0
            if upper_temperature < upper_temperature_set_point - Constant.HYSTERESIS:
                upper_thermostat_state = Constant.ON  # = 1
            else:
                upper_thermostat_state = Constant.OFF
                if lower_temperature < lower_temperature_set_point - Constant.HYSTERESIS:
                    lower_thermostat_state = Constant.ON

            upper_control_states[interval] = upper_thermostat_state
            lower_control_states[interval] = lower_thermostat_state

            # Calculate the upper water heater temperature at end of minute.
            term_u1 = ambient_air_temperature * upper_loss_rate ** 2 * lower_volume \
                      - upper_temperature * upper_loss_rate ** 2 * lower_volume \
                      + lower_temperature * average_water_use ** 2 * lower_volume \
                      - inflow_temperature * average_water_use ** 2 * upper_volume \
                      - upper_temperature * average_water_use ** 2 * lower_volume \
                      + upper_temperature * average_water_use ** 2 * upper_volume \
                      - ambient_air_temperature * lower_loss_rate * upper_loss_rate * upper_volume \
                      + upper_temperature * lower_loss_rate * upper_loss_rate * upper_volume \
                      + lower_temperature * upper_loss_rate * average_water_use * lower_volume \
                      - ambient_air_temperature * lower_loss_rate * average_water_use * upper_volume \
                      + ambient_air_temperature * upper_loss_rate * average_water_use * lower_volume \
                      + upper_temperature * lower_loss_rate * average_water_use * upper_volume \
                      - 2 * upper_temperature * upper_loss_rate * average_water_use * lower_volume \
                      - ambient_air_temperature * upper_loss_rate * average_water_use * upper_volume \
                      + upper_temperature * upper_loss_rate * average_water_use * upper_volume \
                      - upper_heat_rate * power_fraction * upper_thermostat_state * lower_loss_rate * upper_volume ** 2 \
                      - upper_heat_rate * power_fraction * upper_thermostat_state * average_water_use * upper_volume ** 2 \
                      + upper_heat_rate * power_fraction * upper_thermostat_state * average_water_use * lower_volume \
                      * upper_volume \
                      - lower_heat_rate * power_fraction * lower_thermostat_state * average_water_use * lower_volume \
                      * upper_volume \
                      + upper_heat_rate * power_fraction * upper_thermostat_state * average_water_use * lower_volume \
                      * upper_volume

            term_u1 = term_u1 * math.exp(-(upper_loss_rate + average_water_use) / upper_volume)

            term_u1 = term_u1 / ((upper_loss_rate + average_water_use)
                                 * (upper_loss_rate + average_water_use) * (upper_volume - lower_volume))

            term_u2 = lower_volume * math.exp(-(upper_loss_rate + average_water_use) / lower_volume)

            term_u2 = term_u2 * (inflow_temperature * average_water_use ** 2
                                 - lower_temperature * average_water_use ** 2
                                 - lower_temperature * lower_loss_rate * average_water_use
                                 + ambient_air_temperature * lower_loss_rate * average_water_use
                                 + lower_heat_rate * power_fraction * lower_thermostat_state * average_water_use
                                 * lower_volume)

            term_u2 = term_u2 / ((lower_loss_rate + average_water_use)
                                 * (lower_loss_rate * upper_volume
                                    - upper_loss_rate * lower_volume
                                    - average_water_use * (upper_volume - lower_volume)))

            term_u3 = inflow_temperature * average_water_use ** 2 \
                      + ambient_air_temperature * lower_loss_rate * upper_loss_rate \
                      + ambient_air_temperature * lower_loss_rate * average_water_use \
                      + ambient_air_temperature * upper_loss_rate * average_water_use \
                      + upper_heat_rate * power_fraction * upper_thermostat_state * lower_loss_rate * upper_volume \
                      + lower_heat_rate * power_fraction * lower_thermostat_state * average_water_use * lower_volume \
                      + upper_heat_rate * power_fraction * upper_thermostat_state * average_water_use * upper_volume

            term_u3 = term_u3 / (average_water_use * (upper_loss_rate + lower_loss_rate))

            upper_temperatures[interval] = term_u1 + term_u2 + term_u3

            # Calculate lower water heater temperature at end of minute.
            term_l = - (ambient_air_temperature * lower_loss_rate
                        - lower_temperature * lower_loss_rate
                        + inflow_temperature * average_water_use
                        - lower_temperature * average_water_use
                        + lower_heat_rate * power_fraction * lower_thermostat_state * lower_volume)

            term_l = term_l * math.exp(-(lower_loss_rate + average_water_use) / lower_volume)

            term_l = term_l + (ambient_air_temperature * lower_loss_rate
                               + inflow_temperature * average_water_use
                               + lower_heat_rate * power_fraction * lower_thermostat_state * lower_volume)

            lower_temperatures[interval] = term_l / (lower_loss_rate + average_water_use)

            upper_temperature = upper_temperatures[interval]
            lower_temperature = lower_temperatures[interval]
            interval = interval + 1

        return upper_temperatures, lower_temperatures, upper_control_states, lower_control_states

    def schedule_power(self, market):

        # Use this existing method to collect relevant marginal prices which include 1) the market's discovered forward
        # prices and 2) other prices in the remainder of the asset's forward scheduling horizon. The method uses various
        # strategies to forecast meaningful forward prices for the asset's entire forward scheduling horizon.
        marginal_prices = self.get_extended_prices(market)

        # Scheduling must be performed for all the time intervals for which forward marginal prices are being
        # forecast.
        time_intervals = [x.timeInterval for x in marginal_prices]

        current_upper_temperature = self.get_current_upper_temperature()
        current_lower_temperature = self.get_current_lower_temperature()

        # Establish the matrix for keeping track of cumulative transition costs.
        cumulative_costs = np.zeros(len(time_intervals) * 3)
        cumulative_costs.shape = (len(time_intervals), 3)

        # Establish the matrix for keeping track up upper and lower temperatures in each time interval.
        #       (time interval index, alternative index, upper and lower temperature index)
        upper = 0  # index to upper water temperature
        lower = 1  # index to lower water temperature
        temperature = np.zeros(len(time_intervals) * 3 * 2)
        temperature.shape = (len(time_intervals), 3, 2)

        # Establish a matrix to keep track of the alternative control actions, namely the fraction of full power that is
        # to energize the water heater during each forward time interval, on average. In each time interval, the
        # relative control actions are initialized to [0.2, 0.25, 0.3].
        # NOTE: This is variable Phi in the initial Matlab formulation.
        interval_power_fraction = np.zeros(len(time_intervals) * 3)
        interval_power_fraction.shape = (len(time_intervals), 3)
        for x in range(len(time_intervals)):
            interval_power_fraction[x] = [0.2, 0.25, 0.3]

        # Establish a matrix to keep track of the optimal prior state indices.
        best_prior_state = np.zeros(len(time_intervals) * 3)
        best_prior_state = best_prior_state.astype(int)
        best_prior_state.shape = (len(time_intervals), 3)

        # Establish a matrix to keep track of the comfort cost for three alternative control actions in each time
        # interval.
        comfort_cost = np.zeros(len(time_intervals), 3)
        comfort_cost.shape = (len(time_intervals), 3)

        # Establish a matrix to keep track of the electricity usage for three alternative control actions in each time
        # interval.
        electricity = np.zeros(len(time_intervals) * 3)
        electricity.shape = (len(time_intervals), 3)

        p_inf = float("inf")

        while any(best_prior_state[:][1] != 1):

            for time_interval in range(len(time_intervals)):

                for alternative_control_action in range(3):

                    cumulative_costs[time_interval][alternative_control_action] = p_inf

                    for prior_state in [1, 0, 2]:

                        initial_upper_temperature = current_upper_temperature
                        initial_lower_temperature = current_lower_temperature

                        if time_interval > 0:
                            initial_upper_temperature = temperature[time_interval][prior_state][upper]
                            initial_lower_temperature = temperature[time_interval][prior_state][lower]

                        number_of_seconds = int(time_intervals[time_interval].duration.total_seconds())
                        number_of_minutes = number_of_seconds / 60
                        number_of_minutes = round(number_of_minutes)
                        number_of_minutes = int(number_of_minutes)

                        # TODO: Refine water usage forecast. Maybe interpolate between hours for shorter intervals.
                        average_water_use = self.model_water_use(time_intervals[time_interval])

                        power_fraction = interval_power_fraction[time_interval][alternative_control_action]

                        # TODO: 200120DJH: Working here after function predict_temperatures established.
                        upper_temperatures, lower_temperatures, upper_control_states, lower_control_states = \
                            self.predict_temperatures(number_of_minutes,
                                                      initial_upper_temperature,
                                                      initial_lower_temperature,
                                                      average_water_use,
                                                      power_fraction
                                                      )

                        alternative_comfort_cost = self.calculate_comfort_cost(*upper_temperatures)

                        # The cost of electricity in this alternative transition is found from the time interval's
                        # marginal price, the controlled duty cycle fraction, the water heater's heating element size,
                        # and the states of the water heater's upper and lower thermostats.
                        transitional_electricity_usage = 0
                        for x in range(len(upper_control_states)):
                            on_state = upper_control_states[x] or lower_control_states[x]
                            transitional_electricity_usage = transitional_electricity_usage \
                                                             + self.elementPower * power_fraction * on_state / number_of_minutes

                        # Initialize the total cumulative cost of this transition alternative. The initial cost at t=0
                        # is zero. Later time intervals inherit the cumulative costs from the prior state from which the
                        # transition is being made.
                        alternative_cost = 0
                        if time_interval > 0:
                            alternative_cost = cumulative_costs[time_interval - 1][prior_state]

                        # The cost of this transitional alternative is the sum costs 1) inherited from the prior state,
                        # 2) comfort cost penalties incurred by this alternative, and
                        # 3) electricity costs incurred by this alternative transition.
                        alternative_cost = alternative_cost \
                                           + self.costModeSetting * alternative_comfort_cost \
                                           + (1 - self.costModeSetting) * marginal_prices[time_interval] \
                                           * transitional_electricity_usage

                        if alternative_cost < cumulative_costs[time_interval][alternative_control_action]:
                            cumulative_costs[time_interval][alternative_control_action] = alternative_cost
                            temperature[time_interval][alternative_control_action][upper] = upper_temperatures[-1]
                            temperature[time_interval][alternative_control_action][lower] = lower_temperatures[-1]
                            best_prior_state[time_interval][alternative_control_action] = prior_state
                            cumulative_costs[time_interval][alternative_control_action] = alternative_cost
                            electricity[time_interval][alternative_control_action] = transitional_electricity_usage

                        print(time_interval, alternative_control_action, prior_state)

        self.scheduleCalculated = True
        return None

    # @costModeSetting.setter
    def set_cost_mode(self, new_cost_mode):
        # TODO: Use @costModeSetting.setter to make property private and automate value checking.
        """
        Facilitates the changing of cost mode, which is the relative weighting of comfort and electricity costs.
        The cost mode must lie in range (0, 1). The utility (e.g., comfort) cost is multiplied by the cost mode value,
        and utility expense is multiplied by (1 - cost mode).
        :param new_cost_mode: desired cost mode
        :return: new_cost_mode
        """
        self.costModeSetting = new_cost_mode
        self.costModeSetting = min(self.costModeSetting, 1.0)
        self.costModeSetting = max(self.costModeSetting, 0.0)

        return self.costModeSetting

    # @maximumComfortableTemperature.setter
    def set_maximum_comfortable_temperature(self, new_temperature):
        # TODO: Use @maximumComfortableTemperature.setter to make property private and automate value checking.
        """
        Set the maximum comfortable temperature while checking for common logic and entry errors.
        The final setting may be quite different from the input parameter if the parameter does not lie within a logical
        order within the range parameters. Changes are enforced to maintain the logical order between hard and comfort
        constraints.
        :param new_temperature: [deg. C] Requested new temperature setting.
        :return: None
        """

        # Presume the provided temperature is fine.
        self.maximumComfortableTemperature = new_temperature

        # Reduce the temperature if the new temperature exceeds the hard, constant limit.
        if self.maximumComfortableTemperature > Constant.MAXIMUM_ALLOWED_TEMPERATURE:
            self.maximumComfortableTemperature = Constant.MAXIMUM_ALLOWED_TEMPERATURE
            Warning('Maximum comfortable temperature was reduced to ', self.maximumComfortableTemperature, ' C.')

        # Reduce the maximum delivery temperature if it lies above both the upper and lower thermostat set points.
        # Temperatures cannot be made higher than this limit.
        if self.maximumComfortableTemperature > max(self.lowerTemperatureSetPoint, self.upperTemperatureSetPoint):
            self.maximumComfortableTemperature = max(self.lowerTemperatureSetPoint, self.upperTemperatureSetPoint)
            Warning('The maximum comfortable temperature is reduced to ', self.maximumComfortableTemperature,
                    ' C due to thermostat set points.')

        # # Increase the temperature if it lies well below the current minimum comfortable temperature.
        # if self.maximumComfortableTemperature < self.minimumComfortableTemperature + 2:
        #     self.maximumComfortableTemperature = self.minimumComfortableTemperature + 2
        #     raise RuntimeWarning('Maximum comfortable temperature was increased to ',
        #                          self.maximumComfortableTemperature, ' C.')

        # Increase the temperature if it lies not less than 1 degree above the preferred temperature.
        if self.maximumComfortableTemperature < self.preferredDeliveryTemperature + 1:
            self.maximumComfortableTemperature = self.preferredDeliveryTemperature + 1
            Warning('Maximum comfortable temperature was increased to ', self.maximumComfortableTemperature, ' C.')

        return None

    # @minimumComfortableTemperature.setter
    def set_minimum_comfortable_temperature(self, new_temperature):
        # TODO: Use @minimumComfortableTemperature.setter to make property private and automate value checking.
        """
        Set the minimum comfortable temperature while checking for common logic and entry errors.
        The final setting may be quite different from the input parameter if the parameter does not lie within a logical
        order within the range parameters. Changes are enforced to maintain the logical order between hard and comfort
        constraints.
        :param new_temperature: [deg. C] Requested new temperature setting.
        :return:
        """
        # Presume that the provided temperature is acceptable.
        self.minimumComfortableTemperature = new_temperature

        # Increase the temperature if the new temperature is below the hard, constant range limit.
        if self.minimumComfortableTemperature < Constant.MINIMUM_ALLOWED_TEMPERATURE:
            self.minimumComfortableTemperature = Constant.MINIMUM_ALLOWED_TEMPERATURE
            Warning('Minimum comfortable temperature was increased to ', self.minimumComfortableTemperature, ' C.')

        # Reduce the temperature if it lies not far below the preferred delivery temperature.
        if self.minimumComfortableTemperature > self.preferredDeliveryTemperature - 1:
            self.minimumComfortableTemperature = self.preferredDeliveryTemperature - 1
            Warning('Minimum comfortable temperature was reduced to ', self.minimumComfortableTemperature, ' C.')

        return None

    # @preferredDeliveryTemperature.setter
    def set_preferred_delivery_temperature(self, new_temperature):
        # TODO: Use @preferredDeliveryTemperature.setter to make property private and automate value checking.
        """
        Set the preferred water delivery temperature while respecting common logic and entry errors.
        The final setting may be quite different from the input parameter if the parameter does not lie within a logical
        order within the range parameters. Changes are enforced to maintain the logical order between hard and comfort
        constraints.
        :param new_temperature: [deg. C] New temperature setting.
        :return: None.
        """

        # Start by accepting the provided temperature.
        self.preferredDeliveryTemperature = new_temperature

        # Reduce the temperature if it lies above the soft comfort range.
        if self.preferredDeliveryTemperature > self.maximumComfortableTemperature - 1:
            self.preferredDeliveryTemperature = self.maximumComfortableTemperature - 1
            Warning('The preferred delivery temperature was reduced to ',
                    self.preferredDeliveryTemperature, ' C due to maximum comfort temperature constraint.')

        # Reduce the preferred delivery temperature if it lies above both the upper and lower thermostat setpoints.
        # Temperatures cannot be made higher than this limit.
        if self.preferredDeliveryTemperature > max(self.lowerTemperatureSetPoint, self.upperTemperatureSetPoint):
            self.preferredDeliveryTemperature = max(self.lowerTemperatureSetPoint, self.upperTemperatureSetPoint)
            Warning('The preferred temperature is reduced to ',
                    self.preferredDeliveryTemperature, ' C due to thermostat set points.')

        # Increase the temperature is it lies below the soft comfort range.
        if self.preferredDeliveryTemperature < self.minimumComfortableTemperature + 1:
            self.preferredDeliveryTemperature = self.minimumComfortableTemperature + 1
            Warning('The preferred delivery temperature was increased to ',
                    self.preferredDeliveryTemperature, ' C due to minimum comfort temperature constraint.')

        return None

    # @riskModeSetting.setter
    def set_risk_mode(self, new_risk_mode):
        # TODO: Use @riskModeSetting.setter to make property private and automate value checking.
        """
        Facilitates the changing of risk mode, which is the relative position of available prices within their
        cumulative distributions. The risk mode must lie in range (0, 1). Value 0 would use the very lowest prices from
        the distributions; value 0.5 uses the median prices; and value 1.0 uses the highest prices.
        :param new_risk_mode: desired risk mode
        :return: new_risk_mode
        """
        self.riskModeSetting = new_risk_mode

        if self.riskModeSetting > 1.0:
            self.riskModeSetting = 1.0
            Warning('The risk mode is being limited to', self.riskModeSetting, '.')

        elif self.riskModeSetting < 0.0:
            self.riskModeSetting = 0.0
            Warning('The risk mode is being limited to ', self.riskModeSetting, '.')

        return self.riskModeSetting
