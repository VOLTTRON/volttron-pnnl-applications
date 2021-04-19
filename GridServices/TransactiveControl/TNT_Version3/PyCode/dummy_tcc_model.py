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

from volttron.platform.agent import utils

from .vertex import Vertex
from .interval_value import IntervalValue
from .measurement_type import MeasurementType
from .helpers import *
from .market import Market
from .time_interval import TimeInterval
from .local_asset_model import LocalAsset
from .timer import Timer
from .market_state import MarketState
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
import datetime

utils.setup_logging()
_log = logging.getLogger(__name__)


class DummyTccModel(LocalAsset):
    # TCCMODEL - A LocalAssetModel specialization that interfaces integrates
    # the PNNL ILC and/or TCC building systems with the transactive network.
    # TCC - Transactive Control & Coordination: Manages HVAC system load using
    # auctions at the various levels of the HVAC system (e.g., VAV boxes,
    # chillers, etc.)
    # ILC - Integrated Load Control: Originally designed to limit total
    # building load below a prescribed threshold. Has been recently modified
    # to make the threshold price-responsive.
    # This class necessarily redefines two methods: schedule_power() and
    # update_vertices(). The methods call a "single market function" that was
    # developed by Sen Huang at PNNL. This function simulates (using Energy
    # Plus) building performance over a 24-hour period and replies with a
    # series of records for each time interval. The records represent the
    # minimum and maximum inflection points and are therefore very like Vertex
    # objects.

    def __init__(self):
        super(DummyTccModel, self).__init__()
        self.buildingRecords = None
        self.quantities = None
        self.tcc_curves = None
        self.prices = None
        self.building_volttron_agent = None
        self.dummy_q, self.dummy_p, self.dummy_dc = self.create_dummy_curves()

    def set_tcc_curves(self, quantities, prices, curves):
        self.quantities = quantities
        # Ignoring first element since state machine based market does not the correction
        self.tcc_curves = curves[1:]
        self.prices = prices
        _log.debug("TCC set_tcc_curves are: q: {}, p: {}, c: {}".format(self.quantities,
                                                                        self.tcc_curves,
                                                                        self.prices))

    # 191220DJH: This was done pretty well and is a great start to a proper interface between the transactive
    #            network building agent and the complex building control system (i.e., TCC or ILC or ...). The timing
    #            in this interface should be driven by the new market state machine, which will have the building agent
    #            initiate scheduling when it is needed. It seems the forecasts of the TCC asset are hard-coded, and
    #            that will probably have to be fixed if scheduling is to be viable in multiple markets that could have
    #            different numbers of time intervals and different time interval durations, etc.
    # def schedule_power(self, mkt):
    #     """
    #     This function should ask mixmarket to rerun and get back new scheduledPower and curves based on new set of
    #     marginalPrice. However, because the building already provided the curve in the 1st place, there is no need to
    #     rerun the mix market...
    #     """
    #     _log.debug("TCC tcc_model schedule_power()")
    #     self.scheduledPowers = []
    #     time_intervals = mkt.timeIntervals
    #     if self.tcc_curves is not None:
    #         # Curves existed, update vertices first
    #         self.update_vertices(mkt)
    #
    #     for i in range(len(time_intervals)):
    #         value = self.defaultPower
    #         # if self.quantities is not None and len(self.quantities) > i and self.quantities[i] is not None:
    #         #     value = -self.quantities[i]
    #         _log.debug("TCC tcc_model default_power: {}".format(value))
    #         if self.tcc_curves is not None:
    #             # Update power at this marginal_price
    #             marginal_price = find_obj_by_ti(mkt.marginalPrices, time_intervals[i])
    #             marginal_price = marginal_price.value
    #             value = production(self, marginal_price, time_intervals[i])  # [avg. kW]
    #
    #         iv = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ScheduledPower, value)
    #         self.scheduledPowers.append(iv)
    #
    #     sp = [(x.timeInterval.name, x.value) for x in self.scheduledPowers]
    #     _log.debug("TCC scheduledPowers are: {}".format(sp))

    # SN: Schedule Power by starting Mix market
    def schedule_power(self, mkt):
        _log.debug("Market Dummy TCC tcc_model schedule_power()")
        if self.building_volttron_agent is not None and not self.building_volttron_agent.mix_market_running:
            _log.debug("Market name: {} in Market state: {}..Starting building level mix market ".format(mkt.name,
                                                                                                 mkt.marketState))
            resend_balanced_prices = False
            if mkt.marketState == MarketState.DeliveryLead:
                resend_balanced_prices = True
            if mkt.marketSeriesName == "Day-Ahead_Auction":
                _log.debug("Market Dummy TCC tcc_model schedule_power(): {}".format(mkt.marketSeriesName))
                #self.building_volttron_agent.start_mixmarket(True, resend_balanced_prices, mkt)
                pass
            else:
                _log.debug("Market Dummy TCC tcc_model schedule_power(): {}".format(mkt.marketSeriesName))
                self.building_volttron_agent.start_real_time_mixmarket(True, resend_balanced_prices, mkt)
            mkt.check_marginal_prices(self.building_volttron_agent)
            for p in mkt.marginalPrices:
                _log.debug("Building schedule_power Market name: {}, marginal time startTime: {}".format(mkt.name,
                                                                                                         p.timeInterval.startTime))
                _log.debug("Building schedule_power Market name: {}, marginal price: {}".format(mkt.name, p.value))

            _log.debug("Creating building demand curves")
            quantities, prices, curves = self.create_building_demand_curve(mkt)
            _log.debug("Setting scheduled power, quantities: {}, prices: {}, curves: {}".format(quantities,
                                                                                                prices,
                                                                                                curves))
            self.set_scheduled_power(quantities, prices, curves, mkt)

    def add_building_volttron_agent(self, building_volttron_agent):
        self.building_volttron_agent = building_volttron_agent

    def create_building_demand_curve(self, mkt):
        demand_curves = self.dummy_dc

        if mkt.marketSeriesName == "Day-Ahead_Auction":
            _log.debug("Building demand curves: {}, Market name: {} len:{}".format(demand_curves,
                                                                                       mkt.name,
                                                                                       len(demand_curves)))
            return self.dummy_q, self.dummy_p, demand_curves
        else:
            datetime_obj = mkt.marginalPrices[0].timeInterval.startTime
            _log.debug("Building demand curves. Market name: {}, hour: {}".format(mkt.name,
                                                                                 datetime_obj.time().hour))
            hr = datetime_obj.time().hour
            q = [0.0, self.dummy_q[hr+1]]
            p = [self.dummy_p[hr]]
            dc_hour = []
            dc_hour.append((None, None))
            dc_hour.append(demand_curves[hr+1])
            _log.debug("Building demand curves. Market name: {}, q: {}, p: {}, dc_hour: {}".format(mkt.name,
                                                                                      q, p, dc_hour))
            #demand_curves.append((curve.points[0], curve.points[1]))
            return q, p, dc_hour

    def create_dummy_curves(self):
        demand_curves = []
        qp = list()
        import csv

        with open('/home/niddodi/Desktop/qp.csv', mode='r') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for row in csv_reader:
                qp.append(dict(quantity=row['quantity'], price=row['price']))

        quantities = [None, 15.057901542381055, 15.074462852380995, 15.078246172381055, 15.094852262381037,
                      15.89163491118235, 16.052753497385876, 16.554970596955425, 16.499339060753453, 16.206673496228728,
                      16.5803219300812, 16.815806495187626, 17.077485589933183, 17.021639192644663, 16.98750461431373,
                      16.61714778422135, 16.59039164499313, 15.873869862381028, 15.800489182381014, 15.744625552381029,
                      15.681675372381065, 15.697041882381065, 15.780719272381049, 15.83165963238102, 15.031569332381038]
        prices = [0.06, 0.060000000000000005, 0.060000000000000005, 0.060000000000000005, 0.060000000000000005,
                  0.060000000000000005, 0.060000000000000005, 0.060000000000000005, 0.060000000000000005,
                  0.060000000000000005, 0.060000000000000005, 0.060000000000000005, 0.060000000000000005,
                  0.060000000000000005, 0.060000000000000005, 0.060000000000000005, 0.060000000000000005,
                  0.060000000000000005, 0.060000000000000005, 0.060000000000000005, 0.060000000000000005,
                  0.060000000000000005, 0.060000000000000005, 0.060000000000000005, 0.0428]

        demand_curves.append((None, None))
        lenth = int(len(qp) / 2)

        for i in range(0, lenth):
            curve = PolyLine()
            curve.add(Point(quantity=qp[i * 2]['quantity'], price=qp[i * 2]['price']))
            curve.add(Point(quantity=qp[i * 2 + 1]['quantity'], price=qp[i * 2 + 1]['price']))
            demand_curves.append((curve.points[0], curve.points[1]))
        return quantities, prices, demand_curves

    # SN: Set Scheduled Power after mix market is done
    def set_scheduled_power(self, quantities, prices, curves, mkt):
        self.set_tcc_curves(quantities, prices, curves)
        _log.debug("Market {} Dummy TCC tcc_model set_scheduled_power()".format(mkt.name))
        # 200929DJH: This was problematic in Version 3 because there exist perfectly valid scheduled powers in other
        #            markets. Instead, let's calculate any new scheduled powers and eliminate only the scheduled powers
        #            that exist in expired markets.
        #self.scheduledPowers = []
        time_intervals = mkt.timeIntervals

        if self.tcc_curves is not None:
            # Curves existed, update vertices first
            self.update_vertices(mkt)
            self.scheduleCalculated = True

        for i in range(len(time_intervals)):
            time_interval = time_intervals[i]
            value = self.defaultPower
            # if self.quantities is not None and len(self.quantities) > i and self.quantities[i] is not None:
            #     value = -self.quantities[i]
            _log.debug("Market TCC tcc_model default_power: {}".format(value))
            if self.tcc_curves is not None:
                # Update power at this marginal_price
                marginal_price = find_obj_by_ti(mkt.marginalPrices, time_interval)
                marginal_price = marginal_price.value
                value = production(self, marginal_price, time_interval)  # [avg. kW]

            iv = IntervalValue(self, time_interval, mkt, MeasurementType.ScheduledPower, value)
            self.scheduledPowers.append(iv)

        # 200929DJH: This following line is needed to make sure the list of scheduled powers does not grow indefinitely.
        #            Scheduled powers are retained only if their markets have not expired.
        self.scheduledPowers = [x for x in self.scheduledPowers if x.market.marketState != MarketState.Expired]

        sp = [(x.timeInterval.name, x.value) for x in self.scheduledPowers]
        _log.debug("Market {} TCC scheduledPowers are: {}".format(mkt.name,
                                                                  sp))

        if self.scheduleCalculated:
            self.calculate_reserve_margin(mkt)

    def update_vertices(self, mkt):
        if self.tcc_curves is None:
            super(DummyTccModel, self).update_vertices(mkt)
        else:
            time_intervals = mkt.timeIntervals
            _log.debug("Market: {} At {}, Tcc market has {} intervals".format(mkt.name,
                                                                              Timer.get_cur_time(),
                                                                              len(time_intervals)))

            # 191220DJH: This timing issue concerning the 1st market time interval should disappear when using the
            #            market state machine for network markets.
            # 1st mix-market doesn't have tcc_curves info => keep previous active vertices
            # if self.tcc_curves[0] is None:
            #     first_interval_vertices = [iv for iv in self.activeVertices
            #                                if iv.timeInterval.startTime == time_intervals[0].startTime]
            #     self.activeVertices = first_interval_vertices

            # 191220DJH: The mixed-market timing seems to be pretty hard-coded. This will not work generally for
            #            multiple network markets having differing interval durations, numbers of intervals, etc.

            # After 1st mix-market, we always have tcc_curves for 25 market intervals => clear all previous av
            # else:
            #     self.activeVertices = []

            #self.activeVertices = []

            for i in range(len(time_intervals)):
                if self.tcc_curves[i] is None:
                    continue
                # 200925DJH: Clean up active vertices that are to be replaced. This should be fine in Version 3 because
                #            time intervals are unique to their markets.
                try:
                    time_interval = time_intervals[i]
                    self.activeVertices = [x for x in self.activeVertices if x.timeInterval != time_interval]
                    point1 = self.tcc_curves[i][0].tuppleize()
                    q1 = -point1[0]
                    p1 = point1[1]
                    point2 = self.tcc_curves[i][1].tuppleize()
                    q2 = -point2[0]
                    p2 = point2[1]

                    v1 = Vertex(p1, 0, q1)
                    iv1 = IntervalValue(self, time_interval, mkt, MeasurementType.ActiveVertex, v1)
                    self.activeVertices.append(iv1)

                    if q2 != q1:
                        v2 = Vertex(p2, 0, q2)
                        iv2 = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, v2)
                        self.activeVertices.append(iv2)
                except IndexError as e:
                    _log.debug("TCC model e: {}, i: {}".format(e, i))

        # 200929DJH: This is a good place to make sure the list of active vertices is trimmed and does not grow
        #            indefinitely.
        self.activeVertices = [x for x in self.activeVertices if x.market.marketState != MarketState.Expired]

        av = [(x.timeInterval.name, x.value.marginalPrice, x.value.power) for x in self.activeVertices]
        _log.debug("TCC active vertices are: {}".format(av))
