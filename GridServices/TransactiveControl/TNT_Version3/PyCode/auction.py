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
from logging import warning
from .market import Market
from .direction import Direction
from .market_types import MarketTypes
from warnings import warn
from .timer import Timer
from .helpers import production
from .interval_value import IntervalValue
from .measurement_type import MeasurementType

from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)

utils.setup_logging()
_log = logging.getLogger(__name__)

class Auction(Market):
    """
    Auction class child of Market
    An Auction object may be a formal driver of myTransactiveNode's responsibilities within a formal auction. At least
    one Market must exist (see the firstMarket object) to drive the timing with which new TimeIntervals are created.
    """
    def __init__(self):
        # Properties and methods inherited from Market class:
        super(Auction, self).__init__(market_type=MarketTypes.auction)

    def transition_from_active_to_negotiation(self, my_transactive_node):
        """
        This method overwrites the inherited one from class Market.
        200520DJH: Corrected logic so assets are called to schedule their powers only once during this state transition.
        :param my_transactive_node: my transactive node agent object
        :return: None
        """

        # 200730DJH: This will initialize all the marginal price for each time interval using the best available
        #            strategy. I would have preferred not doing so, but so many logic exceptions have been created by
        #            not having existing marginal prices. Point 1: The auction object owns prices only for its active
        #            time intervals. Local assets may predict more future prices if they need to. Point 2: This initial
        #            marginal price should be replaced by the auction mechanisms.
        self.check_marginal_prices(my_transactive_node, return_prices=None)

        # Set the auction convergence flag false prior to the Negotiation market state.
        self.converged = False
        #_log.debug("Market name: {} transition_from_active_to_negotiation".format(self.name))
        # In an auction, each asset is called upon once per market clearing time to schedule its power.
        for x in range(len(my_transactive_node.localAssets)):
            local_asset = my_transactive_node.localAssets[x]  # the indexed local asset

            # Set each local asset's schedule flag false prior to the Negotiation market state.
            local_asset.scheduleCalculated = False

            # Call on the local asset to schedule its power.
            local_asset.schedule(self)

            _log.debug(f"{self.name}: transition_from_active_to_negotiation")

            self.publish_records(my_transactive_node)
            # Publish local asset info
            # SN: No need, publish transactive operation instead
            '''topic = "{}/{}".format(my_transactive_node.local_asset_topic,
                                   my_transactive_node.localAssets[x].name)
            msg = local_asset.getDict()
            headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
            _log.debug(
                "AUCTION:transition_from_active_to_negotiation: {} and info: {}".format(topic, msg))
            my_transactive_node.vip.pubsub.publish("pubsub",topic, headers, msg)
            '''
        return None

    # TODO: On transition to the negotiation state, make sure the auction is not converged.
    def while_in_negotiation(self, my_transactive_node):
        """"
        The result of scheduling is that each local asset will create Vertex structs representing its inelastic or
        elastic power consumption. It may further provide at least two additional vertices that represent its price
        elasticity. In an auction, this scheduling is performed for only local assets. Exchanges with neighbor
        agents are determined in later states using time-coordinated transactive signals.
        These actions are conducted only until a satisfactory converged auction has been found.
        """
        # This logic is only meaningful before the market convergence flag is set true.
        if self.converged is False:
            #_log.debug("Market name: {} while_in_negotiation. Checking asset powers have been scheduled".format(self.name))
            # An Auction should check that all LocalAsset objects have finished scheduling their powers.
            all_calculated = True
            for x in range(len(my_transactive_node.localAssets)):
                local_asset = my_transactive_node.localAssets[x]
                if not local_asset.scheduleCalculated:
                    all_calculated = False
                    break

            # If, in fact, all the assets have scheduled their powers, the auction market has nothing left to do within
            # the Negotiation market state, and the market convergence flag is set true.
            if all_calculated is True:
                #_log.debug("Market name: {} while_in_negotiation. ALL ASSETS HAVE BEEN SCHEDULED".format(self.name))
                topics = []
                self.converged = True
                self._stateIsCompleted = True
                headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
                for local_asset in my_transactive_node.localAssets:
                    # Publish local asset info
                    topic = "{}/{}".format(my_transactive_node.local_asset_topic,
                                           local_asset.name)
                    msg = local_asset.getDict()
                    headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
                    #_log.debug(
                    #    "AUCTION:while_in_negotiation: {} and info: {}".format(topic, msg))
                    #my_transactive_node.vip.pubsub.publish("pubsub", topic, headers, msg)

                # 210208DJH: This new flag must be set true to leave this state and allow the next transition.

        return None

    # TODO: Consider using TransactiveNode property "converged" to keep track of those downstream agents that have \
    #  received their transactive signals. This would require setting the convergence flag to False prior to this state.
    def while_in_market_lead(self, my_transactive_node):
        """
        For activities that should happen while a market object is in its "MarketLead" market state. This method may be
        overwritten by child classes of Market to create alternative market behaviors during this market state.
        :param my_transactive_node: my transactive node agent object
        :return: None
        """
        #_log.debug("Market name: {} while_in_market_lead.".format(self.name))
        # TODO: This could use a convergence flag logic to assert that all bids are received and offers sent.
        # Identify the set of neighbor agents that are identified as "upstream" and "downstream".

        upstream_agents = [x for x in my_transactive_node.neighbors if x.upOrDown == Direction.upstream]

        downstream_agents = [x for x in my_transactive_node.neighbors if x.upOrDown == Direction.downstream]

        unassigned_agents = [x for x in my_transactive_node.neighbors if x.upOrDown != Direction.upstream
                                                                        and x.upOrDown != Direction.downstream]

        for x in range(len(unassigned_agents)):
            print('Warning: Assigning neighbor ' + unassigned_agents[x].name + ' the downstream direction')
            warn('Assigning neighbor ' + unassigned_agents[x].name + ' the downstream direction')
            unassigned_agents[x].upOrDown = Direction.downstream

        if len(upstream_agents) != 1:
            print('Warning: There should be precisely one upstream neighbor for an auction market')
            raise RuntimeWarning('There should be precisely one upstream neighbor for an auction market')

        # Initialize a flag true if all downstream bids have been received. An aggregate auction bid can be constructed
        # only after all bids have been received from downstream agents (and from local assets, of course):
        all_received = True                                                 # a local flag to this method

        #_log.debug("Market name: {} while_in_market_lead. Trying to publish neighbor info".format(self.name))

        # Index through the downstream agents.
        for da in range(len(downstream_agents)):
            downstream_agent = downstream_agents[da]                        # the indexed downstream agent

            # Establish a list for the time intervals for which records have been received by this downstream agent.
            received_time_interval_names = []

            for rs in range(len(downstream_agent.receivedSignal)):
                received_record = downstream_agent.receivedSignal[rs]       # the indexed received record

                received_time_interval_names.append(received_record.timeInterval)

            # Seek any active market time intervals that were not among the received transactive records.
            missing_interval_names = [x.name for x in self.timeIntervals
                                      if x.name not in received_time_interval_names]

            # If any time intervals are found to be missing for this downstream agent,
            if len(missing_interval_names):
                all_received = False
                _log.info("Market name: {} while_in_market_lead downstream_agent NAME: {}, missing_interval_names: {}".format(self.name,
                                                                                                                downstream_agent.name,
                                                                                                                missing_interval_names))
                # and call on the downstream agent model to try and receive the signal again:
                _log.info(f"Before calling receive_transactive_signal: {missing_interval_names}, {downstream_agent.name}")
                downstream_agent.receive_transactive_signal(my_transactive_node, self, downstream_agent.receivedCurves)

        # If all expected bids have been received from downstream agents, have the downstream neighbor models update
        # their vertices and schedule themselves. The result of this will be an updated set of active vertices for each
        # downstream agent.
        if all_received is True:
            _log.info("Market name: {} while_in_market_lead Received all transactive signals from downstream agents".format(self.name))
            # For each downstream agent,
            for da in range(len(downstream_agents)):
                downstream_agent = downstream_agents[da]            # the indexed downstream agent
                _log.info("Market name: {} downstream_agent: NAME: {}".format(self.name,
                                                                              downstream_agent.name))
                # Have each downstream agent model schedule itself. (E.g., schedule power and schedule elasticity via
                # active vertices.
                downstream_agent.schedule(self)

            # Prepare an aggregated bid for the upstream agent if it is a transactive agent. If the upstream agent is
            # transactive,

            if upstream_agents is None or len(upstream_agents) == 0:
                _log.warning('Warning: There must exist one upstream neighbor agent in an auction.')
                # raise Warning('There must exist one upstream neighbor agent in an auction.')
            else:
                upstream_agent = upstream_agents[0]                             # Clear indexing of lone upstream agent

                if upstream_agent.transactive is True:
                    # Call on the upstream agent model  to prepare its transactive signal.
                    upstream_agent.prep_transactive_signal(self, my_transactive_node)

                    # Send the transactive signal (i.e., aggregated bid) to the upstream agent if it is a transactive agent.
                    upstream_agent.send_transactive_signal(self, my_transactive_node, upstream_agent.publishTopic)

            # 210208DJH: This new flag must be set true to leave this state and allow the next transition.
            #            TODO: We don't have foolproof verification that the upstream agent was sent this signal,
            #             but this might be improved later. This seems like the right place because it's confirmed that
            #             all needed signals have been received.
            self._stateIsCompleted = True

    def while_in_delivery_lead(self, my_transactive_node):
        """
        For activities that should happen while a market object is in its "DeliveryLead" market state. This method may
        be overwritten by child classes of Market to create alternative market behaviors during this market state.
        mtn: my transactive node agent object
        """
        # Identify the set of neighbor agents that is identified as "downstream" (i.e., toward demand side) and the set
        # that is "upstream" (i.e., toward generation).
        downstream_agents = []
        upstream_agents = []

        downstream_agents = [x for x in my_transactive_node.neighbors if x.upOrDown == Direction.downstream]

        upstream_agents = [x for x in my_transactive_node.neighbors if x.upOrDown == Direction.upstream]

        unassigned_agents = [x for x in my_transactive_node.neighbors if x.upOrDown != Direction.upstream
                                                                                and x.upOrDown != Direction.downstream]

        for x in range(len(unassigned_agents)):
            _log.warning('Warning: Assigning neighbor ' + unassigned_agents[x].name + ' the downstream direction')
            _log.warning('Assigning neighbor ' + unassigned_agents[x].name + ' the downstream direction')
            unassigned_agents[x].upOrDown = Direction.downstream

        if len(upstream_agents) != 1:
            _log.warning('Warning: There should be precisely one upstream neighbor for an auction market')
            warn('There should be precisely one upstream neighbor for an auction market')

        # Initialize a flag true if all downstream bids have been received. An aggregate auction bid can be constructed
        # only after all bids have been received from downstream agents (and from local assets, of course):
        all_received = True                                                 # a local parameter to this method

        # Clarify that we are referencing the lone upstream agent model.
        upstream_agent = upstream_agents[0]

        if upstream_agent.transactive is True:
            # Create a list of the time interval names among the received transactive signal:
            received_time_intervals = []

            # TODO: Consider using property "converged" as a flag for upstream agents that have received their \
            #  transactive signals. The flag must be set false in the transition to this state.
            for rts in range(len(upstream_agent.receivedSignal)):
                received_record = upstream_agent.receivedSignal[rts]        # the indexed received record

                received_time_intervals.append(received_record.timeInterval)

            # Check whether any active market time intervals are not among the received record intervals.
            missing_time_intervals = [x.name for x in self.timeIntervals if x.name not in received_time_intervals]
            _log.debug("Market name: {} while_in_delivery_lead Received all transactive signals from upstream agents".format(self.name))

            # If time intervals are missing among the upstream agent's transactive records,
            if missing_time_intervals:
                all_received = False

                # Call on the upstream agent model to try and receive the signal again.
                upstream_agent.receive_transactive_signal(my_transactive_node, self, upstream_agent.receivedCurves)

        # If offers have been received for all active market time intervals from the upstream agent,
        # 200618DJH: I think this is correct up to this point, but I had left out some very important steps of the
        #            auction market balancing.

        if all_received is True:
            # Update this Neighbor's active vertices, which is entirely completed from its recently received transactive
            # signal and its records.
            # 200702DJH: Why is this misspelling of "vertices" permitted here???????????????
            # upstream_agent.update_verices(self) #???????????????
            _log.debug("while_in_delivery_lead: update vertices {}".format(self.name))
            upstream_agent.update_vertices(self)
            # Sum all the agent's active local asset and neighbor vertices and determine the LMP at which local power is
            # balanced.
            _log.debug("while_in_delivery_lead: balance:{}".format(self.name))

            self.balance(my_transactive_node)
            # Have the upstream agent neighbor model now schedule its power, based on the local agent's calculated LMPs.
            _log.debug("while_in_delivery_lead:  schedule_power()".format(self.name))

            upstream_agent.schedule_power(self)
            # Re-schedule local asset powers now that the local market price is cleared. This may affect flexible assets
            # if the cleared price differs from the predicted one. Inelastic assets will not be affected.
            # 200702DJH: This following  code revision allows local assets to find their scheduled power using helper
            #            method production(), which interpolates among the local assets' active vertices to find the
            #            power at the cleared market clearing price.
            local_assets = [x for x in my_transactive_node.localAssets]
            for i in range(len(local_assets)):
                local_asset = local_assets[i]
                # local_asset.schedule_power(self) ** COMMENT OUT: TOO CUMBERSOME **
                for time_interval in self.timeIntervals:
                    price = [x.value for x in self.marginalPrices if x.timeInterval == time_interval]
                    power = production(local_asset, price[0], time_interval)
                    # 201012DJH: Shwetha discovered that teh list of powers was continuing to grow because this method
                    #            is called multiple times. Normally, the scheduled power should already exist and can
                    #            simply have its value changed.                    
                    scheduled_power = [x for x in local_asset.scheduledPowers if x.timeInterval == time_interval]
                    _log.debug("while_in_delivery_lead: local asset loop, name: {}, len: {}".format(local_assets[i].name, len(scheduled_power)))

                    if len(scheduled_power) == 0:
                        local_asset.scheduledPowers.append(IntervalValue(calling_object=self,
                                                                         time_interval=time_interval,
                                                                         market=self,
                                                                         measurement_type=
                                                                            MeasurementType.ScheduledPower,
                                                                         value=power
                                                                         )
                                                           )
                    elif len(scheduled_power) == 1:
                        scheduled_power[0].value = power
                    else:
                        scheduled_power[0].value = power
                        warn('A duplicate scheduled power was found for asset ' + str(local_asset.name)
                             + ' in time interval ' + str(time_interval.name))

            # For each downstream agent,
            for x in range(len(downstream_agents)):
                downstream_agent = downstream_agents[x] # the indexed downstream agent

                # 201731DJH: Now that the LMP has been determined, power may be scheduled for this downstream neighbor.
                downstream_agent.schedule_power(self)

                # prepare an aggregated offer for the downstream agent,
                downstream_agent.prep_transactive_signal(self, my_transactive_node)
                _log.debug("SN: while_in_delivery_lead() DOWNSTREAM_AGENT PUBLISH TOPIC: {}".format(
                    downstream_agent.publishTopic))
                _log.debug("SN: while_in_delivery_lead() sending transactive signal to downstream agent: {}".format(
                    downstream_agent.name))

                # and send it a transactive signal (i.e., an offer).
                downstream_agent.send_transactive_signal(self, my_transactive_node, downstream_agent.publishTopic)
            # 210208DJH: This new flag must be set true to leave this state and allow the next transition.
            self._stateIsCompleted = True

    def transition_from_inactive_to_active(self, my_transactive_node):
        """
        For activities that should accompany a market object's transition from market state "Inactive" to
        "Active"
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """
        _log.debug(f"{self.name}: transition_from_inactive_to_active")
        #super(Auction, self).transition_from_inactive_to_active(my_transactive_node)
        self.publish_records(my_transactive_node)
        return None

    def transition_from_negotiation_to_market_lead(self, my_transactive_node):
        """
        For activities that should accompany a market object's transition from market state "Negotiation" to
        "MarketLead."
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """
        _log.debug(f"{self.name}: transition_from_negotiation_to_market_lead")
        #super(Auction, self).transition_from_negotiation_to_market_lead(my_transactive_node)
        self.publish_records(my_transactive_node)
        return None

    def transition_from_market_lead_to_delivery_lead(self, my_transactive_node):
        """
        For activities that should accompany a market object's transition from market state "MarketLead" to
        "DeliveryLead," (i.e., the clearing of the market).
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """
        _log.debug(f"{self.name}: transition_from_market_lead_to_delivery_lead")
        #super(Auction, self).transition_from_market_lead_to_delivery_lead(my_transactive_node)
        self.publish_records(my_transactive_node)
        return None

    def transition_from_delivery_lead_to_delivery(self, my_transactive_node):
        """
        :param my_transactive_node: transactive node object--this agent
        :return: None
        """
        _log.debug(f"{self.name}: transition_from_delivery_lead_to_delivery")
        super(Auction, self).transition_from_delivery_lead_to_delivery(my_transactive_node)
        headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
        msg = dict()
        msg['tnt_market_name'] = self.name
        my_transactive_node.vip.pubsub.publish(peer='pubsub',
                                               topic=my_transactive_node.market_balanced_price_topic,
                                               headers=headers,
                                               message=msg)
        self.publish_records(my_transactive_node)
        return None

    def transition_from_reconcile_to_expired(self, my_transactive_node):
        """
        For activities that should accompany a market object's transition from market state "Reconcile" to "Expired."
        :param my_transactive_node: transactive node object--the agent
        :return: None
        """
        _log.debug("transition_from_reconcile_to_expired")
        super(Auction, self).transition_from_reconcile_to_expired(my_transactive_node)
        self.publish_records(my_transactive_node)
        return None

    def publish_records(self, my_transactive_node, upstream_agents=None, downstream_agents=None):
        headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
        transactive_operation = dict()
        transactive_operation['prices'] = list()
        transactive_operation['demand'] = dict()
        transactive_operation['demand']['bid'] = dict()

#        _log.debug("AUCTION: BEFORE: info: {}".format(transactive_operation))
        for idx, p in enumerate(self.marginalPrices):
            transactive_operation['prices'].append((utils.format_timestamp(p.timeInterval.startTime), p.value))

        for neighbor in my_transactive_node.neighbors:
            transactive_operation['demand']['bid'][neighbor.name] = neighbor.getDict()['sent_signal']

        if self.name.startswith('Real-Time'):
            transactive_operation['demand']['actual'] = dict()
            transactive_operation['demand']['actual']['neighbor'] = dict()
            transactive_operation['demand']['actual']['assets'] = dict()

            for neighbor in my_transactive_node.neighbors:
                transactive_operation['demand']['actual']['neighbor'][neighbor.name] = \
                    neighbor.getDict()['received_signal']
            for asset in my_transactive_node.localAssets:
                transactive_operation['demand']['actual']['assets'][asset.name] = asset.getDict()['vertices']

        topic = "{}/{}".format(my_transactive_node.transactive_operation_topic, self.name)
        my_transactive_node.vip.pubsub.publish(peer='pubsub', topic=topic,
                                               headers=headers, message=transactive_operation)
#        _log.debug("AUCTION: Publishing on market topic: {} and info: {}".format(topic, transactive_operation))

