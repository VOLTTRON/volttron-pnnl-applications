# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# 'AS IS' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}


from datetime import datetime, timedelta, date, time

import logging
"""
utils.setup_logging()
_log = logging.getLogger(__name__)
"""

from .helpers import *
from .measurement_type import MeasurementType
from .measurement_unit import MeasurementUnit
from .interval_value import IntervalValue
from .market import Market
from .time_interval import TimeInterval
from .local_asset_model import LocalAsset
from .temperature_forecast_model import TemperatureForecastModel
from .vertex import Vertex
from .market_state import MarketState

class OpenLoopRichlandLoadPredictor(LocalAsset, object):
    # OPENLOOPRICHLANDLOADPREDICTOR - predicted electrical load of the City of
    # Richland using hour-of-day, season, heating/cooling regime, and
    # forecasted Fahrenheit temperature.

    # Uses Excel file "Richland_Load_Model_Coefficients.xlsx."
    # Predictor formula
    # LOAD = DOW_Intercept(DOW)
    # + HOUR_SEASON_REGIME_Intercept(HOUR,SEASON,REGIME)
    # + Factor(HOUR,SEASON,REGIME) * TEMP
    # DOW_Intercept - average kW - Addend that is a function of categorical
    # day-of-week.
    # HOUR - Categorical hour of day in the range [1, 24]
    # HOUR_SEASON_REGIME_Factor - avg.kW / deg.F - Factor of TEMP. A function
    # of categoricals HOUR, SEASON, and REGIME.
    # HOUR_SEASON_REGIME_Intercept - average kW - Addend that is a function
    # of categoricals HOUR, SEASON, and REGIME.
    # LOAD - average kW - Predicted hourly Richland, WA electric load
    # REGIME - Categorical {"Cool", "Heat", or "NA"}. Applies only in seasons
    # Spring and Fall. Not to be used for Summer or Winter seasons.
    # SEASON - Categorical season
    # "Spring" - [Mar, May]
    # "Summer" - [Jun, Aug]
    # "Fall"   - [Sep, Nov]
    # "Winter" - [Dec, Feb]
    # TEMP - degrees Fahrenheit - a predicted hourly temperature forecast.

    # DOW_INTERCEPT - addend as function of day-of-weak [avg.kW]
    dowIntercept = [144786,  # Monday
                    146281,  # Tuesday
                    146119,  # Wednesday
                    145577,  # Thursday
                    143896,  # Friday
                    139432,  # Saturday
                    138118]  # Sunday
    # SEASON - Maps categorical SEASON to the lookup table as a function of MONTH.
    season = [6,  # January   Winter
              6,  # February  Winter
              1,  # March     Spring
              1,  # April     Spring
              1,  # May       Spring
              3,  # June      Summer
              3,  # July      Summer
              3,  # August    Summer
              4,  # September Fall
              4,  # October   Fall
              4,  # November  Fall
              6]  # December  Winter

    values = [
        [-149652, 1245],
        [-34392, -818],
        [-131968, 1081],
        [-124130, 874],
        [-27203, -954],
        [-1852, -1477],
        [-142988, 1086],
        [-31372, -932],
        [-126688, 944],
        [-122883, 811],
        [-25943, -1024],
        [-188, -1557],
        [-138252, 992],
        [-29081, -1007],
        [-121841, 843],
        [-112887, 631],
        [-23465, -1101],
        [3295, -1641],
        [-149396, 1175],
        [-25538, -1072],
        [-115636, 737],
        [-115148, 657],
        [-19741, -1162],
        [8626, -1712],
        [-136063, 977],
        [-14201, -1247],
        [-114011, 726],
        [-118325, 743],
        [-8144, -1348],
        [17847, -1803],
        [-97348, 365],
        [6257, -1497],
        [-109584, 660],
        [-105047, 612],
        [6052, -1501],
        [29707, -1847],
        [-54845, -178],
        [33539, -1777],
        [-101447, 581],
        [-91533, 465],
        [22052, -1618],
        [41432, -1898],
        [-57767, -24],
        [46722, -1836],
        [-100225, 640],
        [-85241, 410],
        [29349, -1596],
        [47070, -1913],
        [-61391, 77],
        [36055, -1570],
        [-108147, 802],
        [-86269, 453],
        [28127, -1514],
        [45690, -1852],
        [-64123, 148],
        [22501, -1315],
        [-117944, 966],
        [-86623, 485],
        [24430, -1424],
        [42484, -1776],
        [-71313, 274],
        [11830, -1125],
        [-128240, 1131],
        [-88484, 537],
        [22989, -1406],
        [36535, -1635],
        [-80831, 411],
        [7198, -1072],
        [-139864, 1288],
        [-103026, 746],
        [20709, -1379],
        [31963, -1561],
        [-88095, 512],
        [4499, -1061],
        [-151234, 1446],
        [-112251, 879],
        [18836, -1375],
        [27314, -1492],
        [-99170, 664],
        [-3317, -946],
        [-164503, 1628],
        [-124095, 1048],
        [15717, -1342],
        [24360, -1463],
        [-106954, 776],
        [-4613, -960],
        [-175312, 1778],
        [-133986, 1196],
        [17495, -1422],
        [24628, -1504],
        [-116071, 917],
        [-6654, -932],
        [-179354, 1858],
        [-143246, 1349],
        [19348, -1464],
        [27482, -1573],
        [-123134, 1043],
        [-5856, -953],
        [-179156, 1897],
        [-149022, 1474],
        [24897, -1552],
        [34376, -1692],
        [-128790, 1158],
        [-5994, -955],
        [-169346, 1833],
        [-147953, 1540],
        [30195, -1634],
        [39201, -1738],
        [-142610, 1398],
        [-10283, -880],
        [-159736, 1760],
        [-155677, 1709],
        [16822, -1322],
        [34514, -1625],
        [-145600, 1502],
        [-5448, -970],
        [-160091, 1825],
        [-145741, 1600],
        [9838, -1201],
        [31034, -1596],
        [-135428, 1378],
        [-9947, -857],
        [-154202, 1753],
        [-143342, 1562],
        [5620, -1181],
        [27478, -1580],
        [-137880, 1405],
        [-20245, -716],
        [-144872, 1605],
        [-137881, 1393],
        [-2343, -1119],
        [20783, -1555],
        [-135120, 1239],
        [-27681, -716],
        [-139164, 1408],
        [-131328, 1165],
        [-12468, -1056],
        [8443, -1457],
        [-145155, 1261],
        [-33778, -735],
        [-138392, 1271],
        [-128342, 1009],
        [-21707, -987],
        [3295, -1418]
    ]

    def __init__(self,
                    cost_parameters=(0.0, 0.0, 0.0),
                    default_power=0.0,
                    description='',
                    engagement_cost=(0.0, 0.0, 0.0),
                    location='',
                    maximum_power=0.0,
                    measurement_interval=timedelta(hours=1),
                    measurement_type=MeasurementType.Unknown,
                    measurement_unit=MeasurementUnit.Unknown,
                    minimum_power=0.0,
                    name='',
                    scheduling_horizon=timedelta(hours=24),
                    subclass=None):

        super(OpenLoopRichlandLoadPredictor, self).__init__()
        self.temperature_forecaster = TemperatureForecastModel,

        # These are static properties that may be passed as parameters:
        self.costParameters = cost_parameters
        self.defaultPower = default_power
        self.description = description
        self.engagementCost = engagement_cost
        self.location = location
        self.maximumPower = maximum_power
        self.minimumPower = minimum_power
        self.measurementInterval = measurement_interval
        self.measurementType = measurement_type
        self.measurementUnit = measurement_unit
        self.name = name
        self.schedulingHorizon = scheduling_horizon
        self.subclass = subclass

    def schedule_power(self, mkt):
        """
        Predict municipal load.
        This is a model of non-price-responsive load using an open-loop regression model.
        :param mkt:
        :return:
        """

        # Get the active time intervals.
        time_intervals = mkt.timeIntervals  # TimeInterval objects

        TEMP = None
        # Index through the active time intervals.
        for time_interval in time_intervals:
            # Extract the start time from the indexed time interval.
            interval_start_time = time_interval.startTime

            if self.temperature_forecaster is None:  # if isempty(temperature_forecaster)
                # No appropriate information service was found, must use a
                # default temperature value.
                TEMP = 56.6  # [deg.F]
            else:
                # An appropriate information service was found. Get the
                # temperature that corresponds to the indexed time interval.
                interval_value = find_obj_by_ti(self.temperature_forecaster.predictedValues, time_interval)

                if interval_value is None:  # if isempty(interval_value)
                    # No stored temperature was found. Assign a default value.
                    TEMP = 56.6  # [def.F]
                else:
                    # A stored temperature value was found. Use it.
                    TEMP = interval_value.value  # [def.F]

                if TEMP is None:
                    # The temperature value is not a number. Use a default value.
                    TEMP = 56.6  # [def.F]

            # Determine the DOW_Intercept.
            # The DOW_Intercept is a function of categorical day-of-week number
            # DOWN. Calculate the weekday number DOWN.
            DOWN = interval_start_time.weekday()  # weekday(interval_start_time)

            # Look up the DOW_intercept from the short table that is among the
            # class's constant properties.
            DOW_Intercept = self.dowIntercept[DOWN]

            # Determine categorical HOUR of the indexed time interval. This will
            # be needed to mine the HOUR_SEASON_REGIME_Intercept lookup table.
            # The hour is incremented by 1 because the lookup table uses hours
            # [1,24], not [0,23].
            HOUR = interval_start_time.hour  # + 1

            # Determine the categorical SEASON of the indexed time interval.
            # SEASON is a function of MONTH, so start by determining the MONTH of
            # the indexed time interval.
            MONTH = interval_start_time.month  # MONTH = month(interval_start_time)

            # Property season provides an index for use with the
            # HOUR_SEASON_REGIME_Intercept lookup table.
            SEASON = self.season[MONTH - 1]  # obj.season(MONTH);

            # Determine categorical REGIME, which is also an index for use with
            # the HOUR_SEASON_REGIME_Intercept lookup table.
            REGIME = 0  # The default assignment
            if (
                    SEASON == 1 or SEASON == 4) and TEMP <= 56.6:  # (Spring season index OR Fall season index) # AND Heating regime
                REGIME = 1

            # Calcualte the table row. Add final 1 because of header row.
            row = 6 * HOUR + SEASON + REGIME  # 6 * (HOUR - 1) + SEASON + REGIME

            # Matlab is 1-based vs. python 0-based.
            row = row - 1

            # Assign the Intercept and Factor values that were found.
            HOUR_SEASON_REGIME_Intercept = self.values[row][0]
            HOUR_SEASON_REGIME_Factor = self.values[row][1]

            # Finally, predict the city load.
            LOAD = DOW_Intercept + HOUR_SEASON_REGIME_Intercept + HOUR_SEASON_REGIME_Factor * TEMP  # [avg.kW]

            # The table defined electric load as a positive value. The network
            # model defines load as a negative value.
            LOAD = -LOAD  # [avg.kW]

            # Look for the scheduled power in the indexed time interval.
            interval_value = find_obj_by_ti(self.scheduledPowers, time_interval)

            if interval_value is None:
                # No scheduled power was found in the indexed time interval.
                # Create one and store it.
                interval_value = IntervalValue(self, time_interval, mkt, MeasurementType.ScheduledPower, LOAD)
                self.scheduledPowers.append(interval_value)
            else:
                # The interval value already exist. Simply reassign its value.
                interval_value.value = LOAD
        self.scheduleCalculated = True
        # 200929DJH: Remove scheduled powers that lie in expired markets.
        self.scheduledPowers = [x for x in self.scheduledPowers if x.market.marketState != MarketState.Expired]

    @classmethod
    def test_all(cls):
        print('Running test_all()')
        OpenLoopRichlandLoadPredictor.test_schedule_power()

    @classmethod
    def test_schedule_power(cls):
        print('Running test_schedule_power()')
        pf = 'pass'

        # Create a test Market object.
        test_mkt = Market()

        # Create and store a couple TimeInterval objects at a known date and
        # time.
        dt = datetime(2017, 11, 1, 12, 0, 0)  # Wednesday Nov. 1, 2017 at noon
        at = dt
        dur = timedelta(hours=1)
        mkt = test_mkt
        mct = dt
        st = dt
        test_intervals = [TimeInterval(at, dur, mkt, mct, st)]

        st = st + dur  # 1p on the same day
        test_intervals.append(TimeInterval(at, dur, mkt, mct, st))

        test_mkt.timeIntervals = test_intervals

        # Create a test TemperatureForecastModel object and give it some
        # temperature values in the test TimeIntervals.
        # test_forecast = TemperatureForecastModel
        # # The information type should be specified so the test object will
        # # correctly identivy it.
        # test_forecast.informationType = 'temperature'
        # # test_forecast.update_information(test_mkt)
        # test_forecast.predictedValues(1) = IntervalValue(test_forecast, test_intervals(1), test_mkt, 'Temperature', 20)  # Heating regime
        # test_forecast.predictedValues(2) = IntervalValue(test_forecast, test_intervals(2), test_mkt, 'Temperature', 100)  # Cooling regime
        # test_obj.informationServiceModels = {test_forecast}
        # Create a OpenLoopRichlandLoadPredictor test object.
        test_forecast = TemperatureForecastModel()
        test_forecast.informationType = 'temperature'
        test_forecast.predictedValues = [
            IntervalValue(test_forecast, test_intervals[0], test_mkt, MeasurementType.Temperature, 20),
            # Heating regime
            IntervalValue(test_forecast, test_intervals[1], test_mkt, MeasurementType.Temperature, 100)
            # Cooling regime
        ]
        test_obj = OpenLoopRichlandLoadPredictor(test_forecast)

        # Manually evaluate from the lookup table and the above categorical inputs
        # DOW = Wed. ==>
        Intercept1 = 146119
        Intercept2 = 18836
        Intercept3 = -124095
        Factor1 = -1375
        Factor2 = 1048
        Temperature1 = 20
        Temperature2 = 100

        LOAD = [
            -(Intercept1 + Intercept2 + Factor1 * Temperature1),
            -(Intercept1 + Intercept3 + Factor2 * Temperature2)]

        try:
            test_obj.schedule_power(test_mkt)
            print('- the method ran without errors')
        except:
            pf = 'fail'
            # _log.warning('- the method had errors when called')

        # if any(abs([test_obj.scheduledPowers(1: 2).value] - [LOAD])) > 5
        if any([abs(test_obj.scheduledPowers[i].value - LOAD[i]) > 5 for i in range(len(test_obj.scheduledPowers))]):
            pf = 'fail'
            # _log.warning('- the calculated powers were not as expected')
        else:
            print('- the calculated powers were as expected')

        # Success
        print('- the test ran to completion')
        print('Result: #s\n\n', pf)


if __name__ == '__main__':
    OpenLoopRichlandLoadPredictor.test_all()

