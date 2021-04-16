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

import os
import sys
import logging
from datetime import datetime
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
from TNT_Version1.TNSAgent.tns.openloop_richland_load_predictor import OpenLoopRichlandLoadPredictor
from TNT_Version1.TNSAgent.tns.bulk_supplier_dc import BulkSupplier_dc
from TNT_Version1.TNSAgent.tns.transactive_record import TransactiveRecord
from TNT_Version1.TNSAgent.tns.vertex import Vertex
from TNT_Version1.TNSAgent.tns.timer import Timer

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


class CityAgent(Agent, myTransactiveNode):
    def __init__(self, config_path, **kwargs):
        Agent.__init__(self, **kwargs)
        myTransactiveNode.__init__(self)

        self.config_path = config_path
        self.config = utils.load_config(config_path)
        self.name = self.config.get('name')
        self.market_cycle_in_min = int(self.config.get('market_cycle_in_min', 60))
        self.duality_gap_threshold = float(self.config.get('duality_gap_threshold', 0.01))
        self.supplier_loss_factor = float(self.config.get('supplier_loss_factor'))

        self.demand_threshold_coef = float(self.config.get('demand_threshold_coef'))
        self.monthly_peak_power = float(self.config.get('monthly_peak_power'))

        self.neighbors = []

        self.db_topic = self.config.get("db_topic", "tnc")
        self.campus_demand_topic = "{}/campus/city/demand".format(self.db_topic)
        self.city_supply_topic = "{}/city/campus/supply".format(self.db_topic)
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

    def get_exp_start_time(self):
        one_second = timedelta(seconds=1)
        if self.simulation:
            next_exp_time = datetime.now() + one_second
        else:
            now = datetime.now()
            ten_mins = timedelta(minutes=10)
            next_exp_time = now + ten_mins
            if next_exp_time.hour == now.hour:
                next_exp_time = now + one_second
            else:
                _log.debug("{} did not run onstart because it's too late. Wait for next hour.".format(self.name))
                next_exp_time = next_exp_time.replace(minute=0, second=0, microsecond=0)
        return next_exp_time

    def get_next_exp_time(self, cur_exp_time, cur_analysis_time):
        one_hour_simulation = timedelta(seconds=self.simulation_one_hour_in_seconds)
        one_hour = timedelta(hours=1)
        one_minute = timedelta(minutes=1)

        cur_analysis_time = cur_analysis_time.replace(minute=0, second=0, microsecond=0)
        if self.simulation:
            next_exp_time = cur_exp_time + one_hour_simulation
        else:
            cur_exp_time = cur_exp_time.replace(minute=0, second=0, microsecond=0)
            next_exp_time = cur_exp_time + one_hour + one_minute

        next_analysis_time = cur_analysis_time + one_hour + one_minute

        return next_exp_time, next_analysis_time

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        # Add other objects: assets, services, neighbors
        self.init_objects()

        # Subscriptions
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.campus_demand_topic,
                                  callback=self.new_demand_signal)

        # Schedule to run 1st time if now is not too close to the end of hour. Otherwise, schedule to run next hour.
        next_exp_time = self.get_exp_start_time()
        next_analysis_time = next_exp_time
        if self.simulation:
            next_analysis_time = self.simulation_start_time

        _log.debug("{} schedule to run at exp_time: {} analysis_time: {}".format(self.name,
                                                                                 next_exp_time,
                                                                                 next_analysis_time))
        self.core.schedule(next_exp_time, self.schedule_run,
                           format_timestamp(next_exp_time),
                           format_timestamp(next_analysis_time), True)

    def schedule_run(self, cur_exp_time, cur_analysis_time, start_of_cycle=False):
        """
        Run when first start or run at beginning of hour
        :return:
        """
        # Balance
        market = self.markets[0]  # Assume only 1 TNS market per node
        market.balance(self)
        prices = market.marginalPrices
        prices = prices[-25:]
        prices = [x.value for x in prices]
        _time = format_timestamp(Timer.get_cur_time())
        self.vip.pubsub.publish(peer='pubsub',
                                topic=self.price_topic,
                                message={'prices': prices,
                                         'current_time': _time
                                         }
                                )
        self.campus.model.prep_transactive_signal(market, self)
        self.campus.model.send_transactive_signal(self, self.city_supply_topic,
                                                  start_of_cycle=start_of_cycle)

        # Schedule to run next hour with start_of_cycle = True
        cur_exp_time = parser.parse(cur_exp_time)
        cur_analysis_time = parser.parse(cur_analysis_time)
        next_exp_time, next_analysis_time = self.get_next_exp_time(cur_exp_time, cur_analysis_time)
        self.core.schedule(next_exp_time, self.schedule_run,
                           format_timestamp(next_exp_time),
                           format_timestamp(next_analysis_time),
                           start_of_cycle=True)

    def new_demand_signal(self, peer, sender, bus, topic, headers, message):
        _log.debug("At {}, {} receives new demand records: {}".format(Timer.get_cur_time(),
                                                                     self.name, message))
        demand_curves = message['curves']

        # Should not do anything with start_of_cycle signal
        self.campus.model.receive_transactive_signal(self, demand_curves)  # atm, only one campus

        self.balance_market(1)

    def balance_market(self, run_cnt):
        market = self.markets[0]  # Assume only 1 TNS market per node
        market.signal_new_data = True
        market.balance(self)

        if market.converged:
            # Sum all the powers as will be needed by the net supply/demand curve.
            market.assign_system_vertices(self)

            # Check to see if it is ok to send signals
            self.campus.model.check_for_convergence(market)
            if not self.campus.model.converged:
                _log.debug("NeighborModel {} sends records to campus.".format(self.campus.model.name))
                self.campus.model.prep_transactive_signal(market, self)
                self.campus.model.send_transactive_signal(self, self.city_supply_topic, start_of_cycle=False)
            else:
                # Schedule rerun balancing only if not in simulation mode
                if not self.simulation:
                    dt = datetime.now()
                    _log.debug("{} ({}) did not send records due to check_for_convergence()".format(self.name, dt))
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

    def init_objects(self):
        # Add meter
        meter = MeterPoint()
        meter.measurementType = MeasurementType.PowerReal
        meter.name = 'CoRElectricMeter'
        meter.measurementUnit = MeasurementUnit.kWh
        self.meterPoints.append(meter)

        # Add weather forecast service
        weather_service = TemperatureForecastModel(self.config_path, self)
        self.informationServiceModels.append(weather_service)

        # Add inelastive asset
        # Source: https://www.ci.richland.wa.us/home/showdocument?id=1890
        #   Residential customers: 23,768
        #   Electricity sales in 2015:
        # Total:     100.0#   879,700,000 kWh     100,400 avg. kW)
        # Resident:   46.7    327,200,000          37,360
        # Gen. Serv.: 38.1    392,300,000          44,790
        # Industrial: 15.2    133,700,000          15,260
        # Irrigation:  2.4     21,110,000           2,410
        # Other:       0.6      5,278,000             603
        #   2015 Res. rate: $0.0616/kWh
        #   Avg. annual residential cust. use: 14,054 kWh
        #   Winter peak, 160,100 kW (1.6 x average)
        #   Summer peak, 180,400 kW (1.8 x average)
        #   Annual power supply expenses: $35.5M
        # *************************************************************************
        inelastive_load = LocalAsset()
        inelastive_load.name = 'InelasticLoad'
        inelastive_load.maximumPower = -50000  # Remember that a load is a negative power [kW]
        inelastive_load.minimumPower = -200000  # Assume twice the averag PNNL load [kW]

        # Add inelastive asset model
        inelastive_load_model = OpenLoopRichlandLoadPredictor(weather_service)
        inelastive_load_model.name = 'InelasticLoadModel'
        inelastive_load_model.defaultPower = -100420  # [kW]
        inelastive_load_model.defaultVertices = [Vertex(float("inf"), 0.0, -100420.0)]

        # Cross-reference asset & asset model
        inelastive_load_model.object = inelastive_load
        inelastive_load.model = inelastive_load_model

        # Add inelastic as city's asset
        self.localAssets.extend([inelastive_load])

        # Add Market
        market = Market()
        market.name = 'dayAhead'
        market.commitment = False
        market.converged = False
        market.defaultPrice = 0.0428  # [$/kWh]
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

        self.campus = self.make_campus()
        supplier = self.make_supplier()

        # Add campus as city's neighbor
        self.neighbors.extend([self.campus, supplier])

    def make_campus(self):
        # Campus object
        campus = Neighbor()
        campus.name = 'PNNL_Campus'
        campus.description = 'PNNL_Campus'
        campus.maximumPower = 0.0  # Remember loads have negative power [avg.kW]
        campus.minimumPower = -20000  # [avg.kW]

        # Campus model
        campus_model = NeighborModel()
        campus_model.name = 'PNNL_Campus_Model'
        campus_model.location = self.name
        campus_model.defaultPower = -10000  # [avg.kW]
        campus_model.defaultVertices = [Vertex(0.045, 0.0, -10000.0)]
        #campus_model.demandThreshold = 0.8 * campus.maximumPower
        campus_model.transactive = True

        # Cross-reference object & model
        campus_model.object = campus
        campus.model = campus_model

        return campus

    def make_supplier(self):
        # Add supplier
        supplier = Neighbor()
        supplier.name = 'BPA'
        supplier.description = 'The Bonneville Power Administration as electricity supplier to the City of Richland, WA'
        supplier.lossFactor = self.supplier_loss_factor
        supplier.maximumPower = 200800  # [avg.kW, twice the average COR load]
        supplier.minimumPower = 0.0  # [avg.kW, will not export]

        # Add supplier model
        supplierModel = BulkSupplier_dc()
        supplierModel.name = 'BPAModel'
        #supplierModel.demandThreshold = 0.75 * supplier.maximumPower
        supplierModel.converged = False  # Dynamically assigned
        supplierModel.convergenceThreshold = 0  # Not yet implemented
        supplierModel.effectiveImpedance = 0.0  # Not yet implemented
        supplierModel.friend = False  # Separate business entity from COR

        supplierModel.transactive = False  # Not a transactive neighbor
        supplierModel.demand_threshold_coef = self.demand_threshold_coef
        supplierModel.demandThreshold = self.monthly_peak_power
        supplierModel.inject(self,
                             system_loss_topic=self.system_loss_topic,
                             dc_threshold_topic=self.dc_threshold_topic)


        # Add vertices
        # The first default vertex is, for now, based on the flat COR rate to
        # PNNL. The second vertex includes 2# losses at a maximum power that
        # is twice the average electric load for COR. This is helpful to
        # ensure that a unique price, power point will be found. In this
        # model the recipient pays the cost of energy losses.
        # The first vertex is based on BPA Jan HLH rate at zero power
        # importation.
        d1 = Vertex(0, 0, 0)  # create first default vertex
        d1.marginalPrice = 0.04196  # HLH BPA rate Jan 2018 [$/kWh]
        d1.cost = 2000.0  # Const. price shift to COR customer rate [$/h]
        d1.power = 0.0  # [avg.kW]
        # The second default vertex represents imported and lost power at a power
        # value presumed to be the maximum deliverable power from BPA to COR.
        d2 = Vertex(0, 0, 0)  # create second default vertex
        # COR pays for all sent power but receives an amount reduced by
        # losses. This creates a quadratic term in the production cost and
        # a slope to the marginal price curve.
        d2.marginalPrice = d1.marginalPrice / (1 - supplier.lossFactor)  # [$/kWh]
        # From the perspective of COR, it receives the power sent by BPA,
        # less losses.
        d2.power = (1 - supplier.lossFactor) * supplier.maximumPower  # [avg.kW]
        # The production costs can be estimated by integrating the
        # marginal-price curve.
        d2.cost = d1.cost + d2.power * (d1.marginalPrice + 0.5 * (d2.marginalPrice - d1.marginalPrice))  # [$/h]
        supplierModel.defaultVertices = [d1, d2]

        #   COST PARAMTERS
        #     A constant cost parameter is being used here to account for the
        #     difference between wholesale BPA rates to COR and COR distribution
        #     rates to customers like PNNL. A constant of $2,000/h steps the rates
        #     from about 0.04 $/kWh to about 0.06 $/kWh. This may be refined later.
        #     IMPORTANT: This shift has no affect on marginal pricing.
        supplierModel.costParameters[0] = 2000.0  # [$/h]

        # Cross-reference object & model
        supplierModel.object = supplier
        supplier.model = supplierModel

        # Meter
        bpaElectricityMeter = MeterPoint()  # Instantiate an electricity meter
        bpaElectricityMeter.name = 'BpaElectricityMeter'
        bpaElectricityMeter.description = 'BPA electricity to COR'
        bpaElectricityMeter.measurementType = MeasurementType.PowerReal
        bpaElectricityMeter.measurementUnit = MeasurementUnit.kWh
        supplierModel.meterPoints = [bpaElectricityMeter]

        return supplier


def main(argv=sys.argv):
    try:
        utils.vip_main(CityAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
