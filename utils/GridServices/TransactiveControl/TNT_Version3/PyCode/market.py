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

import gevent
import logging
from datetime import timedelta

from volttron.platform.agent import utils

from .vertex import Vertex
from .helpers import *
from .measurement_type import MeasurementType
from .interval_value import IntervalValue
# from meter_point import MeterPoint
from .market_state import MarketState
from .time_interval import TimeInterval
from .timer import Timer
import os
from .market_types import MarketTypes
from .method import Method
from warnings import warn
# from matplotlib import pyplot as plt
from .data_manager import *

utils.setup_logging()
_log = logging.getLogger(__name__)

DEBUG=0


class Market(object):
    # Market Base Class
    # At least one Market must exist (see the firstMarket object) to drive the timing
    # with which new TimeIntervals are created.

    def __init__(self,
                 activation_lead_time=timedelta(hours=0),
                 commitment=False,
                 default_price=0.05,
                 delivery_lead_time=timedelta(hours=0),
                 duality_gap_threshold=0.01,
                 future_horizon=timedelta(hours=24),
                 initial_market_state=MarketState.Inactive,
                 interval_duration=timedelta(hours=1),
                 intervals_to_clear=1,
                 market_clearing_interval=timedelta(hours=1),
                 market_clearing_time=None,
                 market_lead_time=timedelta(hours=0),
                 market_order=1,
                 market_series_name='Market Series',
                 market_to_be_refined=None,
                 market_type=MarketTypes.unknown,
                 method=Method.Interpolation,
                 name='',
                 next_market_clearing_time=None,
                 negotiation_lead_time=timedelta(hours=0),
                 prior_market_in_series=None,
                 real_time_duration=15):

        # These properties are relatively static and may be received as parameters:
        self.activationLeadTime = activation_lead_time  # [timedelta] Time in market state "Active"
        self.commitment = commitment  # [Boolean] If true, scheduled power & price are commitments
        self.defaultPrice = default_price  # [$/kWh] Static default price assignment
        self.deliveryLeadTime = delivery_lead_time  # [timedelta] Time in market state "DeliveryLead"
        self.dualityGapThreshold = duality_gap_threshold  # [dimensionless]; 0.01 = 1%
        self.futureHorizon = future_horizon  # Future functionality: future of price-discovery relevance
        self.initialMarketState = initial_market_state  # [MarketState] New market's initial state
        self.intervalDuration = interval_duration  # [timedelta] Duration of this market's time intervals
        self.intervalsToClear = intervals_to_clear  # [int] Market intervals to be cleared by this market object
        self.marketClearingInterval = market_clearing_interval  # [timedelta] Time between successive market clearings
        self.marketClearingTime = market_clearing_time  # [datetime] Time that a market object clears
        self.marketLeadTime = market_lead_time  # [timedelta] Time in market state "MarketLead"
        self.marketOrder = market_order  # [pos. integer] Ordering of sequential markets  (Unused)
        self.marketSeriesName = market_series_name  # Successive market series objects share this name root
        self.marketToBeRefined = market_to_be_refined  # [Market] Pointer to market to be refined or corrected
        self.marketType = market_type  # [MarketTypes] enumeration
        self.method = Method.Interpolation  # Solution method {1: subgradient, 2: interpolation}
        self.name = name  # This market object's name. Use market series name as root
        self.negotiationLeadTime = negotiation_lead_time  # [timedelta] Time in market state "Negotiation"
        self.nextMarketClearingTime = next_market_clearing_time  # [datetime] Time of next market object's clearing
        self.priorMarketInSeries = prior_market_in_series  # [Market] Pointer to preceding market in this market series

        # These are dynamic properties that are assigned in code and should not be manually configured:
        self.activeVertices = []  # [IntervalValue]; values are [vertices]
        self.blendedPrices1 = []  # [IntervalValue] (future functionality)
        self.blendedPrices2 = []  # [IntervalValue] (future functionality)
        self.converged = False
        self.dualCosts = []  # [IntervalValue]; Values are [$]
        self.isNewestMarket = False  # [Boolean] Flag held by only newest market in market series
        self.marketState = MarketState.Inactive  # [MarketState] Current market state
        self.marginalPrices = []  # [IntervalValue]; Values are [$/kWh]
        self.netPowers = []  # [IntervalValue]; Values are [avg.kW]
        #        average_price = 0.06                                # Initialization [$/kWh]
        average_price = 0.035  # Close to real time
        st_dev_price = 0.01  # Initialization [$/kWh]
        self.priceModel = [average_price, st_dev_price] * 24  # Each hour's tuplet average and st. dev. price.
        self.productionCosts = []  # [IntervalValue]; Values are [$]
        self.reconciled = False  # [Boolean] Convergence flag
        self.timeIntervals = []  # [TimeInterval] Current list of active time intervals
        self.totalDemand = []  # [IntervalValue]; Values are [avg.kW]
        self.totalDualCost = 0.0  # [$]
        self.totalGeneration = []  # [IntervalValue]; Values are [avg.kW]
        self.totalProductionCost = 0.0  # [$]

        self.new_data_signal = False
        self.deliverylead_schedule_power = False
        self.real_time_duration = real_time_duration
        # 210118DJH: Must introduce a flag to end activities after various market states. This flag should be made
        #            false in each transition and made true after all the tasks have been completed in the ensuing
        #            market state.
        self._stateIsCompleted = False

    def events(self, my_transactive_node):
        """
        This is the market state machine. Activities should be assigned to state transition events and to the states
        themselves using the supplied methods. This state machine should not itself be modified by implementers because
        doing so may affect alternative market methods' state models.
        :param: my_transactive_node: transactive node--this agent--that keeps track of market objects
        :return: None
        """
        current_time = Timer.get_cur_time()
        if DEBUG:
            _log.debug(
            "Market name: {}, current_time: {}, marketState: {}".format(self.name, current_time, self.marketState))

        reconcile_start_time = self.marketClearingTime + self.deliveryLeadTime \
                               + self.intervalsToClear * self.intervalDuration
        if DEBUG:
            _log.debug("Market method: {}, self.marketClearingTime: {}, self.deliveryLeadTime: {}, self.intervalsToClear: {}, self.intervalDuration: {}".format(
                self.name,
                self.marketClearingTime,
                self.deliveryLeadTime,
                self.intervalsToClear,
                self.intervalDuration))

        # EVENT 1A: % A NEW MARKET OBJECT BECOMES ACTIVE ***************************************************************
        # This is the instantiation of a market object in market state "Active." This transition occurs at a time when
        # a new market object is needed, as specified relative to its market clearing time. Specifically, a new market
        # object is instantiated in its "Inactive" state a specified negotiation lead time and market lead time prior to
        # the market's clearing time. Note that this logic seems a little backward because the state's start must be
        # determined *before* the needed market object exists.

        # 191212DJH: This logic is simplified greatly by the introduction of flag isNewestMarket. The potential need for
        # new market objects is triggered only by the newest market in any series.

        if self.isNewestMarket is True:
            future_clearing_time = current_time + self.activationLeadTime \
                                   + self.negotiationLeadTime + self.marketLeadTime
            if DEBUG:
                _log.debug("Market nextMarketClearingTime: {}, future_clearing_time: {}".format(self.nextMarketClearingTime,
                                                                                            future_clearing_time))
            if self.nextMarketClearingTime < future_clearing_time:
                self.spawn_markets(my_transactive_node, self.nextMarketClearingTime)
                self.isNewestMarket = False
                # 210118DJH: New flag. Set true when responsibilities in market state are completed.
                self._stateIsCompleted = True
            if DEBUG:
                _log.info("Market name: {}, self.marketState: {}".format(self.name, self.marketState))

        # EVENT 1B: TRANSITION FROM INACTIVE TO ACTIVE STATE ***********************************************************
        if self.marketState == MarketState.Inactive:
            activation_start_time = self.marketClearingTime - self.marketLeadTime - self.negotiationLeadTime \
                                    - self.activationLeadTime
            if DEBUG:
                _log.debug("In Market name: {}, Market State: {}, Current time: {}, activation_start_time: {}".format(
                self.name,
                self.marketState,
                current_time,
                activation_start_time))
            if current_time >= activation_start_time:
                # Change the market state to "Active."
                self.marketState = MarketState.Active

                # Call this replaceable method where appropriate actions can be taken.
                self.transition_from_inactive_to_active(my_transactive_node)

                # 210118DJH: New flag. Set false upon transition to new market state.
                self._stateIsCompleted = False

        # EVENT 1C: ACTIONS WHILE IN THE ACTIVE STATE ******************************************************************
        # These are actions to be taken while the market object is in its initial "Active" market state.
        # 210118DJH. New flag. No state should be entered until the prior one is done.
        if self.marketState == MarketState.Active and self._stateIsCompleted is not True:
            # Place actions to be taken in this state in the following method. The method may be overwritten by child
            # classes of class Market.
            # 210118DJH: NOTE: Flag "_stateIsComplete" must be set true after the market's responsibilities have been
            #            completed in this next method or its replacements.
            self.while_in_active(my_transactive_node)

        # EVENT 2A: TRANSITION FROM ACTIVE TO NEGOTIATION STATE ********************************************************
        # This is the transition from "Active" to "Negotiation" market states. Market state "Negotiation" begins at a
        # time specified before an upcoming market clearing of a market object. Specifically, it begins a specified
        # market lead time, less another negotiation lead time, prior to the clearing of the market object.

        # 210118DJH. New flag. Do not transition out of a state until it is completed.
        if self.marketState == MarketState.Active and self._stateIsCompleted is True:
            if DEBUG:
                _log.debug(
                "In Market name: {}, Market State: {}, Current time: {}, marketClearingTime: {}, marketLeadTime: {}, negotiationLeadTime:{}, ".format(
                    self.name,
                    self.marketState,
                    current_time,
                    self.marketClearingTime,
                    self.marketLeadTime,
                    self.negotiationLeadTime))

            negotiation_start_time = self.marketClearingTime - self.marketLeadTime - self.negotiationLeadTime
            if DEBUG:
                _log.debug(
                "In Market name: {} In Market State: {}, current_time: {}, negotiation_start_time: {}".format(self.name,
                                                                                                              self.marketState,
                                                                                                              current_time,
                                                                                                              negotiation_start_time))

            if current_time >= negotiation_start_time:
                # Change the market state to "Negotiation."
                self.marketState = MarketState.Negotiation

                # Place other transition actions in this following method. The method may be replaced.
                # of class Market.
                self.transition_from_active_to_negotiation(my_transactive_node)

                # 210118DJH: New flag. Set false upon entering a new market state.
                self._stateIsCompleted = False

        # EVENT 2B: ACTIONS WHILE IN MARKET STATE NEGOTIATION **********************************************************
        # These are the actions while in the "Negotiation" market state.

        if self.marketState == MarketState.Negotiation and self._stateIsCompleted is not True:
            if DEBUG:
                _log.debug("In Market name: {} In Market State: {}".format(self.name, self.marketState))
            # Place actions to be completed during this market state in the following method. The method may be
            # overwritten by child classes of class Market. Note that the actions during this state may be made
            # dependent upon a convergence flag.
            # 210118DJH: NOTE: Flag "_stateIsComplete" must be set true after the market's responsibilities have been
            #            completed in this next method or its replacements.
            self.while_in_negotiation(my_transactive_node)

        # EVENT 3A: TRANSITION FROM NEGOTIATION TO MARKET LEAD STATE ***************************************************
        # This is the transition from "Negotiation" to "MarketLead" market states.
        # The transition occurs at a time relative to the market object's market clearing time. Specifically, it starts
        # a defined lead time prior to the market clearing time.
        # 210118DJH: Adding flag. No state transition should be allowed unless the prior state is completed.
        if self.marketState == MarketState.Negotiation and self._stateIsCompleted is True:

            market_lead_start_time = self.marketClearingTime - self.marketLeadTime
            if DEBUG:
                _log.debug(
                f"Market State: {self.marketState}, Type of current time: {type(current_time)}, Type of market_lead_start_time: {type(market_lead_start_time)}")

            if current_time >= market_lead_start_time:
                # Change the market state to "MarketLead."
                self.marketState = MarketState.MarketLead

                #  Place other transition actions in this following method. The method may be replaced.
                #  of class Market.
                self.transition_from_negotiation_to_market_lead(my_transactive_node)

                # 210118DJH: New flag. Set false prior to transition to new market state.
                self._stateIsCompleted = False

        # EVENT 3B: ACTIONS WHILE IN THE MARKET LEAD STATE *************************************************************
        # These are the actions while in the "MarketLead" market state.

        if self.marketState == MarketState.MarketLead and self._stateIsCompleted is not True:
            #  Specify actions for the market state "MarketLead" in this following method. The method may be
            #  overwritten by child classes of class Market.
            # 210118DJH: NOTE: Flag "_stateIsComplete" must be set true after the market's responsibilities have been
            #            completed in this next method or its replacements.
            self.while_in_market_lead(my_transactive_node)

        # EVENT 4A: TRANSITION FROM MARKET LEAD TO DELIVERY LEAD STATE *************************************************
        # This is the transition from "MarketLead" to "DeliveryLead" market states.
        # 210118DJH: Adding flag. No state transition should be allowed unless the prior state is done.
        if self.marketState == MarketState.MarketLead and self._stateIsCompleted is True:
            if DEBUG:
                _log.debug("In Market name: {}, Market State: {}, Current time: {}, marketClearingTime: {}".format(
                self.name,
                self.marketState,
                current_time,
                self.marketClearingTime))
            # This transition is simply the market clearing time.
            delivery_lead_start_time = self.marketClearingTime

            if DEBUG:
                _log.debug(
                "In Market name: {} In Market State: {}, current_time: {}, delivery_lead_start_time: {}".format(
                    self.name,
                    self.marketState,
                    current_time,
                    delivery_lead_start_time))

            if DEBUG:
                _log.debug(
                f"Market State: {self.marketState}, Type of current time: {type(current_time)}, Type of delivery_lead_start_time: {type(delivery_lead_start_time)}")

            if current_time >= delivery_lead_start_time:
                # Set the market state to "DeliveryLead."
                self.marketState = MarketState.DeliveryLead

                # Place other transition actions here. This following method may be replaced.
                self.transition_from_market_lead_to_delivery_lead(my_transactive_node)

                # 210118DJH: New flag. Set false prior to new market state.
                self._stateIsCompleted = False

        # EVENT 4B: ACTIONS WHILE IN MARKET STATE DELIVERY LEAD ********************************************************
        # These are the actions while in the "DeliveryLead" market state.

        if self.marketState == MarketState.DeliveryLead and self._stateIsCompleted is not True:
            # Place actions in this following method if they are to occur during market state "DeliveryLead." This
            # method may be overwritten by child classes of class Market.
            # 210118DJH: NOTE: Flag "_stateIsComplete" must be set true after the market's responsibilities have been
            #            completed in this next method or its replacements.
            self.while_in_delivery_lead(my_transactive_node)

        # EVENT 5A: TRANSITION FROM DELIVERY LEAD TO DELIVERY **********************************************************
        # This is the transition from "DeliveryLead" to "Delivery" market states. The start of market state "Delivery"
        # is timed relative to the market object's market clearing time. Specifically, it begins a delivery lead time
        # after the market has cleared.
        # 210118DJH: Adding flag. No state transition should be allowed unless the prior state is done.
        if self.marketState == MarketState.DeliveryLead and self._stateIsCompleted is True:

            delivery_start_time = self.marketClearingTime + self.deliveryLeadTime
            if DEBUG:
                _log.debug(
                "In Market name: {} In Market State: {}, current_time: {}, delivery_start_time: {}".format(self.name,
                                                                                                           self.marketState,
                                                                                                           current_time,
                                                                                                           delivery_start_time))

            if DEBUG:
                _log.debug(
                f"Market State: {self.marketState}, Type of current time: {type(current_time)}, Type of delivery_start_time: {type(delivery_start_time)}")
            if current_time >= delivery_start_time:
                # Change the market state from "DeliverLead" to "Delivery."
                self.marketState = MarketState.Delivery

                # Other actions for this transition should be placed in the following method, which can be replaced.
                self.transition_from_delivery_lead_to_delivery(my_transactive_node)

                # 210118DJH: New flag. Set false prior to each new market state.
                self._stateIsCompleted = False

        # EVENT 5B: ACTIONS WHILE IN MARKET STATE DELIVERY *************************************************************
        # These are the actions while in the "Delivery" market state.

        if self.marketState == MarketState.Delivery and self._stateIsCompleted is not True:
            # Place any actions to be conducted in market state "Delivery" in this following method. The method may be
            # overwritten by child classes of class Market.
            # 210118DJH: NOTE: Flag "_stateIsComplete" must be set true after the market's responsibilities have been
            #            completed in this next method or its replacements.
            self.while_in_delivery(my_transactive_node)

        # EVENT 6A: TRANSITION FROM DELIVERY TO RECONCILE **************************************************************
        # This is the transition from "Delivery" to "Reconcile" market states. The Reconcile market state begins at a
        # time referenced from the market object's clearing time. Specifically, reconciliation begins after all the
        # market object's market intervals and an additional delivery lead time have expired after the market clears.
        # 210118DJH: Adding flag. No state transition should be allowed unless the prior state is completed.
        if self.marketState == MarketState.Delivery and self._stateIsCompleted is True:
            if DEBUG:
                _log.debug(
                "In Market name: {} In Market State: {}, marketClearingTime: {}, deliveryLeadTime: {}, intervalsToClear: {}, intervalDuration: {}".format(
                    self.name,
                    self.marketState,
                    self.marketClearingTime,
                    self.deliveryLeadTime,
                    self.intervalsToClear,
                    self.intervalDuration))

            reconcile_start_time = self.marketClearingTime + self.deliveryLeadTime \
                                   + self.intervalsToClear * self.intervalDuration
            if DEBUG:
                _log.debug("In Market name: {} In Market State: {}, current_time: {}, reconcile_start_time: {}".format(self.name,
                                                                                                            self.marketState,
                                                                                                            current_time,
                                                                                                            reconcile_start_time))
            if current_time >= reconcile_start_time:
                if DEBUG:
                    _log.debug("In Market name: {} In Market State: {}, current_time: {}, reconcile_start_time: {}".format(
                    self.name,
                    self.marketState,
                    current_time,
                    reconcile_start_time))
                # Change the market state to "Reconcile."
                self.marketState = MarketState.Reconcile

                # Other transition actions may be placed in this method.
                self.transition_from_delivery_to_reconcile(my_transactive_node)

                # 210118DJH: New flag. Set flat false prior to every new market state.
                self._stateIsCompleted = False

        # EVENT 6A: ACTIONS WHILE IN MARKET STATE RECONCILE ************************************************************
        # These are the actions while in the "DeliveryLead" market state.

        if self.marketState == MarketState.Reconcile and self._stateIsCompleted is not True:
            if DEBUG:
                _log.debug("In Market name: {} In Market State: {}".format(self.name, self.marketState))
            # Place actions in this following method if they should occur during market state "Reconcile." This method
            # may be overwritten by children of the Market class.
            # 210118DJH: NOTE: Flag "_stateIsComplete" must be set true after the market's responsibilities have been
            #            completed in this next method or its replacements.
            self.while_in_reconcile(my_transactive_node)

        # EVENT 7A: TRANSITION FROM RECONCILE TO EXPIRED ***************************************************************
        # This is the transition from "Reconcile" to "Expired" market states.
        # 210118DJH: Adding flag. No state transition should be allowed unless the prior state is completed.
        if self.marketState == MarketState.Reconcile and self._stateIsCompleted is True:

            # 210118DJH: The use of flag "reconciled" is redundant now that flag "stateIsCompleted" is available.
            #            TODO: Replace instanced of flag "reconciled" by new flag "stateIsCompleted."
            if self.reconciled is True:
                # Change the market state to "Expired".
                self.marketState = MarketState.Expired

                # Replace this method for other transitional actions.
                self.transition_from_reconcile_to_expired(my_transactive_node)

                # 210118DJH: New flag. Set false prior to any new state.
                self._stateIsCompleted = False

        # EVENT 7B: WHILE EXPIRED **************************************************************************************
        # These are the actions while in the "Expired" market state. It should be pretty standard that market objects
        # are deleted after they expire, so it is unlikely that alternative actions will be needed by child Market
        # classes.

        if self.marketState == MarketState.Expired and self._stateIsCompleted is not True:
            if DEBUG:
                _log.debug("Expired. In Market name: {} In Market State: {}".format(self.name,
                                                                                self.marketState))
            # Delete market intervals that are defined by this market object.
            self.timeIntervals = []

            # Remove the expired market object from the agent's list of markets.
            # 200908DJH: Shwetha says this does not work because you can't remove an indexed item from inside a for
            # loop as we index through the list MyTransactiveMode.markets. I've tested that this revised approach works,
            # however, as long as there are no further references to self in the remainder of the loop.
            # my_transactive_node.markets.remove(self)  # REPLACE OR USE ALTERNATIVE APPROACH
            # my_transactive_node.markets[:] = [x for x in my_transactive_node.markets if x != self]

            # NOTE: We let garbage collection finally delete the object once it is entirely out of scope.

    def spawn_markets(self, my_transactive_node, new_market_clearing_time):
        """
        This method is called when a test determines that a new market object may be needed. The base method creates the
        new market object, as will be normal for systems having only one market. This method must be replaced or
        extended if
        (1) Still more markets should be instantiated, as may happen when market self is refined or corrected by another
        market series. If this is the case, not only the next needed market in this series, but also one or more markets
        in another market series must be instantiated.
        (2) The markets in this series are instantiated by another market series. In this case, this method shoudl be
        replaced by a pass (no action).
        :param: my_transactive_node: my transactive node agent object
        :param: new_market_clearing_time: new market objects market clearing time
        :return: None
        """

        # A new market object must be instantiated. Many of its properties are the same as that of the called market
        # or can be derived therefrom. The new market should typically be initialized from the same class as the calling
        # market (i.e., self).
        new_market = self.__class__()  # This uses a constructor, but most properties must be redefined.

        new_market.marketSeriesName = self.marketSeriesName
        new_market.marketClearingTime = new_market_clearing_time
        new_market.nextMarketClearingTime = new_market.marketClearingTime + self.marketClearingInterval
        new_market.deliveryLeadTime = self.deliveryLeadTime
        new_market.marketLeadTime = self.marketLeadTime
        new_market.negotiationLeadTime = self.negotiationLeadTime
        new_market.commitment = self.commitment
        new_market.defaultPrice = self.defaultPrice
        new_market.futureHorizon = self.futureHorizon
        new_market.initialMarketState = self.initialMarketState
        new_market.intervalDuration = self.intervalDuration
        new_market.intervalsToClear = self.intervalsToClear
        new_market.marketClearingInterval = self.marketClearingInterval
        new_market.marketOrder = self.marketOrder
        new_market.method = self.method
        new_market.priceModel = self.priceModel  # It must be clear that this is a copy, not a reference.
        new_market.marketState = MarketState.Active
        new_market.isNewestMarket = True  # This new market now assumes the flag as newest market
        new_market.priorMarketInSeries = self

        # The market instance is named by concatenating the market name and its market clearing time. There MUST be a
        # simpler way to format this in Python!
        dt = str(new_market.marketClearingTime)
        new_market.name = new_market.marketSeriesName.replace(' ', '_') + '_' + dt[:19]

        # Append the new market object to the list of market objects that is maintained by the agent.
        my_transactive_node.markets.append(new_market)

        # Initialize the Market object's time intervals.
        new_market.check_intervals()

        # Initialize the marginal prices in the Market object's time intervals.
        new_market.check_marginal_prices(my_transactive_node)

        # 210127DJH: Save information about the new Market object into a formatted csv file.
        append_table(obj=new_market)

    def transition_from_inactive_to_active(self, my_transactive_node):
        """
        These actions, if any are taken as a market transitions from its inactive to its active market state.
        :param my_transactive_node: TransactiveNode object--this agent
        :return: None
        """
        pass
        return None

    def while_in_active(self, my_transactive_node):
        """
        For activities that should happen while a market object is in its initial "Active" market state. This method
        may be overwritten by child classes of Market to create alternative market behaviors during this market state.
        It will be rare for a market object to have actions in its Active state. It usually will immediately enter its
        Negotiation state.
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """
        # pass
        # 210118DJH: NOTE: Flag "_stateIsComplete" must be set true after the market's responsibilities have been
        #            completed in this next method or its replacements.
        self._stateIsCompleted = True
        return None

    def transition_from_active_to_negotiation(self, my_transactive_node):
        """
        For activities that should accompany a market object's transition from market state "Active" to "Negotiation."
        This method may be overwritten by child classes of Market to create alternative market behaviors during this
        transition.
        :param my_transactive_node: my transactive node agent object
        :return: None
        """
        pass
        return None

    def while_in_negotiation(self, my_transactive_node):
        """
        For activities that should happen while a market object is in its "Negotiation" market state. This method may
        be overwritten by child classes of Market to create alternative market behaviors during this market state.
        :param my_transactive_node: my transactive node agent object
        :return: None
        """

        # A convergence flag is available to distinguish actions to be undertaken while actively negotiating and others
        # while convergence has been obtained.
        if not self.converged:
            self.balance(my_transactive_node)  # A consensus method conducts negotiations while in negotiation state.

        else:
            # This is most likely a wait state while converged in the negotiation state.
            pass
            # 210118DJH: NOTE: Flag "_stateIsComplete" must be set true after the market's responsibilities have been
            #            completed in this next method or its replacements.
            self._stateIsCompleted = True

        return None

    def transition_from_negotiation_to_market_lead(self, my_transactive_node):
        """
        For activities that should accompany a market object's transition from market state "Negotiation" to
        "MarketLead." This method may be overwritten by child classes of Market to create alternative market behaviors
        during this transition.
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """
        pass
        return None

    def while_in_market_lead(self, my_transactive_node):
        """
        For activities that should happen while a market object is in its "MarketLead" market state. This method may
        be overwritten by child classes of Market to create alternative market behaviors during this market state.
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """
        pass
        # 210118DJH: NOTE: Flag "_stateIsComplete" must be set true after the market's responsibilities have been
        #            completed in this next method or its replacements.
        self._stateIsCompleted = True
        return None

    def transition_from_market_lead_to_delivery_lead(self, my_transactive_node):
        """
        For activities that should accompany a market object's transition from market state "MarketLead" to
        "DeliveryLead," (i.e., the clearing of the market). This method may be overwritten by child classes of Market
        to create alternative market behaviors during this transition.
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """
        pass
        return None

    def while_in_delivery_lead(self, my_transactive_node):
        """
        For activities that should happen while a market object is in its "DeliveryLead" market state. This method may
        be overwritten by child classes of Market to create alternative market behaviors during this market state.
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """
        pass
        # 210118DJH: NOTE: Flag "_stateIsComplete" must be set true after the market's responsibilities have been
        #            completed in this next method or its replacements.
        self._stateIsCompleted = True
        return None

    def transition_from_delivery_lead_to_delivery(self, my_transactive_node):
        """
        For activities that should accompany a market object's transition from market state "DeliveryLead" to
        "Delivery." This method may be overwritten by child classes of Market to create alternative market behaviors
        during this transition.
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """
        # A good practice upon entering the delivery period is to update the market's price model using the final
        # marginal prices.
        final_prices = self.marginalPrices
        for x in range(len(final_prices)):
            self.model_prices(final_prices[x].timeInterval.startTime, final_prices[x].value)

        self.deliverylead_schedule_power = False
        return None

    def while_in_delivery(self, my_transactive_node):
        """
        For activities that should happen while a market object is in its "Delivery" market state. This method may be
        overwritten by child classes of Market to create alternative market behaviors during this market state.
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """

        # TBD: These actions will be common to most transactive systems during the delivery market state:
        # - monitor and meter assets and power exchanges
        # - control assets to negotiated average power
        pass
        # 210118DJH: NOTE: Flag "_stateIsComplete" must be set true after the market's responsibilities have been
        #            completed in this next method or its replacements.
        self._stateIsCompleted = True
        return None

    def transition_from_delivery_to_reconcile(self, my_transactive_node):
        """
        For activities that should accompany a market object's transition from market state "Delivery" to "Reconcile."
        This method may be overwritten by child classes of Market to create alternative market behaviors during this
        transition.
        :param my_transactive_node: transactive node object--the agent
        :return: None
        """
        pass
        return None

    def while_in_reconcile(self, my_transactive_node):
        """
        For activities that should happen while a market object is in its "Reconcile" market state. This method may be
        overwritten by child classes of Market to create alternative market behaviors during this market state.
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """
        # 201013DJH: Moving code that stored a file of various market, asset, and neighbor interval values from this
        #            method to transition_from_reconcile_to_expired(). There was a risk that many duplicate file records
        #            would have been created. Now the file is created once for this market just before it expires.
        # NOTE: The implementer may wish to automatically assert reconciliation at this point, which allows a state
        # transition to the Expired state. This could be done by making a call to this parent method directly, or by
        # using a super() method call.
        # 200908DJH: So, let's go ahead and claim it as our default.
        self.reconciled = True
        # 210118DJH: NOTE: Flag "_stateIsComplete" must be set true after the market's responsibilities have been
        #            completed in this next method or its replacements.
        self._stateIsCompleted = True

        return None

    def transition_from_reconcile_to_expired(self, my_transactive_node):
        """
        For activities that should accompany a market object's transition from market state "Reconcile" to "Expired."
        This method may be overwritten by child classes of Market to create alternative market behaviors during this
        transition.
        :param my_transactive_node: transactive node object--the agent
        :return: None
        """
        # 201013DJH: Moved code that stored a file of various market, asset, and neighbor interval values from
        #            while_in_reconciliation() to here. There was a risk that many duplicate file records would have
        #            been created. Now, a file is created once for this market just before it expires.

        # Save market object data:

        # Create a table for market object data.
        data = []

        # Append data for active market vertices:
        for x in range(len(self.activeVertices)):
            datum = [self.name,
                     self.activeVertices[x].timeInterval.name,
                     self.activeVertices[x].value.marginalPrice,
                     self.activeVertices[x].value.power]
            data.append(datum)

        # Append data for local assets:
        for x in range(len(my_transactive_node.localAssets)):
            vertices = [y for y in my_transactive_node.localAssets[x].activeVertices
                        if y.timeInterval.market == self]

            for z in range(len(vertices)):
                datum = [my_transactive_node.localAssets[x].name,
                         vertices[z].timeInterval.name,
                         vertices[z].value.marginalPrice,
                         vertices[z].value.power]
                data.append(datum)

        # Append data for neighbor data:
        for x in range(len(my_transactive_node.neighbors)):
            vertices = [y for y in my_transactive_node.neighbors[x].activeVertices
                        if y.timeInterval.market == self]

            for z in range(len(vertices)):
                datum = [my_transactive_node.neighbors[x].name,
                         vertices[z].timeInterval.name,
                         vertices[z].value.marginalPrice,
                         vertices[z].value.power]
                data.append(datum)

        # Write the vertex data into a csv file based on the current working directory.

        filename = self.marketSeriesName + ".csv"
        data_folder = os.getcwd()
        data_folder = data_folder + "\\.."
        data_folder = data_folder + "\\Market_Data\\"
        full_filename = data_folder + filename

        import csv

        my_file = open(full_filename, 'w+')
        with my_file:
            writer = csv.writer(my_file)
            writer.writerows(data)

        # Gather simpler marginal price data:
        price_data = []

        for x in self.marginalPrices:  #
            datum = [self.name,
                     x.timeInterval.startTime,
                     x.value]
            price_data.append(datum)

        filename = self.name + ".csv"
        full_filename = data_folder + filename
        if DEBUG:
            _log.debug("while_in_reconcile: write price data into csv: {}".format(full_filename))

        my_file = open(full_filename, 'w+')
        with my_file:
            writer = csv.writer(my_file)
            writer.writerows(price_data)
        return None

    def model_prices(self, date_time, new_price=None, k=14.0):
        """
        Returns the average and standard deviation prices for the provided datetime in this market. If a new price is
        provided, then the price model is updated using this price in the given date and time.
        Note: In order for this to work, the Market.priceModel table must be initialized from its preceding Market
              object of the same type, i.e., sharing the same market name.

        :param date_time: The date and time of the prediction or update.
        :param new_price: [$/kWh] (optional) price provided to update the model for the given date and time.
        :param k: [whole number] Iteration counter.

        :return avg_price: [$/kWh] average model price for the given date and time
        :return sd_price: [$/kWh] standard price deviation for given date and time
        """
        # Initialize the average and standard deviation prices.
        avg_price = None
        sd_price = None

        try:
            h = int(date_time.hour)  # Extract the hour in [0,24] from referenced date_time.

            # Find the current average and standard deviation prices for this market object.
            avg_price = self.priceModel[2 * h]
            sd_price = self.priceModel[2 * h + 1]

            if new_price is not None:
                avg_price = ((k - 1.0) * avg_price + new_price) / k
                sd_price = (((k - 1.0) * sd_price ** 2 + (avg_price - new_price) ** 2) / k) ** 0.5
                self.priceModel[2 * h] = avg_price
                self.priceModel[2 * h + 1] = sd_price

        except RuntimeWarning as warning:
            print('A price could not be found from the price model:', warning)

        return avg_price, sd_price

    def assign_system_vertices(self, my_transactive_node):
        """
        Collect active vertices from neighbor and asset models and reassign them with aggregate system information
        for all active time intervals.

        ASSUMPTIONS:
        - Active time intervals exist and are up-to-date
        - Local convergence has occurred, meaning that power balance, marginal price, and production costs have been
          adequately resolved from the
        local agent's perspective
        - The active vertices of local assets exist and are up-to-date.
        - The vertices represent available power flexibility.
        - The vertices include meaningful, accurate production-cost information.
        - There is agreement locally and in the network concerning the format and content of transactive records.

        Calls method sum_vertices in each time interval.

        INPUTS:
        :param my_transactive_node: TransactiveNode object--the agent

        OUTPUTS:
        - Updates property activeVertices - vertices that define the net system balance and flexibility. The meaning of
          the vertex properties are
        - marginalPrice: marginal price [$/kWh]
        - cost: total production cost at the vertex [$]. (A locally meaningful blended electricity price is (total
          production cost / total production)).
        - power: system net power at the vertex (The system "clears" where system net power is zero.)
        """

        for time_interval in self.timeIntervals:
            # Find and delete existing aggregate active vertices in the indexed time interval. They will be recreated.
            self.activeVertices = [x for x in self.activeVertices
                                   if x.timeInterval.startTime != time_interval.startTime]

            # Call the utility sum_vertices to recreate the aggregate vertices in the indexed time interval. (This
            # method is separated out because it will be used by other methods.)
            summed_vertices = self.sum_vertices(my_transactive_node, time_interval)

            # Create and store an interval value for each vertex.
            for vertex in summed_vertices:
                self.activeVertices.append(IntervalValue(calling_object=self,
                                                         time_interval=time_interval,
                                                         market=self,
                                                         measurement_type=MeasurementType.SystemVertex,
                                                         value=vertex
                                                         )
                                           )

    def balance(self, my_transactive_node, k=1):
        """
        Balance current market
        :param my_transactive_node: my transactive node object
        :param k: iteration counter
        :return:
        """
        # TODO: A test is badly needed for method balance().
        # 202015DJH: The base balance method is being greatly simplified. Whereas it originally iterated to find a
        #            marginal price in each active time interval, it now simply performs a single iteration using either
        #            the iterative sub-gradient or interpolation approach. Iteration and preconditions may need to be
        #            completed within the market's state machine.
        # TODO: Consider having the balance method solve for both marginal price AND quantity.

        # Gather the active time intervals in this market.
        time_intervals = self.timeIntervals  # TimeIntervals

        # if self.method == Method.Interpolation:
        if self.method == 2:
            self.assign_system_vertices(my_transactive_node)
            # TODO: Un-comment this next debug code.
            av = [(x.timeInterval.name, x.value.marginalPrice, x.value.power) for x in self.activeVertices]

        # Index through active time intervals.
        for i in range(len(time_intervals)):
            # Find the marginal price interval value for the corresponding indexed time interval.
            marginal_price = find_obj_by_ti(self.marginalPrices, time_intervals[i])

            # Extract its  marginal price value as a trial clearing price (that may be replaced).
            # 200716DJH: There is a problem trying to test length of marginal_price, which is an IntervalValue. This was
            #            not found when marginal_price = None, but an exception is thrown if there already exists a
            #            marginal_price in this market and time interval.
            # if marginal_price is None or len(marginal_price) == 0:
            if marginal_price is None:
                cleared_marginal_price = self.defaultPrice
                marginal_price = IntervalValue(self,
                                               time_intervals[i],
                                               self,
                                               MeasurementType.MarginalPrice,
                                               cleared_marginal_price
                                               )
                self.marginalPrices.append(marginal_price)
            else:
                cleared_marginal_price = marginal_price.value  # [$/kWh]

            if self.method == 1:
                # if self.method == Method.Subgradient:
                # Find the net power corresponding to the indexed time interval.
                net_power = find_obj_by_ti(self.netPowers, time_intervals[i])
                total_generation = find_obj_by_ti(self.totalGeneration, time_intervals[i])
                total_demand = find_obj_by_ti(self.totalDemand, time_intervals[i])

                net_power = net_power.value / (total_generation.value - total_demand.value)

                # Update the marginal price using sub-gradient search.
                cleared_marginal_price = cleared_marginal_price - (net_power * 1e-1) / (10 + k)  # [$/kWh]

            elif self.method == 2:  # self.method == Method.Interpolation:
                # Get the indexed active system vertices.
                active_vertices = [x.value for x in self.activeVertices
                                   if x.timeInterval.startTime == time_intervals[i].startTime]

                # Order the system vertices in the indexed time interval by price and power.
                active_vertices = order_vertices(active_vertices)

                try:
                    # Find the vertex that bookcases the balance point from the lower side.
                    lower_active_vertex = [x for x in active_vertices if x.power < 0]
                    if len(lower_active_vertex) == 0:
                        _log.warning('No load demand cases were found in {}'.format(time_intervals[i].name))
                        err_msg = "At {}, there is no point having power < 0".format(time_intervals[i].name)
                    else:
                        lower_active_vertex = lower_active_vertex[-1]

                    # Find the vertex that bookcases the balance point from the upper side.
                    upper_active_vertex = [x for x in active_vertices if x.power >= 0]
                    if len(upper_active_vertex) == 0:
                        _log.warning('No supply power cases were found in {}'.format(time_intervals[i].name))
                        err_msg = "At {}, there is no point having power >= 0 ".format(time_intervals[i].name)
                    else:
                        upper_active_vertex = upper_active_vertex[0]

                    # Interpolate the marginal price in the interval using a principle of similar triangles.
                    power_range = upper_active_vertex.power - lower_active_vertex.power

                    marginal_price_range = upper_active_vertex.marginalPrice - lower_active_vertex.marginalPrice
                    if power_range == 0:
                        _log.warning(
                            'There is no power range to interpolate. Marginal price is not unique in {}'.format(
                                time_intervals[i].name))
                        err_msg = "At {}, power range is 0".format(time_intervals[i].name)
                    cleared_marginal_price = - marginal_price_range * lower_active_vertex.power / power_range \
                                             + lower_active_vertex.marginalPrice
                    # TODO: Consider adding a feature to find each asset's and neighbor's cleared power at this point.
                    #       This would require interpolation of the cleared average power, and the implication must be
                    #       interpreted for each asset and neighbor.

                except RuntimeWarning as warning:
                    _log.warning('No balance point was found in {}'.format(time_intervals[i].name))

                    _log.error(err_msg)
                    # _log.error("{} failed to find balance point. "
                    #            "Market active vertices: {}".format(mtn.name,
                    #                                                [(tis[i].name, x.marginalPrice, x.power)
                    #                                                 for x in av]))

                    self.converged = False
                    return
            # Regardless of the method used, assign the cleared marginal price to the marginal price value for the
            # indexed active time interval.
            # 200205DJH: The intention here is that the marginal price is the actual IntervalValue object. Check that
            #            it is assigned properly in its market list.
            marginal_price.value = cleared_marginal_price  # [$/kWh]


    def old_balance(self, mtn):
        """
        Balance current market
        :param mtn: my transactive node object
        :return:
        """
        # TODO: Consider having the balance method solve for both marginal price AND quantity. The quantity is unique to
        #  the local assets and neighbors. This improvement would facilitate current convergence issues that occur when
        #  cost functions are linear, not quadratic. Partial quantities are allowed even though quantity is not a proper
        #  function of marginal price. Note that this introduces new issues for assets that cannot be throttled down.
        self.new_data_signal = False

        # Check and update the time intervals at the beginning of the process. This should not need to be repeated in
        # process iterations.
        # TODO: This check should be done within the market state machine, not here. Typically, it would be done once
        #  for each clearing to check that market intervals are proper.
        self.check_intervals()

        # TODO: This check should be done within the market state machine, not here. Typically, it would be done once
        #  for each clearing to check that marginal prices exist for the market's forward time intervals.
        # Clean up or initialize marginal prices. This should not be repeated in process iterations.
        self.check_marginal_prices(mtn)

        # TODO: Move this to the market state machine. Iterations to convergence, if any, should be moved to the state
        #  machine methods.
        # Set a flag to indicate an unconverged condition.
        self.converged = False

        # Iterate to convergence. "Convergence" here refers to the status of the local convergence of (1) local supply
        # and demand and (2) dual costs. This local convergence says nothing about the additional convergence between
        # transactive neighbors and their calculations.

        # TODO: Move iteration of the market balancing process to the market state machine, not here. Not all markets
        #  iterate. A typical auction state machine will invoke one balancing operation. Others must iterate.
        # Initialize the iteration counter k
        k = 1

        while not self.converged and k < 100:
            # 200205DJH: I'm not sure of this logic that was introduced by new_data_signal. I think it might be unique
            # to the PNNL building model and should no longer be needed.
            # TODO: Clean up logic introduced by new_data_signal.
            # if self.new_data_signal:
            #     self.converged = False
            #     return

            # Invite all neighbors and local assets to schedule themselves based on current marginal prices
            self.schedule(mtn)

            # Update the primal and dual costs for each time interval and altogether for the entire time horizon.
            self.update_costs(mtn)

            # Update the total supply and demand powers for each time interval. These sums are needed for the
            # sub-gradient search and for the calculation of blended price.
            self.update_supply_demand(mtn)

            # Check duality gap for convergence.
            # Calculate the duality gap, defined here as the relative difference between total production and dual
            # costs.
            if self.totalProductionCost == 0:
                dg = float("inf")
            else:
                dg = self.totalProductionCost - self.totalDualCost  # [$]
                dg = dg / self.totalProductionCost  # [dimensionless. 0.01 is 1#]

            # Display the iteration counter and duality gap. This may be commented out once we have confidence in the
            # convergence of the iterations.
            """
            _log.debug("Market balance iteration %i: (tpc: %f, tdc: %f, dg: %f)" %
                       (k, self.totalProductionCost, self.totalDualCost, dg))
            """

            # Check convergence condition
            if abs(dg) <= self.dualityGapThreshold:  # Converged
                # 1.3.1 System has converged to an acceptable balance.
                self.converged = True

            # System is not converged. Iterate. The next code in this method revised the marginal prices in active
            # intervals to drive the system toward balance and convergence.

            # Gather active time intervals ti
            tis = self.timeIntervals  # TimeIntervals

            # A parameter is used to determine how the computational agent searches for marginal prices.
            #
            # Method 1: Subgradient Search - This is the most general solution technique to be used on
            #           non-differentiable solution spaces. It uses the difference between primal costs (mostly
            #           production costs, in this case) and dual costs (which are modified using gross profit or
            #           consumer cost) to estimate the magnitude of power imbalance in each active time interval. Under
            #           certain conditions, a solution is guaranteed. Many iterations may be needed. The method can be
            #           fooled, so I've found, by interim oscillatory solutions. This method may fail when large assets
            #           have linear, not quadratic, cost functions.
            #
            # Method 2: Interpolation - If certain requirements are met, the solution might be greatly accelerated by
            #           interpolating between the inflection points of the net power curve.
            #           Requirements:
            #           1. All Neighbors and LocalAssets are represented by linear or quadratic cost functions, thus
            #              ensuring that the net power curve is perfectly linear between its inflection points.
            #           2: All Neighbors and Assets update their active vertices in a way that represents their
            #              residual flexibility, which can be none, thus ensuring a meaningful connection between
            #              balancing in time intervals and scheduling of the individual Neighbors and LocalAssets.
            #              This method might fail when many assets do complex scheduling of their flexibility.

            if self.method == 2:
                self.assign_system_vertices(mtn)
                # av = [(x.timeInterval.name, x.value.marginalPrice, x.value.power) for x in self.activeVertices]
                # _log.debug("{} market active vertices are: {}".format(self.name, av))

            # Index through active time intervals.
            for i in range(len(tis)):
                # Find the marginal price interval value for the corresponding indexed time interval.
                mp = find_obj_by_ti(self.marginalPrices, tis[i])

                # Extract its  marginal price value.
                xlamda = mp.value  # [$/kWh]

                if self.method == 1:
                    # Find the net power corresponding to the indexed time interval.
                    np = find_obj_by_ti(self.netPowers, tis[i])
                    tg = find_obj_by_ti(self.totalGeneration, tis[i])
                    td = find_obj_by_ti(self.totalDemand, tis[i])

                    np = np.value / (tg.value - td.value)

                    # Update the marginal price using subgradient search.
                    xlamda = xlamda - (np * 1e-1) / (10 + k)  # [$/kWh]

                elif self.method == 2:
                    # Get the indexed active system vertices
                    av = [x.value for x in self.activeVertices if x.timeInterval.startTime == tis[i].startTime]

                    # Order the system vertices in the indexed time interval
                    av = order_vertices(av)

                    try:
                        # Find the vertex that bookcases the balance point from the lower side.
                        # Fix a case where all intersection points are on X-axis by using < instead of <=
                        lower_av = [x for x in av if x.power < 0]
                        if len(lower_av) == 0:
                            err_msg = "At {}, there is no point having power < 0".format(tis[i].name)
                        else:
                            lower_av = lower_av[-1]

                        # Find the vertex that bookcases the balance point from the upper side.
                        upper_av = [x for x in av if x.power >= 0]
                        if len(upper_av) == 0:
                            err_msg = "At {}, there is no point having power >= 0".format(tis[i].name)
                        else:
                            upper_av = upper_av[0]

                        # Interpolate the marginal price in the interval using a principle of similar triangles.
                        power_range = upper_av.power - lower_av.power
                        mp_range = upper_av.marginalPrice - lower_av.marginalPrice
                        if power_range == 0:
                            err_msg = "At {}, power range is 0".format(tis[i].name)
                        xlamda = - mp_range * lower_av.power / power_range + lower_av.marginalPrice
                    except:
                        """
                        _log.error(err_msg)
                        _log.error("{} failed to find balance point. "
                                   "Market active vertices: {}".format(mtn.name,
                                                                       [(tis[i].name, x.marginalPrice, x.power)
                                                                        for x in av]))
                        """

                        self.converged = False
                        return

                # Regardless of the method used, variable "xlamda" should now hold the updated marginal price. Assign it
                # to the marginal price value for the indexed active time interval.
                mp.value = xlamda  # [$/kWh]

            # Increment the iteration counter.
            k = k + 1
            if k == 100:
                self.converged = True

            if self.new_data_signal:
                self.converged = False
                return

    def calculate_blended_prices(self):
        """
        Calculate the blended prices for active time intervals.

        The blended price is the averaged weighted price of all locally generated and imported energies. A sum is made
        of all costs of generated and imported energies, which are prices weighted by their corresponding energy. This
        sum is divided by the total generated and imported energy to get the average.

        The blended price does not include supply surplus and may therefore be a preferred representation of price for
        local loads and friendly neighbors, for which myTransactiveNode is not competitive and profit-seeking.
        """

        self.check_intervals()

        time_intervals = self.timeIntervals

        production_costs = self.productionCosts

        # Perform checks on interval primal production costs to ensure smooth calculations. NOTE: This does not check
        # the veracity of the primal costs.

        if production_costs is None or len(production_costs) == 0:
            warn('Production costs have not been calculated.')
            #            _log.warning('Primal costs have not yet been calculated.')
            return

        elif len(time_intervals) > len(production_costs):
            warn('There is at least one time interval without a prod. cost.')
            #            _log.warning('Missing primal costs for active time intervals.')
            return

        elif len(time_intervals) < len(production_costs):
            warn('Extra production cost(s) were found and will be removed.')
            #            _log.warning('Removing primal costs that are not among active time intervals.')
            self.productionCosts = [x for x in self.productionCosts if x.timeInterval in self.timeIntervals]

        for time_interval in time_intervals:
            # Calculate a blended price for this market time interval.
            production_cost = find_obj_by_ti(self.productionCosts, time_interval)  # [$]
            total_generation = find_obj_by_ti(self.totalGeneration, time_interval)  # [kWh]
            blended_price = production_cost / total_generation  # [$/kWh]

            # Remove and replace any blended price in the current time interval.
            self.blendedPrices1 = [x for x in self.blendedPrices1 if x != time_interval]
            interval_value = IntervalValue(self,
                                           time_interval,
                                           self,
                                           MeasurementType.BlendedPrice,
                                           blended_price)
            self.blendedPrices1.append(interval_value)

    # 1911DJH: This next code is really unnecessary now that market timing logic has been simplified. Knowing one
    # market clearing time, one may find the next by simply adding the market clearing interval.
    def update_market_clearing_time(self, cur_time):
        self.marketClearingTime = cur_time.replace(minute=0, second=0, microsecond=0)
        self.nextMarketClearingTime = self.marketClearingTime + timedelta(hours=1)

    def check_intervals(self):
        # Check or create the set of instantiated TimeIntervals in this Market

        # Initialize the first interval starting time in this market.
        starting_times = [self.marketClearingTime + self.deliveryLeadTime]

        # Find the last starting time in the market delivery period.
        last_starting_time = starting_times[0] + self.intervalDuration * (self.intervalsToClear - 1)
        _log.info("starting_times: {0}, last_starting_time: {1}".format(starting_times, last_starting_time))

        # Assign the remaining interval start times in the market delivery period.
        while starting_times[-1] < last_starting_time:
            starting_times.append(starting_times[-1] + self.intervalDuration)
        _log.info("After starting_times: {0}, ".format(starting_times))
        # Index through the needed TimeIntervals based on their start times.
        for starting_time in starting_times:

            # This is a test to see whether the interval exists.
            # 200924DJH: This check is inadequate in Version 3 because starting times are no longer necessarily unique.
            #            The criterion must be revised to make sure the time interval is also in this market.
            # time_intervals = [x for x in self.timeIntervals if x.startTime == starting_time]
            time_intervals = [x for x in self.timeIntervals if x.startTime == starting_time and x.market == self]

            if len(time_intervals) == 0:  # None was found. Append a new time interval to the list of time intervals.
                self.timeIntervals.append(TimeInterval(activation_time=Timer.get_cur_time(),
                                                       duration=self.intervalDuration,
                                                       market=self,
                                                       market_clearing_time=self.marketClearingTime,
                                                       start_time=starting_time
                                                       )
                                          )

            elif len(time_intervals) == 1:  # The TimeInterval already exists. There is really no problem.
                pass  # All is OK. There's no action to take.

            else:  # Duplicate time intervals exist. Remove all but one.
                # First remove ALL the time intervals having the current starting time.
                # 200924DJH: This logic must be revised in Version 3 to make sure OTHER market intervals are not
                #            eliminated.
                # self.timeIntervals = [x for x in self.timeIntervals if x.startTime != starting_time]
                self.timeIntervals = [x for x in self.timeIntervals
                                      if x.startTime != starting_time and x.market != self]
                # Then append one lone time interval for this starting time.
                self.timeIntervals.append(time_intervals[0])

    def check_marginal_prices(self, my_transactive_node, return_prices=None):
        """
        191212DJH: Much of the logic may be simplified upon the introduction of isNewestMarket flag and assertion that
        priorRefinedMarket points to the specific market object that is being refined or corrected.

        Check that marginal prices exist for active time intervals.

        Updated Oct. 2019. Focusses now on initializing marginal prices for the market's time intervals. A priority is
        established for the best available prices from which to initialize new market periods:
        1. If the market interval already has a price, stop. 
        2. If the same time interval exists from a prior market clearing, its price may be used. This can be the case
           where similar successive markets' delivery periods overlap, e.g., a rolling window of 24 hours.
        3. If this market corrects another prior market, its cleared price should be used, e.g., a real-time market
           that corrects day-ahead market periods.
        4. If there exists a price forecast model for this market, this model should be used to forecast price. See
           method Market.model_prices().
        5. If all above methods fail, market periods should be assigned the market's default price. See property
           Market.defaultPrice.
        INPUTS:
        :param my_transactive_node: myTransactiveNode object--this agent
        :param return_prices: For future functionality. (Return prices if True.)
        OUTPUTS:
           populates list of active marginal prices (see class IntervalValue)
        """
        # _log.info("ACTIVE Time intervals {}".format(self.timeIntervals.startTime))

        # Index through active time intervals ti
        for time_interval in self.timeIntervals:
            _log.info("ACTIVE Time intervals {}".format(time_interval.startTime))
            # Initialize the marginal price.
            marginal_price = None

            # METHOD #1: If the market interval already has a price, you're done.
            # Check to see if a marginal price exists in the active time interval.
            interval_value = find_obj_by_ti(self.marginalPrices, time_interval)

            if interval_value is None:

                # METHOD #2. If the same time interval exists from the prior market clearing, its price may be used.
                # This can be the case where similar successive markets' delivery periods overlap, e.g., a rolling
                # window of 24 hours.

                # The time interval will be found in prior markets of this series only if more than one time
                # interval is cleared by each market.
                if not isinstance(self.priorMarketInSeries, type(None)) \
                        and self.priorMarketInSeries is not None \
                        and self.intervalsToClear > 1 \
                        and marginal_price is None:

                    # Look for only the market just prior to this one, based on its market clearing time.
                    prior_market_in_series = self.priorMarketInSeries

                    # Gather the marginal prices from the most recent similar market.
                    prior_marginal_prices = prior_market_in_series.marginalPrices

                    # If a valid marginal price is found in the most recent market,
                    # 200902DJH: This next if statement is problematic because, if false, the elif logic is not used as
                    # it should be. The fix is to use if statements without elif with continue commands after any valid
                    # marginal price assignment.
                    if len(prior_marginal_prices) != 0:

                        # Index through those prior marginal prices,
                        for prior_marginal_price in prior_marginal_prices:

                            # and if any are found such that the currently indexed time interval lies within its
                            # timing,
                            start_time = prior_marginal_price.timeInterval.startTime
                            end_time = start_time + prior_market_in_series.intervalDuration
                            '''_log.debug("Market name: {}, start_time: {}: time_interval.startTime: {} end_time: {} Method 2".format(self.name,
                                                                                                       start_time,
                                                                                                       time_interval.startTime,
                                                                                                       end_time))
                            '''

                            if start_time <= time_interval.startTime < end_time:
                                # _log.debug("Market name: {}, check_marginal_price: {} found time between start and end")
                                # then capture this value for the new marginal price in this time interval,
                                marginal_price = prior_marginal_price.value

                        if marginal_price is not None:
                            self.marginalPrices.append(IntervalValue(calling_object=self,
                                                                     time_interval=time_interval,
                                                                     market=self,
                                                                     measurement_type=MeasurementType.MarginalPrice,
                                                                     value=marginal_price
                                                                     )
                                                       )
                            continue  # 200902DJH: elif logic removed.

                # METHOD #3. If this market corrects another prior market,  its cleared price should be used,
                # e.g., a real-time market that corrects day-ahead market periods. This is indicated by naming a
                # prior market name, which points to a series that is to be corrected.

                # If there is a prior market indicated and a marginal price has not been found,
                # 200902DJH: Change this from elif to if with added continue statement
                if not isinstance(self.marketToBeRefined, type(None)) \
                        and self.marketToBeRefined is not None \
                        and marginal_price is None:
                    # _log.debug("Market name: {}, check_marginal_price: Method 3".format(self.name))
                    # Read the this market's prior refined market name.
                    prior_market = self.marketToBeRefined

                    # Gather the marginal prices from the most recent similar market.
                    prior_marginal_prices = prior_market.marginalPrices

                    # If a valid marginal price is found in the most recent market,
                    if len(prior_marginal_prices) != 0:

                        # Some marginal prices were found in the most recent similar market.
                        marginal_price = None

                        # Index through those prior marginal prices.
                        for prior_marginal_price in prior_marginal_prices:
                            # If any are found such that the currently indexed time interval lies within its timing,
                            start_time = prior_marginal_price.timeInterval.startTime
                            end_time = start_time + prior_market.intervalDuration
                            '''_log.debug("Market name: {}, check_marginal_price: start_time: {}, time_interval.startTime: {} end_time: {}".format(self.name,
                                                                                                                                                start_time,
                                                                                                                                                time_interval.startTime,
                                                                                                                                                end_time))
                            '''
                            if start_time <= time_interval.startTime < end_time:
                                # capture this value as the marginal price in this time interval.
                                marginal_price = prior_marginal_price.value

                        if marginal_price is not None:
                            self.marginalPrices.append(IntervalValue(calling_object=self,
                                                                     time_interval=time_interval,
                                                                     market=self,
                                                                     measurement_type=MeasurementType.MarginalPrice,
                                                                     value=marginal_price
                                                                     )
                                                       )
                            continue  # 200902DJH: elif logic removed.

                # METHOD #4. Use the price model to predict marginal price. See method Market.model_prices().
                # 200902DJH: Change elif to if with continue statement.
                if self.priceModel is not None and marginal_price is None:
                    marginal_price = self.model_prices(time_interval.startTime)[0]
                    self.marginalPrices.append(IntervalValue(calling_object=self,
                                                             time_interval=time_interval,
                                                             market=self,
                                                             measurement_type=MeasurementType.MarginalPrice,
                                                             value=marginal_price
                                                             )
                                               )
                    continue  # 200902DJH: elif logic removed.

                # METHOD 5. If all above methods fail, market periods should be assigned the market's default price.
                # 200902DJH: Change elif to if with continue statement.
                if self.defaultPrice is not None and marginal_price is None:
                    marginal_price = self.defaultPrice
                    self.marginalPrices.append(IntervalValue(calling_object=self,
                                                             time_interval=time_interval,
                                                             market=self,
                                                             measurement_type=MeasurementType.MarginalPrice,
                                                             value=marginal_price
                                                             )
                                               )
                    continue  # 200902DJH: elif logic removed.

                # METHOD 6: If all the above logic fails to assign the marginal price, assign as None.
                self.marginalPrices.append(IntervalValue(calling_object=self,
                                                         time_interval=time_interval,
                                                         market=self,
                                                         measurement_type=MeasurementType.MarginalPrice,
                                                         value=marginal_price
                                                         )
                                           )

        return None

    def schedule(self, my_transactive_node):
        """
        Process called to
        (1) invoke all models to update the scheduling of their resources, loads, or neighbor
        (2) converge to system balance using sub-gradient search.
        :param: my_transactive_node: TransactiveNode object--this agent
        """

        # Call each local asset to schedule itself.
        for local_asset in my_transactive_node.localAssets:
            local_asset.schedule(self)

        # Call each neighbor to schedule itself.
        for neighbor in my_transactive_node.neighbors:
            neighbor.schedule(self)

    def sum_vertices(self, my_transactive_node, time_interval, object_to_exclude=None):
        """
        Create system vertices with systemF information for a single time interval. An optional argument allows the
        exclusion of a transactive neighbor object, which is useful for transactive records and their corresponding
        demand or supply curves. This utility method should be used for creating transactive signals (by excluding the
        neighbor object), and for visualization tools that review the local system's net supply/demand curve.
        :param: my_transactive_node:
        :param: time_interval:
        :param: object_to_exclude:
        :returns: vertices: list of Vertex objects in the given time interval.
        """
        # TODO: This has evolved to be a stand-alone, static function. Change to a static function.
        # Initialize a list of marginal prices mps at which vertices will be created.
        marginal_price_list = []
        # Index through the active neighbor objects
        for i in range(len(my_transactive_node.neighbors)):
            neighbor = my_transactive_node.neighbors[i]

            # Jump out of this iteration if neighbor model nm happens to be the "object to exclude"
            if object_to_exclude is not None and neighbor == object_to_exclude:
                continue

            # Find the neighbor model's active vertices in this time interval
            interval_values = find_objs_by_ti(neighbor.activeVertices, time_interval)  #

            if len(interval_values) > 0:
                # At least one active vertex was found in the time interval. Extract the vertices from the interval
                # values.
                vertices = [x.value for x in interval_values]  #

                if len(vertices) == 1:
                    # There is one vertex. This means the power is constant for this neighbor. Enforce the policy of
                    # assigning infinite marginal price to constant vertices.
                    marginal_prices = [float("inf")]  # [$/kWh]

                else:
                    # There are multiple vertices. Use the marginal price values from the vertices themselves.
                    marginal_prices = [x.marginalPrice for x in vertices]  # [$/kWh]

                marginal_price_list.extend(marginal_prices)  # marginal prices [$/kWh]

        for i in range(len(my_transactive_node.localAssets)):
            # Change the reference to the corresponding local asset model
            asset = my_transactive_node.localAssets[i]  # a local asset model

            # Jump out of this iteration if local asset model nm happens to be
            # the "object to exclude"
            if object_to_exclude is not None and asset == object_to_exclude:
                continue

            # Find the local asset model's active vertices in this time interval.
            interval_values = find_objs_by_ti(asset.activeVertices, time_interval)

            if len(interval_values) > 0:
                # At least one active vertex was found in the time interval. Extract the vertices from the interval
                # values.
                vertices = [x.value for x in interval_values]  #
                # Extract the marginal prices from the vertices.
                if len(vertices) == 1:
                    # There is one vertex. This means the power is constant for this local asset. Enforce the policy of
                    # assigning infinite marginal price to constant vertices.
                    marginal_prices = [float("inf")]  # [$/kWh]

                else:
                    # There are multiple vertices. Use the marginal price values from the vertices themselves.
                    marginal_prices = [x.marginalPrice for x in vertices]  # marginal prices [$/kWh]

                marginal_price_list.extend(marginal_prices)  # [$/kWh]

        # A list of vertex marginal prices have been created.
        # Sort the marginal prices from least to greatest.
        marginal_price_list.sort()  # [$/kWh]
        # Ensure that no more than two vertices will be created at the same marginal price. The third output of function
        # unique() is useful here because it is the index of unique entries in the original vector.
        # [~, ~, ind] = unique(mps)  # index of unique vector contents

        # Create a new vector of marginal prices. The first two entries are accepted because they cannot violate the
        # two-duplicates rule. The vector is padded with zeros, which should be computationally efficient. A counter is
        # used and should be incremented with new vector entries.
        if len(marginal_price_list) >= 3:
            marginal_price_list_new = [marginal_price_list[0],
                                       marginal_price_list[1]]
        else:
            # _log.debug("market name {} sum_vertices: 5 b".format(self.name))
            marginal_price_list_new = list(marginal_price_list)

        # Index through the indices and append the new list only when there are fewer than three duplicates.
        for i in range(2, len(marginal_price_list)):
            if marginal_price_list[i] != marginal_price_list[i - 1] \
                    or marginal_price_list[i - 1] != marginal_price_list[i - 2]:
                marginal_price_list_new.append(marginal_price_list[i])

        # Trim the new list of marginal prices mps_new that had been padded with zeros and rename it mps.
        # mps = mps_new  # marginal prices [$/kWh]

        # 180907DJH: THIS CONDITIONAL (COMMENTED OUT) WAS NOT QUITE RIGHT. A MARGINAL PRICE AT INFINITY IS MEANINGFUL
        #             ONLY IF THERE IS EXACTLY ONE VERTEX-NO FLEXIBILITY. OTHERWISE, IT IS SUPERFLUOUS AND SHOULD BE
        #             ELIMINATED. THIS MUCH SIMPLER APPROACH ENSURES THAT INFINITY IS RETAINED ONLY IF THERE IS A SINGLE
        #             MARGINAL PRICE. OTHERWISE, INFINITY MARGINAL PRICES ARE TRIMMED FROM THE SET.
        marginal_price_list = [marginal_price_list_new[0]]
        for i in range(1, len(marginal_price_list_new)):
            if marginal_price_list_new[i] != float('inf'):
                marginal_price_list.append(marginal_price_list_new[i])

        # A clean list of marginal prices has been created
        # Correct assignment of vertex power requires a small offset of any duplicate values. Index through the new list
        # of marginal prices again.
        for i in range(1, len(marginal_price_list)):
            if marginal_price_list[i] == marginal_price_list[i - 1]:
                # A duplicate has been found. Offset the first of the two by a very small number.
                marginal_price_list[i - 1] = marginal_price_list[i - 1] - 1e-10  # [$/kWh]

        # Create vertices at the marginal prices. Initialize the list of vertices.
        vertices = []
        # Index through the cleaned list of marginal prices
        for i in range(len(marginal_price_list)):
            # Create a vertex at the indexed marginal price value
            interval_value = Vertex(marginal_price_list[i], 0, 0)

            # Initialize the net power pwr and total production cost pc at the indexed vertex
            vertex_power = 0.0  # [avg.kW]
            vertex_production_cost = 0.0  # [$]

            # Include power and production costs from neighbor models. Index through the active neighbor models.
            for k in range(len(my_transactive_node.neighbors)):
                neighbor = my_transactive_node.neighbors[k]

                if neighbor == object_to_exclude:
                    continue

                # Calculate the indexed neighbor model's power at the indexed marginal price and time interval. NOTE:
                # This must not corrupt the "scheduled power" at the converged system's marginal price.
                neighbors_power = production(neighbor, marginal_price_list[i], time_interval)  # [avg.kW]

                # Calculate the neighbor model's production cost at the indexed marginal price and time interval, and
                # add it to the sum production cost pc. NOTE: This must not corrupt the "scheduled" production cost for
                # this neighbor model.
                vertex_production_cost = vertex_production_cost \
                                         + prod_cost_from_vertices(neighbor, time_interval, neighbors_power)

                # Add the neighbor model's power to the sum net power at this vertex.
                vertex_power = vertex_power + neighbors_power  # [avg.kW]

            # Include power and production costs from local asset models. Index through the local asset models.
            for k in range(len(my_transactive_node.localAssets)):
                asset = my_transactive_node.localAssets[k]

                if asset == object_to_exclude:
                    continue

                # Calculate the power for the indexed local asset model at the indexed marginal price and time interval.
                assets_power = production(asset, marginal_price_list[i], time_interval)  # [avg.kW]

                # Find the indexed local asset model's production cost and add it to the sum of production cost pc for
                # this vertex.
                vertex_production_cost = vertex_production_cost \
                                         + prod_cost_from_vertices(asset, time_interval, assets_power)  # [$]

                # Add local asset power p to the sum net power pwr for this vertex.
                vertex_power = vertex_power + assets_power  # [avg.kW]

            # Save the sum production cost pc into the new vertex iv
            interval_value.cost = vertex_production_cost  # [$]

            # Save the net power pwr into the new vertex iv
            interval_value.power = vertex_power  # [avg.kW]

            # Append Vertex iv to the list of vertices
            vertices.append(interval_value)

        return vertices

    def update_costs(self, my_transactive_node):
        """
        Sum the production and dual costs from all modeled local resources, local loads, and neighbors, and then sum
        them for the entire duration of the time horizon being calculated.

        PRESUMPTIONS:
        - Dual costs have been created and updated for all active time intervals for all neighbor objects
        - Production costs have been created and updated for all active time intervals for all asset objects

        INPUTS:
        :param: my_transactive_node - TransactiveNode object--this agent

        OUTPUTS:
        - Updates Market.productionCosts - an array of total production cost in each active time interval
        - Updates Market.totalProductionCost - the sum of production costs for the entire future time horizon of
          active time intervals
        - Updates Market.dualCosts - an array of dual cost for each active time interval
        - Updates Market.totalDualCost - the sum of all the dual costs for the entire future time horizon of active
          time intervals
        """

        # Call each LocalAsset to update its costs.
        for local_asset in my_transactive_node.localAssets:
            local_asset.update_costs(self)

        # Call each Neighbor to update its costs.
        for neighbor in my_transactive_node.neighbors:
            neighbor.update_costs(self)

        for time_interval in self.timeIntervals:

            sum_dual_cost = 0.0  # [$]

            sum_production_cost = 0.0  # [$]

            for local_asset in my_transactive_node.localAssets:
                interval_value = find_obj_by_ti(local_asset.dualCosts, time_interval)
                sum_dual_cost = sum_dual_cost + interval_value.value  # [$]

                interval_value = find_obj_by_ti(local_asset.productionCosts, time_interval)
                sum_production_cost = sum_production_cost + interval_value.value  # [$]

            for neighbor in my_transactive_node.neighbors:
                interval_value = find_obj_by_ti(neighbor.dualCosts, time_interval)
                sum_dual_cost = sum_dual_cost + interval_value.value  # [$]

                interval_value = find_obj_by_ti(neighbor.productionCosts, time_interval)
                sum_production_cost = sum_production_cost + interval_value.value  # [$]

            # Check to see if a sum dual cost exists for this market in the indexed time interval.
            interval_value = find_obj_by_ti(self.dualCosts, time_interval)

            if interval_value is None:
                # No dual cost was found for the indexed time interval. Create an IntervalValue and assign it the sum
                # dual cost for the indexed time interval.
                interval_value = IntervalValue(self, time_interval, self, MeasurementType.DualCost, sum_dual_cost)  #

                # Append the dual cost to the list of interval dual costs
                self.dualCosts.append(interval_value)  # IntervalValues

            else:
                # A sum dual cost value exists in the indexed time interval. Simply reassign its value.
                interval_value.value = sum_dual_cost  # [$]

            # Check to see if a sum production cost exists in the indexed time interval
            interval_value = find_obj_by_ti(self.productionCosts, time_interval)

            if interval_value is None:
                # No sum production cost was found for the indexed time interval. Create an IntervalValue and assign it
                # the sum production cost for the indexed time interval.
                interval_value = IntervalValue(self, time_interval, self, MeasurementType.ProductionCost,
                                               sum_production_cost)

                # Append the production cost to the list of interval production costs
                self.productionCosts.append(interval_value)

            else:
                # A sum production cost value exists in the indexed time interval. Simply reassign its value.
                interval_value.value = sum_production_cost  # sum production cost [$]

        # Sum total dual cost for the entire forward horizon.
        self.totalDualCost = sum([x.value for x in self.dualCosts])  # [$]

        # Sum total primal cost for the entire time horizon
        self.totalProductionCost = sum([x.value for x in self.productionCosts])  # [$]

    def update_supply_demand(self, my_transactive_node):
        """
        For each time interval, sum the power that is generated, imported, consumed, or exported for all modeled local
        resources, neighbors, and local load.
        :param: my_transactive_node: TransactiveNode object--this agent
        """

        for time_interval in self.timeIntervals:

            total_generation = 0.0  # [avg.kW]

            total_demand = 0.0  # [avg.kW]

            for local_asset in my_transactive_node.localAssets:
                interval_value = find_obj_by_ti(local_asset.scheduledPowers, time_interval)
                scheduled_power = interval_value.value  # [avg.kW]

                if scheduled_power > 0:  # Generation case: Add positive powers to total generation.
                    total_generation = total_generation + scheduled_power  # [avg.kW]

                else:  # Demand case: Add negative powers to total demand.
                    total_demand = total_demand + scheduled_power  # [avg.kW]

            for neighbor in my_transactive_node.neighbors:
                # Find scheduled power for this neighbor in the indexed time interval.
                interval_value = find_obj_by_ti(neighbor.scheduledPowers, time_interval)
                scheduled_power = interval_value.value  # [avg.kW]

                if scheduled_power > 0:  # Generation case: Add positive power to total generation.
                    total_generation = total_generation + scheduled_power  # [avg.kW]

                else:  # Demand case: Add negative power to total demand.
                    total_demand = total_demand + scheduled_power  # [avg.kW]

            # At this point, total generation and importation and total demand and exportation have been calculated for
            # the indexed time interval.

            # Save the total generation in the indexed time interval.

            # Check whether total generation exists for the indexed time interval
            interval_value = find_obj_by_ti(self.totalGeneration, time_interval)

            if interval_value is None:
                # No total generation was found in the indexed time interval. Create an interval value.
                interval_value = IntervalValue(self, time_interval, self, MeasurementType.TotalGeneration,
                                               total_generation)

                # Append the total generation to the list of total generations.
                self.totalGeneration.append(interval_value)

            else:
                # Total generation exists in the indexed time interval. Simply reassign its value.
                interval_value.value = total_generation

            # Calculate and save total demand for this time interval. NOTE that this formulation includes both
            # consumption and exportation among total load.

            # Check whether total demand exists for the indexed time interval.
            interval_value = find_obj_by_ti(self.totalDemand, time_interval)
            if interval_value is None:
                # No total demand was found in the indexed time interval. Create an interval value.
                interval_value = IntervalValue(self, time_interval, self, MeasurementType.TotalDemand, total_demand)

                # Append the total demand to the list of total demands.
                self.totalDemand.append(interval_value)

            else:
                # Total demand was found in the indexed time interval. Simply reassign it.
                interval_value.value = total_demand

            # Update net power for the interval. Net power is the sum of total generation and total load. By convention,
            # generation power is positive and consumption is negative.

            # Check whether net power exists for the indexed time interval
            interval_value = find_obj_by_ti(self.netPowers, time_interval)

            if interval_value is None:  # Net power is not found in the indexed time interval. Create an interval value.
                interval_value = IntervalValue(self, time_interval, self, MeasurementType.NetPower,
                                               total_generation + total_demand)

                # Append the net power, an IntervalValue, to the list of net powers.
                self.netPowers.append(interval_value)

            else:  # A net power was found in the indexed time interval. Simply reassign its value.
                interval_value.value = total_generation + total_demand

        np = [(x.timeInterval.name, x.value) for x in self.netPowers]
        #        _log.debug("{} market netPowers are: {}".format(self.name, np))

    def view_net_vertices(self):
        """
        If within an operating system that supports graphical data representations, this method plots a market's active
        vertices.
        """
        # TODO: This needs to be reviewed. This should plot vertex power as a function of vertex price for a single
        #       market time interval. I don't see that such a plot can be had from this method. Methods in the base
        #       Transactive Network Template should be independent of platform. This depends on Volttron.
        # 200211DJH: See method see_net_curve that provides a superior representation.
        time_intervals = self.timeIntervals

        def by_start_times(time_interval_list):
            return time_interval_list.startTime

        time_intervals.sort(key=by_start_times)  # 200207DJH: Is this actually used by the method??

        import plotly.express as px

        import pandas as pd
        df = pd.read_csv('https://raw.githubusercontent.com/plotly/datasets/master/finance-charts-apple.csv')

        fig = px.line(df, x='Date', y='AAPL.High')
        fig.show()

    def see_net_curve(self, time_interval=None, show=True):
        """
        Visualize the net supply/demand curve in this market for a given market period.
        This should remain independent from any implementation platform, which probably means it must be called by an
        active display interface.
        :param time_interval:
        :param show: [Boolean] Set False to not show figure (useful for testing)
        :return:
        """
        positive_infinity = float('Inf')
        negative_infinity = float('-Inf')
        price_extension = 0.1  # [$/kWh]

        if time_interval is None:
            time_interval = self.timeIntervals[0]

        vertices = [x.value for x in self.activeVertices if x.timeInterval == time_interval]

        vertices = order_vertices(vertices)

        # Extend the curve toward negative infinity marginal price.
        if vertices[0].marginalPrice == negative_infinity:
            vertices[0].marginalPrice = -price_extension
        elif vertices[0].marginalPrice == positive_infinity:
            vertices = [Vertex(-price_extension, 0, vertices[0].power)] + vertices
        else:
            vertices = [Vertex(vertices[0].marginalPrice - price_extension, 0, vertices[0].power)] + vertices

        # Extend the curve toward positive infinity marginal price.
        if vertices[-1].marginalPrice == positive_infinity:
            vertices[-1].marginalPrice = price_extension
        else:
            vertices = vertices + [Vertex(vertices[-1].marginalPrice + price_extension, 0, vertices[-1].power)]

        marginal_prices = [x.marginalPrice for x in vertices]
        net_powers = [x.power for x in vertices]

        # fig, ax = plt.subplots()
        # ax.plot(marginal_prices, net_powers)
        #
        # ax.set(xlabel='marginal price [$/kWh]',
        #        ylabel='average power [kW]',
        #        title=(self.name + 'Net Supply/Demand Curve ' + time_interval.name)
        #        )
        # ax.grid()
        #
        # if show is True:
        #     plt.show()

    def see_marginal_prices(self, show=True):
        """
        Visualize this market's current marginal prices for its active time intervals.
        This should remain independent from any implementation platform, which probably means it must be called by an
        active display interface.
        :param show: [Boolean] Set False to not show figure (useful for testing)
        :return:
        """

        marginal_prices = [x.value for x in self.marginalPrices]
        marginal_prices.append(marginal_prices[-1])

        start_times = [x.timeInterval.startTime for x in self.marginalPrices]
        start_times.append(start_times[-1] + self.intervalDuration)

        # fig, ax = plt.subplots()
        # ax.step(start_times, marginal_prices, where='post')
        #
        # ax.set(xlabel='interval starting times',
        #        ylabel='marginal prices [$/kWh]',
        #        title=(self.name + ' Marginal Prices')
        #        )
        # ax.grid()
        #
        # if show is True:
        #     plt.show()

    def getDict(self):
        market_dict = {
            "market_name": self.name,
            "marketSeriesId": self.marketSeriesName,
            "totalDemand": self.totalDemand,
            "totalDualCost": self.totalDualCost,
            "totalGeneration": self.totalGeneration,
            "totalProductionCost": self.totalProductionCost
        }
        return market_dict

    def getMarketSeriesDict(self):
        market_series_dict = {
            "market_name": self.name,
            "marketSeriesId": self.marketSeriesName,
            "method": self.method,
            "commitment": self.commitment,
            "duration": self.duration,
            "initialMarketState": self.initialMarketState,
            "totalProductionCost": self.totalProductionCost,
            "dualityGapThreshold": self.dualityGapThreshold,
            "marketClearingInterval": self.marketClearingInterval,
            "futureHorizon": self.futureHorizon,
            "intervalDuration": self.intervalDuration,
            "intervalsToClear": self.intervalsToClear,
            "marketOrder": self.marketOrder
        }
        return market_series_dict
