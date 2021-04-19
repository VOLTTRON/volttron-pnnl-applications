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

import sys
import logging
from dateutil.parser import parse
import dateutil.tz
import types
import gevent
from sympy import symbols
from sympy.parsing.sympy_parser import parse_expr
from datetime import datetime as dt
from datetime import timedelta as td
from volttron.platform.agent import utils
from transactive_utils.transactive_base.transactive import TransactiveBase
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.math_utils import mean, stdev

#from decorators import time_cls_methods

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = '0.3'


class UncontrolLoadAgent(TransactiveBase):
    """
    The UncontrolLoadAgent submits a fixed demand curve to represent
    the uncontrolled load within a building.
    """

    def __init__(self, config_path, **kwargs):
        try:
            config = utils.load_config(config_path)
        except StandardError:
            config = {}
        self.agent_name = config.get("agent_name", "uncontrol")
        self.current_hour = None
        self.power_aggregation = []
        self.current_power = None
        self.sim_flag = config.get("sim_flag", True)
        self.building_topic = topics.DEVICES_VALUE(campus=config.get("campus", ""),
                                                   building=config.get("building", ""),
                                                   unit=None,
                                                   path="",
                                                   point="all")
        self.demand_aggregation_master = {}
        self.demand_aggregation_working = {}
        self.agent_name = "uncontrol_load"
        self.uc_load_array = []
        self.rt_power = {}
        self.prices = []
        self.normalize_to_hour = 0.
        q_uc = []
        for i in range(24):
            q_uc.append(float(config.get("power_" + str(i), 0)))
        self.q_uc = q_uc
        self.current_datetime = None
        self.devices = config.get("devices", {})
        self.realtime_interval = config.get("realtime_interval", 15)
        TransactiveBase.__init__(self, config, **kwargs)

    def setup(self):
        """
        :param sender:
        :param kwargs:
        :return:
        """
        self.record_topic = '/'.join(["UncontrolLoad"])
        for market in self.market_manager_list:
            market.offer_callback = self.offer_callback
            market.create_demand_curve = self.create_demand_curve
            market.init_markets()

        if self.market_type == "rtp":
            self.update_prices = self.price_manager.update_rtp_prices
        else:
            self.update_prices = self.price_manager.update_prices

        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='mixmarket/start_new_cycle',
                                  callback=self.update_prices)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='tnc/cleared_prices',
                                  callback=self.price_manager.update_cleared_prices)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix="/".join([self.record_topic,
                                                   "update_model"]),
                                  callback=self.update_model)

        for device, points in self.devices.items():
            device_topic = self.building_topic(unit=device)
            _log.debug('Subscribing to {}'.format(device_topic))
            self.demand_aggregation_master[device_topic] = points
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=device_topic,
                                      callback=self.aggregate_power)

    def offer_callback(self, timestamp, market_name, buyer_seller):
        market_time = None
        for market in self.market_manager_list:
            if market_name in market.market_intervals:
                market_time = market.market_intervals[market_name]
                market_cls = market
                break
        if market_time is not None:
            demand_curve = self.create_demand_curve(market_name, parse(market_time), realtime=self.price_manager.correction_market)
            market_cls.demand_curve[market_time] = demand_curve
            result, message = self.make_offer(market_name, buyer_seller, demand_curve)
        else:
            _log.debug("Could not find market time during offer callback!")

    def create_demand_curve(self, market_name, market_time, realtime=False):
        """
        Create demand curve.  market_index (0-23) where next hour is 0
        (or for single market 0 for next market).  sched_index (0-23) is hour
        of day corresponding to market that demand_curve is being created.
        :param market_index: int; current market index where 0 is the next hour.
        :param sched_index: int; 0-23 corresponding to hour of day
        :param occupied: bool; true if occupied
        :return:
        """
        _log.debug("%s create_demand_curve - market_name: %s - market_time: %s",
                   self.core.identity,  market_name, market_time)
        demand_curve = PolyLine()
        prices = self.price_manager.get_price_array(market_time)
        if self.price_manager.correction_market:
            q = self.calculate_realtime_power(market_time.hour)
        else:
            q = self.q_uc[market_time.hour]
        for price in prices:
            demand_curve.add(Point(price=price, quantity=q))

        topic_suffix = "DemandCurve"
        message = {
            "MarketTime": str(market_time),
            "MarketName": market_name,
            "Curve": demand_curve.tuppleize(),
            "Commodity": "electricity"
        }
        _log.debug("%s debug demand_curve - curve: %s",
                   self.core.identity, demand_curve.points)
        self.publish_record(topic_suffix, message)
        return demand_curve

    def calculate_realtime_power(self, _hour):
        start_time = self.current_datetime - td(minutes=self.realtime_interval)
        power_array = []
        power_dict = {}
        q = 0
        for _time, power in self.rt_power.items():
            _log.debug("RT1 -- start_time: %s -- time: %s -- power: %s", start_time, _time, power)
            if _time >= start_time:
                power_array.append(power)
                power_dict[_time] = power
                _log.debug("RT2 -- power_array: %s", power_array)
        if power_array and self.realtime_interval < 60:
            smoothing_constant = 2.0 / (len(power_array) + 1.0) * 2.0 if power_array else 1.0
            smoothing_constant = smoothing_constant if smoothing_constant <= 1.0 else 1.0
            power_array.sort(reverse=True)
            _log.debug("RT3 -- sort power_array: %s", power_array)
            for n in range(len(power_array)):
                q += power_array[n] * smoothing_constant * (1.0 - smoothing_constant) ** n
            q += power_array[-1] * (1.0 - smoothing_constant) ** (len(power_array))
        else:
            q = self.q_uc[_hour]
        self.rt_power = power_dict
        _log.debug("RT3 -- q: %s", q)
        return q

    def init_predictions(self, output_info):
        pass

    def update_state(self, market_time, market_index, occupied, price, prices):
        pass

    def aggregate_power(self, peer, sender, bus, topic, headers, message):
        """
        Power measurements for devices are aggregated.
        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        :return:
        """
        _log.debug("{}: received topic for power aggregation: {}".format(self.agent_name, topic))
        data = message[0]
        if not self.sim_flag:
            current_time = parse(headers["Date"])
            current_time = current_time.astimezone(self.input_data_tz)
        else:
            current_time = parse(headers["Date"])
        self.current_datetime = current_time
        current_hour = current_time.hour
        try:
            current_points = self.demand_aggregation_working.pop(topic)
        except KeyError:
            if self.power_aggregation:
                self.current_power = sum(self.power_aggregation)
            else:
                self.current_power = 0.
            self.demand_aggregation_working = self.demand_aggregation_master.copy()

        conversion = current_points.get("conversion")
        point_list = []
        points = []
        for point in current_points.get("points", []):
            point_list.append((point, data[point]))
            points.append(point)
        if conversion is not None:
            value = float(self.conversion_handler(conversion, points, point_list))
        else:
            value = float(data[point])
        _log.debug("uncontrol - topic {} value {}".format(topic, value))
        self.power_aggregation.append(value)
        if not self.demand_aggregation_working:
            if self.power_aggregation:
                self.uc_load_array.append(sum(self.power_aggregation))
                self.rt_power[current_time] = - sum(self.power_aggregation)
                self.normalize_to_hour += 1.0
                _log.debug("Current ts uncontrollable load: {}".format(sum(self.power_aggregation)))
            else:
                self.current_power = 0.
            self.power_aggregation = []
            self.demand_aggregation_working = self.demand_aggregation_master.copy()

            if self.current_hour is not None and current_hour != self.current_hour:
                self.q_uc[self.current_hour] = max(-mean(self.uc_load_array)*self.normalize_to_hour/60.0, 10.0)
                _log.debug("Current hour uncontrollable load: {}".format(mean(self.uc_load_array)*self.normalize_to_hour/60.0))
                self.uc_load_array = []
                self.normalize_to_hour = 0
            self.current_hour = current_hour

    def conversion_handler(self, conversion, points, point_list):
        expr = parse_expr(conversion)
        sym = symbols(points)
        return float(expr.subs(point_list))


def main():
    """Main method called to start the agent."""
    utils.vip_main(UncontrolLoadAgent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass