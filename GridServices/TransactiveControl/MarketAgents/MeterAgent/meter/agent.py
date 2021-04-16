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
from transactive_utils.transactive_base.aggregator_base import Aggregator
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.2"


class MeterAgent(Aggregator):
    """
    The SampleElectricMeterAgent serves as a sample of an electric meter that
    sells electricity for a single building at a fixed price.
    """

    def __init__(self, config_path, **kwargs):
        try:
            config = utils.load_config(config_path)
        except StandardError:
            config = {}
        self.demand_limit = config.get("demand_limit")
        self.agent_name = config.get("agent_name", "meter")
        Aggregator.__init__(self, config, **kwargs)
        self.price = None

    def init_predictions(self, output_info):
        pass

    def update_state(self, market_time, market_index, price, prices):
        pass

    def translate_aggregate_demand(self, agg_demand, index, market_time, realtime):
        electric_supply_curve = PolyLine()
        if self.demand_limit is not None:
            electric_supply_curve.add(Point(price=0, quantity=self.demand_limit))
            electric_supply_curve.add(Point(price=1000, quantity=self.demand_limit))
        else:
            price = (agg_demand.min_y() + agg_demand.max_y()) / 2
            if self.price_manager is not None:
                cleared_price = self.price_manager.get_current_cleared_price(market_time)
                if cleared_price is not None:
                    price = cleared_price

            electric_supply_curve.add(Point(price=price, quantity=0))
            electric_supply_curve.add(Point(price=price, quantity=10000))
        _log.debug("{}: electric demand : {}".format(self.core.identity, electric_supply_curve.points))
        self.supplier_curves[market_time] = electric_supply_curve


def main():
    """Main method called to start the agent."""
    utils.vip_main(MeterAgent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
