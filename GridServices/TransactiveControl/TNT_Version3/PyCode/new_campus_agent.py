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

# }}}

# import os

# TODO: Re-enable the logging and volttron functions in new_campus_agent.py

import sys
import logging
import datetime
from dateutil import parser
from datetime import timedelta

from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)


from helpers import *
from measurement_type import MeasurementType
from measurement_unit import MeasurementUnit
from meter_point import MeterPoint
# from market import Market
from market_state import MarketState
from neighbor_model import Neighbor
from TransactiveNode import TransactiveNode
from temperature_forecast_model import TemperatureForecastModel
from solar_pv_resource_model import SolarPvResource
from openloop_pnnl_load_predictor import OpenLoopPnnlLoadPredictor
from .vertex import Vertex
from .timer import Timer
from .day_ahead_auction import DayAheadAuction

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


class CampusAgent(Agent, TransactiveNode):
    def __init__(self, config_path, **kwargs):
        Agent.__init__(self, **kwargs)
        TransactiveNode.__init__(self)

        # self.config_path = config_path
        self.config = utils.load_config(config_path)
        self.name = self.config.get('name')
        self.market_cycle_in_min = int(self.config.get('market_cycle_in_min', 60))
        self.duality_gap_threshold = float(self.config.get('duality_gap_threshold', 0.01))
        self.building_names = self.config.get('buildings', [])
        self.building_powers = self.config.get('building_powers')
        self.db_topic = self.config.get("db_topic", "tnc")
        self.PV_max_kW = float(self.config.get("PV_max_kW"))
        self.city_loss_factor = float(self.config.get("city_loss_factor"))

        self.demandThresholdCoef = float(self.config.get('demand_threshold_coef'))
        self.monthly_peak_power = float(self.config.get('monthly_peak_power'))

        self.neighbors = []

        self.city_supply_topic = "{}/city/campus/supply".format(self.db_topic)
        self.building_demand_topic = "/".join([self.db_topic, "{}/campus/demand"])
        self.campus_demand_topic = "{}/campus/city/demand".format(self.db_topic)
        self.campus_supply_topic = "/".join([self.db_topic, "campus/{}/supply"])
        self.solar_topic = "/".join([self.db_topic, "campus/pv"])
        self.system_loss_topic = "{}/{}/system_loss".format(self.db_topic, self.name)
        self.dc_threshold_topic = "{}/{}/dc_threshold_topic".format(self.db_topic, self.name)

        self.reschedule_interval = timedelta(minutes=10, seconds=1)

        self.simulation = self.config.get('simulation', False)
        # self.simulation_start_time = parser.parse(self.config.get('simulation_start_time'))
        self.simulation_one_hour_in_seconds = int(self.config.get('simulation_one_hour_in_seconds'))

        Timer.created_time = Timer.get_cur_time()
        Timer.simulation = self.simulation
        Timer.sim_start_time = self.simulation_start_time
        Timer.sim_one_hr_in_sec = self.simulation_one_hour_in_seconds
        self._stop_agent = False

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        # Add other objects: assets, services, neighbors
        self.init_objects()

        # Subscriptions
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.city_supply_topic,
                                  callback=self.new_supply_signal)

        for bldg in self.building_names:
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=self.building_demand_topic.format(bldg),
                                      callback=self.new_demand_signal)

        # SN: Added for new state machine based TNT implementation
        self.core.spawn_later(5, self.state_machine_loop)

    def new_demand_signal(self, peer, sender, bus, topic, headers, message):
        _log.debug("At {}, {} receives new demand records: {}".format(Timer.get_cur_time(),
                                                                        self.name, message))
        building_name = message['source']
        demand_curves = message['curves']
        start_of_cycle = message['start_of_cycle']
        fail_to_converged = message['fail_to_converged']

        neighbors = [n for n in self.neighbors if n.name == building_name]
        if len(neighbors) == 1:
            neighbor = neighbors[0]

            neighbor.receivedCurves = demand_curves
            # 191219DJH: This logic should be deferred to the new market state machine, please.
            # neighbor.receive_transactive_signal(self, demand_curves)
            # self.balance_market(1, start_of_cycle, fail_to_converged, neighbor)
            # self.markets[0].events(self)
        else:
            _log.error("{}: There are {} building(s) with name {}."
                       .format(self.name, len(neighbors), building_name))
            _log.error("Neighbors are: {}".format([x.name for x in self.neighbors]))
            _log.error("Message is: {}".format(message))
            _log.error("Check value of 'name' key in the config file for building {}.".format(building_name))

    def new_supply_signal(self, peer, sender, bus, topic, headers, message):
        _log.debug("At {}, {} receives new supply records: {}".format(Timer.get_cur_time(),
                                                                     self.name, message))
        source = message['source']
        supply_curves = message['curves']
        start_of_cycle = message['start_of_cycle']
        fail_to_converged = message['fail_to_converged']
        # SN: Added for new TNT state machine based implementation
        self.city.receivedCurves = supply_curves
        # 191219DJH: this logic should be deferred to the new market state machine, please.
        # self.city.receive_transactive_signal(self, supply_curves)
        # if start_of_cycle:
            # self.balance_market(1, start_of_cycle, fail_to_converged)

    # 191219DJH: The logic in this method should almost entirely be deferred to the market state machine, please.
    '''
    def balance_market(self, run_cnt, start_of_cycle=False, fail_to_converged=False, fail_to_converged_neighbor=None):
        market = self.markets[0]  # Assume only 1 TNS market per node
        market.signal_new_data = True
        market.balance(self)  # Assume only 1 TNS market per node

        if market.converged:
            _log.debug("TNS market {} balanced successfully.".format(market.name))

            # Sum all the powers as will be needed by the net supply/demand curve.
            market.assign_system_vertices(self)

            # Send only if either of the 2 conditions below occurs:
            # 1) Model balancing did not converge
            # 2) A new cycle (ie. begin of hour)
            for n in self.neighbors:
                # If the neighbor failed to converge (eg., building1 failed to converge)
                if n == fail_to_converged_neighbor and n is not None:
                    n.model.prep_transactive_signal(market, self)
                    topic = self.campus_demand_topic
                    if n != self.city:
                        topic = self.campus_supply_topic.format(n.name)
                    n.model.send_transactive_signal(self, topic, start_of_cycle)
                    _log.debug("NeighborModel {} sent records.".format(n.model.name))

                else:
                    # Always send signal downstream at the start of a new cyle
                    if start_of_cycle:
                        if n != self.city:
                            n.model.prep_transactive_signal(market, self)
                            topic = self.campus_supply_topic.format(n.name)
                            n.model.send_transactive_signal(self, topic, start_of_cycle)
                            _log.debug("NeighborModel {} sent records.".format(n.model.name))
                    else:
                        _log.debug("Not start of cycle. Check convergence for neighbor {}.".format(n.model.name))
                        n.model.check_for_convergence(market)
                        if not n.model.converged:
                            n.model.prep_transactive_signal(market, self)
                            topic = self.campus_demand_topic
                            if n != self.city:
                                topic = self.campus_supply_topic.format(n.name)
                            n.model.send_transactive_signal(self, topic, start_of_cycle)
                            _log.debug("NeighborModel {} sent records.".format(n.model.name))
                        else:
                            _log.debug("{} ({}) did not send records due to check_for_convergence()."
                                       .format(n.model.name, self.name))

            # Schedule rerun balancing if not in simulation mode
            if not self.simulation:
                # For start_of_cyle=True, the code above always send signal to neighbors so don't need to reschedule
                # Schedule rerun if any neighbor is not converged
                if not start_of_cycle:
                    if not all([n.model.converged for n in self.neighbors]):
                        dt = Timer.get_cur_time()
                        # Schedule to rerun after 5 minutes if it is in the same hour and is the first reschedule
                        next_run_dt = dt + self.reschedule_interval
                        if dt.hour == next_run_dt.hour and run_cnt >= 1:
                            _log.debug("{} reschedule to run at {}".format(self.name, next_run_dt))
                            self.core.schedule(next_run_dt, self.balance_market, run_cnt + 1)
        else:
            _log.debug("Market balancing sub-problem failed.")
            self.city.model.prep_transactive_signal(market, self)
            self.city.model.send_transactive_signal(self, self.campus_demand_topic, start_of_cycle)
            '''

    def init_objects(self):
        # Add meter
        meter = self.make_campus_meter()

        # Add weather forecast service
        weather_service = TemperatureForecastModel(self.config_path, self)
        self.informationServiceModels.append(weather_service)

        # Add local asset to represent bulk inelastic campus load
        inelastic_load = self.make_inelastic_load(weather_service)

        # Add solar PV asset
        solar_pv = self.make_solar_pv_resource()

        # Add Market
        market = self.make_day_ahead_market()

        # Add city object
        # 191218DJH: Why is the city neighbor uniquely made a property of the campus agent?? is this proper, legal?
        self.city = self.make_city_neighbor()

        # Add buildings
        for bldg_name in self.building_names:
            bldg_neighbor = self.make_bldg_neighbor(bldg_name)

    def make_bldg_neighbor(self, name):
        bldg_powers = self.building_powers[name]

        # Create a building neighbor
        # 191219DJH: There are no longer separate object and model classes for neighbors.
        bldg = Neighbor()
        bldg.name = name
        bldg.maximumPower = bldg_powers[0]                      # Remember loads have negative power [avg.kW]
        bldg.minimumPower = bldg_powers[1]                      # [avg.kW]
        _log.debug("{} has minPower of {} and maxPower of {}".format(bldg.name,
                                                                     bldg.minimumPower, bldg.maximumPower))
        bldg.location = self.name
        bldg.convergenceThreshold = 0.02
        bldg.friend = True
        bldg.transactive = True
        bldg.costParameters = [0, 0, 0]
        bldg.upOrDown = 'downstream'                    # Newly required for agents participating in auction markets

        # This is different building to building
        bldg.defaultPower = bldg.minimumPower/2                 # bldg_powers[2]  # [avg.kW]
        bldg.defaultVertices = [Vertex(float("inf"), 0, bldg.defaultPower, True)]
        # SN: Added to integrate new state machine logic with VOLTTRON
        # This topic will be used to send transactive signal
        bldg.publishTopic = self.campus_supply_topic

        self.neighbors.append(bldg)

        return bldg

    def make_campus_meter(self):
        meter = MeterPoint(
                            measurement_type=MeasurementType.PowerReal,
                            name='CampusElectricityMeter',
                            measurement_unit=MeasurementUnit.kWh)

        self.meterPoints.append(meter)

        return meter

    def make_inelastic_load(self, weather_service):
        # 191219DJH: There are no longer separate object and model classes for local assets.
        inelastic_load = OpenLoopPnnlLoadPredictor(weather_service)
        inelastic_load.temperature_forecaster = weather_service
        inelastic_load.name = 'InelasticBuildings'          # Campus buildings that are not responsive
        inelastic_load.maximumPower = 0                     # Remember that a load is a negative power [kW]
        inelastic_load.minimumPower = -2 * 8200             # Assume twice the average PNNL load [kW]
        inelastic_load.engagementCost = [0, 0, 0]           # Transition costs irrelevant
        inelastic_load.defaultPower = -6000                 # [kW]
        inelastic_load.defaultVertices = [Vertex(0, 0, -6000.0, 1)]

        self.localAssets.append(inelastic_load)

        return inelastic_load

    def make_solar_pv_resource(self):
        # 191219DJH: Asset object and model classes are no longer separated. The properties of class SolarPvResourc()
        # have been moved to class SolarPvResourceModel().
        solar_pv = SolarPvResource()
        solar_pv.maximumPower = self.PV_max_kW                      # [avg.kW]
        solar_pv.minimumPower = 0.0                                 # [avg.kW]
        solar_pv.name = 'SolarPv'
        solar_pv.description = '120 kW solar PV site on the campus'

        solar_pv.cloudFactor = 1.0                                  # dimensionless
        solar_pv.engagementCost = [0, 0, 0]
        solar_pv.defaultPower = 0.0                                 # [avg.kW]
        solar_pv.defaultVertices = [Vertex(0, 0, 30.0, True)]
        solar_pv.costParameters = [0, 0, 0]
        # solar_pv.inject(self, power_topic=self.solar_topic)

        # Add solar_pv as local campus asset
        self.localAssets.append(solar_pv)

        return solar_pv

    def make_day_ahead_market(self):
        # 191219DJH: It will be important that different agents' markets are similarly, if not identically,
        # instantiated. I.e., the day ahead market at the city must be defined just like the ones at the campus and
        # building nodes. Otherwise, the negotiations between the network agents will probably not work within the
        # context of the new market state machines.
        market = DayAheadAuction()                          # A child of class Auction.
        market.commitment = True                            # To be corrected by 15-minute real-time auction markets
        market.converged = False
        market.defaultPrice = 0.0428                        # [$/kWh]
        market.dualityGapThreshold = self.duality_gap_threshold  # [0.02 = 2#]
        market.initialMarketState = MarketState.Inactive
        market.marketOrder = 1                              # This is first market
        market.intervalsToClear = 24                        # 24 hours are cleared altogether
        market.futureHorizon = timedelta(hours=24)          # Projects 24 hourly future intervals
        market.intervalDuration = timedelta(hours=1)        # [h] Intervals are 1 h long
        market.marketClearingInterval = timedelta(days=1)   # The market clears daily
        market.marketSeriesName = "Day-Ahead_Auction"       # Prepends future market object names
        market.method = 2                                   # Use simpler interpolation solver

        # This times must be defined the same for all network agents.
        market.deliveryLeadTime = timedelta(hours=1)
        market.negotiationLeadTime = timedelta(minutes=15)
        market.marketLeadTime = timedelta(minutes=15)
        market.activationLeadTime = timedelta(minutes=0)

        # Determine the current and next market clearing times in this market:
        current_time = Timer.get_cur_time()

        # Presume first delivery hour starts at 10:00 each day:
        delivery_start_time = current_time.replace(hour=10, minute=0, second=0, microsecond=0)

        # The market clearing time must occur a delivery lead time prior to delivery:
        market.marketClearingTime = delivery_start_time - market.deliveryLeadTime

        # If it's too late today to begin the market processes, according to all the defined lead times, skip to the
        # next market object:
        if current_time > market.marketClearingTime - market.marketLeadTime \
                                                        - market.negotiationLeadTime - market.activationLeadTime:
            market.marketClearingTime = market.marketClearingTime + market.marketClearingInterval

        # Schedule the next market clearing for another market cycle later:
        market.nextMarketClearingTime = market.marketClearingTime + market.marketClearingInterval

        dt = str(market.marketClearingTime)
        market.name = market.marketSeriesName.replace(' ', '_') + '_' + dt[:19]

        market.isNewestMarket = True

        self.markets.append(market)

        return market

        # IMPORTANT: The real-time correction markets are instantiated by the day-ahead markets as they become
        # instantiated.

    def make_city_neighbor(self):
        # 191219DJH: There are no longer separate neighbor object and model classes.
        city = Neighbor()
        city.name = 'CoR'
        city.description = 'City of Richland (COR) electricity supplier node'
        city.maximumPower = 20000                                   # Remember loads have negative power [signed avg.kW]
        city.minimumPower = 0  # [avg.kW]
        city.lossFactor = self.city_loss_factor
        city.location = self.name
        city.transactive = True
        city.defaultPower = 10000                                   # [signed avg.kW]
        city.defaultVertices = [
                                Vertex(0.046, 160, 0, True),
                                Vertex(0.048, 160 + city.maximumPower * (0.046 + 0.5 * (0.048 - 0.046)),
                                city.maximumPower, True)]
        city.costParameters = [0, 0, 0]
        city.demandThresholdCoef = self.demandThresholdCoef
        city.demandThreshold = self.monthly_peak_power
        city.upOrDown = 'upstream'  # Newly required for agents participating in auction markets.
        city.inject(self,
                    system_loss_topic=self.system_loss_topic,
                    dc_threshold_topic=self.dc_threshold_topic)

        # SN: Added to integrate new state machine logic with VOLTTRON
        # This topic will be used to send transactive signal
        city.publishTopic = self.campus_demand_topic
        # Add city as campus' neighbor
        self.neighbors.append(city)

        return city

    def state_machine_loop(self):
        # 191218DJH: This is the entire timing logic. It relies on current market object's state machine method events()
        import time
        while not self._stop_agent:  # a condition may be added to provide stops or pauses.
            for i in range(len(self.markets)):
                self.markets[i].events(self)
                # NOTE: A delay may be added, but the logic of the market(s) alone should be adequate to drive system
                # activities
                time.sleep(1)

    @Core.receiver('onstop')
    def onstop(self, sender, **kwargs):
        self._stop_agent = True


# noinspection PyUnresolvedReferences
def main(argv=sys.argv):
    try:
        utils.vip_main(CampusAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
