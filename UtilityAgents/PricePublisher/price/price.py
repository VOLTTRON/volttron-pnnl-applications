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
from datetime import timedelta as td
import pandas as pd
import dateutil.tz
from dateutil import parser
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent import utils
from volttron.platform.agent.utils import format_timestamp

from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.buy_sell import SELLER


_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def price_publisher(config_path, **kwargs):
    """Parses the Electric Meter Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: Market Service Agent
    :rtype: MarketServiceAgent
    """
    _log.debug("Starting MeterAgent")
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}

    if not config:
        _log.info("Using defaults for starting configuration.")
    agent_name = config.get("agent_name", "price_publisher")
    market_name = config.get('market_name', 'electric')
    verbose_logging = config.get('verbose_logging', True)
    price_file = config.get('price_file', None)
    return PricePublisherAgent(agent_name, market_name, price_file, verbose_logging, **kwargs)


class PricePublisherAgent(MarketAgent):
    """
    The SampleElectricMeterAgent serves as a sample of an electric meter that
    sells electricity for a single building at a fixed price.
    """

    def __init__(self, agent_name, market_name, price_file, verbose_logging, **kwargs):
        super(PricePublisherAgent, self).__init__(verbose_logging, **kwargs)
        self.agent_name = agent_name
        self.price_file = price_file
        self.power_prices = None
        self.join_market(market_name, SELLER, self.reservation_callback, self.offer_callback,
                         None, self.price_callback, self.error_callback)

    @Core.receiver('onstart')
    def setup(self, sender, **kwargs):
        """
        Set up subscriptions for demand limiting case.
        :param sender:
        :param kwargs:
        :return:
        """
        if self.price_file is None:
            _log.debug("Electric supplier has no price information from file: {}".format(self.price_file))
            sys.exit()
        try:
            self.power_prices = pd.read_csv(self.price_file)
            self.power_prices = self.power_prices.set_index(self.power_prices.columns[0])
            self.power_prices.index = pd.to_datetime(self.power_prices.index, format="%m/%d/%Y %H:%M")

            self.power_prices['MA'] = self.power_prices.rolling(window=24).mean()
            self.power_prices['STD'] = self.power_prices["price"].rolling(window=24).std()
            self.power_prices['month'] = self.power_prices.index.month.astype(int)
            self.power_prices['day'] = self.power_prices.index.day.astype(int)
            self.power_prices['hour'] = self.power_prices.index.hour.astype(int)
        except:
            _log.debug("ERROR reading price file!")
            sys.exit()

    def reservation_callback(self, timestamp, market_name, buyer_seller):
        reservation = False
        _log.debug("Current_time: {}".format(timestamp))
        to_zone = dateutil.tz.gettz("US/Pacific")
        timestamp = timestamp.astimezone(to_zone)
        current_offset = timestamp.hour-1
        current_hour = timestamp.hour
        if current_offset == -1:
            current_offset = 23
        current_time = timestamp.replace(hour=current_offset, month=8, year=2017, tzinfo=None)
        _log.debug("Parsed_time: {}".format(current_time))
        end_time = current_time + td(hours=24)
        mask = (self.power_prices.index > current_time) & (self.power_prices.index <= end_time)
        prices = self.power_prices.loc[mask]
        prices = [price for price in prices['price']]
        self.vip.pubsub.publish(peer='pubsub',
                                topic='mixmarket/start_new_cycle',
                                message={"prices": prices,
                                         "hour": str(current_hour)})
        return reservation

    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        pass

    def error_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux):
        pass

    def offer_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux):
        pass


def main():
    """Main method called to start the agent."""
    utils.vip_main(price_publisher, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
