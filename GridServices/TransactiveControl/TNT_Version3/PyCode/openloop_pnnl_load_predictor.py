"""
Copyright (c) 2020, Battelle Memorial Institute
All rights reserved.
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.
This material was prepared as an account of work sponsored by an agency of the
United States Government. Neither the United States Government nor the United
States Department of Energy, nor Battelle, nor any of their employees, nor any
jurisdiction or organization that has cooperated in th.e development of these
materials, makes any warranty, express or implied, or assumes any legal
liability or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed, or
represents that its use would not infringe privately owned rights.
Reference herein to any specific commercial product, process, or service by
trade name, trademark, manufacturer, or otherwise does not necessarily
constitute or imply its endorsement, recommendation, or favoring by the
United States Government or any agency thereof, or Battelle Memorial Institute.
The views and opinions of authors expressed herein do not necessarily state or
reflect those of the United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
"""


from datetime import datetime, timedelta, date, time
from volttron.platform.agent import utils

import logging
utils.setup_logging()
_log = logging.getLogger(__name__)

from .helpers import *
from .measurement_type import MeasurementType
from .interval_value import IntervalValue
from .market import Market
from .time_interval import TimeInterval
from .local_asset_model import LocalAsset
from .temperature_forecast_model import TemperatureForecastModel
from .market_state import MarketState

class OpenLoopPnnlLoadPredictor(LocalAsset, object):
    """
    Predict electrical load for PNNL using hour-of-day, season, heating/cooling regime, and
    forecasted Fahrenheit temperature.

    # Predictor formula
    # LOAD = DOW_Intercept(DOW) 
    #     + HOUR_SEASON_REGIME_Intercept(HOUR,SEASON,REGIME) 
    #     + Factor(HOUR,SEASON,REGIME) * TEMP
    #   DOW_Intercept - average kW - Addend that is a function of categorical
    # day-of-week.
    #   HOUR - Categorical hour of day in the range [1, 24]
    #   HOUR_SEASON_REGIME_Factor - avg.kW / deg.F - Factor of TEMP. A function
    # of categoricals HOUR, SEASON, and REGIME.
    #   HOUR_SEASON_REGIME_Intercept - average kW - Addend that is a function
    # of categoricals HOUR, SEASON, and REGIME.
    #   LOAD - average kW - Predicted hourly Richland, WA electric load 
    #   REGIME - Categorical {"Cool", "Heat", or "NA"}. Applies only in seasons
    # Spring and Fall. Not to be used for Summer or Winter seasons.
    #   SEASON - Categorical season
    # "Spring" - [Mar, May]
    # "Summer" - [Jun, Aug]
    # "Fall"   - [Sep, Nov]
    # "Winter" - [Dec, Feb]
    #   TEMP - degrees Fahrenheit - a predicted hourly temperature forecast.
    """

    # day-of-weak intercept [avg.kW]
    dowIntercept = [4873.7724,  # Monday
                    5136.2654,  # Tuesday
                    5161.2918,  # Wednesday
                    5141.6897,  # Thursday
                    5126.1266,  # Friday
                    5105.3477,  # Saturday
                    4857.791]  # Sunday

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

    # Hourly intercepts & factors
    values = [
        [-1943.11, 15.6343],
        [-1552.8804, 16.6403],
        [-6247.8216, 71.3126],
        [-2251.3143, 20.9037],
        [-547.049, -4.6144],
        [-25.2204, -19.1221],
        [-1606.8704, 10.7018],
        [1093.5591, -39.7774],
        [-5736.2878, 64.4014],
        [-1987.0481, 17.5103],
        [-627.4722, -0.5267],
        [-18.9381, -19.806],
        [-1511.3221, 9.4007],
        [1112.4923, -42.4567],
        [-5055.4535, 56.2573],
        [-2086.5558, 19.3164],
        [-330.4092, -11.0824],
        [28.7608, -21.7085],
        [-1525.0984, 9.9538],
        [-232.7103, -12.8593],
        [-4857.2835, 55.1424],
        [-2312.4072, 23.321],
        [-335.6932, -10.5493],
        [8.4233, -21.4868],
        [-1501.8945, 9.5271],
        [-90.3775, -16.8266],
        [-4898.6781, 58.9768],
        [-2612.3769, 28.493],
        [-391.9833, -9.6644],
        [62.4388, -23.4449],
        [-1460.8928, 9.817],
        [-215.3726, -12.6349],
        [-4763.1406, 60.2987],
        [-2636.8692, 29.9408],
        [-235.7405, -13.0967],
        [100.8946, -23.2533],
        [-1519.5356, 11.8468],
        [-263.8305, -8.9912],
        [-4806.1193, 65.1989],
        [-2510.7624, 29.0978],
        [-44.8651, -15.4569],
        [171.2517, -22.6678],
        [-2863.6288, 38.2499],
        [-41.217, -14.8757],
        [-5248.4303, 79.0486],
        [-2451.4885, 29.4601],
        [0.7864, -16.187],
        [222.1435, -22.5848],
        [-3590.8804, 55.3771],
        [-220.219, -11.1466],
        [-4564.7572, 77.0245],
        [-3172.1709, 45.1119],
        [-18.1817, -15.2875],
        [232.8771, -22.2868],
        [-4424.5551, 75.1374],
        [-549.1433, -3.2277],
        [-3580.7334, 69.5824],
        [-3625.8969, 57.3149],
        [-93.0818, -13.249],
        [221.3399, -22.5538],
        [-4997.8612, 90.8162],
        [-830.2337, 4.048],
        [-3160.1563, 69.3706],
        [-3505.2878, 60.104],
        [-238.3141, -8.9121],
        [173.306, -21.8904],
        [-4177.9602, 81.3158],
        [-1222.3354, 17.007],
        [-2170.4431, 58.8392],
        [-2912.916, 54.2375],
        [-590.1081, 1.2771],
        [98.116, -20.4409],
        [-5176.7371, 102.354],
        [-1261.63, 19.8332],
        [-1529.6446, 53.2529],
        [-3072.6906, 59.9573],
        [-933.1589, 12.6848],
        [32.2006, -19.9075],
        [-4520.0244, 92.5771],
        [-1314.6758, 23.9202],
        [-1107.9132, 50.4486],
        [-2403.1575, 51.0468],
        [-1113.1989, 20.6902],
        [-33.8796, -18.6636],
        [-6800.9014, 133.6859],
        [-1633.8593, 33.0039],
        [-1445.4818, 54.92],
        [-2832.6941, 59.6413],
        [-1408.041, 32.3344],
        [-50.9795, -18.9281],
        [-5431.0986, 107.0872],
        [-1488.7255, 25.6563],
        [-3173.4875, 77.2325],
        [-3693.5133, 76.8222],
        [-1194.7255, 23.4421],
        [-45.9922, -19.5673],
        [-5992.3743, 110.3572],
        [-1878.372, 29.0651],
        [-3957.759, 82.4821],
        [-5490.5798, 103.3779],
        [-835.4966, 6.534],
        [-32.2415, -21.0935],
        [-5783.3567, 99.4203],
        [-2053.5194, 27.9052],
        [-4980.1168, 90.8157],
        [-5973.1272, 103.1991],
        [-430.9645, -7.2753],
        [88.6098, -24.8673],
        [-5667.0474, 90.2872],
        [-1627.7297, 16.7943],
        [-5467.5471, 90.6342],
        [-5798.9386, 91.9255],
        [-348.664, -10.4816],
        [133.7956, -25.7193],
        [-5303.5978, 78.6711],
        [-2389.936, 33.6549],
        [-5981.5298, 91.2828],
        [-5137.4116, 74.6948],
        [-338.4086, -10.2973],
        [109.1836, -23.9551],
        [-4366.7304, 58.8032],
        [-321.0364, -11.0856],
        [-6707.9043, 93.3347],
        [-4331.4294, 57.3982],
        [-468.3587, -7.9906],
        [66.5494, -22.5677],
        [-3346.2906, 40.3274],
        [-107.2114, -16.4339],
        [-6706.8615, 87.4963],
        [-3460.5223, 41.7777],
        [-386.2494, -9.3355],
        [35.6762, -21.0269],
        [-2947.8641, 32.604],
        [5439.256, -135.4803],
        [-6764.6892, 83.0583],
        [-2914.7403, 32.101],
        [-355.9943, -9.6203],
        [18.7951, -20.0777],
        [-2357.3823, 22.8541],
        [-3760.169, 66.7557],
        [-6545.7827, 77.1116],
        [-2541.5235, 25.6375],
        [-435.6842, -7.0618],
        [-3.21265, -19.4645]
    ]

    def __init__(self, temperature_forecaster):
        super(OpenLoopPnnlLoadPredictor, self).__init__()
        self.temperature_forecaster = temperature_forecaster
        self.model_2017_consumption = 42350128.
        self.campus_2017_consumption = 91116072.
        self.scale_factor = self.campus_2017_consumption/self.model_2017_consumption

    def schedule_power(self, mkt):
        """
        Predict municipal load.
        This is a model of non-price-responsive load using an open-loop regression model.
        :param mkt:
        :return:
        """

        # Get the active time intervals.
        time_intervals = mkt.timeIntervals  # TimeInterval objects
        _log.debug("openloop_pnnl_load_predictor: Market: {} time_intervals len: {}".format(mkt.name,
                                                                                            len(mkt.timeIntervals)))
        TEMP = None
        # Index through the active time intervals.
        # 200928DJH: Go back to basic indexing.
        # for time_interval in time_intervals:
        for i in range(len(time_intervals)):
            time_interval = time_intervals[i]

            # Extract the start time from the indexed time interval.
            interval_start_time = time_interval.startTime

            if self.temperature_forecaster is None:
                # No appropriate information service was found, must use a default temperature value.
                TEMP = 56.6  # [deg.F]
            else:
                # An appropriate information service was found. Get the temperature that corresponds to the indexed time
                # interval.
                interval_value = find_obj_by_ti(self.temperature_forecaster.predictedValues, time_interval)

                if interval_value is None:
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
            if (SEASON == 1 or SEASON == 4) and TEMP <= 56.6:  # (Spring  OR Fall season) AND Heating regime
                REGIME = 1

            # Calculate the table row. Add final 1 because of header row.
            row = 6 * HOUR + SEASON + REGIME  # 6 * (HOUR - 1) + SEASON + REGIME

            # Matlab is 1-based vs. python 0-based.
            row = row - 1

            # Assign the Intercept and Factor values that were found.
            HOUR_SEASON_REGIME_Intercept = self.values[row][0]
            HOUR_SEASON_REGIME_Factor = self.values[row][1]

            # Finally, predict the city load.
            LOAD = DOW_Intercept + HOUR_SEASON_REGIME_Intercept + HOUR_SEASON_REGIME_Factor * TEMP  # [avg.kW]

            # Scale for whole campus
            LOAD *= self.scale_factor

            # The table defined electric load as a positive value. The network
            # model defines load as a negative value.
            LOAD = -LOAD  # [avg.kW]

            # Look for the scheduled power in the indexed time interval.
            interval_value = find_obj_by_ti(self.scheduledPowers, time_interval)

            if interval_value is None:
                # No scheduled power was found in the indexed time interval. Create one and store it.
                interval_value = IntervalValue(calling_object=self,
                                               time_interval=time_interval,
                                               market=mkt,
                                               measurement_type=MeasurementType.ScheduledPower,
                                               value=LOAD
                                               )
                self.scheduledPowers.append(interval_value)

            else:
                # The interval value already exist. Simply reassign its value.
                interval_value.value = LOAD
        self.scheduleCalculated = True
        _log.debug("Market: {} schedule_power {}".format(mkt.name, self.scheduledPowers))
        for power in self.scheduledPowers:
            _log.debug("schedule_power Market {}, time interval: {}, power value: {} ".format(power.market.name,
                                                                                   power.timeInterval.startTime,
                                                                                           power.value))
        # 200929DJH: Trim the list of scheduled powers for any that lie in expired markets.
        self.scheduledPowers = [x for x in self.scheduledPowers if x.market.marketState != MarketState.Expired]

    @classmethod
    def test_all(cls):
        # TEST_ALL() - test all the class methods
        print('Running OpenLoopRichlandLoadPredictor.test_all()')
        OpenLoopPnnlLoadPredictor.test_schedule_power()
    
    @classmethod
    def predict_2017(cls):
        from .market import Market
        import helpers
        from dateutil import parser

        forecaster = TemperatureForecastModel('/home/hngo/PycharmProjects/volttron-applications/pnnl/TNSAgent/campus_config')

        # Create market with some time intervals
        mkt = Market()
        analysis_time = parser.parse("2017-01-01 00:00:00")
        mkt.marketClearingTime = analysis_time
        mkt.nextMarketClearingTime = mkt.marketClearingTime + mkt.marketClearingInterval

        # Control steps using horizon
        mkt.futureHorizon = timedelta(days=365)

        mkt.check_intervals(analysis_time)

        # set time intervals
        forecaster.update_information(mkt)

        # schedule powers
        predictor = OpenLoopPnnlLoadPredictor(forecaster)
        predictor.schedule_power(mkt)

        powers = [(x.timeInterval.startTime, x.value) for x in predictor.scheduledPowers]
        total_power = sum([s[1] for s in powers])

        print(powers)
        print(total_power)


if __name__ == '__main__':
    OpenLoopPnnlLoadPredictor.predict_2017()
