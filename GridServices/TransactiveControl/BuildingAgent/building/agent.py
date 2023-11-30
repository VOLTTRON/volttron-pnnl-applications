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
from datetime import timedelta
import uuid
import gevent

from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from volttron.platform.agent.base_market_agent.buy_sell import SELLER

from TNT_Version3.PyCode.helpers import *
from TNT_Version3.PyCode.measurement_type import MeasurementType
from TNT_Version3.PyCode.measurement_unit import MeasurementUnit
from TNT_Version3.PyCode.meter_point import MeterPoint
from TNT_Version3.PyCode.market_state import MarketState
from TNT_Version3.PyCode.TransactiveNode import TransactiveNode
from TNT_Version3.PyCode.neighbor_model import Neighbor
from TNT_Version3.PyCode.temperature_forecast_model import TemperatureForecastModel
from TNT_Version3.PyCode.vertex import Vertex
from TNT_Version3.PyCode.timer import Timer
from TNT_Version3.PyCode.tcc_model import TccModel
from TNT_Version3.PyCode.dummy_tcc_model import DummyTccModel
from TNT_Version3.PyCode.day_ahead_auction import DayAheadAuction
from TNT_Version3.PyCode.direction import Direction

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

# ep_res_path = '/Users/ngoh511/Documents/projects/PycharmProjects/transactivenetwork/TNSAgent/tns/test_data/energyplus.txt'

#
# mixmarket_log = '/home/volttron/volttron/mixmarket'
# if not os.path.exists(mixmarket_log):
#     _log2 = setup_logging('mixmarket', mixmarket_log + '.log')
# else:
#     temp = str(uuid.uuid4())
#     _log2 = setup_logging('mixmarket', mixmarket_log + temp + '.log')

__version__ = '0.1'


class BuildingAgent(MarketAgent, TransactiveNode):
    def __init__(self, config_path, **kwargs):
        MarketAgent.__init__(self, **kwargs)
        TransactiveNode.__init__(self)

        self.config_path = config_path
        self.config = utils.load_config(config_path)
        self.name = self.config.get('name')
        city = self.config.get("city_name", "city")
        campus = self.config.get("campus_name", "campus")
        self.agent_name = self.config.get('agentid', 'building_agent')
        self.db_topic = self.config.get("db_topic", "tnc")
        #self.db_topic = self.config.get("db_topic", "record")
        self.power_topic = self.config.get("power_topic")

        self.market_cycle_in_min = int(self.config.get('market_cycle_in_min', 60))
        self.duality_gap_threshold = float(self.config.get('duality_gap_threshold', 0.01))
        self.campus_loss_factor = float(self.config.get('campus_loss_factor', 0.01))

        self.neighbors = []
        self.campus = None
        self.max_deliver_capacity = float(self.config.get('max_deliver_capacity'))
        self.demandThresholdCoef = float(self.config.get('demand_threshold_coef'))
        self.monthly_peak_power = float(self.config.get('monthly_peak_power'))

        #  self.building_demand_topic = "{}/{}/campus/demand".format(self.db_topic, self.name)
        #  self.campus_supply_topic = "{}/campus/{}/supply".format(self.db_topic, self.name)

        self.building_demand_topic = "{}/{}/{}/demand".format(self.db_topic, self.name, campus)
        self.campus_supply_topic = "{}/{}/{}/supply".format(self.db_topic, campus, self.name)
        self.system_loss_topic = "{}/{}/system_loss".format(self.db_topic, self.name)
        self.day_ahead_price_topic = "{}/{}/DayAheadPrices".format(self.db_topic, self.name)
        self.dc_threshold_topic = "{}/{}/dc_threshold_topic".format(self.db_topic, self.name)

        self.mix_market_running = False
        verbose_logging = self.config.get('verbose_logging', True)

        self.prices = [None for i in range(24)]
        self.quantities = [None for i in range(24)]
        self.building_demand_curves = [None for i in range(24)]
        self.mix_market_duration = timedelta(minutes=20)

        self.reschedule_interval = timedelta(minutes=10, seconds=1)

        self.simulation = self.config.get('simulation', False)
        try:
            self.simulation_start_time = parser.parse(self.config.get('simulation_start_time'))
            self.simulation_one_hour_in_seconds = int(self.config.get('simulation_one_hour_in_seconds'))
        except:
            self.simulation_start_time = Timer.get_cur_time()
            self.simulation_one_hour_in_seconds = 3600

        # Create market names to join
        self.base_market_name = 'electric'  # Need to agree on this with other market agents

        self.market_names = []
        for i in range(24):
            self.market_names.append('_'.join([self.base_market_name, str(i)]))

        Timer.created_time = Timer.get_cur_time()
        Timer.simulation = self.simulation
        Timer.sim_start_time = self.simulation_start_time
        Timer.sim_one_hr_in_sec = self.simulation_one_hour_in_seconds

        if self.simulation:
            self.ep_lines = []
            self.cur_ep_line = 0
            # with open(ep_res_path, 'r') as fh:
            #     for line in fh:
            #         self.ep_lines.append(line)

        #_log2.debug("Mixmarket for agent {}:".format(self.name))
        self._stop_agent = False
        self.elastic_load = None
        self._mix_market_done = [False]*24
        self._building_market_prices = [None]*24
        self.cleared_price_topic = 'tnc/cleared_prices/{}'.format(self.name)
        # New TNT db topics
        self.transactive_operation_topic = "{}/{}/transactive_operation".format(self.db_topic, self.name)
        self.local_asset_topic = "{}/{}/local_assets".format(self.db_topic, self.name)
        self.neighbor_topic = "{}/{}/neighbors".format(self.db_topic, self.name)
        self.transactive_record_topic = "{}/{}/transactive_record".format(self.db_topic, self.name)
        self.market_balanced_price_topic = "{}/{}/market_balanced_prices".format(self.db_topic, self.name)
        self.market_topic = "{}/{}/market".format(self.db_topic, self.name)
        self.tnt_real_time_market = None
        self.real_time_building_demand_curve = [None for i in range(2)]
        self.real_time_market_name = 'refinement_electric'
        self.real_time_price = [None for i in range(2)]
        self.real_time_mix_market_running = False
        self.real_time_quantity = [None for i in range(2)]
        self.current_day_ahead_market_name = None
        self.day_ahead_mixmarket_running = False
        self.day_ahead_clear_price_sent = {}
        self.real_time_clear_price_sent = {}
        self.real_time_duration = self.config.get('real_time_market_duration', 15)
        self.start_tent_market_topic = "{}/start_tent".format(self.db_topic)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        # Add other objects: assets, services, neighbors
        self.init_objects()

        # Join electric mix-markets
        for market in self.market_names:
            self.join_market(market, SELLER, self.reservation_callback, self.offer_callback,
                             self.aggregate_callback, self.price_callback, self.error_callback)

        # Join real time market
        self.join_market(self.real_time_market_name, SELLER, self.real_time_reservation_callback,
                         self.real_time_offer_callback, self.real_time_aggregate_callback,
                         self.real_time_price_callback, self.error_callback)
        # Subscriptions
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.campus_supply_topic,
                                  callback=self.new_supply_signal)

        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.power_topic,
                                  callback=self.new_demand_signal)

        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.market_balanced_price_topic,
                                  callback=self.send_cleared_price)

        #self.vip.pubsub.subscribe(peer='pubsub',
        #                          prefix=self.start_tent_market_topic,
        #                          callback=self.start_tent_market)
        # SN: Added for new state machine based TNT implementation
        self.core.spawn_later(5, self.state_machine_loop)

    def start_tent_market(self, peer, sender, bus, topic, headers, message):
        # SN: Added for new state machine based TNT implementation
        self.core.spawn_later(5, self.state_machine_loop)

    # 191219DJH: This appears to mostly drive the mixed market. Consider whether any of this functionality will fight
    #            with the new market state machine, which should now direct all timing in the transactive network.
    def new_supply_signal(self, peer, sender, bus, topic, headers, message):
        _log.debug("At {}, {} receives new supply records: {}".format(Timer.get_cur_time(),
                                                                     self.name, message))
        supply_curves = message['curves']
        start_of_cycle = message['start_of_cycle']
        tnt_market_name = message['tnt_market_name']
        # 191219DJH: CAUTION: This next logic might be replaced by the market state machine (?)
        # self.campus.receive_transactive_signal(self, supply_curves)
        # SN: Added for new state machine based TNT implementation
        self.campus.receivedCurves = supply_curves
        _log.debug("At {}, mixmarket state is {}, start_of_cycle {}".format(Timer.get_cur_time(),
                                                                            self.mix_market_running,
                                                                            start_of_cycle))

        db_topic = "/".join([self.db_topic, self.name, "CampusSupply"])
        message = supply_curves
        headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
        self.vip.pubsub.publish("pubsub", db_topic, headers, message).get()

        _log.debug("Market {} CLEARED ".format(tnt_market_name))
        if start_of_cycle:
            _log.debug("At {}, start of cycle. "
                       "Mixmarket state before overriding is {}".format(Timer.get_cur_time(),
                                                                        self.mix_market_running))

            # if self.simulation:
            #     self.run_ep_sim(start_of_cycle)
            # else:
            self.start_mixmarket(start_of_cycle)
        # else:
        #     _log.debug("CAMPUS SUPPLY CURVES: At {}, start of cycle. {}".format(Timer.get_cur_time(),
        #                                                 start_of_cycle))
        #     for curve in supply_curves:
        #         _log.debug("CAMPUS SUPPLY CURVES: {}".format(curve))
        #     # find market index
        #     market_idx = self.find_tnt_market_index(tnt_market_name)
        #     # Send cleared price to building level assets
        #     self.send_cleared_price(self.markets[market_idx], supply_curves)

        # for idx, p in enumerate(self.markets[0].marginalPrices):
        #     _log.debug("new_supply_signal: At {} Market marginal prices are: {}".format(self.name, p.value))

    def publish_message(self, topic, message, timestamp=None):

        now = format_timestamp(timestamp) if timestamp else format_timestamp(Timer.get_cur_time())
        message.update({"Date": now})
        header = {headers_mod.DATE: now}
        try:
            _log.debug(f"message = {message}")
            self.vip.pubsub.publish(peer='pubsub',
                                    topic=topic,
                                    message= message,
                                    headers= header)
        except Exception as e:
            _log.error("In Publish: {}".format(str(e)))

    def send_cleared_price(self, peer, sender, bus, topic, headers, message):
        _log.info("At {}, {} receives new cleared prices: {}".format(Timer.get_cur_time(),
                                                                     self.name, message))
        tnt_market_name = message['tnt_market_name']
        market_idx = self.find_tnt_market_index(tnt_market_name)
        market = self.markets[market_idx]
        tmp_price = []
        time_intervals = list()

        for p in market.marginalPrices:
            tmp_price.append(p.value)
            time_intervals.append(p.timeInterval.startTime.strftime('%Y%m%dT%H%M%S'))

        prices_tuple = list()
        if market.name.startswith('Day-Ahead'):
            for idx, p in enumerate(market.marginalPrices):
                self._building_market_prices[idx] = p.value
                avg_price, std_dev = market.model_prices(p.timeInterval.startTime)
                prices_tuple.append((avg_price, std_dev))
            self.prices = self._building_market_prices  # [p.value for p in prices]
            _log.info("Market for name: {} CLEARED marginal prices are: {}, flag: {}".format(market.name,
                                                                                    self.prices,
                                                                                    self.day_ahead_clear_price_sent))

            if not self.day_ahead_clear_price_sent[market.name]:
                _log.info("Market for name: {}, publishing cleared price".format(self.day_ahead_clear_price_sent))
                message = {"prices": self.prices,#[DAH1, DAH2]
                           "price_info": prices_tuple,
                           "market_intervals": time_intervals,#[T1, T2]
                           "correction_market": False}
                self.publish_message(self.cleared_price_topic, message)
                for i, price in enumerate(self.prices):
                    self.publish_message(self.day_ahead_price_topic, {"day_ahead_price":price}, time_intervals[i])
                     
                self.day_ahead_clear_price_sent[market.name] = True
            _log.info(f"Market for name: {market.name}, published cleared price {self.day_ahead_clear_price_sent[market.name]}")
                
        elif market.name.startswith('Real-Time'):
            price = market.marginalPrices
            # Get real time price from Real time market
            self.real_time_price = [price[0].value]
            avg_price, std_dev = market.model_prices(price[0].timeInterval.startTime)
            price_tuple = [(avg_price, std_dev)]
            _log.info(f"Market for name: {market.name} CLEARED marginal price are: {self.real_time_price}, PRICE TUPLE = {price_tuple} flag: {self.real_time_clear_price_sent[market.name]}")
            if not self.real_time_clear_price_sent.get(market.name, False):
                message = {"prices": self.real_time_price,
                           "price_info": price_tuple,
                           "market_intervals": time_intervals,
                           "correction_market": True}
                self.publish_message(self.cleared_price_topic, message)
                self.real_time_clear_price_sent[market.name] = True
                _log.info(f"Market for name: {market.name}, published cleared price: {self.real_time_clear_price_sent[market.name]}")

    def new_demand_signal(self, peer, sender, bus, topic, headers, message):
        mtrs = self.campus.meterPoints
        if len(mtrs) > 0:
            _log.info("METER points are available")
            bldg_meter = mtrs[0]
            power_unit = message[1]
            cur_power = float(message[0]["WholeBuildingPower"])
            power_unit = power_unit.get("WholeBuildingPower", {}).get("units", "kW")
            if isinstance(power_unit, str) and power_unit.lower() == "watts":
                cur_power = cur_power / 1000.0
            bldg_meter.set_meter_value(cur_power)
            if Timer.get_cur_time().minute >= 58:
                bldg_meter.update_avg()

        # for idx, p in enumerate(self.markets[0].marginalPrices):
        #     _log.debug("new_demand_signal: At {} Market marginal prices are: {}".format(self.name, p.value))

    def near_end_of_hour(self, now):
        near_end_of_hour = False
        if (now + self.mix_market_duration).hour != now.hour:
            near_end_of_hour = True
            _log.debug("{} did not start mixmarket because it's too late.".format(self.name))
        return near_end_of_hour

    def start_real_time_mixmarket(self, start_of_cycle, resend_balanced_prices=False, mkt=None):
        self.real_time_price = [None]
        self.real_time_quantity = [None]

        _log.debug("Building start_realtime_mixmarket: market name: {}".format(mkt.name))
        if mkt is None:
            # Balance market with previous known demands
            self.tnt_real_time_market = self.markets[0]  # If mkt is None, Assume only 1 TNS market per node
        else:
            self.tnt_real_time_market = mkt

        # Check if now is near the end of the hour, applicable only if not in simulation mode
        now = Timer.get_cur_time()
        near_end_of_hour = False
        if not self.simulation:
            near_end_of_hour = self.near_end_of_hour(now)

        self.tnt_real_time_market.check_marginal_prices(self)

        _log.debug("Building start_realtime_mixmarket for name: {}: converged: {}, resend_balanced_prices: {}, near_end_of_hour: {}".format(
            self.tnt_real_time_market.name,
            self.tnt_real_time_market.converged,
            resend_balanced_prices,
            near_end_of_hour
            ))
        _log.debug("Building start_realtime_mixmarket for name: {}, marginal prices: {}".format(self.tnt_real_time_market.name,
                                                                                       self.tnt_real_time_market.marginalPrices))
        if not self.tnt_real_time_market.converged or resend_balanced_prices:
            self.real_time_clear_price_sent[self.tnt_real_time_market.name] = False
            _log.info("Building start_realtime_mixmarket: here1: {}".format(self.real_time_clear_price_sent[self.tnt_real_time_market.name]))
            # Get price of the hour
            price = self.tnt_real_time_market.marginalPrices
            _log.debug("Building start_realtime_mixmarket: price: {}".format(price[0].value))
            initial_price = self.tnt_real_time_market.marginalPrices
            prices_tuple = None
            _log.debug("Building start_realtime_mixmarket: initial startTime : {}".format(initial_price[0].timeInterval.startTime))
            avg_price, std_dev = self.tnt_real_time_market.model_prices(initial_price[0].timeInterval.startTime)
            prices_tuple = [(avg_price, std_dev)]

            self.real_time_price = [price[0].value]
            market_start_hour = price[0].timeInterval.startTime.hour
            time_intervals = [price[0].timeInterval.startTime.strftime('%Y%m%dT%H%M%S')]
            # Signal to start mix market only if the previous market is done
            if not self.real_time_mix_market_running and not near_end_of_hour:
                _log.debug("Building start_realtime_mixmarket: here2")
                self.real_time_mix_market_running = True
                # Update weather information
                weather_service = None
                if len(self.informationServiceModels)>0:
                    weather_service = self.informationServiceModels[0]
                    weather_service.update_information(self.tnt_real_time_market)
                _log.info("Market name: {} start_realtime_mixmarket Building At market START Market marginal prices are: {}".format(mkt.name,
                                                                                                            self.real_time_price))
                if weather_service is None:
                    message = {"prices": self.real_time_price,
                               "price_info": prices_tuple,
                               "market_intervals": time_intervals,
                               "correction_market": True}
                    self.publish_message('mixmarket/start_new_cycle', message)
                else:
                    temps = [x.value for x in weather_service.predictedValues if x.timeInterval.startTime.hour == market_start_hour]
                    # temps = temps[-24:]
                    _log.debug("temps are {}".format(temps))
                    message = {"prices": self.real_time_price,
                               "price_info": prices_tuple,
                               "market_intervals": time_intervals,
                               "temp": temps,
                               "correction_market": True}
                    self.publish_message('mixmarket/start_new_cycle', message)


    # 191219DJH: Consider the interactions of mixed market with the market state machine, please.
    #            I'm finding it very hard to determine which functions address the mixed market, and which address the
    #            network market(s). This is confusing. All building functions should have been addressed by a building
    #            asset model.
    #            IMPORTANT: This must be rethought still again when there are multiple and correction markets. THERE IS
    #                       NOT SIMPLY ONE OBJECT "MARKET".
    def start_mixmarket(self, start_of_cycle, resend_balanced_prices=False, mkt=None):
        # Reset price array
        self.prices = [None for i in range(24)]

        # Save the 1st quantity as prior 2nd quantity
        # cur_quantity = self.quantities[1]
        # cur_curve = self.building_demand_curves[1]

        # Reset quantities and curves
        self.quantities = [None for i in range(24)]
        self.building_demand_curves = [None for i in range(24)]

        # If new cycle, set the 1st quantity to the corresponding quantity of previous hour
        # if start_of_cycle:
        #     self.quantities[0] = cur_quantity
        #     self.building_demand_curves[0] = cur_curve

        if mkt is None:
            # Balance market with previous known demands
            market = self.markets[0]  # If mkt is None, Assume only 1 TNS market per node
        else:
            market =mkt
            self.current_day_ahead_market_name = mkt.name
        market.signal_new_data = True

        # Check if now is near the end of the hour, applicable only if not in simulation mode
        now = Timer.get_cur_time()
        near_end_of_hour = False
        if not self.simulation:
            near_end_of_hour = self.near_end_of_hour(now)

        market.check_marginal_prices(self)

        _log.debug("Building start_mixMarket for name: {}: converged: {}, resend_balanced_prices: {}, near_end_of_hour: {}".format(
            market.name,
            market.converged,
            resend_balanced_prices,
            near_end_of_hour
            ))
        _log.debug("Building start_mixMarket for name: {}, marginal prices: {}".format(market.name,
                                                                                       market.marginalPrices))
        if not market.converged or resend_balanced_prices:
            self.day_ahead_mixmarket_running = True
            self.day_ahead_clear_price_sent[market.name] = False
            _log.info("Building start_mixMarket: here1, falg: {}".format(self.day_ahead_clear_price_sent[market.name]))
            prices = market.marginalPrices
            initial_prices = market.marginalPrices
            prices_tuple = list()
            time_intervals = list()
            for x in range(len(initial_prices)):
                avg_price, std_dev = market.model_prices(initial_prices[x].timeInterval.startTime)
                prices_tuple.append((avg_price, std_dev))
                time_intervals.append(initial_prices[x].timeInterval.startTime.strftime('%Y%m%dT%H%M%S'))

            for idx, p in enumerate(prices):
                self._building_market_prices[idx] = p.value
            self.prices = self._building_market_prices #[p.value for p in prices]

            # Signal to start mix market only if the previous market is done
            if not self.mix_market_running and not near_end_of_hour:
                _log.debug("Building start_mixMarket: here2")
                self.mix_market_running = True
                # Update weather information
                weather_service = None
                if len(self.informationServiceModels)>0:
                    weather_service = self.informationServiceModels[0]
                    weather_service.update_information(market)
                _log.info("Market name: {} Building At market START Market marginal prices are: {}".format(mkt.name,
                                                                                                            self.prices))
                if weather_service is None:
                    message = {"prices": self.prices,
                               "price_info": prices_tuple,
                               "market_intervals": time_intervals,
                               "correction_market": False}
                    self.publish_message('mixmarket/start_new_cycle', message)
                else:
                    temps = [x.value for x in weather_service.predictedValues]
                    temps = temps[-24:]
                    _log.debug("temps are {}".format(temps))
                    message = {"prices": self.prices,
                               "price_info": prices_tuple,
                               "market_intervals": time_intervals,
                               "temp": temps,
                               "correction_market": False}
                    self.publish_message('mixmarket/start_new_cycle', message)

    # 191219DJH: The mix of markets will be hard to disentangle. I can't tell for certain which variables belong to each
    #            process. The network markets should all be driven by the new market state machine hereafter, so the
    #            network actions should be stripped from this method. There will be many markets in the network, not
    #            simply "market" as done here. The building should have been handled entirely as a local asset.
    '''
    def balance_market(self, run_cnt):
    market = self.markets[0]  # Assume only 1 TNS market per node
    market.new_data_signal = True
    # market.balance(self)
    # market.events(self)

    if market.converged:
        _log.debug("TNS market {} balanced successfully.".format(market.name))
        balanced_curves = [(x.timeInterval.startTime,
                            x.value.marginalPrice,
                            x.value.power) for x in market.activeVertices]
        _log.debug("Balanced curves: {}".format(balanced_curves))

        # Sum all the powers as will be needed by the net supply/demand curve.
        market.assign_system_vertices(self)

        # Check to see if it is ok to send signals
        self.campus.check_for_convergence(market)
        if not self.campus.converged:
            _log.debug("Campus model not converged. Sending signal back to campus.")
            self.campus.prep_transactive_signal(market, self)
            self.campus.send_transactive_signal(self, self.building_demand_topic)
    '''

    def init_objects(self):

        # Add weather forecast service
        weather_service = TemperatureForecastModel(self.config_path, self)
        self.informationServiceModels.append(weather_service)

        # Add elastic load asset
        self.elastic_load = self.make_tcc_model()

        # Add day-ahead market
        market = self.make_day_ahead_market()

        # Campus neighbor object
        self.campus = self.make_campus_neighbor()

        topics = []

    def make_day_ahead_market(self):
        # 191219DJH: It will be important that different agents' markets are similarly, if not identically,
        # instantiated. I.e., the day ahead market at the city must be defined just like the ones at the campus and
        # building nodes. Otherwise, the negotiations between the network agents will probably not work within the
        # context of the new market state machines.
        market = DayAheadAuction()  # A child of class Auction.
        market.commitment = True  # To be corrected by 15-minute real-time auction markets
        market.converged = False
        market.defaultPrice = 0.0428  # [$/kWh]
        market.dualityGapThreshold = self.duality_gap_threshold  # [0.02 = 2#]
        market.initialMarketState = MarketState.Inactive
        market.marketOrder = 1  # This is first market
        market.intervalsToClear = 24  # 24 hours are cleared altogether
        market.futureHorizon = timedelta(hours=24)  # Projects 24 hourly future intervals
        market.intervalDuration = timedelta(hours=1)  # [h] Intervals are 1 h long
        # market.marketClearingInterval = timedelta(days=1)  # The market clears daily
        market.marketClearingInterval = timedelta(days=1)
        market.marketSeriesName = "Day-Ahead_Auction"  # Prepends future market object names
        market.method = 2  # Use simpler interpolation solver

        # This times must be defined the same for all network agents.
        market.deliveryLeadTime = timedelta(hours=1)
        #    market.negotiationLeadTime = timedelta(minutes=15)
        market.negotiationLeadTime = timedelta(minutes=8)

        market.marketLeadTime = timedelta(minutes=15)
        market.activationLeadTime = timedelta(minutes=0)
        market.real_time_duration = self.real_time_duration

        # Determine the current and next market clearing times in this market:
        current_time = Timer.get_cur_time()
        current_hour = current_time.hour + 1
        current_time = current_time - timedelta(hours=24)
        # _log.debug("BUILDING agent current_time: {}".format(current_time))
        # Presume first delivery hour starts at 10:00 each day:
        new_hr = current_time.hour + 1
        delivery_start_time = current_time.replace(hour=new_hr, minute=0, second=0, microsecond=0)

        # The market clearing time must occur a delivery lead time prior to delivery:
        while delivery_start_time - market.deliveryLeadTime - market.marketLeadTime - market.negotiationLeadTime - market.activationLeadTime < current_time:
            delivery_start_time = delivery_start_time + timedelta(hours=1)
            _log.debug("MAKE BUILDING DA MARKET LOOP: {}".format(delivery_start_time))
        market.marketClearingTime = delivery_start_time - market.deliveryLeadTime
        _log.debug("MAKE BUILDING DA MARKET CLEARING TIME: {}".format(market.marketClearingTime))
        # If it's too late today to begin the market processes, according to all the defined lead times, skip to the
        # next market object:
        # if current_time > market.marketClearingTime - market.marketLeadTime \
        #   market.marketClearingTime = market.marketClearingTime + market.marketClearingInterval

        market.nextMarketClearingTime = market.marketClearingTime + market.marketClearingInterval
        _log.debug("MAKE BUILDING DA MARKET NEXT CLEARING TIME: {}".format(market.nextMarketClearingTime))
        dt = str(market.marketClearingTime)
        market.name = market.marketSeriesName.replace(' ', '_') + '_' + dt[:19]

        market.isNewestMarket = True

        self.markets.append(market)
        # Initialize the Market object's time intervals.
        market.check_intervals()

        # Initialize the marginal prices in the Market object's time intervals.
        market.check_marginal_prices(self)
        market.marketState = MarketState.Delivery
        for p in market.marginalPrices:
            _log.debug("Market name: {} Initial marginal prices: {}".format(market.name, p.value))
        return market

    def make_campus_neighbor(self):
        # 191219DJH: There are no longer separate object and model neighbor classes.
        #campus = Neighbor(demand_rate=0.0)
        campus = Neighbor()
        campus.name = 'PNNL_Campus'
        campus.description = 'PNNL_Campus'
        campus.maximumPower = self.max_deliver_capacity
        campus.minimumPower = 0.  # [avg.kW]
        campus.lossFactor = self.campus_loss_factor
        campus.location = self.name
        campus.defaultVertices = [Vertex(0.045, 25, 0, True), Vertex(0.048, 0, self.max_deliver_capacity, True)]
        campus.transactive = True
        campus.demandThresholdCoef = self.demandThresholdCoef
        # campus.demandThreshold = self.demand_threshold_coef * self.monthly_peak_power
        campus.demandThreshold = self.monthly_peak_power
        campus.upOrDown = Direction.upstream #'upstream'
        # campus.inject(self,
        #               system_loss_topic=self.system_loss_topic,
        #               dc_threshold_topic=self.dc_threshold_topic)

        # Avg building meter
        building_meter = MeterPoint()
        building_meter.name = self.name + ' ElectricMeter'
        building_meter.measurementType = MeasurementType.AverageDemandkW
        building_meter.measurementUnit = MeasurementUnit.kWh
        campus.meterPoints.append(building_meter)

        # SN: Added to integrate new state machine logic with VOLTTRON
        # This topic will be used to send transactive signal
        campus.publishTopic = self.building_demand_topic

        # Add campus as building's neighbor
        self.neighbors.append(campus)

        return campus

    def make_tcc_model(self):
        elastic_load = TccModel() #DummyTccModel()
        elastic_load.name = 'TccModel' #'DummyTccModel'
        elastic_load.maximumPower = 0  # Remember that a load is a negative power [kW]
        elastic_load.minimumPower = -self.max_deliver_capacity
        elastic_load.defaultPower = -0.5 * self.max_deliver_capacity  # [kW]
        elastic_load.defaultVertices = [Vertex(0.055, 0, -elastic_load.defaultPower, True),
                                             Vertex(0.06, 0, -elastic_load.defaultPower / 2, True)]

        elastic_load.add_building_volttron_agent(self)
        # Add inelastic and elastic loads as building' assets
        self.localAssets.append(elastic_load)

        return elastic_load

    def state_machine_loop(self):
        # 191218DJH: This is the entire timing logic. It relies on current market object's state machine method events()
        import time
        market = self.markets[0]
        self._building_market_prices = [market.defaultPrice]*24

        _log.info("Initial price: {}".format(self._building_market_prices))

        while not self._stop_agent:  # a condition may be added to provide stops or pauses.
            markets_to_remove = []
            for i in range(len(self.markets)):
                self.markets[i].events(self)
                #_log.debug("Markets: {}, Market name: {}, Market state: {}".format(len(self.markets),
                #                                                                   self.markets[i].name,
                #                                                                   self.markets[i].marketState))

                if self.markets[i].marketState == MarketState.Expired:
                    markets_to_remove.append(self.markets[i])
                # NOTE: A delay may be added, but the logic of the market(s) alone should be adequate to drive system
                # activities
                #gevent.sleep(0.05)
                gevent.sleep(0.01)
            for mkt in markets_to_remove:
                _log.debug("Market name: {}, Market state: {}. It will be removed shortly".format(mkt.name,
                                                                                                  mkt.marketState))
                if mkt.name in self.day_ahead_clear_price_sent:
                    del self.day_ahead_clear_price_sent[mkt.name]
                else:
                    if mkt.name in self.real_time_clear_price_sent:
                        del self.real_time_clear_price_sent[mkt.name]
                self.markets.remove(mkt)


    @Core.receiver('onstop')
    def onstop(self, sender, **kwargs):
        self._stop_agent = True

    #########################################################################
    # SN: TCC Real Time MixMarket methods
    #########################################################################
    def real_time_reservation_callback(self, timestamp, market_name, buyer_seller):
        _log.debug("{}: wants reservation for {} as {} at {}".format(self.agent_name,
                                                                           market_name,
                                                                           buyer_seller,
                                                                           timestamp))
        if self.day_ahead_mixmarket_running:
            _log.debug("{}: No reservation for {} as day_ahead_mixmarket_running: {}".format(self.agent_name,
                                                                                               market_name,
                                                                                               self.day_ahead_mixmarket_running))
            return False
        else:
            _log.debug("{}: reservation made for {} as day_ahead_mixmarket_running: {}".format(self.agent_name,
                                                                                               market_name,
                                                                                               self.day_ahead_mixmarket_running))
            return True


    def real_time_offer_callback(self, timestamp, market_name, buyer_seller):
        # Get price from marginal price of TNT market
        price = self.tnt_real_time_market.marginalPrices
        # Quantity
        min_quantity = 0
        max_quantity = 10000  # float("inf")
        # Create supply curve
        supply_curve = PolyLine()
        supply_curve.add(Point(quantity=min_quantity, price=price[0].value))
        supply_curve.add(Point(quantity=max_quantity, price=price[0].value))

        # Make offer
        _log.debug("{}: offer for {} as {} at {} - Curve: {} {}".format(self.agent_name,
                                                                        market_name,
                                                                        SELLER,
                                                                        timestamp,
                                                                        supply_curve.points[0],
                                                                        supply_curve.points[1]))
        success, message = self.make_offer(market_name, SELLER, supply_curve)
        _log.debug("{}: offer has {} - Message: {}".format(self.agent_name, success, message))

    def real_time_aggregate_callback(self, timestamp, market_name, buyer_seller, aggregate_demand):
        if buyer_seller == BUYER and market_name == self.real_time_market_name:  # self.base_market_name in market_name:
            _log.debug("{}: at ts {} min of aggregate curve : {}".format(self.agent_name,
                                                                         timestamp,
                                                                         aggregate_demand.points[0]))
            _log.debug("{}: at ts {} max of aggregate curve : {}".format(self.agent_name,
                                                                         timestamp,
                                                                         aggregate_demand.points[- 1]))
            _log.debug("At {}: Report aggregate Market: {} buyer Curve: {}".format(Timer.get_cur_time(),
                                                                                   market_name,
                                                                                   aggregate_demand))
            self.real_time_building_demand_curve = [(aggregate_demand.points[0], aggregate_demand.points[-1])]
            db_topic = "/".join([self.db_topic, self.name, "AggregateDemand"])
            message = {
                "Timestamp": format_timestamp(timestamp),
                "MarketName": market_name,
                "Curve": aggregate_demand.points
            }
            self.publish_message(db_topic, message)

    def real_time_price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        _log.debug("{}: cleared price ({}, {}) for {} as {} at {}".format(Timer.get_cur_time(),
                                                                              price,
                                                                              quantity,
                                                                              market_name,
                                                                              buyer_seller,
                                                                              timestamp))
        if price is not None:
            self.real_time_price = [price]
        if quantity is not None:
            self.real_time_quantity = [quantity]

        tnt_market_idx = None
        for idx in range(len(self.markets)):
            if self.markets[idx].name == self.tnt_real_time_market.name:
                tnt_market_idx = idx

        self.real_time_mix_market_running = False

        curves_arr = [(c[0].tuppleize(), c[1].tuppleize()) if c is not None else None
                      for c in self.real_time_building_demand_curve]
        _log.debug("Real Time market Data at time {}:".format(Timer.get_cur_time()))
        _log.debug("Real Time market Market intervals: {}".format(self.markets[tnt_market_idx].name))
        _log.debug("Real Time market Quantities: {}".format(self.real_time_quantity))
        _log.debug("Real Time market Prices: {}".format(self.real_time_price))
        _log.debug("Real Time market Curves: {}".format(curves_arr))

        db_topic = "/".join([self.db_topic, self.name, "RealTimeDemand"])
        message = {"Timestamp": format_timestamp(timestamp), "Curves": self.real_time_building_demand_curve}
        self.publish_message(db_topic, message)
        # SN: Setting TCC curves in local asset model (TccModel)
        self.elastic_load.set_scheduled_power(self.real_time_quantity,
                                              self.real_time_price,
                                              self.real_time_building_demand_curve,
                                              self.markets[tnt_market_idx])


    #########################################################################
    # SN: Electric MixMarket methods
    #########################################################################
    def offer_callback(self, timestamp, market_name, buyer_seller):
        if market_name in self.market_names:
            _log.debug("Building offer_callback: market_name: {}".format(market_name))
            # Get the price for the corresponding market
            idx = int(market_name.split('_')[-1])
            _log.debug("Building offer_callback: prices: {}".format(self.prices))
            price = self.prices[idx]
            # price *= 1000.  # Convert to mWh to be compatible with the mixmarket
            _log.debug("Building offer_callback: market index: {}, price at index: {}".format(idx, price))
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
                                                                        supply_curve.points[0],
                                                                        supply_curve.points[1]))
            success, message = self.make_offer(market_name, SELLER, supply_curve)
            _log.debug("{}: offer has {} - Message: {}".format(self.agent_name, success, message))

    # Dummy callbacks
    def aggregate_power(self, peer, sender, bus, topic, headers, message):
        _log.debug("{}: received topic for power aggregation: {}".format(self.agent_name,
                                                                         topic))
        data = message[0]
        _log.debug("{}: updating power aggregation: {}".format(self.agent_name,
                                                               data))

    #########################################################################
    # SN: TCC Market methods
    #########################################################################
    def reservation_callback(self, timestamp, market_name, buyer_seller):
        _log.debug("{}: wants reservation for {} as {} at {}".format(self.agent_name,
                                                                           market_name,
                                                                           buyer_seller,
                                                                           timestamp))
        if not self.day_ahead_mixmarket_running:
            _log.debug("{}: No reservation for {} as day_ahead_mixmarket_running: {}".format(self.agent_name,
                                                                                             market_name,
                                                                                             self.day_ahead_mixmarket_running))
            return False
        else:
            _log.debug("{}: reservation made for {} as day_ahead_mixmarket_running: {}".format(self.agent_name,
                                                                                             market_name,
                                                                                             self.day_ahead_mixmarket_running))
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
            self.building_demand_curves[idx] = (aggregate_demand.points[0], aggregate_demand.points[-1])
            #idx += 1  # quantity has 25 values while there are 24 future markets
            db_topic = "/".join([self.db_topic, self.name, "AggregateDemand"])
            message = {
                "Timestamp": format_timestamp(timestamp),
                "MarketName": market_name,
                "Curve": aggregate_demand.points
            }
            self.publish_message(db_topic, message)

    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        _log.debug("{}: cleared price ({}, {}) for {} as {} at {}".format(Timer.get_cur_time(),
                                                                          price,
                                                                          quantity,
                                                                          market_name,
                                                                          buyer_seller,
                                                                          timestamp))
        idx = int(market_name.split('_')[-1])
        _log.debug("Market index: {}".format(idx))

        #self.prices[idx+1] = price  # price has 24 values, current hour price is excluded
        self.prices[idx] = price  # price has 24 values, current hour price is excluded
        if price is None:
            raise "Market {} did not clear. Price is none.".format(market_name)
        #idx += 1  # quantity has 25 values while there are 24 future markets
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
        mix_market_done = all([False if q is None else True for q in self.quantities])

        now = Timer.get_cur_time()
        idx = int(market_name.split('_')[-1])
        _log.debug("Mix market done: {}, market idx: {}".format(mix_market_done, idx))

        if mix_market_done:
            self.day_ahead_mixmarket_running = False
            # Check if any quantity is greater than physical limit of the supply wire
            _log.debug("Quantity: {}".format(self.quantities))
            if not all([False if q > self.max_deliver_capacity else True for q in self.quantities]):
                _log.error("One of quantity is greater than "
                           "physical limit {}".format(self.max_deliver_capacity))

            # Check demand curves exist
            all_curves_exist = all([False if q is None else True for q in self.building_demand_curves])
            if not all_curves_exist:
                _log.error("Demand curves: {}".format(self.building_demand_curves))
                raise "Mix market has all quantities but not all demand curves"

            # Update demand and balance market
            self.mix_market_running = False

            curves_arr = [(c[0].tuppleize(), c[1].tuppleize()) if c is not None else None
                          for c in self.building_demand_curves]
            _log.debug("Data at time {}:".format(Timer.get_cur_time()))
            _log.debug("Market intervals: {}".format([x.name for x in self.markets[0].timeIntervals]))
            _log.debug("Quantities: {}".format(self.quantities))
            _log.debug("Prices: {}".format(self.prices))
            _log.debug("Curves: {}".format(curves_arr))

            db_topic = "/".join([self.db_topic, self.name, "AggregateDemand"])
            message = {"Timestamp": format_timestamp(timestamp), "Curves": self.building_demand_curves}
            self.publish_message(db_topic, message)

            # Get TNT market index from current day ahead market name
            tnt_mkt_idx = self.find_tnt_market_index(self.current_day_ahead_market_name)

            db_topic = "/".join([self.db_topic, self.name, "Price"])
            price_message = []
            for i in range(len(self.markets[tnt_mkt_idx].timeIntervals)):
                ts = self.markets[tnt_mkt_idx].timeIntervals[i].name
                price = self.prices[i]
                quantity = self.quantities[i]
                price_message.append({'timeInterval': ts, 'price': price, 'quantity': quantity})
            message = {"Timestamp": format_timestamp(timestamp), "Price": price_message}
            headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
            self.vip.pubsub.publish("pubsub", db_topic, headers, message).get()

            # SN: Setting TCC curves in local asset model (TccModel)
            self.elastic_load.set_scheduled_power(self.quantities,
                                                  self.prices,
                                                  self.building_demand_curves,
                                                  self.markets[tnt_mkt_idx])
            for curve in self.building_demand_curves:
                _log.debug("XXX Building curves: {}".format(curve))

            #self.balance_market(1)

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
        # 191219DJH: The assumption of 1 TNS market per node will no longer be valid.
        #            ***** This logic should be driven by the market state machines *****
        #            I honestly can't tell where TNS ends and mixed market starts in this method code.
        market = self.markets[0]  # Assume only 1 TNS market per node
        market.signal_new_data = True
        # market.balance(self)
        # market.events(self)

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

                self.elastic_load.set_tcc_curves(self.quantities,
                                                        self.prices,
                                                        self.building_demand_curves)
                #self.balance_market(1)
            # End E+ output reading

    def error_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux):
        _log.debug("{}: error for {} as {} at {} - Message: {}".format(self.agent_name,
                                                                       market_name,
                                                                       buyer_seller,
                                                                       timestamp,
                                                                       error_message))

    def find_tnt_market_index(self, market_name):
        # Get TNT market index from current day ahead market name
        tnt_mkt_idx = None
        for idx in range(len(self.markets)):
            if self.markets[idx].name == market_name:
                tnt_mkt_idx = idx
                break
        return tnt_mkt_idx

def main(argv=sys.argv):
    try:
        utils.vip_main(BuildingAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
