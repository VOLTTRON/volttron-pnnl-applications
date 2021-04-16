# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2018, Battelle Memorial Institute
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
from volttron.platform.agent import utils
from volttron.platform.messaging import topics
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
import numpy as np

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def light_agent(config_path, **kwargs):
    """Parses the lighting agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: Market Service Agent
    :rtype: MarketServiceAgent
    """
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}

    if not config:
        _log.info("Using defaults for starting configuration.")

    base_name = config.get("market_name", "electric")
    market_name = []
    for i in range(24):
        market_name.append('_'.join([base_name, str(i)]))
    agent_name = config.get('agent_name', "lighting")
    default_occ_lighting_level = config.get('default_dimming_level', 0.)
    min_occupied_lighting_level = config.get("min_occupied_lighting_level", 70.0)
    heartbeat_period = config.get('heartbeat_period', 3600)
    power_absnom = config.get('Pabsnom', 0.)
    non_responsive = config.get('non_responsive', False)

    schedule_topic = topics.DEVICES_VALUE(campus=config.get("campus", ""),
                                          building=config.get("building", ""),
                                          unit=config.get("schedule_device", ""),
                                          path=config.get("schedule_path", ""),
                                          point="all")

    schedule_point = config.get("schedule_point", "SupplyFanStatus")
    lighting_setpoint = config["lighting_level_stpt"]
    base_rpc_path = topics.RPC_DEVICE_PATH(campus=config.get("campus", ""),
                                           building=config.get("building", ""),
                                           unit=config.get("device", ""),
                                           path=config.get("path", ""),
                                           point=lighting_setpoint)

    actuator = config.get("actuator", "platform.actuator")
    verbose_logging = config.get('verbose_logging', True)
    return LightAgent(market_name, agent_name, min_occupied_lighting_level,
                      default_occ_lighting_level, power_absnom, non_responsive, verbose_logging,
                      base_rpc_path, schedule_topic, schedule_point, actuator, heartbeat_period, **kwargs)


def ease(target, current, limit):
    return current - np.sign(current - target) * min(abs(current - target), abs(limit))


def clamp(value, x1, x2):
    min_value = min(x1, x2)
    max_value = max(x1, x2)
    return min(max(value, min_value), max_value)


class LightAgent(MarketAgent):
    """
    Transactive control lighting agent.
    """

    def __init__(self, market_name, agent_name, min_occupied_lighting_level,
                 default_occ_lighting_level, power_absnom, non_responsive, verbose_logging,
                 base_rpc_path, schedule_topic, schedule_point, actuator, heartbeat_period, **kwargs):
        super(LightAgent, self).__init__(verbose_logging, **kwargs)
        self.market_name = market_name
        self.agent_name = agent_name
        self.qmin = min_occupied_lighting_level/100.0
        self.qmax = default_occ_lighting_level/100.0
        self.power_absnom = power_absnom
        self.non_responsive = non_responsive
        self.actuation_topic = base_rpc_path
        self.actuator = actuator
        self.schedule_topic = schedule_topic
        self.schedule_point = schedule_point
        self.demand_curve = None
        self.hvac_avail = 1
        self.price_cleared = None
        self.qnorm = float(self.qmax)
        self.lighting_stpt = None
        self.default_lighting_stpt = None
        self.heartbeat_period = heartbeat_period
        self.demand_curve = []
        for market in self.market_name:		
            self.join_market(market, BUYER, None, self.offer_callback,
                             None, self.price_callback, self.error_callback)
            self.demand_curve.append(PolyLine())

    @Core.receiver('onstart')
    def setup(self, sender, **kwargs):
        _log.debug("{}: schedule topic for HVAC - {}".format(self.agent_name,
                                                             self.schedule_topic))
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.schedule_topic,
                                  callback=self.update_state)
        try:
            self.lighting_stpt = self.vip.rpc.call(self.actuator,
                                                   'get_point',
                                                   self.agent_name,
                                                   self.actuator_topic).get(timeout=10)
        except:
            self.lighting_stpt = round(self.qnorm, 2)
        self.default_lighting_stpt = self.lighting_setpoint
        self.core.periodic(self.heartbeat_period, self.actuate_setpoint)

    def offer_callback(self, timestamp, market_name, buyer_seller):
        index = self.market_name.index(market_name)
        result, message = self.make_offer(market_name, buyer_seller, self.create_demand_curve(index))
        _log.debug("{}: result of the make offer {} at {}".format(self.agent_name,
                                                                  result,
                                                                  timestamp))
        if not result and market_name.lower() == self.market_name[0].lower():
            _log.debug("{}: maintain current lighting level: {}".format(self.agent_name, self.qnorm))
            self.lighting_stpt = round(self.default_lighting_stpt, 2)

    def create_demand_curve(self, index):
        """
        Create electric demand curve for agents respective lighting zone.
        :return:
        """
        self.demand_curve[index] = PolyLine()
        p_min = 10.
        p_max = 100.
        if self.hvac_avail:
            self.demand_curve[index].add(Point(price=min(p_min, p_max), quantity=max(self.qmin, self.qmax) * self.power_absnom))
            self.demand_curve[index].add(Point(price=max(p_min, p_max), quantity=min(self.qmin, self.qmax)* self.power_absnom))
        else:
            self.demand_curve[index].add(Point(price=max(p_min, p_max), quantity=0.))
            self.demand_curve[index].add(Point(price=min(p_min, p_max), quantity=0.))
        return self.demand_curve[index]

    def update_state(self, peer, sender, bus, topic, headers, message):
        """
        Update state from device data from message bus.
        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        :return:
        """
        _log.debug('{}: received one new data set'.format(self.agent_name))
        info = message[0]
        self.hvac_avail = info[self.schedule_point]
        if self.hvac_avail:
            self.qnorm = self.qmax
        else:
            self.qnorm = 0.0

    def update_set(self, market_name):
        """
        Determine new set point for the zone lighting level.
        :return:
        """
        if self.price_cleared is not None and not self.non_responsive and self.hvac_avail:
            self.lighting_stpt = clamp(self.demand_curve[0].x(self.price_cleared) / self.power_absnom, self.qmax, self.qmin)
        else:
            self.lighting_stpt = self.default_lighting_stpt

    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        """
        Price callback for agent when interacting with electric market.
        :param timestamp:
        :param market_name:
        :param buyer_seller:
        :param price:
        :param quantity:
        :return:
        """
        _log.debug("{}: price {} quantity{}, for {} as {} at {}".format(self.agent_name,
                                                                        price,
                                                                        quantity,
                                                                        market_name,
                                                                        buyer_seller,
                                                                        timestamp))
        self.price_cleared = price
        if self.price_cleared is not None:
            if market_name.lower() == self.market_name[0].lower():
                self.update_set(market_name)

    def error_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux):
        """
        Error callback for agent when interacting with electric market.
        :param timestamp:
        :param market_name:
        :param buyer_seller:
        :param error_code:
        :param error_message:
        :param aux:
        :return:
        """
        _log.debug("{}: error for {} at {} - Message: {}".format(self.agent_name,
                                                                 market_name,
                                                                 timestamp,
                                                                 error_message))
#        if market_name.lower() == self.market_name[0].lower():
#            if aux.get('Sn,Dn', 0) == -1 and aux.get('Sx,Dx', 0) == -1:
#            if aux.get('SQx,DQn', 0) == -1:
#                _log.debug("{}: use minimum lighting level: {}".format(self.agent_name, self.qmin))
#                self.vip.rpc.call(self.actuator, 'set_point', self.agent_name, self.actuation_topic, self.qmin).get(timeout=10)
#                return
#            else:
#                _log.debug("{}: maintain default lighting level at: {}".format(self.agent_name, self.qnorm))
#                self.vip.rpc.call(self.actuator, 'set_point', self.agent_name, self.actuation_topic, round(self.qnorm, 2)).get(timeout=10)
#        else:
#            _log.debug("{}: maintain default lighting level at: {}".format(self.agent_name, self.qnorm))
#            self.vip.rpc.call(self.actuator, 'set_point', self.agent_name, self.actuation_topic, round(self.qnorm, 2)).get(timeout=10)

    def actuate_setpoint(self):
        _log.debug("{}: new lighting level is {}".format(self.agent_name,
                                                         self.lighting_stpt))
        self.vip.rpc.call(self.actuator, 'set_point', self.agent_name,
                          self.actuation_topic, round(self.lighting_stpt, 2)).get(timeout=10)

def main():
    """Main method called to start the agent."""
    utils.vip_main(light_agent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass