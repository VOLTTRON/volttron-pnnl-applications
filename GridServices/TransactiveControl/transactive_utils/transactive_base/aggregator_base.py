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
        if self.market_type == "tns":
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

