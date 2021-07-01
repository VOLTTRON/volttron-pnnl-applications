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

import logging

from transactive_utils.transactive_base.transactive import TransactiveBase
from transactive_utils.transactive_base.markets import AggregatorMarket
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER
from volttron.platform.agent.utils import setup_logging

_log = logging.getLogger(__name__)
setup_logging()
__version__ = '0.4'


class Aggregator(TransactiveBase):
    def __init__(self, config, **kwargs):
        super(Aggregator, self).__init__(config, aggregator=self, **kwargs)
        default_config = {
            "supplier_market_name": "",
            "consumer_market_name": [],
            "aggregate_clearing_market": "electric"
        }
        if config:
            default_config.update(config)
        self.aggregate_clearing_market = "electric"
        self.consumer_commodity = self.commodity
        self.supplier_curves = {}
        self.supplier_markets = []
        self.consumer_demand_curves = {}
        self.consumer_markets = {}
        self.aggregate_demand = {}
        self.supply_commodity = None
        self.markets_initialized = False
        self.day_ahead_supply_market = None
        self.rtp_supplier_markets = []
        self.rtp_consumer_markets = {}
        self.day_ahead_consumer_market = {}
        self.market_map = {}

        if self.default_config is not None and self.default_config:
            self.default_config.update(default_config)
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure,
                                  actions=["NEW", "UPDATE"],
                                  pattern="config")

    def configure(self, config_name, action, contents, **kwargs):
        config = self.default_config.copy()
        config.update(contents)
        self.configure_main(config_name, action, contents)
        _log.debug("Update agent %s configuration.", self.core.identity)
        if action == "NEW" or "UPDATE":
            supplier_market_base_name = config.get("supplier_market_name", "")
            self.supply_commodity = supplier_market_base_name
            consumer_market_base_name = config.get("consumer_market_name", [])

            if isinstance(consumer_market_base_name, str):
                consumer_market_base_name = [consumer_market_base_name]
            self.consumer_commodity = consumer_market_base_name
            self.aggregate_clearing_market = config.get("aggregate_clearing_market")
            self.consumer_demand_curves = dict.fromkeys(consumer_market_base_name, {})
            self.consumer_markets = dict.fromkeys(consumer_market_base_name, [])
            self.rtp_consumer_markets = dict.fromkeys(consumer_market_base_name, [])
            if not self.markets_initialized:
                self.supplier_markets = ['_'.join([supplier_market_base_name, str(i)]) for i in range(24)]
                self.rtp_supplier_markets = ["_".join(["refinement", supplier_market_base_name])]
                self.aggregate_demand = {}
                if consumer_market_base_name:
                    for market_name in self.consumer_markets:
                        self.consumer_markets[market_name] = ['_'.join([market_name, str(i)]) for i in range(24)]
                        self.rtp_consumer_markets[market_name] = ["_".join(["refinement", market_name])]
                self.init_markets()
                self.setup()

    def init_markets(self):
        if self.market_type == "tent":
            self.markets_initialized = True
            self.day_ahead_market = AggregatorMarket(self.supplier_markets, self.consumer_markets, False,
                                                     self.outputs, [], self, self.price_manager)
            self.rtp_market = AggregatorMarket(self.rtp_supplier_markets, self.rtp_consumer_markets, True,
                                               self.outputs, [], self, self.price_manager)
            self.market_manager_list = [self.day_ahead_market, self.rtp_market]
        else:
            self.rtp_market = AggregatorMarket(self.rtp_supplier_markets, self.rtp_consumer_markets, True,
                                               self.outputs, [], self, self.price_manager)
            self.market_manager_list = [self.rtp_market]

