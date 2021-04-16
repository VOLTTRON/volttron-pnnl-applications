import logging
import gevent
from dateutil.parser import parse
from transactive_utils.transactive_base.utils import calculate_epoch, lists_to_dict
from volttron.platform.agent.utils import setup_logging
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER

_log = logging.getLogger(__name__)
setup_logging()


class Market(object):
    def __init__(self, outputs, market_list, parent, price_manager):
        self.outputs = outputs
        self.market_list = market_list
        self.market_intervals = {}
        self.demand_curve = {}
        self.join_market = parent.join_market
        self.make_offer = parent.make_offer
        self.get_q = parent.get_q
        self.publish_record = parent.publish_record
        self.schedule = parent.schedule
        self.identity = parent.core.identity
        self.update_state = parent.update_state
        self.update_flag = parent.update_flag
        self.parent = parent
        self.ct_flexibility = []
        self.off_setpoint = None
        self.price_manager = price_manager

    def update_market_intervals(self, intervals):
        for market, interval in zip(self.market_list, intervals):
            self.market_intervals[market] = interval

    def get_market_time(self, market_name):
        if self.market_intervals and market_name in self.market_intervals:
            return self.market_intervals[market_name]
        else:
            _log.debug("Cannot retrieve market time %s", self.identity)

    def init_markets(self):
        """
        Join markets.  For TNS will join 24 market or 1 market
        for real-time price scenario.
        :return: None
        """
        for market in self.market_list:
            _log.debug("Join market: %s  --  %s", self.identity, market)
            self.join_market(market, BUYER, self.reservation_callback, self.offer_callback,
                             None, self.price_callback, self.error_callback)
            self.demand_curve[market] = PolyLine()

    def check_schedule(self, dt):
        dt = parse(dt)
        current_schedule = self.schedule[dt.weekday()]
        if "always_on" in current_schedule:
            return True
        if "always_off" in current_schedule:
            return False
        _start = current_schedule["start"]
        _end = current_schedule["end"]
        if _start <= dt.time() < _end:
            return True
        else:
            return False

    def reservation_callback(self, timestamp, market_name, buyer_seller):
        pass

    def offer_callback(self, timestamp, market_name, buyer_seller):
        pass

    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        pass

    def create_demand_curve(self, market_name, market_time, occupied, realtime):
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
                   self.identity,  market_name, market_time)
        demand_curve = PolyLine()
        prices = self.price_manager.get_price_array(market_time)
        i = 0
        for control, price in zip(self.ct_flexibility, prices):
            if occupied:
                _set = control
            else:
                _set = self.off_setpoint
            q = self.get_q(_set, market_time, occupied, realtime=realtime)
            # q = 100*(i+1)
            # i +=1
            demand_curve.add(Point(price=price, quantity=q))

        topic_suffix = "DemandCurve"
        message = {
            "MarketTime": str(market_time),
            "MarketName": market_name,
            "Curve": demand_curve.tuppleize(),
            "Commodity": self.parent.commodity
        }
        _log.debug("%s debug demand_curve - curve: %s",
                   self.identity, demand_curve.points)
        self.publish_record(topic_suffix, message)
        return demand_curve

    def error_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux):
        """
        Callback if there is a error for a market.
        :param timestamp:
        :param market_name: str; market error occured for.
        :param buyer_seller: str; is participant a buyer or seller
        :param error_code: str; error code
        :param error_message: str; error message
        :param aux: dict; auxillary infor for non-intersection of curves
        :return:
        """

        _log.error("%s - error for Market: %s", self.identity, market_name)
        _log.error("buyer_seller : %s - error: %s - aux: %s", buyer_seller, error_message, aux)


class RealTimeMarket(Market):
    def __init__(self, outputs, market_list, parent, price_manager):
        super().__init__(outputs, market_list, parent, price_manager)

    def reservation_callback(self, timestamp, market_name, buyer_seller):
        """
        Request reservation for volttron market.  For day-ahead request reservation for all 24
        hourly markets in a day.  For correction market request only for next hour.
        :param timestamp:
        :param market_name:
        :param buyer_seller:
        :return:
        """
        if self.price_manager.correction_market:
            return True
        else:
            return False

    def offer_callback(self, timestamp, market_name, buyer_seller):
        output_info, mapped = self.parent.get_current_output()
        self.ct_flexibility = output_info["ct_flex"]
        self.off_setpoint = output_info["off_setpoint"]
        self.parent.flexibility = output_info["flex"]
        market_time = self.market_intervals[market_name]
        occupied = True

        if self.schedule:
            occupied = self.check_schedule(market_time)

        demand_curve = self.create_demand_curve(market_name, market_time, occupied, realtime=True)
        self.demand_curve[market_time] = demand_curve
        result, message = self.make_offer(market_name, buyer_seller, demand_curve)

    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        market_time = self.market_intervals[market_name]
        market_epoch = calculate_epoch(market_time)
        price = self.price_manager.cleared_prices[market_epoch]
        cleared_quantity = "None"
        if self.demand_curve[market_time].points:
            cleared_quantity = self.demand_curve[market_time].x(price)

        _log.debug("%s RT price_callback - - price callback market: %s, price: %s, quantity: %s",
                   self.identity, market_name, price, quantity)
        topic_suffix = "MarketClear"
        message = {
            "MarketIndex": market_name,
            "Price": price,
            "Quantity": [quantity, cleared_quantity],
            "Commodity": self.parent.commodity
        }
        self.publish_record(topic_suffix, message)
        # If a price is known update the state of agent (in concrete
        # implementation of transactive agent).
        if price is not None:
            prices = self.price_manager.get_price_array(market_time)
            if self.parent.actuation_method == "market_clear":
                if self.parent.actuation_enabled and not self.parent.actuation_disabled:
                    self.parent.do_actuation(price)


class DayAheadMarket(Market):
    def __init__(self, outputs, market_list, parent, price_manager):
        super().__init__(outputs, market_list, parent, price_manager)
        self.update_flag = parent.update_flag = [False] * len(market_list)

    def reservation_callback(self, timestamp, market_name, buyer_seller):
        """
        Request reservation for volttron market.  For day-ahead request reservation for all 24
        hourly markets in a day.  For correction market request only for next hour.
        :param timestamp:
        :param market_name:
        :param buyer_seller:
        :return:
        """
        if self.price_manager.run_dayahead_market:
            return True
        else:
            return False

    def offer_callback(self, timestamp, market_name, buyer_seller):
        self.price_manager.run_dayahead_market = False
        output_info, mapped = self.parent.get_current_output()
        self.ct_flexibility = output_info["ct_flex"]
        self.off_setpoint = output_info["off_setpoint"]
        self.parent.flexibility = output_info["flex"]
        market_index = self.market_list.index(market_name)
        if market_index > 0:
            while not self.update_flag[market_index - 1]:
                gevent.sleep(1)
        if market_index == 0 and self.parent.current_datetime is not None:
            self.parent.init_predictions(output_info)

        market_time = self.market_intervals[market_name]
        occupied = True
        if self.schedule:
            occupied = self.check_schedule(market_time)

        demand_curve = self.create_demand_curve(market_name, market_time, occupied, realtime=False)
        self.demand_curve[market_name] = demand_curve
        result, message = self.make_offer(market_name, buyer_seller, demand_curve)

    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        market_time = self.market_intervals[market_name]
        market_index = self.market_list.index(market_name)
        market_epoch = calculate_epoch(parse(market_time))
        price = self.price_manager.cleared_prices[market_epoch]
        cleared_quantity = "None"
        if self.demand_curve[market_name].points:
            cleared_quantity = self.demand_curve[market_name].x(price)

        _log.debug("%s DA price_callback market: %s, price: %s, quantity: %s",
                   self.identity, market_name, price, quantity)
        topic_suffix = "MarketClear"
        message = {
            "MarketIndex": market_name,
            "Price": price,
            "Quantity": [quantity, cleared_quantity],
            "Commodity": self.parent.commodity
        }
        self.publish_record(topic_suffix, message)
        # If a price is known update the state of agent (in concrete
        # implementation of transactive agent).
        if price is not None:
            prices = self.price_manager.get_price_array(market_time)
            occupied = True
            if self.schedule:
                occupied = self.check_schedule(market_time)
            _log.debug("price callback - market_name: %s -- index: %s - occupied: %s - price: %s -- prices: %s",
                       market_name, market_index, occupied, price, prices)
            self.update_state(market_time, market_index, occupied, price, prices)
        if market_index == len(self.market_list) - 1:
            for i in range(len(self.update_flag)):
                self.update_flag[i] = False


class AggregatorMarket(Market):
    def __init__(self, supplier_markets, consumer_markets, rtp, outputs, market_list, parent, price_manager):
        super().__init__(outputs, market_list, parent, price_manager)
        self.supplier_markets = supplier_markets
        self.consumer_markets = consumer_markets
        self.supplier_market_map = dict.fromkeys(supplier_markets, [])
        self.supplier_curves = parent.supplier_curves
        self.markets_initialized = parent.markets_initialized
        self.supply_commodity = parent.supply_commodity
        self.rtp_market_flag = rtp
        self.aggregate_clearing_market = parent.aggregate_clearing_market
        self.aggregate_demand = parent.aggregate_demand
        self.translate_aggregate_demand = parent.translate_aggregate_demand
        self.consumer_demand_curves = parent.consumer_demand_curves
        idx = 0
        consumer_list = []
        for supplier_market in list(self.supplier_market_map.keys()):
            for market_base, market_list in self.consumer_markets.items():
                consumer_list.append(market_list[idx])
            self.supplier_market_map[supplier_market] = consumer_list
            consumer_list = []
            idx += 1

    def get_supply_market_name(self, market):
        no_market = None
        for supply_market, consumer_markets in self.supplier_market_map.items():
            if market in consumer_markets:
                return supply_market
        return no_market

    def update_market_intervals(self, intervals):
        for market, interval in zip(self.supplier_markets, intervals):
            _log.debug("Aggregator market_intervals - %s -- %s", market, interval)
            self.market_intervals[market] = interval
        for market_base, market_list in self.consumer_markets.items():
            for market, interval in zip(market_list, intervals):
                _log.debug("Aggregator market_intervals - %s -- %s", market, interval)
                self.market_intervals[market] = interval

    def init_markets(self):
        for market in self.supplier_markets:
            self.markets_initialized = True
            _log.debug("Join market: %s  --  %s as %s", self.identity, market, SELLER)
            self.join_market(market, SELLER, self.reservation_callback, None,
                             self.aggregate_callback, self.supplier_price_callback, self.error_callback)
        for market_base, market_list in self.consumer_markets.items():
            for market in market_list:
                self.markets_initialized = True
                _log.debug("Join market: %s  --  %s as %s", self.identity, market, BUYER)
                self.join_market(market, BUYER, self.reservation_callback, None,
                                 None, self.consumer_price_callback, self.error_callback)

    def reservation_callback(self, timestamp, market_name, buyer_seller):
        """
        Request reservation for volttron market.  For day-ahead request reservation for all 24
        hourly markets in a day.  For correction market request only for next hour.
        :param timestamp:
        :param market_name:
        :param buyer_seller:
        :return:
        """
        _log.debug("RESERVATION: %s -- rtp - %s -- correction -- %s -- dayahead -- %s", market_name, self.rtp_market_flag, self.price_manager.correction_market, self.price_manager.run_dayahead_market)
        if self.rtp_market_flag:
            if self.price_manager.correction_market:
                return True
            else:
                return False
        else:
            if self.price_manager.run_dayahead_market:
                return True
            else:
                return False

    def aggregate_callback(self, timestamp, market_name, buyer_seller, agg_demand):
        if buyer_seller == BUYER:
            market_time = self.get_market_time(market_name)
            consumer_markets = self.supplier_market_map.get(market_name, [])
            market_index = self.supplier_markets.index(market_name)
            _log.debug("%s - received aggregated %s curve - %s", self.identity, market_name, agg_demand.points)
            self.aggregate_demand[market_time] = agg_demand
            self.translate_aggregate_demand(agg_demand, market_name, market_time, self.rtp_market_flag)
            if consumer_markets:
                _log.debug("AGGREGATE: %s -- %s", self.consumer_markets.keys(), consumer_markets)
                for market_base, market_name in zip(list(self.consumer_markets.keys()), consumer_markets):
                    success, message = \
                        self.make_offer(market_name, BUYER, self.consumer_demand_curves[market_base][market_time])

                    # Database code for data analysis
                    topic_suffix = "/".join([self.identity, "DemandCurve"])
                    message = {
                        "MarketIndex": market_index,
                        "Curve": self.consumer_demand_curves[market_base][market_time].tuppleize(),
                        "Commodity": market_base
                    }
                    _log.debug("%s debug demand_curve - curve: %s",
                               self.identity, self.consumer_demand_curves[market_base][market_time].points)
                    self.publish_record(topic_suffix, message)
            elif self.supplier_markets:
                success, message = self.make_offer(market_name, SELLER, self.supplier_curves[market_time])
            else:
                _log.warning("%s - No markets to submit supply curve!", self.identity)
                success = False

            if success:
                _log.debug("%s: make a offer for %s",
                           self.identity, market_name)
            else:
                _log.debug("%s: offer for the %s was rejected",
                           self.identity, market_name)

    def consumer_price_callback(self, timestamp, consumer_market, buyer_seller, price, quantity):
        self.report_cleared_price(buyer_seller, consumer_market, price, quantity, timestamp)
        supply_market_name = self.get_supply_market_name(consumer_market)
        for market_base, market_list in self.consumer_markets.items():
            if consumer_market in market_list:
                supply_market_name = self.get_supply_market_name(consumer_market)
                market_time = self.get_market_time(supply_market_name)
                if market_base == self.aggregate_clearing_market:
                    if price is not None:
                        self.make_supply_offer(price, supply_market_name)
                    if self.consumer_demand_curves[market_base][market_time] is not None and self.consumer_demand_curves[market_base][market_time]:
                        cleared_quantity = self.consumer_demand_curves[market_base][market_time].x(price)
                        _log.debug("%s price callback market: %s, price: %s, quantity: %s", self.identity, consumer_market, price, quantity)
                        topic_suffix = "/".join([self.identity, "MarketClear"])
                        message = {
                            "MarketInterval": market_time,
                            "Price": price,
                            "Quantity": [quantity, cleared_quantity],
                            "Commodity": market_base
                        }
                        self.publish_record(topic_suffix, message)

    def create_supply_curve(self, clear_price, market_time):
        supply_curve = PolyLine()
        try:
            if self.aggregate_demand:
                min_quantity = self.aggregate_demand[market_time].min_x()*0.8
                max_quantity = self.aggregate_demand[market_time].max_x()*1.2
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
            _log.debug("{}: make offer for Market: {} {} Curve: {}".format(self.identity,
                                                                           supply_market,
                                                                           SELLER,
                                                                           supply_curve.points))
        market_index = self.supplier_markets.index(supply_market)
        topic_suffix = "/".join([self.identity, "SupplyCurve"])
        message = {"MarketIndex": market_index, "Curve": supply_curve.tuppleize(), "Commodity": self.supply_commodity}
        _log.debug("{} debug demand_curve - curve: {}".format(self.identity, supply_curve.points))
        self.publish_record(topic_suffix, message)

    def report_cleared_price(self, buyer_seller, market_name, price, quantity, timestamp):
        _log.debug("{}: ts - {}, Market - {} as {}, Price - {} Quantity - {}".format(self.identity,
                                                                                     timestamp,
                                                                                     market_name,
                                                                                     buyer_seller,
                                                                                     price,
                                                                                     quantity))

    def offer_callback(self, timestamp, market_name, buyer_seller):
        pass
