import logging
import sys
from datetime import timedelta as td
import numpy as np

from dateutil.parser import parse
import dateutil.tz
import gevent

from volttron.platform.agent.math_utils import mean, stdev
from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from volttron.platform.agent.utils import setup_logging, format_timestamp, get_aware_utc_now
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.vip.agent import errors

from transactive_utils.models import Model

_log = logging.getLogger(__name__)
setup_logging()
__version__ = '0.3'


class TransactiveBase(MarketAgent, Model):
    def __init__(self, config, aggregator=None, **kwargs):
        MarketAgent.__init__(self, **kwargs)
        default_config = {
            "campus": "",
            "building": "",
            "device": "",
            "agent_name": "",
            "actuation_method": "periodic",
            "control_interval": 900,
            "market_name": "electric",
            "input_data_timezone": "UTC",
            "actuation_enable_topic": "tnc/actuate",
            "actuation_enabled_onstart": False,
            "price_multiplier": 1.0,
            "inputs": [],
            "outputs": [],
            "schedule": {},
            "model_parameters": {},
        }
        # Initaialize run parameters
        self.aggregator = aggregator

        self.actuation_enabled = False
        self.actuation_disabled = False
        self.current_datetime = None
        self.current_schedule = None
        self.current_hour = None
        self.current_price = None
        self.actuation_obj = None
        self.flexibility = None
        self.ct_flexibility = None
        self.off_setpoint = None
        self.demand_limiting = False
        self.occupied = False
        self.mapped = None
        self.market_prices = {}
        self.day_ahead_prices = []
        self.last_24_hour_prices = []
        self.input_topics = set()

        self.commodity = "electricity"
        self.update_flag = []
        self.demand_curve = []
        self.actuation_price_range = None
        self.prices = []
        self.default_min_price = 0.01
        self.default_max_price = 0.1
        self.market_list = []
        self.market_type = None

        # Variables declared in configure_main
        self.record_topic = None
        self.market_number = None
        self.single_market_contol_interval = None
        self.hour_prediction_offset = 1
        self.inputs = {}
        self.outputs = {}
        self.schedule = {}
        self.actuation_method = None
        self.actuate_onstart = None
        self.input_data_tz = None
        self.actuation_rate = None
        self.actuate_topic = None
        self.price_multiplier = None
        self.static_price_flag = False
        self.prediction_error = 1.0
        self.default_min_price = 0.01
        self.default_max_price = 0.1
        self.oat_predictions = []
        if config:
            default_config.update(config)
            self.default_config = default_config
        else:
            self.default_config = default_config
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure_main,
                                  actions=["NEW", "UPDATE"],
                                  pattern="config")

    def configure_main(self, config_name, action, contents, **kwargs):
        config = self.default_config.copy()
        config.update(contents)
        _log.debug("Update agent %s configuration -- config --  %s", self.core.identity, config)
        if action == "NEW" or "UPDATE":
            campus = config.get("campus", "")
            building = config.get("building", "")
            device = config.get("device", "")
            subdevice = config.get("subdevice", "")
            self.demand_limiting = config.get("demand_limiting", False)

            base_record_list = ["tnc", campus, building, device, subdevice]
            base_record_list = list(filter(lambda a: a != "", base_record_list))
            self.record_topic = '/'.join(base_record_list)
            self.actuate_onstart = config.get("actuation_enabled_onstart", True)
            self.actuation_disabled = True if not self.actuate_onstart else False
            self.actuation_method = config.get("actuation_method")
            self.actuation_rate = config.get("control_interval")
            actuate_topic = config.get("actuation_enable_topic", "default")
            if actuate_topic == "default":
                base_record_list.append('actuate')
                self.actuate_topic = '/'.join(base_record_list)
            else:
                self.actuate_topic = actuate_topic
            self.price_multiplier = config.get("price_multiplier", 1.0)
            input_data_tz = config.get("input_data_timezone")
            self.input_data_tz = dateutil.tz.gettz(input_data_tz)
            inputs = config.get("inputs", [])
            schedule = config.get("schedule")
            self.clear_input_subscriptions()
            self.input_topics = set()
            self.init_inputs(inputs)
            self.init_schedule(schedule)
            outputs = config.get("outputs")
            self.init_outputs(outputs)
            self.init_actuation_state(self.actuate_topic, self.actuate_onstart)
            self.init_input_subscriptions()
            self.static_price_flag = config.get('static_price_flag', False)
            self.default_min_price = config.get('static_minimum_price', 0.01)
            self.default_max_price = config.get('static_maximum_price', 0.1)
            market_name = config.get("market_name", "electric")
            self.market_type = config.get("market_type", "tns")
            tns = False if self.market_type != "tns" else True
            #  VOLTTRON MarketService does not allow "leaving"
            #  markets.  Market participants can choose not to participate
            #  in the market process by sending False during the reservation
            #  phase.  This means that once the markets in market_name are
            #  joined the deployment can only be changed from an TNS market
            #  to single time step market by rebuilding both the agent
            #  and the VOLTTRON MarketService.
            _log.debug("CREATE MODEL")
            model_config = config.get("model_parameters", {})
            Model.__init__(self, model_config, **kwargs)
            if not self.market_list and tns is not None and self.model is not None:
                if tns:
                    self.market_number = 24
                    self.single_market_contol_interval = None
                else:
                    self.hour_prediction_offset = 0
                    self.market_number = 1
                    self.single_market_contol_interval = config.get("single_market_control_interval", 15)
                for i in range(self.market_number):
                    self.market_list.append('_'.join([market_name, str(i)]))
                if self.aggregator is None:
                    _log.debug("%s is a transactive agent.", self.core.identity)
                    self.init_markets()
            self.setup()

    def setup(self, **kwargs):
        """
        On start.
        :param sender:
        :param kwargs:
        :return:
        """
        if self.market_type == "rtp":
            self.update_prices = self.update_rtp_prices
        else:
            self.update_prices = self.update_tns_prices
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='mixmarket/start_new_cycle',
                                  callback=self.update_prices)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix="/".join([self.record_topic,
                                                   "update_model"]),
                                  callback=self.update_model)

    @Core.receiver("onstop")
    def shutdown(self, sender, **kwargs):
        _log.debug("Shutting down %s", self.core.identity)
        if self.outputs and self.actuation_enabled:
            for output_info in list(self.outputs.values()):
                topic = output_info["topic"]
                release = output_info["release"]
                actuator = output_info["actuator"]
                if self.actuation_obj is not None:
                    self.actuation_obj.kill()
                    self.actuation_obj = None
                self.actuate(topic, release, actuator)

    def init_markets(self):
        """
        Join markets.  For TNS will join 24 market or 1 market
        for real-time price scenario.
        :return: None
        """
        for market in self.market_list:
            _log.debug("Join market: %s  --  %s", self.core.identity, market)
            self.join_market(market, BUYER, None, self.offer_callback,
                             None, self.price_callback, self.error_callback)
            self.update_flag.append(False)
            self.demand_curve.append(PolyLine())

    def init_inputs(self, inputs):
        for input_info in inputs:
            try:
                point = input_info["point"]
                mapped = input_info["mapped"]
                topic = input_info["topic"]
            except KeyError as ex:
                _log.error("Exception on init_inputs %s", ex)
                sys.exit()

            value = input_info.get("initial_value")
            self.inputs[mapped] = {point: value}
            self.input_topics.add(topic)

    def init_outputs(self, outputs):
        for output_info in outputs:
            # Topic to subscribe to for data (currently data format must be
            # consistent with a MasterDriverAgent all publish)
            topic = output_info["topic"]
            # Point name from as published by MasterDriverAgent
            point = output_info.pop("point")
            mapped = output_info.pop("mapped")
            # Options for release are None or default
            # None assumes BACnet release via priority array
            # default will safe original value, at start of agent run for control restoration
            # TODO: Update release value anytime agent has state transition for actuation_enable
            release = output_info.get("release", None)
            # Constant offset to apply to apply to determined actuation value
            offset = output_info.get("offset", 0.0)
            # VIP identity of Actuator to call via RPC to perform control of device
            actuator = output_info.get("actuator", "platform.actuator")
            # This is the flexibility range for the market commodity the
            # transactive agent will utilize
            flex = output_info["flexibility_range"]
            # This is the flexibility of the control point, by default the same as the
            # market commodity but not necessarily
            ct_flex = output_info.get("control_flexibility", flex)
            ct_flex, flex = self.set_control(ct_flex, flex)
            self.ct_flexibility = ct_flex
            fallback = output_info.get("fallback", mean(ct_flex))
            # TODO:  Use condition to determine multiple output scenario
            condition = output_info.get("condition", True)

            try:
                value = self.vip.rpc.call(actuator,
                                          'get_point',
                                          topic).get(timeout=10)
            except (RemoteError, gevent.Timeout, errors.VIPError) as ex:
                _log.warning("Failed to get {} - ex: {}".format(topic, str(ex)))
                value = fallback
            if isinstance(release, str) and release.lower() == "default" and value is not None:
                release_value = value
            else:
                release_value = None
            off_setpoint = output_info.get("off_setpoint", value)
            self.outputs[mapped] = {
                "point": point,
                "topic": topic,
                "actuator": actuator,
                "release": release_value,
                "value": value,
                "off_setpoint": off_setpoint,
                "offset": offset,
                "flex": flex,
                "ct_flex": ct_flex,
                "condition": condition
            }

    def set_control(self, ct_flex, flex):
        ct_flex = np.linspace(ct_flex[0], ct_flex[1], 11)
        flex = np.linspace(flex[0], flex[1], 11)
        return ct_flex, flex

    def init_input_subscriptions(self):
        """
        Create topic subscriptions for devices.
        :return:
        """
        for topic in self.input_topics:
            _log.debug('Subscribing to: ' + topic)
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topic,
                                      callback=self.update_input_data)

    def clear_input_subscriptions(self):
        """
        Create topic subscriptions for devices.
        :return:
        """
        for topic in self.input_topics:
            _log.debug('Unubscribing to: ' + topic)
            self.vip.pubsub.unsubscribe(peer='pubsub',
                                        prefix=topic,
                                        callback=self.update_input_data)

    def init_schedule(self, schedule):
        """
        Parse schedule for use in determining occupancy.
        :param schedule:
        :return:
        """
        if schedule:
            for day_str, schedule_info in schedule.items():
                _day = parse(day_str).weekday()
                if schedule_info not in ["always_on", "always_off"]:
                    start = parse(schedule_info["start"]).time()
                    end = parse(schedule_info["end"]).time()
                    self.schedule[_day] = {"start": start, "end": end}
                else:
                    self.schedule[_day] = schedule_info
        else:
            self.occupied = True

    def init_actuation_state(self, actuate_topic, actuate_onstart):
        """
        On-start initialize the actuation state of agent.  Create subscription to
        allow for dynamically disabling/enabling actuation for agent.
        :param actuate_topic:
        :param actuate_onstart:
        :return:
        """
        if self.outputs:
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=actuate_topic,
                                      callback=self.update_actuation_state)
            if actuate_onstart:
                self.update_actuation_state(None, None, None, None, None, True)
        else:
            _log.info("%s - cannot initialize actuation state, "
                      "no configured outputs.", self.core.identity)

    def check_schedule(self, dt):
        if self.actuation_disabled:
            _log.debug("Actuation is disabled!")
            return
        current_schedule = self.schedule[dt.weekday()]
        if "always_on" in current_schedule:
            self.occupied = True
            if not self.actuation_enabled:
                self.update_actuation_state(None, None, None, None, None, True)
            return
        if "always_off" in current_schedule:
            self.occupied = False
            if self.actuation_enabled:
                self.update_actuation_state(None, None, None, None, None, False)
            return
        _start = current_schedule["start"]
        _end = current_schedule["end"]
        if _start <= self.current_datetime.time() < _end:
            self.occupied = True
            if not self.actuation_enabled:
                self.update_actuation_state(None, None, None, None, None, True)
        else:
            self.occupied = False
            if self.actuation_enabled:
                self.update_actuation_state(None, None, None, None, None, False)

    def check_future_schedule(self, dt):
        current_schedule = self.schedule[dt.weekday()]
        if "always_on" in current_schedule:
            return True
        if "always_off" in current_schedule:
            return False
        _start = current_schedule["start"]
        _end = current_schedule["end"]
        if _start < dt.time() < _end:
            return True
        else:
            return False

    def update_actuation_state(self, peer, sender, bus, topic, headers, message):
        state = message
        if sender is not None:
            _log.debug("%s actuation disabled %s",
                       self.core.identity, not bool(state))
            if self.actuation_disabled and not (bool(state)):
                return
            self.actuation_disabled = not bool(state)

        _log.debug("update actuation state : %s with method - %s", state, self.actuation_method)
        if self.actuation_enabled and not bool(state):
            for output_info in list(self.outputs.values()):
                topic = output_info["topic"]
                release = output_info["release"]
                actuator = output_info["actuator"]
                if self.actuation_obj is not None:
                    self.actuation_obj.kill()
                    self.actuation_obj = None
                self.actuate(topic, release, actuator)
        elif not self.actuation_enabled and bool(state):
            for name, output_info in self.outputs.items():
                offset = output_info.get("offset", 0.0)
                actuator = output_info.get("actuator", "platform.actuator")
                topic = output_info["topic"]
                release = output_info.get("release", None)
                if release is not None:
                    try:
                        release_value = self.vip.rpc.call(actuator,
                                                          'get_point',
                                                          topic).get(timeout=10)
                    except (RemoteError, gevent.Timeout, errors.VIPError) as ex:
                        _log.warning("Failed to get {} - ex: {}".format(topic, str(ex)))
                        release_value = None
                else:
                    release_value = None
                self.outputs[name]["release"] = release_value
            if self.actuation_method == "periodic":
                _log.debug("Setup periodic actuation: %s -- %s", self.core.identity, self.actuation_rate)
                self.actuation_obj = self.core.periodic(self.actuation_rate, self.do_actuation, wait=self.actuation_rate)
        self.actuation_enabled = state

    def update_outputs(self, name, price):
        _log.debug("update_outputs: %s - current_price: %s", self.core.identity, self.current_price)
        if price is None:
            if self.current_price is None:
                return
            price = self.current_price
        sets = self.outputs[name]["ct_flex"]
        if self.actuation_price_range is not None:
            prices = self.actuation_price_range
        else:
            prices = self.determine_prices()
        if self.demand_limiting:
            price = max(np.mean(prices), price)
        _log.debug("Call determine_control: %s", self.core.identity)
        value = self.determine_control(sets, prices, price)
        self.outputs[name]["value"] = value
        point = self.outputs.get("point", name)
        topic_suffix = "Actuate"
        message = {point: value, "Price": price}
        self.publish_record(topic_suffix, message)

    def do_actuation(self, price=None):
        _log.debug("do_actuation {}".format(self.outputs))
        for name, output_info in self.outputs.items():
            if not output_info["condition"]:
                continue
            _log.debug("call update_outputs - %s", self.core.identity)
            self.update_outputs(name, price)
            topic = output_info["topic"]
            point = output_info["point"]
            actuator = output_info["actuator"]
            value = output_info.get("value")
            offset = output_info["offset"]
            if value is not None and self.occupied:
                value = value + offset
                self.actuate(topic, value, actuator)

    def actuate(self, point_topic, value, actuator):
        try:
            self.vip.rpc.call(actuator,
                              'set_point',
                              self.core.identity,
                              point_topic,
                              value).get(timeout=15)
        except (RemoteError, gevent.Timeout, errors.VIPError) as ex:
            _log.warning("Failed to set %s - ex: %s", point_topic, str(ex))

    def offer_callback(self, timestamp, market_name, buyer_seller):
        for name, output in self.outputs.items():
            output_info = output
            self.mapped = name
            if output["condition"]:
                break
        self.flexibility = output_info["flex"]
        self.ct_flexibility = output_info["ct_flex"]
        self.off_setpoint = output_info["off_setpoint"]
        market_index = self.market_list.index(market_name)
        if market_index > 0:
            while not self.update_flag[market_index - 1]:
                gevent.sleep(1)
        if market_index == len(self.market_list) - 1:
            self.update_flag = [False]*len(self.market_list)
        if market_index == 0 and self.current_datetime is not None:
            self.init_predictions(output_info)

        schedule_index = self.determine_schedule_index(market_index)
        market_time = self.current_datetime + td(hours=market_index + self.hour_prediction_offset)
        if self.schedule:
            occupied = self.check_future_schedule(market_time)
        else:
            occupied = True

        demand_curve = self.create_demand_curve(market_index,
                                                schedule_index,
                                                occupied)
        self.demand_curve[market_index] = demand_curve
        result, message = self.make_offer(market_name, buyer_seller, demand_curve)

    def create_demand_curve(self, market_index, sched_index, occupied):
        """
        Create demand curve.  market_index (0-23) where next hour is 0
        (or for single market 0 for next market).  sched_index (0-23) is hour
        of day corresponding to market that demand_curve is being created.
        :param market_index: int; current market index where 0 is the next hour.
        :param sched_index: int; 0-23 corresponding to hour of day
        :param occupied: bool; true if occupied
        :return:
        """
        _log.debug("%s create_demand_curve - index: %s - sched: %s",
                   self.core.identity,  market_index, sched_index)
        demand_curve = PolyLine()
        prices = self.determine_prices()
        self.update_prediction_error()
        for control, price in zip(self.ct_flexibility, prices):
            if occupied:
                _set = control
            else:
                _set = self.off_setpoint
            q = self.get_q(_set, sched_index, market_index, occupied)
            demand_curve.add(Point(price=price, quantity=q))

        topic_suffix = "DemandCurve"
        message = {
            "MarketIndex": market_index,
            "Curve": demand_curve.tuppleize(),
            "Commodity": self.commodity
        }
        _log.debug("%s debug demand_curve - curve: %s",
                   self.core.identity, demand_curve.points)
        self.publish_record(topic_suffix, message)
        return demand_curve

    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        market_index = self.market_list.index(market_name)
        if price is None:
            if self.market_prices:
                try:
                    price = self.market_prices[market_index]
                    _log.warning("%s - market %s did not clear, "
                                 "using market_prices!",
                                 self.core.identity, market_name)
                except IndexError:
                    _log.warning("%s - market %s did not clear, and exception "
                                 "was raised when accessing market_prices!",
                                 self.core.identity, market_name)
            else:
                _log.warning("%s - market %s did not clear, "
                             "and no market_prices!",
                             self.core.identity, market_name)
        if self.demand_curve and self.demand_curve[market_index].points:
            cleared_quantity = self.demand_curve[market_index].x(price)
        else:
            cleared_quantity = "None"

        schedule_index = self.determine_schedule_index(market_index)
        _log.debug("%s price callback market: %s, price: %s, quantity: %s",
                   self.core.identity, market_name, price, quantity)
        topic_suffix = "MarketClear"
        message = {
            "MarketIndex": market_index,
            "Price": price,
            "Quantity": [quantity, cleared_quantity],
            "Commodity": self.commodity
        }
        self.publish_record(topic_suffix, message)
        # If a price is known update the state of agent (in concrete
        # implementation of transactive agent).
        self.update_prediction(cleared_quantity)
        if price is not None:
            self.update_state(market_index, schedule_index, price)
            # For single timestep market do actuation when price clears.
            if self.actuation_method == "market_clear" and market_index == 0:
                if self.actuation_enabled and not self.actuation_disabled:
                    self.do_actuation(price)

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

        _log.error("%s - error for Market: %s", self.core.identity, market_name)
        _log.error("buyer_seller : %s - error: %s - aux: %s",
                   buyer_seller, error_message, aux)

    def update_tns_prices(self, peer, sender, bus, topic, headers, message):
        _log.debug("Get prices prior to market start.")
        current_hour = parse(message['Date']).hour

        # Store received prices so we can use it later when doing clearing process
        if self.day_ahead_prices:
            self.actuation_price_range = self.determine_prices()
            if current_hour != self.current_hour:
                self.current_price = self.day_ahead_prices[0]
                self.last_24_hour_prices.append(self.current_price)
                if len(self.last_24_hour_prices) > 24:
                    self.last_24_hour_prices.pop(0)
                    self.market_prices = self.last_24_hour_prices
                elif len(self.last_24_hour_prices) == 24:
                    self.market_prices = self.last_24_hour_prices
                else:
                    self.market_prices = message['prices']
        else:
            self.market_prices = message["prices"]

        self.current_hour = current_hour
        self.oat_predictions = []
        oat_predictions = message.get("temp", [])
        self.oat_predictions = oat_predictions
        self.day_ahead_prices = message['prices']  # Array of prices

    def update_rtp_prices(self, peer, sender, bus, topic, headers, message):
        hour = float(message['hour'])
        self.market_prices = message["prices"]
        _log.debug("Get RTP Prices: {}".format(self.market_prices))
        self.current_price = self.market_prices[-1]

    def determine_control(self, sets, prices, price):
        """
        prices is an list of 11 elements, evenly spaced from the smallest price
        to the largest price and corresponds to the y-values of a line.  sets
        is an np.array of 11 elements, evenly spaced from the control value at
        the lowest price to the control value at the highest price and
        corresponds to the x-values of a line.  Price is the cleared price.
        :param sets: np.array;
        :param prices: list;
        :param price: float
        :return:
        """
        _log.debug("determine_control - transactive.py: %s", self.core.identity)
        control = np.interp(price, prices, sets)
        control = self.clamp(control, min(self.ct_flexibility), max(self.ct_flexibility))
        return control

    def determine_prices(self):
        """
        Determine minimum and maximum price from 24-hour look ahead prices.  If the TNS
        market architecture is not utilized, this function must be overwritten in the child class.
        :return:
        """
        if self.market_prices and not self.static_price_flag:
            avg_price = np.mean(self.market_prices)
            std_price = np.std(self.market_prices)
            price_min = avg_price - self.price_multiplier * std_price
            price_max = avg_price + self.price_multiplier * std_price
        else:
            avg_price = None
            std_price = None
            price_min = self.default_min_price
            price_max = self.default_max_price
        _log.debug("Prices: {} - avg: {} - std: {}".format(self.market_prices, avg_price, std_price))
        price_array = np.linspace(price_min, price_max, 11)
        return price_array

    def update_input_data(self, peer, sender, bus, topic, headers, message):
        """
        Call back method for data subscription for
        device data from MasterDriverAgent.
        :param peer:
        :param sender:
        :param bus:
        :param topic: str; topic for device - devices/campus/building/device/all
        :param headers: dict; contains Date/Timestamp
        :param message: list of dicts of key value pairs; [{data}, {metadata}]
        :return:
        """
        # data is assumed to be in format from VOLTTRON master driver.
        data = message[0]
        try:
            current_datetime = parse(headers.get("Date"))
        except TypeError:
            _log.debug("%s could not parse Datetime in input data payload!",
                       self.core.identity)
            current_datetime = None
        if current_datetime is not None:
            self.current_datetime = current_datetime.astimezone(self.input_data_tz)
        self.update_data(data)
        if current_datetime is not None and self.schedule:
            self.check_schedule(current_datetime)

    def update_data(self, data):
        """
        Each time data comes in on message bus from MasterDriverAgent
        update the data for access by model.
        :param data: dict; key value pairs from master driver.
        :return:
        """
        to_publish = {}
        for name, input_data in self.inputs.items():
            for point, value in input_data.items():
                if point in data:
                    self.inputs[name][point] = data[point]
                    to_publish[point] = data[point]
        topic_suffix = "InputData"
        message = to_publish
        self.publish_record(topic_suffix, message)
        # Call models update_data method
        if self.model is not None:
            self.model.update_data()

    def determine_schedule_index(self, index):
        """
        Determine the actual hour for schedule that
        corresponds to a market index
        :param index: int; market_index
        :return:
        """

        if self.current_datetime is None:
            return index

        schedule_index = index + self.current_datetime.hour + self.hour_prediction_offset
        if schedule_index >= 24:
            schedule_index = schedule_index - 24
        return schedule_index

    def get_input_value(self, mapped):
        """
        Called by model of concrete implementation of transactive to
        obtain the current value for a mapped data point.
        :param mapped:
        :return:
        """
        try:
            return list(self.inputs[mapped].values())[0]
        except KeyError:
            return None

    def update_model(self, peer, sender, bus, topic, headers, message):
        config = self.store_model_config(message)
        if self.model is not None:
            self.model.configure(message)

    def clamp(self, value, x1, x2):
        min_value = min(abs(x1), abs(x2))
        max_value = max(abs(x1), abs(x2))
        value = value
        return min(max(value, min_value), max_value)

    def publish_record(self, topic_suffix, message):
        headers = {headers_mod.DATE: format_timestamp(get_aware_utc_now())}
        message["TimeStamp"] = format_timestamp(self.current_datetime)
        topic = "/".join([self.record_topic, topic_suffix])
        self.vip.pubsub.publish("pubsub", topic, headers, message).get()
