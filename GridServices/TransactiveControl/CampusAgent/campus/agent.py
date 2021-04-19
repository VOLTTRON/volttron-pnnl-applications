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

import os
import sys
import logging
import datetime
from dateutil import parser

from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)

from TNT_Version1.TNSAgent.tns.helpers import *
from TNT_Version1.TNSAgent.tns.measurement_type import MeasurementType
from TNT_Version1.TNSAgent.tns.measurement_unit import MeasurementUnit
from TNT_Version1.TNSAgent.tns.meter_point import MeterPoint
from TNT_Version1.TNSAgent.tns.market import Market
from TNT_Version1.TNSAgent.tns.market_state import MarketState
from TNT_Version1.TNSAgent.tns.neighbor import Neighbor
from TNT_Version1.TNSAgent.tns.local_asset import LocalAsset
from TNT_Version1.TNSAgent.tns.local_asset_model import LocalAssetModel
from TNT_Version1.TNSAgent.tns.myTransactiveNode import myTransactiveNode
from TNT_Version1.TNSAgent.tns.neighbor_model import NeighborModel
from TNT_Version1.TNSAgent.tns.temperature_forecast_model import TemperatureForecastModel
from TNT_Version1.TNSAgent.tns.solar_pv_resource import SolarPvResource
from TNT_Version1.TNSAgent.tns.solar_pv_resource_model import SolarPvResourceModel
from TNT_Version1.TNSAgent.tns.openloop_pnnl_load_predictor import OpenLoopPnnlLoadPredictor
from TNT_Version1.TNSAgent.tns.vertex import Vertex
from TNT_Version1.TNSAgent.tns.timer import Timer

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'

class CampusAgent(Agent, myTransactiveNode):
    def __init__(self, config_path, **kwargs):
        Agent.__init__(self, **kwargs)
        myTransactiveNode.__init__(self)

        self.config_path = config_path
        self.config = utils.load_config(config_path)
        self.name = self.config.get('name')
        self.market_cycle_in_min = int(self.config.get('market_cycle_in_min', 60))
        self.duality_gap_threshold = float(self.config.get('duality_gap_threshold', 0.01))
        self.building_names = self.config.get('buildings', [])
        self.building_powers = self.config.get('building_powers')
        self.db_topic = self.config.get("db_topic", "tnc")
        self.PV_max_kW = float(self.config.get("PV_max_kW"))
        self.city_loss_factor = float(self.config.get("city_loss_factor"))

        self.demand_threshold_coef = float(self.config.get('demand_threshold_coef'))
        self.monthly_peak_power = float(self.config.get('monthly_peak_power'))

        self.neighbors = []

        self.city_supply_topic = "{}/city/campus/supply".format(self.db_topic)
        self.building_demand_topic = "/".join([self.db_topic, "{}/campus/demand"])
        self.campus_demand_topic = "{}/campus/city/demand".format(self.db_topic)
        self.campus_supply_topic = "/".join([self.db_topic, "campus/{}/supply"])
        self.solar_topic = "/".join([self.db_topic, "campus/pv"])
        self.system_loss_topic = "{}/{}/system_loss".format(self.db_topic, self.name)
        self.dc_threshold_topic = "{}/{}/dc_threshold_topic".format(self.db_topic, self.name)
        self.price_topic = "{}/{}/marginal_prices".format(self.db_topic, self.name)

        self.reschedule_interval = timedelta(minutes=10, seconds=1)

        self.simulation = self.config.get('simulation', False)
        self.simulation_start_time = parser.parse(self.config.get('simulation_start_time'))
        self.simulation_one_hour_in_seconds = int(self.config.get('simulation_one_hour_in_seconds'))

        Timer.created_time = datetime.now()
        Timer.simulation = self.simulation
        Timer.sim_start_time = self.simulation_start_time
        Timer.sim_one_hr_in_sec = self.simulation_one_hour_in_seconds

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
            neighbor.model.receive_transactive_signal(self, demand_curves)
            self.balance_market(1, start_of_cycle, fail_to_converged, neighbor)
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

        self.city.model.receive_transactive_signal(self, supply_curves)

        if start_of_cycle:
            self.balance_market(1, start_of_cycle, fail_to_converged)

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
                        dt = datetime.now()
                        # Schedule to rerun after 5 minutes if it is in the same hour and is the first reschedule
                        next_run_dt = dt + self.reschedule_interval
                        if dt.hour == next_run_dt.hour and run_cnt >= 1:
                            _log.debug("{} reschedule to run at {}".format(self.name, next_run_dt))
                            self.core.schedule(next_run_dt, self.balance_market, run_cnt + 1)
            prices = market.marginalPrices

            # There is a case where the balancing happens at the end of the hour and continues to the next hour, which
            # creates 26 values. Get the last 25 values.
            prices = prices[-25:]
            prices = [x.value for x in prices]
            self.vip.pubsub.publish(peer='pubsub',
                                        topic=self.price_topic,
                                        message={'prices': prices,
                                                 'current_time': format_timestamp(Timer.get_cur_time())
                                                 }
                                        )
        else:
            _log.debug("Market balancing sub-problem failed.")
            self.city.model.prep_transactive_signal(market, self)
            self.city.model.send_transactive_signal(self, self.campus_demand_topic, start_of_cycle)

    def init_objects(self):
        # Add meter
        meter = MeterPoint()
        meter.measurementType = MeasurementType.PowerReal
        meter.name = 'CampusElectricityMeter'
        meter.measurementUnit = MeasurementUnit.kWh
        self.meterPoints.append(meter)

        # Add weather forecast service
        weather_service = TemperatureForecastModel(self.config_path, self)
        self.informationServiceModels.append(weather_service)

        # Add inelastive asset
        inelastive_load = LocalAsset()
        inelastive_load.name = 'InelasticBuildings'  # Campus buildings that are not responsive
        inelastive_load.maximumPower = 0  # Remember that a load is a negative power [kW]
        inelastive_load.minimumPower = -2 * 8200  # Assume twice the average PNNL load [kW]

        # Add inelastive asset model
        inelastive_load_model = OpenLoopPnnlLoadPredictor(weather_service)
        inelastive_load_model.name = 'InelasticBuildingsModel'
        inelastive_load_model.engagementCost = [0, 0, 0]  # Transition costs irrelevant
        inelastive_load_model.defaultPower = -6000  # [kW]
        inelastive_load_model.defaultVertices = [Vertex(0, 0, -6000.0, 1)]

        # Cross-reference asset & asset model
        inelastive_load_model.object = inelastive_load
        inelastive_load.model = inelastive_load_model

        # Add solar PV asset
        solar_pv = SolarPvResource()
        solar_pv.maximumPower = self.PV_max_kW  # [avg.kW]
        solar_pv.minimumPower = 0.0  # [avg.kW]
        solar_pv.name = 'SolarPv'
        solar_pv.description = '120 kW solar PV site on the campus'

        # Add solar PV asset model
        solar_pv_model = SolarPvResourceModel()
        solar_pv_model.cloudFactor = 1.0  # dimensionless
        solar_pv_model.engagementCost = [0, 0, 0]
        solar_pv_model.name = 'SolarPvModel'
        solar_pv_model.defaultPower = 0.0  # [avg.kW]
        solar_pv_model.defaultVertices = [Vertex(0, 0, 30.0, True)]
        solar_pv_model.costParameters = [0, 0, 0]
        solar_pv_model.inject(self, power_topic=self.solar_topic)

        # Cross-reference asset & asset model
        solar_pv.model = solar_pv_model
        solar_pv_model.object = solar_pv

        # Add inelastive and solar_pv as campus' assets
        self.localAssets.extend([inelastive_load, solar_pv])

        # Add Market
        market = Market()
        market.name = 'dayAhead'
        market.commitment = False
        market.converged = False
        market.defaultPrice = 0.04  # [$/kWh]
        market.dualityGapThreshold = self.duality_gap_threshold  # [0.02 = 2#]
        market.initialMarketState = MarketState.Inactive
        market.marketOrder = 1  # This is first and only market
        market.intervalsToClear = 1  # Only one interval at a time
        market.futureHorizon = timedelta(hours=24)  # Projects 24 hourly future intervals
        market.intervalDuration = timedelta(hours=1)  # [h] Intervals are 1 h long
        market.marketClearingInterval = timedelta(hours=1)  # [h]
        market.marketClearingTime = Timer.get_cur_time().replace(hour=0,
                                                                 minute=0,
                                                                 second=0,
                                                                 microsecond=0)  # Aligns with top of hour
        market.nextMarketClearingTime = market.marketClearingTime + timedelta(hours=1)
        self.markets.append(market)

        # City object
        city = Neighbor()
        city.name = 'CoR'
        city.description = 'City of Richland (COR) electricity supplier node'
        city.maximumPower = 20000  # Remember loads have negative power [avg.kW]
        city.minimumPower = 0  # [avg.kW]
        city.lossFactor = self.city_loss_factor

        # City model
        city_model = NeighborModel()
        city_model.name = 'CoR_Model'
        city_model.location = self.name
        city_model.transactive = True
        city_model.defaultPower = 10000  # [avg.kW]
        city_model.defaultVertices = [Vertex(0.046, 160, 0, True),
                                      Vertex(0.048,
                                             160 + city.maximumPower * (0.046 + 0.5 * (0.048 - 0.046)),
                                             city.maximumPower, True)]
        city_model.costParameters = [0, 0, 0]
        city_model.demand_threshold_coef = self.demand_threshold_coef
        city_model.demandThreshold = self.monthly_peak_power
        city_model.inject(self,
                          system_loss_topic=self.system_loss_topic,
                          dc_threshold_topic=self.dc_threshold_topic)

        # Cross-reference object & model
        city_model.object = city
        city.model = city_model
        self.city = city

        # Add city as campus' neighbor
        self.neighbors.append(city)

        # Add buildings
        for bldg_name in self.building_names:
            bldg_neighbor = self.make_bldg_neighbor(bldg_name)
            self.neighbors.append(bldg_neighbor)

    def make_bldg_neighbor(self, name):
        bldg_powers = self.building_powers[name]

        # Create neighbor
        bldg = Neighbor()
        bldg.name = name
        bldg.maximumPower = bldg_powers[0]  # Remember loads have negative power [avg.kW]
        bldg.minimumPower = bldg_powers[1]  # [avg.kW]
        _log.debug("{} has minPower of {} and maxPower of {}".format(bldg.name,
                                                                     bldg.minimumPower, bldg.maximumPower))

        # Create neighbor model
        bldg_model = NeighborModel()
        bldg_model.name = name + '_Model'
        bldg_model.location = self.name
        bldg_model.convergenceThreshold = 0.02
        bldg_model.friend = True
        bldg_model.transactive = True
        bldg_model.costParameters = [0, 0, 0]

        # This is different building to building
        bldg_model.defaultPower = bldg.minimumPower/2  # bldg_powers[2]  # [avg.kW]
        bldg_model.defaultVertices = [Vertex(float("inf"), 0, bldg_model.defaultPower, True)]

        # Cross reference object & model
        bldg.model = bldg_model
        bldg_model.object = bldg

        return bldg


def main(argv=sys.argv):
    try:
        utils.vip_main(CampusAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
