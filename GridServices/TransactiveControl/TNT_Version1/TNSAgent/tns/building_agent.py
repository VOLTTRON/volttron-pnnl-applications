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

import os
import sys
import logging
import datetime
import gevent
from dateutil import parser
import uuid


from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from volttron.platform.agent.base_market_agent.buy_sell import SELLER

from .helpers import *
from .measurement_type import MeasurementType
from .measurement_unit import MeasurementUnit
from .meter_point import MeterPoint
from .market import Market
from .market_state import MarketState
from .neighbor import Neighbor
from .local_asset import LocalAsset
from .local_asset_model import LocalAssetModel
from .myTransactiveNode import myTransactiveNode
from .neighbor_model import NeighborModel
from .temperature_forecast_model import TemperatureForecastModel
from .solar_pv_resource import SolarPvResource
from .solar_pv_resource_model import SolarPvResourceModel
from .vertex import Vertex
from .interval_value import IntervalValue
from .timer import Timer
from .tcc_model import TccModel

utils.setup_logging()
_log = logging.getLogger(__name__)

utils.setup_logging()


def setup_logging(name, log_file, level=logging.DEBUG):
    handler = logging.FileHandler(log_file)
    fmt = '%(asctime)s %(name)s %(levelname)s: %(message)s'
    handler.setFormatter(logging.Formatter(fmt))

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger

#ep_res_path = '/Users/ngoh511/Documents/projects/PycharmProjects/transactivenetwork/TNSAgent/tns/test_data/energyplus.txt'
mixmarket_log = '/home/volttron/volttron/mixmarket'
if not os.path.exists(mixmarket_log):
    _log2 = setup_logging('mixmarket', mixmarket_log + '.log')
else:
    temp = str(uuid.uuid4())
    _log2 = setup_logging('mixmarket', mixmarket_log + temp + '.log')


__version__ = '0.1'


class BuildingAgent(MarketAgent, myTransactiveNode):
    def __init__(self, config_path, **kwargs):
        MarketAgent.__init__(self, **kwargs)
        myTransactiveNode.__init__(self)

        self.config_path = config_path
        self.config = utils.load_config(config_path)
        self.name = self.config.get('name')
        self.agent_name = self.config.get('agentid', 'building_agent')
        self.db_topic = self.config.get("db_topic", "tnc")
        self.power_topic = self.config.get("power_topic")

        self.market_cycle_in_min = int(self.config.get('market_cycle_in_min', 60))
        self.duality_gap_threshold = float(self.config.get('duality_gap_threshold', 0.01))
        self.campus_loss_factor = float(self.config.get('campus_loss_factor', 0.01))

        self.neighbors = []
        self.max_deliver_capacity = float(self.config.get('max_deliver_capacity'))
        self.demand_threshold_coef = float(self.config.get('demand_threshold_coef'))
        self.monthly_peak_power = float(self.config.get('monthly_peak_power'))

        self.building_demand_topic = "{}/{}/campus/demand".format(self.db_topic, self.name)
        self.campus_supply_topic = "{}/campus/{}/supply".format(self.db_topic, self.name)
        self.system_loss_topic = "{}/{}/system_loss".format(self.db_topic, self.name)
        self.dc_threshold_topic = "{}/{}/dc_threshold_topic".format(self.db_topic, self.name)

        self.mix_market_running = False
        verbose_logging = self.config.get('verbose_logging', True)

        self.prices = [None for i in range(25)]
        self.quantities = [None for i in range(25)]
        self.building_demand_curves = [None for i in range(25)]
        self.mix_market_duration = timedelta(minutes=20)

        self.reschedule_interval = timedelta(minutes=10, seconds=1)

        self.simulation = self.config.get('simulation', False)
        try:
            self.simulation_start_time = parser.parse(self.config.get('simulation_start_time'))
            self.simulation_one_hour_in_seconds = int(self.config.get('simulation_one_hour_in_seconds'))
        except:
            self.simulation_start_time = datetime.now()
            self.simulation_one_hour_in_seconds = 3600

        # Create market names to join
        self.base_market_name = 'electric'  # Need to agree on this with other market agents
        self.market_names = []
        for i in range(24):
            self.market_names.append('_'.join([self.base_market_name, str(i)]))

        Timer.created_time = datetime.now()
        Timer.simulation = self.simulation
        Timer.sim_start_time = self.simulation_start_time
        Timer.sim_one_hr_in_sec = self.simulation_one_hour_in_seconds

        if self.simulation:
            self.ep_lines = []
            self.cur_ep_line = 0
            # with open(ep_res_path, 'r') as fh:
            #     for line in fh:
            #         self.ep_lines.append(line)

        _log2.debug("Mixmarket for agent {}:".format(self.name))

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        # Add other objects: assets, services, neighbors
        self.init_objects()

        # Join electric mix-markets
        for market in self.market_names:
            self.join_market(market, SELLER, self.reservation_callback, self.offer_callback,
                             self.aggregate_callback, self.price_callback, self.error_callback)

        # Subscriptions
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.campus_supply_topic,
                                  callback=self.new_supply_signal)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.power_topic,
                                  callback=self.new_demand_signal)

    def new_supply_signal(self, peer, sender, bus, topic, headers, message):
        _log.debug("At {}, {} receives new supply records: {}".format(Timer.get_cur_time(),
                                                                     self.name, message))
        supply_curves = message['curves']
        start_of_cycle = message['start_of_cycle']

        self.campus.model.receive_transactive_signal(self, supply_curves)
        _log.debug("At {}, mixmarket state is {}, start_of_cycle {}".format(Timer.get_cur_time(),
                                                                            self.mix_market_running,
                                                                            start_of_cycle))

        db_topic = "/".join([self.db_topic, self.name, "CampusSupply"])
        message = supply_curves
        headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
        self.vip.pubsub.publish("pubsub", db_topic, headers, message).get()

        if start_of_cycle:
            _log.debug("At {}, start of cycle. "
                       "Mixmarket state before overriding is {}".format(Timer.get_cur_time(),
                                                                        self.mix_market_running))

            # if self.simulation:
            #     self.run_ep_sim(start_of_cycle)
            # else:
            self.start_mixmarket(start_of_cycle)

    def new_demand_signal(self, peer, sender, bus, topic, headers, message):
        mtrs = self.campus.model.meterPoints
        if len(mtrs) > 0:
            bldg_meter = mtrs[0]
            power_unit = message[1]
            cur_power = float(message[0]["WholeBuildingPower"])
            power_unit = power_unit.get("WholeBuildingPower", {}).get("units", "kW")
            if isinstance(power_unit, str) and power_unit.lower() == "watts":
                cur_power = cur_power / 1000.0
            bldg_meter.set_meter_value(cur_power)
            if Timer.get_cur_time().minute >= 58:
                bldg_meter.update_avg()

    def near_end_of_hour(self, now):
        near_end_of_hour = False
        if (now + self.mix_market_duration).hour != now.hour:
            near_end_of_hour = True
            _log.debug("{} did not start mixmarket because it's too late.".format(self.name))

        return near_end_of_hour

    def start_mixmarket(self, start_of_cycle):
        # Reset price array
        self.prices = [None for i in range(25)]

        # Save the 1st quantity as prior 2nd quantity
        cur_quantity = self.quantities[1]
        cur_curve = self.building_demand_curves[1]

        # Reset quantities and curves
        self.quantities = [None for i in range(25)]
        self.building_demand_curves = [None for i in range(25)]

        # If new cycle, set the 1st quantity to the corresponding quantity of previous hour
        if start_of_cycle:
            self.quantities[0] = cur_quantity
            self.building_demand_curves[0] = cur_curve

        # Balance market with previous known demands
        market = self.markets[0]  # Assume only 1 TNS market per node
        market.signal_new_data = True
        market.balance(self)

        # Check if now is near the end of the hour, applicable only if not in simulation mode
        now = Timer.get_cur_time()
        near_end_of_hour = False
        if not self.simulation:
            near_end_of_hour = self.near_end_of_hour(now)

        if market.converged:
            # Get new prices (expected 25 values: current hour + next 24)
            prices = market.marginalPrices

            # There is a case where the balancing happens at the end of the hour and continues to the next hour, which
            # creates 26 values. Get the last 25 values.
            prices = prices[-25:]
            self.prices = [p.value for p in prices]

            # Signal to start mix market only if the previous market is done
            if not self.mix_market_running and not near_end_of_hour:
                self.mix_market_running = True
                # Update weather information
                weather_service = None
                if len(self.informationServiceModels)>0:
                    weather_service = self.informationServiceModels[0]
                    weather_service.update_information(market)

                _log.debug("prices are {}".format(self.prices))
                if weather_service is None:
                    self.vip.pubsub.publish(peer='pubsub',
                                            topic='mixmarket/start_new_cycle',
                                            message={"prices": self.prices[-24:],
                                                     "Date": format_timestamp(now)})
                else:
                    temps = [x.value for x in weather_service.predictedValues]
                    temps = temps[-24:]
                    _log.debug("temps are {}".format(temps))
                    self.vip.pubsub.publish(peer='pubsub',
                                            topic='mixmarket/start_new_cycle',
                                            message={"prices": self.prices[-24:],
                                                     "temp": temps,
                                                     "Date": format_timestamp(now)})

    def balance_market(self, run_cnt):
        market = self.markets[0]  # Assume only 1 TNS market per node
        market.new_data_signal = True
        market.balance(self)

        if market.converged:
            _log.debug("TNS market {} balanced successfully.".format(market.name))
            balanced_curves = [(x.timeInterval.startTime,
                                x.value.marginalPrice,
                                x.value.power) for x in market.activeVertices]
            _log.debug("Balanced curves: {}".format(balanced_curves))

            # Sum all the powers as will be needed by the net supply/demand curve.
            market.assign_system_vertices(self)

            # Check to see if it is ok to send signals
            self.campus.model.check_for_convergence(market)
            if not self.campus.model.converged:
                _log.debug("Campus model not converged. Sending signal back to campus.")
                self.campus.model.prep_transactive_signal(market, self)
                self.campus.model.send_transactive_signal(self, self.building_demand_topic)

    def offer_callback(self, timestamp, market_name, buyer_seller):
        if market_name in self.market_names:
            # Get the price for the corresponding market
            idx = int(market_name.split('_')[-1])
            price = self.prices[idx+1]
            #price *= 1000.  # Convert to mWh to be compatible with the mixmarket

            # Quantity
            min_quantity = 0
            max_quantity = 10000  # float("inf")

            # Create supply curve
            supply_curve = PolyLine()
            supply_curve.add(Point(quantity=min_quantity, price=price))
            supply_curve.add(Point(quantity=max_quantity, price=price))

            # Make offer
            _log.debug("{}: offer for {} as {} at {} - Curve: {} {}".format(self.agent_name,
                                                                         market_name,
                                                                         SELLER,
                                                                         timestamp,
                                                                         supply_curve.points[0], supply_curve.points[1]))
            success, message = self.make_offer(market_name, SELLER, supply_curve)
            _log.debug("{}: offer has {} - Message: {}".format(self.agent_name, success, message))

    def init_objects(self):
        # Add meter
        # meter = MeterPoint()
        # meter.name = 'BuildingElectricMeter'
        # meter.measurementType = MeasurementType.PowerReal
        # meter.measurementUnit = MeasurementUnit.kWh
        # self.meterPoints.append(meter)

        # Add weather forecast service
        weather_service = TemperatureForecastModel(self.config_path, self)
        self.informationServiceModels.append(weather_service)

        # # Add inelastive asset
        # inelastive_load = LocalAsset()
        # inelastive_load.name = 'InelasticBldgLoad'
        # inelastive_load.maximumPower = 0  # Remember that a load is a negative power [kW]
        # inelastive_load.minimumPower = -200
        #
        # # Add inelastive asset model
        # inelastive_load_model = LocalAssetModel()
        # inelastive_load_model.name = 'InelasticBuildingModel'
        # inelastive_load_model.defaultPower = -100  # [kW]
        # inelastive_load_model.defaultVertices = [Vertex(float("inf"), 0, -100, True)]
        #
        # # Cross-reference asset & asset model
        # inelastive_load_model.object = inelastive_load
        # inelastive_load.model = inelastive_load_model

        # Add elastive asset
        elastive_load = LocalAsset()
        elastive_load.name = 'TccLoad'
        elastive_load.maximumPower = 0  # Remember that a load is a negative power [kW]
        elastive_load.minimumPower = -self.max_deliver_capacity

        # Add inelastive asset model
        # self.elastive_load_model = LocalAssetModel()
        self.elastive_load_model = TccModel()
        self.elastive_load_model.name = 'TccModel'
        self.elastive_load_model.defaultPower = -0.5*self.max_deliver_capacity  # [kW]
        self.elastive_load_model.defaultVertices = [Vertex(0.055, 0, -self.elastive_load_model.defaultPower, True),
                                                    Vertex(0.06, 0, -self.elastive_load_model.defaultPower/2, True)]

        # Cross-reference asset & asset model
        self.elastive_load_model.object = elastive_load
        elastive_load.model = self.elastive_load_model

        # Add inelastive and elastive loads as building' assets
        self.localAssets.extend([elastive_load])

        # Add Market
        market = Market()
        market.name = 'dayAhead'
        market.commitment = False
        market.converged = False
        market.defaultPrice = 0.0428  # [$/kWh]
        market.dualityGapThreshold = self.duality_gap_threshold  # [0.02 = 2#]
        market.initialMarketState = MarketState.Inactive
        market.marketOrder = 1  # This is first and only market
        market.intervalsToClear = 1  # Only one interval at a time
        market.futureHorizon = timedelta(hours=24)  # Projects 24 hourly future intervals
        market.intervalDuration = timedelta(hours=1)  # [h] Intervals are 1 h long
        market.marketClearingInterval = timedelta(hours=1)  # [h]
        market.marketClearingTime = Timer.get_cur_time().replace(hour=0,
                                                                 minute=0,
                                                                 second=0,
                                                                 microsecond=0)  # Aligns with top of hour
        market.nextMarketClearingTime = market.marketClearingTime + timedelta(hours=1)
        self.markets.append(market)

        # Campus object
        campus = Neighbor()
        campus.name = 'PNNL_Campus'
        campus.description = 'PNNL_Campus'
        campus.maximumPower = self.max_deliver_capacity
        campus.minimumPower = 0.  # [avg.kW]
        campus.lossFactor = self.campus_loss_factor

        # Campus model
        campus_model = NeighborModel()
        campus_model.name = 'PNNL_Campus_Model'
        campus_model.location = self.name
        campus_model.defaultVertices = [Vertex(0.045, 25, 0, True), Vertex(0.048, 0, self.max_deliver_capacity, True)]

        campus_model.transactive = True
        campus_model.demand_threshold_coef = self.demand_threshold_coef
        # campus_model.demandThreshold = self.demand_threshold_coef * self.monthly_peak_power
        campus_model.demandThreshold = self.monthly_peak_power
        campus_model.inject(self,
                            system_loss_topic=self.system_loss_topic,
                            dc_threshold_topic=self.dc_threshold_topic)

        # Avg building meter
        building_meter = MeterPoint()
        building_meter.name = self.name + ' ElectricMeter'
        building_meter.measurementType = MeasurementType.AverageDemandkW
        building_meter.measurementUnit = MeasurementUnit.kWh
        campus_model.meterPoints.append(building_meter)

        # Cross-reference object & model
        campus_model.object = campus
        campus.model = campus_model
        self.campus = campus

        # Add campus as building's neighbor
        self.neighbors.append(campus)


    # Dummy callbacks
    def aggregate_power(self, peer, sender, bus, topic, headers, message):
        _log.debug("{}: received topic for power aggregation: {}".format(self.agent_name,
                                                                         topic))
        data = message[0]
        _log.debug("{}: updating power aggregation: {}".format(self.agent_name,
                                                               data))

    def reservation_callback(self, timestamp, market_name, buyer_seller):
        _log.debug("{}: wants reservation for {} as {} at {}".format(self.agent_name,
                                                                           market_name,
                                                                           buyer_seller,
                                                                           timestamp))
        return True

    def aggregate_callback(self, timestamp, market_name, buyer_seller, aggregate_demand):
        if buyer_seller == BUYER and market_name in self.market_names:  # self.base_market_name in market_name:
            _log.debug("{}: at ts {} min of aggregate curve : {}".format(self.agent_name,
                                                                         timestamp,
                                                                         aggregate_demand.points[0]))
            _log.debug("{}: at ts {} max of aggregate curve : {}".format(self.agent_name,
                                                                         timestamp,
                                                                         aggregate_demand.points[- 1]))
            _log.debug("At {}: Report aggregate Market: {} buyer Curve: {}".format(Timer.get_cur_time(),
                                                                                   market_name,
                                                                                   aggregate_demand))
            idx = int(market_name.split('_')[-1])
            idx += 1  # quantity has 25 values while there are 24 future markets
            self.building_demand_curves[idx] = (aggregate_demand.points[0], aggregate_demand.points[-1])

    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        _log.debug("{}: cleared price ({}, {}) for {} as {} at {}".format(Timer.get_cur_time(),
                                                                          price,
                                                                          quantity,
                                                                          market_name,
                                                                          buyer_seller,
                                                                          timestamp))
        idx = int(market_name.split('_')[-1])
        self.prices[idx+1] = price  # price has 24 values, current hour price is excluded
        if price is None:
            raise "Market {} did not clear. Price is none.".format(market_name)
        idx += 1  # quantity has 25 values while there are 24 future markets
        if self.quantities[idx] is None:
            self.quantities[idx] = 0.
        if quantity is None:
            _log.error("Quantity is None. Set it to 0. Details below.")
            _log.debug("{}: ({}, {}) for {} as {} at {}".format(self.agent_name,
                                                                price,
                                                                quantity,
                                                                market_name,
                                                                buyer_seller,
                                                                timestamp))
            quantity = 0
        self.quantities[idx] += quantity

        _log.debug("At {}, Quantity is {} and quantities are: {}".format(Timer.get_cur_time(),
                                                                         quantity,
                                                                         self.quantities))
        if quantity is not None and quantity < 0:
            _log.error("Quantity received from mixmarket is negative!!! {}".format(quantity))

        # If all markets (ie. exclude 1st value) are done then update demands, otherwise do nothing
        mix_market_done = all([False if q is None else True for q in self.quantities[1:]])
        if mix_market_done:
            # Check if any quantity is greater than physical limit of the supply wire
            _log.debug("Quantity: {}".format(self.quantities))
            if not all([False if q > self.max_deliver_capacity else True for q in self.quantities[1:]]):
                _log.error("One of quantity is greater than "
                           "physical limit {}".format(self.max_deliver_capacity))

            # Check demand curves exist
            all_curves_exist = all([False if q is None else True for q in self.building_demand_curves[1:]])
            if not all_curves_exist:
                _log.error("Demand curves: {}".format(self.building_demand_curves))
                raise "Mix market has all quantities but not all demand curves"

            # Update demand and balance market
            self.mix_market_running = False
            #self.elastive_load_model.default_powers = [-q if q is not None else None for q in self.quantities]
            curves_arr = [(c[0].tuppleize(), c[1].tuppleize()) if c is not None else None
                          for c in self.building_demand_curves]
            _log2.debug("Data at time {}:".format(Timer.get_cur_time()))
            _log2.debug("Market intervals: {}".format([x.name for x in self.markets[0].timeIntervals]))
            _log2.debug("Quantities: {}".format(self.quantities))
            _log2.debug("Prices: {}".format(self.prices))
            _log2.debug("Curves: {}".format(curves_arr))

            db_topic = "/".join([self.db_topic, self.name, "AggregateDemand"])
            message = {"Timestamp": format_timestamp(timestamp), "Curves": self.building_demand_curves}
            headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
            self.vip.pubsub.publish("pubsub", db_topic, headers, message).get()

            db_topic = "/".join([self.db_topic, self.name, "Price"])
            price_message = []
            for i in range(len(self.markets[0].timeIntervals)):
                ts = self.markets[0].timeIntervals[i].name
                price = self.prices[i]
                quantity = self.quantities[i]
                price_message.append({'timeInterval': ts, 'price': price, 'quantity': quantity})
            message = {"Timestamp": format_timestamp(timestamp), "Price": price_message}
            headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
            self.vip.pubsub.publish("pubsub", db_topic, headers, message).get()

            self.elastive_load_model.set_tcc_curves(self.quantities,
                                                    self.prices,
                                                    self.building_demand_curves)
            self.balance_market(1)

    def run_ep_sim(self, start_of_cycle):
        # Reset price array
        self.prices = [None for i in range(25)]

        # Save the 1st quantity as prior 2nd quantity
        cur_quantity = self.quantities[1]
        cur_curve = self.building_demand_curves[1]

        # Reset quantities and curves
        self.quantities = [None for i in range(25)]
        self.building_demand_curves = [None for i in range(25)]

        # If new cycle, set the 1st quantity to the corresponding quantity of previous hour
        if start_of_cycle:
            self.quantities[0] = cur_quantity
            self.building_demand_curves[0] = cur_curve

        # Balance market with previous known demands
        market = self.markets[0]  # Assume only 1 TNS market per node
        market.signal_new_data = True
        market.balance(self)

        # Check if now is near the end of the hour, applicable only if not in simulation mode
        now = Timer.get_cur_time()
        near_end_of_hour = False
        if not self.simulation:
            near_end_of_hour = self.near_end_of_hour(now)

        if market.converged:
            # Get new prices (expected 25 values: current hour + next 24)
            prices = market.marginalPrices

            # There is a case where the balancing happens at the end of the hour and continues to the next hour, which
            # creates 26 values. Get the last 25 values.
            prices = prices[-25:]
            self.prices = [p.value for p in prices]

            # Signal to start mix market only if the previous market is done
            if not self.mix_market_running and not near_end_of_hour:
                self.mix_market_running = True

            # Read data from e+ output file
            self.quantities = []
            self.prices = []
            self.building_demand_curves = []

            if self.cur_ep_line < len(self.ep_lines):
                for i in range(self.cur_ep_line, len(self.ep_lines)):
                    line = self.ep_lines[i]
                    if "mixmarket DEBUG: Quantities: " in line:
                        self.quantities = eval(line[line.find('['):])
                    if "mixmarket DEBUG: Prices: " in line:
                        self.prices = eval(line[line.find('['):])
                    if "mixmarket DEBUG: Curves: " in line:
                        tmp = eval(line[line.find('['):])

                        for item in tmp:
                            if item is None:
                                self.building_demand_curves.append(item)
                            else:
                                p1 = Point(item[0][0], item[0][1])
                                p2 = Point(item[1][0], item[1][1])
                                self.building_demand_curves.append((p1, p2))

                    # Stop when have enough information (ie. all data responded by a single E+ simulation)
                    if len(self.quantities) > 0 and len(self.prices) > 0 and len(self.building_demand_curves) > 0:
                        self.cur_ep_line = i + 1
                        break

                self.elastive_load_model.set_tcc_curves(self.quantities,
                                                        self.prices,
                                                        self.building_demand_curves)
                self.balance_market(1)
            # End E+ output reading

    def error_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux):
        _log.debug("{}: error for {} as {} at {} - Message: {}".format(self.agent_name,
                                                                       market_name,
                                                                       buyer_seller,
                                                                       timestamp,
                                                                       error_message))


def main(argv=sys.argv):
    try:
        utils.vip_main(BuildingAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())