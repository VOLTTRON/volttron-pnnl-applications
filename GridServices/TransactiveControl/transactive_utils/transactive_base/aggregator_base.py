import logging

from transactive_utils.transactive_base.transactive import TransactiveBase
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER
from volttron.platform.agent.utils import setup_logging

_log = logging.getLogger(__name__)
setup_logging()
__version__ = '0.3'


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
        self.supplier_curve = []
        self.supplier_market = []
        self.consumer_demand_curve = {}
        self.consumer_market = {}
        self.aggregate_demand = []
        self.supply_commodity = None
        self.markets_initialized = False
        if self.default_config is not None and self.default_config:
            self.default_config.update(default_config)
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure,
                                  actions=["NEW", "UPDATE"],
                                  pattern="config")

    def configure(self, config_name, action, contents, **kwargs):
        self.configure_main(config_name, action, contents)
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

            self.aggregate_clearing_market = config.get("aggregate_clearing_market")
            self.consumer_demand_curve = dict.fromkeys(consumer_market_base_name, [])
            self.consumer_market = dict.fromkeys(consumer_market_base_name, [])
            if self.market_number is not None and not self.markets_initialized:
                self.supplier_market = ['_'.join([supplier_market_base_name, str(i)]) for i in range(self.market_number)]
                self.aggregate_demand = [None] * self.market_number
                if consumer_market_base_name:
                    for market_name in self.consumer_market:
                        self.consumer_market[market_name] = ['_'.join([market_name, str(i)]) for i in range(self.market_number)]
                        self.consumer_demand_curve[market_name] = [None] * self.market_number
                self.init_markets()

    def init_markets(self):

        for market in self.supplier_market:
            self.markets_initialized = True
            _log.debug("Join market: %s  --  %s as %s", self.core.identity, market, SELLER)
            self.join_market(market, SELLER, None, None,
                             self.aggregate_callback, self.supplier_price_callback, self.error_callback)
            self.supplier_curve.append(None)
        for market_base, market_list in self.consumer_market.items():
            for market in market_list:
                self.markets_initialized = True
                _log.debug("Join market: %s  --  %s as %s", self.core.identity, market, BUYER)
                self.join_market(market, BUYER, None, None,
                                 None, self.consumer_price_callback, self.error_callback)

    def aggregate_callback(self, timestamp, market_name, buyer_seller, agg_demand):
        if buyer_seller == BUYER:
            market_index = self.supplier_market.index(market_name)
            _log.debug("%s - received aggregated %s curve - %s",
                       self.core.identity, market_name, agg_demand.points)
            self.aggregate_demand[market_index] = agg_demand
            self.translate_aggregate_demand(agg_demand, market_index)

            if self.consumer_market:
                for market_base, market_list in self.consumer_market.items():
                    success, message = \
                        self.make_offer(market_list[market_index], BUYER, self.consumer_demand_curve[market_base][market_index])

                    # Database code for data analysis
                    topic_suffix = "/".join([self.core.identity, "DemandCurve"])
                    message = {
                        "MarketIndex": market_index,
                        "Curve": self.consumer_demand_curve[market_base][market_index].tuppleize(),
                        "Commodity": market_base
                    }
                    _log.debug("%s debug demand_curve - curve: %s",
                               self.core.identity, self.consumer_demand_curve[market_base][market_index].points)
                    self.publish_record(topic_suffix, message)
            elif self.supplier_market:
                success, message = \
                    self.make_offer(self.supplier_market[market_index], SELLER, self.supplier_curve[market_index])
            else:
                _log.warning("%s - No markets to submit supply curve!", self.core.identity)
                success = False

            if success:
                _log.debug("%s: make a offer for %s",
                           self.core.identity, market_name)
            else:
                _log.debug("%s: offer for the %s was rejected",
                           self.core.identity, market_name)

    def consumer_price_callback(self, timestamp, consumer_market, buyer_seller, price, quantity):
        self.report_cleared_price(buyer_seller, consumer_market, price, quantity, timestamp)
        for market_base, market_list in self.consumer_market.items():
            if consumer_market in market_list:
                market_index = market_list.index(consumer_market)
                if market_base == self.aggregate_clearing_market:
                    supply_market = self.supplier_market[market_index]
                    if price is not None:
                        self.make_supply_offer(price, supply_market)
                    if self.consumer_demand_curve[market_base][market_index] is not None and self.consumer_demand_curve[market_base][market_index]:
                        cleared_quantity = self.consumer_demand_curve[market_base][market_index].x(price)
                        _log.debug("%s price callback market: %s, price: %s, quantity: %s", self.core.identity, consumer_market, price, quantity)
                        topic_suffix = "/".join([self.core.identity, "MarketClear"])
                        message = {
                            "MarketIndex": market_index,
                            "Price": price,
                            "Quantity": [quantity, cleared_quantity],
                            "Commodity": market_base
                        }
                        self.publish_record(topic_suffix, message)

    def create_supply_curve(self, clear_price, supply_market):
        index = self.supplier_market.index(supply_market)
        supply_curve = PolyLine()
        try:
            if self.aggregate_demand:
                min_quantity = self.aggregate_demand[index].min_x()*0.8
                max_quantity = self.aggregate_demand[index].max_x()*1.2
            else:
                min_quantity = 0.0
                max_quantity = 10000.0
        except:
            min_quantity = 0.0
            max_quantity = 10000.0
        supply_curve.add(Point(price=clear_price, quantity=min_quantity))
        supply_curve.add(Point(price=clear_price, quantity=max_quantity))
        return supply_curve

    def supplier_price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        self.report_cleared_price(buyer_seller, market_name, price, quantity, timestamp)

    def make_supply_offer(self, price, supply_market):
        supply_curve = self.create_supply_curve(price, supply_market)
        success, message = self.make_offer(supply_market, SELLER, supply_curve)
        if success:
            _log.debug("{}: make offer for Market: {} {} Curve: {}".format(self.core.identity,
                                                                           supply_market,
                                                                           SELLER,
                                                                           supply_curve.points))
        market_index = self.supplier_market.index(supply_market)
        topic_suffix = "/".join([self.core.identity, "SupplyCurve"])
        message = {"MarketIndex": market_index, "Curve": supply_curve.tuppleize(), "Commodity": self.supply_commodity}
        _log.debug("{} debug demand_curve - curve: {}".format(self.core.identity, supply_curve.points))
        self.publish_record(topic_suffix, message)

    def report_cleared_price(self, buyer_seller, market_name, price, quantity, timestamp):
        _log.debug("{}: ts - {}, Market - {} as {}, Price - {} Quantity - {}".format(self.core.identity,
                                                                                     timestamp,
                                                                                     market_name,
                                                                                     buyer_seller,
                                                                                     price,
                                                                                     quantity))

    def offer_callback(self, timestamp, market_name, buyer_seller):
        pass