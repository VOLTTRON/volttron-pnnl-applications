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

# TODO: Reenable logging and volttron components in new_city_agent.py.

import os
import sys
import logging
from datetime import datetime, timedelta
from dateutil import parser
import gevent

from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)

from TNT_Version3.PyCode.helpers import *
from TNT_Version3.PyCode.measurement_type import MeasurementType
from TNT_Version3.PyCode.measurement_unit import MeasurementUnit
from TNT_Version3.PyCode.meter_point import MeterPoint
from TNT_Version3.PyCode.day_ahead_auction import DayAheadAuction
from TNT_Version3.PyCode.market_state import MarketState
from TNT_Version3.PyCode.TransactiveNode import TransactiveNode
from TNT_Version3.PyCode.neighbor_model import Neighbor
from TNT_Version3.PyCode.temperature_forecast_model import TemperatureForecastModel
from TNT_Version3.PyCode.openloop_richland_load_predictor import OpenLoopRichlandLoadPredictor
from TNT_Version3.PyCode.bulk_supplier_dc import BulkSupplier_dc
from TNT_Version3.PyCode.vertex import Vertex
from TNT_Version3.PyCode.timer import Timer
from TNT_Version3.PyCode.direction import Direction
from volttron.platform.messaging import headers as headers_mod

# utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


class CityAgent(Agent, TransactiveNode):
    def __init__(self, config_path, **kwargs):
        Agent.__init__(self, **kwargs)
        TransactiveNode.__init__(self)

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
        #self.db_topic = self.config.get("db_topic", "record")
        self.campus_demand_topic = "{}/campus/city/demand".format(self.db_topic)
        self.city_supply_topic = "{}/city/campus/supply".format(self.db_topic)
        self.system_loss_topic = "{}/{}/system_loss".format(self.db_topic, self.name)
        self.dc_threshold_topic = "{}/{}/dc_threshold_topic".format(self.db_topic, self.name)

        self.reschedule_interval = timedelta(minutes=10, seconds=1)

        self.simulation = self.config.get('simulation', False)
        self.simulation_start_time = parser.parse(self.config.get('simulation_start_time'))
        self.simulation_one_hour_in_seconds = int(self.config.get('simulation_one_hour_in_seconds'))

        Timer.created_time = Timer.get_cur_time()
        Timer.simulation = self.simulation
        Timer.sim_start_time = self.simulation_start_time
        Timer.sim_one_hr_in_sec = self.simulation_one_hour_in_seconds
        self._stop_agent = False
        self.campus = None
        # New TNT db topics
        self.transactive_operation_topic = "{}/{}/transactive_operation".format(self.db_topic, self.name)
        self.local_asset_topic = "{}/{}/local_assets".format(self.db_topic, self.name)
        self.neighbor_topic = "{}/{}/neighbors".format(self.db_topic, self.name)
        self.transactive_record_topic = "{}/{}/transactive_record".format(self.db_topic, self.name)
        self.market_balanced_price_topic = "{}/{}/market_balanced_prices".format(self.db_topic, self.name)
        self.market_topic = "{}/{}/market".format(self.db_topic, self.name)
        self.real_time_duration = self.config.get('real_time_market_duration', 15)
        self.start_tent_market_topic = "{}/start_tent".format(self.db_topic)

    def get_exp_start_time(self):
        one_second = timedelta(seconds=1)
        if self.simulation:
            next_exp_time = Timer.get_cur_time() + one_second
        else:
            now = Timer.get_cur_time()
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
        # self.core.schedule(next_exp_time, self.schedule_run,
        #                    format_timestamp(next_exp_time),
        #                    format_timestamp(next_analysis_time), True)
        headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
        self.vip.pubsub.publish("pubsub", self.start_tent_market_topic, headers, "start").get()

        # SN: Added for new state machine based TNT implementation
        self.core.spawn_later(10, self.state_machine_loop)

    def schedule_run(self, cur_exp_time, cur_analysis_time, start_of_cycle=False):
        # 191218DJH: The logic in this section should be REPLACED by the new market state machine. See method go().
        """
        Run when first start or run at beginning of hour
        :return:
        """
        # Balance
        market = self.markets[0]  # Assume only 1 TNS market per node
        # market.balance(self)
        # market.events(self)
        # self.campus.prep_transactive_signal(market, self)
        # self.campus.send_transactive_signal(self, self.city_supply_topic,
        #                                    start_of_cycle=start_of_cycle)

        # Schedule to run next hour with start_of_cycle = True
        cur_exp_time = parser.parse(cur_exp_time)
        cur_analysis_time = parser.parse(cur_analysis_time)
        next_exp_time, next_analysis_time = self.get_next_exp_time(cur_exp_time, cur_analysis_time)
        self.core.schedule(next_exp_time, self.schedule_run,
                           format_timestamp(next_exp_time),
                           format_timestamp(next_analysis_time),
                           start_of_cycle=True)

    # This appears to be the method by which the city receives transactive records from the campus. That's fine, but the
    # timing logic (i.e., "self.balance_market(1)") is ill advised and should be deferred to the market state machine.
    def new_demand_signal(self, peer, sender, bus, topic, headers, message):
        _log.debug("At {}, {} receives new demand records: {}".format(Timer.get_cur_time(), self.name, message))
        demand_curves = message['curves']
        # SN: Added for new TNT state machine based implementation
        self.campus.receivedCurves = demand_curves
        # Should not do anything with start_of_cycle signal
        # self.campus.receive_transactive_signal(self, demand_curves)  # atm, only one campus

        # 191219DJH: This logic should be deferred to the new market state machine, please.
        # self.balance_market(1)
        # self.markets[0].events(self)
        # for idx, p in enumerate(self.markets[0].marginalPrices):
        #     _log.debug("new_demand_signal: At {} Market marginal prices are: {}".format(self.name, p.value))

    '''
    # 191218DJH: The logic in this section should be deferred to the new market state machine. See method self.go().
    def balance_market(self, run_cnt):
        
        market = self.markets[0]  # Assume only 1 TNS market per node
        market.signal_new_data = True
        market.balance(self)

        if market.converged:
            # Sum all the powers as will be needed by the net supply/demand curve.
            market.assign_system_vertices(self)

            # Check to see if it is ok to send signals
            self.campus.check_for_convergence(market)
            if not self.campus.converged:
                _log.debug("NeighborModel {} sends records to campus.".format(self.campus.name))
                self.campus.prep_transactive_signal(market, self)
                self.campus.send_transactive_signal(self, self.city_supply_topic, start_of_cycle=False)
            else:
                # Schedule rerun balancing only if not in simulation mode
                if not self.simulation:
                    dt = Timer.get_cur_time()
                    _log.debug("{} ({}) did not send records due to check_for_convergence()".format(self.name, dt))
                    # Schedule to rerun after 5 minutes if it is in the same hour and is the first reschedule
                    next_run_dt = dt + self.reschedule_interval
                    if dt.hour == next_run_dt.hour and run_cnt >= 1:
                        _log.debug("{} reschedule to run at {}".format(self.name, next_run_dt))
                        self.core.schedule(next_run_dt, self.balance_market, run_cnt + 1)
        else:
            pass
            _log.debug("Market balancing sub-problem failed.")
            '''

    def init_objects(self):
        # Add CoR meter
        cor_meter = self.make_cor_meter()

        # Add weather forecast service
        weather_service = TemperatureForecastModel(self.config_path, self)
        self.informationServiceModels.append(weather_service)

        # Add inelastic asset
        inelastic_load = self.make_inelastic_load(weather_service)

        # Add day-ahead market
        market = self.make_day_ahead_market()

        # Add transactive campus neighbor
        self.campus = self.make_campus()

        # Add non-transactive wholesale electricity supplier neighbor
        supplier = self.make_supplier()

        topics = []


    def make_campus(self):
        # 191218DJH: There are no longer separate Neighbor object and model classes.
        campus = Neighbor()
        campus.name = 'PNNL_Campus'
        campus.description = 'PNNL_Campus'
        campus.maximumPower = 0.0                   # Remember loads have negative power [avg.kW]
        campus.minimumPower = -20000                # [avg.kW]
        campus.location = self.name
        campus.defaultPower = -10000                # [avg.kW]
        campus.defaultVertices = [Vertex(0.045, 0.0, -10000.0)]
        # campus.demandThreshold = 0.8 * campus.maximumPower
        campus.transactive = True
        campus.upOrDown = Direction.downstream #'downstream'
        # SN: Added to integrate new state machine logic with VOLTTRON
        # This topic will be used to send transactive signal to neighbor
        _log.debug("SN: CITY SUPPLY TOPIC: {}".format(self.city_supply_topic))
        campus.publishTopic = self.city_supply_topic
        _log.debug("SN: CITY campus neighbor getDict: {}".format(campus.getDict()))
        self.neighbors.append(campus)
        return campus

    def make_supplier(self):
        # 191218DJH: there are no longer separate Neighbor object and model classes. Class BulkSupplier_dc inherits from
        supplier = BulkSupplier_dc()                        # A child of Neighbor class
        supplier.name = 'BPA'
        supplier.description = 'The Bonneville Power Administration as electricity supplier to the City of Richland, WA'
        supplier.lossFactor = self.supplier_loss_factor
        supplier.maximumPower = 200800                      # [avg.kW, twice the average COR load]
        supplier.minimumPower = 0.0                         # [avg.kW, will not export]
        # supplierModel.demandThreshold = 0.75 * supplier.maximumPower
        supplier.converged = False                          # Dynamically assigned
        supplier.convergenceThreshold = 0                   # Not yet implemented
        supplier.effectiveImpedance = 0.0                   # Not yet implemented
        supplier.friend = False                             # Separate business entity from COR
        supplier.transactive = False                        # Not a transactive neighbor
        supplier.demandThresholdCoef = self.demand_threshold_coef
        supplier.demandThreshold = self.monthly_peak_power
        supplier.upOrDown = Direction.upstream #'upstream'

        # supplier.inject(self,
        #                 system_loss_topic=self.system_loss_topic,
        #                 dc_threshold_topic=self.dc_threshold_topic)

        # Add vertices
        # The first default vertex is, for now, based on the flat COR rate to PNNL. The second vertex includes 2 losses
        # at a maximum power that is twice the average electric load for COR. This is helpful to ensure that a unique
        # price, power point will be found. In this model the recipient pays the cost of energy losses.
        # The first vertex is based on BPA Jan HLH rate at zero power importation.
        d1 = Vertex(0, 0, 0)                        # create first default vertex
        d1.marginalPrice = 0.04196                  # HLH BPA rate Jan 2018 [$/kWh]
        d1.cost = 2000.0                            # Const. price shift to COR customer rate [$/h]
        d1.power = 0.0                              # [avg.kW]
        # The second default vertex represents imported and lost power at a power value presumed to be the maximum
        # deliverable power from BPA to COR.
        d2 = Vertex(0, 0, 0)                        # create second default vertex
        # COR pays for all sent power but receives an amount reduced by losses. This creates a quadratic term in the
        # production cost and a slope to the marginal price curve.
        d2.marginalPrice = d1.marginalPrice / (1 - supplier.lossFactor)  # [$/kWh]
        # From the perspective of COR, it receives the power sent by BPA, less losses.
        d2.power = (1 - supplier.lossFactor) * supplier.maximumPower  # [avg.kW]
        # The production costs can be estimated by integrating the marginal-price curve.
        d2.cost = d1.cost + d2.power * (d1.marginalPrice + 0.5 * (d2.marginalPrice - d1.marginalPrice))  # [$/h]
        supplier.defaultVertices = [d1, d2]

        #   COST PARAMTERS
        #     A constant cost parameter is being used here to account for the difference between wholesale BPA rates to
        #     COR and COR distribution rates to customers like PNNL. A constant of $2,000/h steps the rates from about
        #     0.04 $/kWh to about 0.06 $/kWh. This may be refined later.
        #     IMPORTANT: This shift has no affect on marginal pricing.
        supplier.costParameters[0] = 2000.0  # [$/h]

        # Meter
        bpaElectricityMeter = MeterPoint()                          # Instantiate an electricity meter
        bpaElectricityMeter.name = 'BpaElectricityMeter'
        bpaElectricityMeter.description = 'BPA electricity to COR'
        bpaElectricityMeter.measurementType = MeasurementType.PowerReal
        bpaElectricityMeter.measurementUnit = MeasurementUnit.kWh
        supplier.meterPoints = [bpaElectricityMeter]

        _log.debug("SN: CITY supplier neighbor getDict: {}".format(supplier.getDict()))
        # Add supplier as city's neighbor
        self.neighbors.append(supplier)

        return supplier

    def state_machine_loop(self):
        # 191218DJH: This is the entire timing logic. It relies on current market object's state machine method events()
        import time
        while not self._stop_agent:  # a condition may be added to provide stops or pauses.
            markets_to_remove = []
            for i in range(len(self.markets)):
                self.markets[i].events(self)
                #_log.debug("Markets: {}, Market name: {}, Market state: {}".format(len(self.markets),
                #                                                                   self.markets[i].name,
                #                                                                   self.markets[i].marketState))

                if self.markets[i].marketState == MarketState.Expired:
                    markets_to_remove.append(self.markets[i])
                # NOTE: A delay may be added, but the logic of the market(s) alone should be adequate to drive system
                # activities
                gevent.sleep(0.01)
            for mkt in markets_to_remove:
                _log.debug("Market name: {}, Market state: {}. It will be removed shortly".format(mkt.name,
                                                                                                  mkt.marketState))
                self.markets.remove(mkt)

    def make_day_ahead_market(self):
        # 191219DJH: It will be important that different agents' markets are similarly, if not identically,
        # instantiated. I.e., the day ahead market at the city must be defined just like the ones at the campus and
        # building nodes. Otherwise, the negotiations between the network agents will probably not work within the
        # context of the new market state machines.
        market = DayAheadAuction()                      # A child of class Auction.
        market.commitment = True                        # To be corrected by 15-minute real-time auction markets
        market.converged = False
        market.defaultPrice = 0.0428                    # [$/kWh]
        market.dualityGapThreshold = self.duality_gap_threshold  # [0.02 = 2#]
        market.initialMarketState = MarketState.Inactive
        market.marketOrder = 1                          # This is first market
        market.intervalsToClear = 24                    # 24 hours are cleared altogether
        market.futureHorizon = timedelta(hours=24)      # Projects 24 hourly future intervals
        market.intervalDuration = timedelta(hours=1)    # [h] Intervals are 1 h long
        market.marketClearingInterval = timedelta(days=1)
        #market.marketClearingInterval = timedelta(days=1)  # The market clears daily
        market.marketSeriesName = "Day-Ahead_Auction"   # Prepends future market object names
        market.method = 2                               # Use simpler interpolation solver

        # This times must be defined the same for all network agents.
        market.deliveryLeadTime = timedelta(hours=1)
#        market.negotiationLeadTime = timedelta(minutes=15)
        market.negotiationLeadTime = timedelta(minutes=8)
        market.marketLeadTime = timedelta(minutes=15)
        market.activationLeadTime = timedelta(minutes=0)
        market.real_time_duration = self.real_time_duration

        # Determine the current and next market clearing times in this market:
        current_time = Timer.get_cur_time()
        current_time = current_time - timedelta(hours=24)
        _log.debug("CITY agent current_time: {}".format(current_time))
        # Presume first delivery hour starts at 10:00 each day:
        #delivery_start_time = current_time.replace(hour=10, minute=0, second=0, microsecond=0)
        delivery_start_time = current_time.replace(hour=2, minute=0, second=0, microsecond=0)

        # The market clearing time must occur a delivery lead time prior to delivery:
        market.marketClearingTime = delivery_start_time - market.deliveryLeadTime
        _log.debug("market.marketClearingTime: {}".format(market.marketClearingTime))
        # If it's too late today to begin the market processes, according to all the defined lead times, skip to the
        # next market object:
        if current_time > market.marketClearingTime - market.marketLeadTime \
                                                            - market.negotiationLeadTime - market.activationLeadTime:
            market.marketClearingTime = market.marketClearingTime + market.marketClearingInterval

        # Schedule the next market clearing for another market cycle later:
        market.nextMarketClearingTime = market.marketClearingTime + market.marketClearingInterval
        _log.debug("CITY: Market nextMarketClearingTime: {}".format(market.nextMarketClearingTime))

        dt = str(market.marketClearingTime)
        market.name = market.marketSeriesName.replace(' ', '_') + '_' + dt[:19]

        market.isNewestMarket = True
        # Initialize the Market object's time intervals.
        market.check_intervals()

        # Initialize the marginal prices in the Market object's time intervals.
        market.check_marginal_prices(self)

        self.markets.append(market)

        for p in market.marginalPrices:
            _log.debug("Market name: {} Initial marginal prices: {}".format(market.name, p.value))
        market.marketState = MarketState.Delivery
        return market

        # IMPORTANT: The real-time correction markets are instantiated by the day-ahead markets as they become
        # instantiated.

    def make_inelastic_load(self, weather_service):
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
        # 191218DJH: There are no longer separate LocalAsset object and model classes.
        inelastic_load = OpenLoopRichlandLoadPredictor(weather_service,
                                                       default_power=-100420,
                                                       description='Correlation model of bulk inelastic city load',
                                                       maximum_power=-50000,
                                                       minimum_power=-200000,
                                                       name='InelasticCityLoad')  # A child of class LocalAsset

        inelastic_load.temperature_forecaster = weather_service
        inelastic_load.default_vertices = [Vertex(float("inf"), 0.0, -100420.0)]

        # Add inelastic load as city's asset
        self.localAssets.append(inelastic_load)

        return inelastic_load

    def make_cor_meter(self):
        meter = MeterPoint(
            measurement_type=MeasurementType.PowerReal,
            measurement_unit=MeasurementUnit.kWh,
            name='CoRElectricMeter')

        self.meterPoints.append(meter)

        return meter

    @Core.receiver('onstop')
    def onstop(self, sender, **kwargs):
        self._stop_agent = True

# TODO: Reenable logging and volttron functionality in new_city_agent.py
def main(argv=sys.argv):
    try:
        utils.vip_main(CityAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
