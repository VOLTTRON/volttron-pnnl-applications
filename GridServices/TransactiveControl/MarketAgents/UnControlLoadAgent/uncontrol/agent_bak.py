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
from collections import defaultdict
from sympy import symbols
from sympy.parsing.sympy_parser import parse_expr
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent import utils
from volttron.platform.agent.math_utils import mean
from volttron.platform.messaging import topics
from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import SELLER
from volttron.platform.agent.base_market_agent.buy_sell import BUYER

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


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
    q_uc=[]   
    for i in range(24):
        market_name.append('_'.join([base_name, str(i)]))
        q_uc.append(float(config.get("power_"+str(i), 0)))

    verbose_logging = config.get('verbose_logging', True)
    building_topic = topics.DEVICES_VALUE(campus=config.get("campus", ""),
                                          building=config.get("building", ""),
                                          unit=None,
                                          path="",
                                          point="all")
    devices = config.get("devices")
    return UncontrolAgent(agent_name, market_name, verbose_logging, q_uc, building_topic, devices, **kwargs)

class UncontrolAgent(MarketAgent):


    def __init__(self, agent_name, market_name, verbose_logging, q_uc, building_topic, devices, **kwargs):
        super(UncontrolAgent, self).__init__(verbose_logging, **kwargs)
        self.market_name = market_name
        self.q_uc = q_uc		
        self.price_index=0
        self.price_min = 10.
        self.price_max = 100.
        self.infinity = 1000000
        self.num = 0
        self.market_num_indicate = 0		
        self.power_aggregation = []
        self.current_power = None
        self.demand_aggregation_master = {}
        self.demand_aggregation_working = {}
        self.agent_name = agent_name
        self.demand_curve = []
        for market in self.market_name:
            self.join_market(self.market, SELLER, self.reservation_callback, self.offer_callback,
                         None, self.price_callback, self.error_callback)
            self.demand_curve.append(PolyLine()

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
        if 1:
            for device, points in self.devices.items():
                device_topic = self.building_topic(unit=device)
                _log.debug('Subscribing to {}'.format(device_topic))
                self.demand_aggregation_master[device_topic] = points
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=device_topic,
                                          callback=self.aggregate_power)
            self.demand_aggregation_working = self.demand_aggregation_master.copy()
            _log.debug('Points are  {}'.format(self.demand_aggregation_working))

    def offer_callback(self, timestamp, market_name, buyer_seller):
        index = self.market_name.index(market_name)
        result, message = self.make_offer(market_name, buyer_seller, self.create_demand_curve(index))
        _log.debug("{}: demand max {} and min {} at {}".format(self.agent_name,
                                                               self.demand_curve[index].x(10),
                                                               self.demand_curve[index].x(100),
                                                               timestamp))
        _log.debug("{}: result of the make offer {} at {}".format(self.agent_name,
                                                                  result,
                                                                  timestamp))        
        
    def conversion_handler(self, conversion, point, data):
        expr = parse_expr(conversion)
        sym = symbols(point)
        point_list = [(point, data[point])]
        return float(expr.subs(point_list))

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
        _log.debug("{}: received topic for power aggregation: {}".format(self.agent_name,
                                                                         topic))
        data = message[0]
        try:
            current_points = self.demand_aggregation_working.pop(topic)
        except KeyError:
            if self.power_aggregation:
                self.current_power = sum(self.power_aggregation)
            else:
                self.current_power = 0.
            self.demand_aggregation_working = self.demand_aggregation_master.copy()
         
        conversion = current_points.get("conversion")
        for point in current_points.get("points", []):
            if conversion is not None:
                value = float(self.conversion_handler(conversion, point, data))
            else:
                value = float(data[point])
            self.power_aggregation.append(value)
        if not self.demand_aggregation_working:
            if self.power_aggregation:
                self.current_power = sum(self.power_aggregation)

            else:
                self.current_power = 0.
            self.power_aggregation = []
            self.demand_aggregation_working = self.demand_aggregation_master.copy()
            _log.debug("Power check: {}".format(self.demand_aggregation_working))
            self.num=self.num+1
            if self.num>=59:
                   self.q_uc[self.market_num_indicate]=-self.current_power
                   self.market_num_indicate=self.market_num_indicate+1
                   if self.market_num_indicate>23:
                               self.market_num_indicate=0
                   self.num=0							   

        _log.debug("{}: updating power aggregation: {}".format(self.agent_name,
                                                           self.current_power))  
    def create_demand_curve(self, index):
        self.demand_curve[index] = PolyLine()
        p_min = 10.
        p_max = 100.
        qMin = self.q_uc[index]
        qMax = self.q_uc[index]
        if self.hvac_avail:
            self.demand_curve[index].add(Point(price=max(p_min, p_max), quantity=min(qMin, qMax)))
            self.demand_curve[index].add(Point(price=min(p_min, p_max), quantity=max(qMin, qMax)))
        else:
            self.demand_curve[index].add(Point(price=max(p_min, p_max), quantity=0.1))
            self.demand_curve[index].add(Point(price=min(p_min, p_max), quantity=0.1))
#        if self.hvac_avail:
#            _log.debug("{} - Tout {} - Tin {} - q {}".format(self.agent_name, self.tOut, self.tIn, self.qHvacSens))
        return self.demand_curve[index]


    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        _log.debug("{}: cleared price ({}, {}) for {} as {} at {}".format(self.agent_name,
                                                                          price,
                                                                          quantity,
                                                                          market_name,
                                                                          buyer_seller,
                                                                          timestamp))

    def error_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux):
        _log.debug("{}: error for {} as {} at {} - Message: {}".format(self.agent_name,
                                                                       market_name,
                                                                       buyer_seller,
                                                                       timestamp,
                                                                       error_message))


def main():
    """Main method called to start the agent."""
    utils.vip_main(uncontrol_agent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass