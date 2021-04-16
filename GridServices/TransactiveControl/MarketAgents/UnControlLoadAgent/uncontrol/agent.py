# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
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

import sys
import logging
import dateutil.tz
from dateutil import parser
from sympy import symbols
from sympy.parsing.sympy_parser import parse_expr
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent import utils
from volttron.platform.agent.math_utils import mean, stdev
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import SELLER
from volttron.platform.agent.base_market_agent.buy_sell import BUYER

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"
TIMEZONE = "US/Pacific"


def uncontrol_agent(config_path, **kwargs):
    """Parses the uncontrollable load agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: Market Service Agent
    :rtype: MarketServiceAgent
    """

    _log.debug("Starting the uncontrol agent")
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}

    if not config:
        _log.info("Using defaults for starting configuration.")
    agent_name = config.get("agent_name", "uncontrol")
    base_name = config.get('market_name', 'electric')
    market_name = []
    q_uc = []
    price_multiplier = config.get('price_multiplier', 1.0)
    default_min_price = config.get('static_minimum_price', 0.01)
    default_max_price = config.get('static_maximum_price', 100.0)
    market_type = config.get("market_type", "tns")
    single_market_interval = config.get("single_market_interval", 15)
    market_number = 24
    if market_type == "rtp":
        market_number = 1
    for i in range(market_number):
        market_name.append('_'.join([base_name, str(i)]))
    for i in range(24):
        q_uc.append(float(config.get("power_" + str(i), 0)))

    verbose_logging = config.get('verbose_logging', True)
    building_topic = topics.DEVICES_VALUE(campus=config.get("campus", ""),
                                          building=config.get("building", ""),
                                          unit=None,
                                          path="",
                                          point="all")
    devices = config.get("devices")
    static_price_flag = config.get('static_price_flag', False)

    record_topic = '/'.join(["tnc", config.get("campus", ""), config.get("building", "")])
    sim_flag = config.get("sim_flag", False)

    return UncontrolAgent(agent_name, market_name, single_market_interval, verbose_logging, q_uc, building_topic, devices,
                          price_multiplier, default_min_price, default_max_price, sim_flag, record_topic, static_price_flag, **kwargs)


class UncontrolAgent(MarketAgent):
    def __init__(self, agent_name, market_name, single_market_interval, verbose_logging, q_uc, building_topic, devices,
                 price_multiplier, default_min_price, default_max_price, sim_flag, record_topic, static_price_flag, **kwargs):
        super(UncontrolAgent, self).__init__(verbose_logging, **kwargs)
        self.market_name = market_name
        self.q_uc = q_uc
        self.price_index = 0
        self.price_multiplier = price_multiplier
        self.default_max_price = default_max_price
        self.default_min_price = default_min_price
        self.static_price_flag = static_price_flag

        self.infinity = 1000000
        self.current_hour = None
        self.power_aggregation = []
        self.current_power = None
        self.sim_flag = sim_flag
        self.demand_aggregation_master = {}
        self.demand_aggregation_working = {}
        self.agent_name = agent_name
        self.uc_load_array = []
        self.prices = []
        self.single_timestep_power = 0
        self.single_market_interval = single_market_interval
        self.normalize_to_hour = 0.
        self.record_topic = record_topic
        self.current_datetime = None
        for market in self.market_name:
            self.join_market(market, BUYER, None, self.offer_callback,
                             None, self.price_callback, self.error_callback)

        self.building_topic = building_topic
        self.devices = devices

    @Core.receiver('onstart')
    def setup(self, sender, **kwargs):
        """
        Set up subscriptions for demand limiting case.
        :param sender:
        :param kwargs:
        :return:
        """
        for device, points in self.devices.items():
            device_topic = self.building_topic(unit=device)
            _log.debug('Subscribing to {}'.format(device_topic))
            self.demand_aggregation_master[device_topic] = points
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=device_topic,
                                      callback=self.aggregate_power)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='mixmarket/start_new_cycle',
                                  callback=self.get_prices)

        self.demand_aggregation_working = self.demand_aggregation_master.copy()
        _log.debug('Points are  {}'.format(self.demand_aggregation_working))

    def get_prices(self, peer, sender, bus, topic, headers, message):
        _log.debug("Get prices prior to market start.")

        # Store received prices so we can use it later when doing clearing process
        self.prices = message['prices']  # Array of price

    def offer_callback(self, timestamp, market_name, buyer_seller):
        index = self.market_name.index(market_name)
        load_index = self.determine_load_index(index)
        demand_curve = self.create_demand_curve(load_index, index)
        result, message = self.make_offer(market_name, buyer_seller, demand_curve)

        _log.debug("{}: result of the make offer {} at {}".format(self.agent_name,
                                                                  result,
                                                                  timestamp))

    def conversion_handler(self, conversion, points, point_list):
        expr = parse_expr(conversion)
        sym = symbols(points)
        return float(expr.subs(point_list))

    def determine_load_index(self, index):
        if self.current_hour is None:
            return index
        elif index + self.current_hour + 1 < 24:
            return self.current_hour + index + 1
        else:
            return self.current_hour + index + 1 - 24

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
            current_time = parser.parse(headers["Date"])
            to_zone = dateutil.tz.gettz(TIMEZONE)
            current_time = current_time.astimezone(to_zone)
        else:
            current_time = parser.parse(headers["Date"])
        self.current_datetime = current_time
        current_hour = current_time.hour

        try:
            current_points = self.demand_aggregation_working.pop(topic)
        except KeyError:
            if self.power_aggregation:
                self.current_power = sum(self.power_aggregation)
            else:
                self.current_power = 0.
            _log.debug("ERROR - topic: {} -- waiting on {}".format(topic, self.demand_aggregation_working))
            self.demand_aggregation_working = self.demand_aggregation_master.copy()
            self.power_aggregation = []
            return

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
                self.normalize_to_hour += 1.0
                _log.debug("Current ts uncontrollable load: {}".format(sum(self.power_aggregation)))
            else:
                self.current_power = 0.
            self.power_aggregation = []
            self.demand_aggregation_working = self.demand_aggregation_master.copy()
            if len(self.market_name) > 1:
                if self.current_hour is not None and current_hour != self.current_hour:
                    self.q_uc[self.current_hour] = max(mean(self.uc_load_array)*self.normalize_to_hour/60.0, 10.0)
                    _log.debug("Current hour uncontrollable load: {}".format(mean(self.uc_load_array)*self.normalize_to_hour/60.0))
                    self.uc_load_array = []
                    self.normalize_to_hour = 0
            else:
                if len(self.uc_load_array) > self.single_market_interval:
                    self.uc_load_array.pop(0)
                smoothing_constant = 2.0 / (len(self.uc_load_array) + 1.0) * 2.0 if self.uc_load_array else 1.0
                smoothing_constant = smoothing_constant if smoothing_constant <= 1.0 else 1.0
                power_sort = list(self.uc_load_array)
                power_sort.sort(reverse=True)
                exp_power = 0
                for n in range(len(self.uc_load_array)):
                    exp_power += power_sort[n] * smoothing_constant * (1.0 - smoothing_constant) ** n
                exp_power += power_sort[-1] * (1.0 - smoothing_constant) ** (len(self.uc_load_array))
                _log.debug("Projected power: {}".format(exp_power))
                self.single_timestep_power = -exp_power
            self.current_hour = current_hour

    def create_demand_curve(self, load_index, index):
        demand_curve = PolyLine()
        price_min, price_max = self.determine_prices()
        try:
            if len(self.market_name) > 1:
                qMin = self.q_uc[load_index]
                qMax = self.q_uc[load_index]
            else:
                qMin = self.single_timestep_power
                qMax = self.single_timestep_power
            demand_curve.add(Point(price=max(price_min, price_max), quantity=min(qMin, qMax)))
            demand_curve.add(Point(price=min(price_min, price_max), quantity=max(qMin, qMax)))
        except:
            demand_curve.add(Point(price=max(price_min, price_max), quantity=0.1))
            demand_curve.add(Point(price=min(price_min, price_max), quantity=0.1))
        topic_suffix = "/".join([self.agent_name, "DemandCurve"])
        message = {"MarketIndex": index, "Curve": demand_curve.tuppleize(), "Commodity": "Electric"}
        self.publish_record(topic_suffix, message)
        _log.debug("{} debug demand_curve - curve: {}".format(self.agent_name, demand_curve.points))
        return demand_curve

    def determine_prices(self):
        try:
            if self.prices and not self.static_price_flag:
                avg_price = mean(self.prices)
                std_price = stdev(self.prices)
                price_min = avg_price - self.price_multiplier * std_price
                price_max = avg_price + self.price_multiplier * std_price
            else:
                price_min = self.default_min_price
                price_max = self.default_max_price
        except:
            price_min = self.default_min_price
            price_max = self.default_max_price
        return price_min, price_max

    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        _log.debug("{}: cleared price ({}, {}) for {} as {} at {}".format(self.agent_name,
                                                                          price,
                                                                          quantity,
                                                                          market_name,
                                                                          buyer_seller,
                                                                          timestamp))
        index = self.market_name.index(market_name)

    def error_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux):
        _log.debug("{}: error for {} as {} at {} - Message: {}".format(self.agent_name,
                                                                       market_name,
                                                                       buyer_seller,
                                                                       timestamp,
                                                                       error_message))

    def publish_record(self, topic_suffix, message):
        headers = {headers_mod.DATE: utils.format_timestamp(utils.get_aware_utc_now())}
        message["TimeStamp"] = utils.format_timestamp(self.current_datetime)
        topic = "/".join([self.record_topic, topic_suffix])
        self.vip.pubsub.publish("pubsub", topic, headers, message).get()


def main():
    """Main method called to start the agent."""
    utils.vip_main(uncontrol_agent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass