# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

import os
import sys
import logging
import datetime
from dateutil import parser

from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from volttron.platform.agent.base_market_agent.buy_sell import SELLER

from timer import Timer

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


class CampusAgent(MarketAgent):
    def __init__(self, config_path, **kwargs):
        MarketAgent.__init__(self, **kwargs)

        self.config_path = config_path
        self.config = utils.load_config(config_path)
        self.name = self.config.get('name')
        self.T = int(self.config.get('T', 24))

        self.db_topic = self.config.get("db_topic", "tnc")
        self.city_supply_topic = "{}/city/campus/supply".format(self.db_topic)
        self.campus_demand_topic = "{}/campus/city/demand".format(self.db_topic)
        self.campus_supply_topic = "/".join([self.db_topic, "campus/{}/supply"])

        # Create market names to join
        self.quantities = [None] * self.T
        self.reserves = [None] * self.T
        self.base_market_name = 'electric'  # Need to agree on this with other market agents
        self.market_names = []
        for i in range(self.T):
            self.market_names.append('_'.join([self.base_market_name, str(i)]))

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        # Subscriptions
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.city_supply_topic,
                                  callback=self.new_supply_signal)

        # Join electric mix-markets
        for market in self.market_names:
            self.join_market(market, SELLER, self.reservation_callback, self.offer_callback,
                             self.aggregate_callback, self.price_callback, self.error_callback)

    def new_supply_signal(self, peer, sender, bus, topic, headers, message):
        price = message['price']
        price_reserved = message['price_reserved']
        converged = message['converged']
        start_of_cycle = message['start_of_cycle']

        _log.info("Campus {} receive from city: {}, {}".format(self.name,
                                                               price, price_reserved))

        # TODO: mock start mixmarket.
        # TODO: Comment send_to_city and uncomment start_mixmarket for real testing
        self.send_to_city(map(lambda x: x*2, price),
                          map(lambda x: x+5, price_reserved))
        # self.start_mixmarket(converged, price, price_reserved, start_of_cycle)

    def start_mixmarket(self, converged, price, price_reserved, start_of_cycle):
        _log.info("Starting mixmarket...")
        self.vip.pubsub.publish(peer='pubsub',
                                topic='mixmarket/start_new_cycle',
                                message={
                                    "converged": converged,
                                    "prices": price,
                                    "reserved_prices": price_reserved,
                                    "start_of_cycle": start_of_cycle
                                })

    def offer_callback(self, timestamp, market_name, buyer_seller):
        if market_name in self.market_names:
            # Get the price for the corresponding market
            idx = int(market_name.split('_')[-1])
            price = self.prices[idx]
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

    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        if buyer_seller == BUYER and market_name in self.market_names:
            _log.debug("{}: cleared price ({}, {}) for {} as {} at {}".format(Timer.get_cur_time(),
                                                                              price,
                                                                              quantity,
                                                                              market_name,
                                                                              buyer_seller,
                                                                              timestamp))
        idx = int(market_name.split('_')[-1])
        self.prices[idx] = price
        if price is None:
            raise "Market {} did not clear. Price is none.".format(market_name)
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

        _log.debug("At {}, q is {} and qs are: {}".format(Timer.get_cur_time(),
                                                          quantity,
                                                          self.quantities))
        if quantity is not None and quantity < 0:
            _log.error("Quantity received from mixmarket is negative!!! {}".format(quantity))

        # If all markets (ie. exclude 1st value) are done then update demands.
        # Otherwise do nothing
        mix_market_done = all([False if q is None else True for q in self.quantities])
        if mix_market_done:
            self.mix_market_running = False
            self.send_to_city(self.quantities, self.reserves)

    def send_to_city(self, power_demand, committed_reserves):
        self.vip.pubsub.publish(peer='pubsub',
                                topic=self.campus_demand_topic,
                                message={
                                    'power_demand': power_demand,
                                    'committed_reserves': committed_reserves
                                })

    def error_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux):
        _log.debug("{}: error for {} as {} at {} - Message: {}".format(self.agent_name,
                                                                       market_name,
                                                                       buyer_seller,
                                                                       timestamp,
                                                                       error_message))


def main(argv=sys.argv):
    try:
        utils.vip_main(CampusAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
