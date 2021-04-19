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
from .local_asset import LocalAsset
from .local_asset_model import LocalAssetModel
from .timer import Timer

utils.setup_logging()
_log = logging.getLogger(__name__)


class TccModel(LocalAssetModel):
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
        super(TccModel, self).__init__()
        self.buildingRecords = None
        self.quantities = None
        self.tcc_curves = None
        self.prices = None

    def set_tcc_curves(self, quantities, prices, curves):
        self.quantities = quantities
        self.tcc_curves = curves
        self.prices = prices

    def schedule_power(self, mkt):
        """
        This function should ask mixmarket to rerun and get back new scheduledPower and curves based on new set of
        marginalPrice. However, because the building already provided the curve in the 1st place, there is no need to
        rerun the mix market...
        """
        self.scheduledPowers = []
        time_intervals = mkt.timeIntervals
        if self.tcc_curves is not None:
            # Curves existed, update vertices first
            self.update_vertices(mkt)

        for i in range(len(time_intervals)):
            value = self.defaultPower
            # if self.quantities is not None and len(self.quantities) > i and self.quantities[i] is not None:
            #     value = -self.quantities[i]

            if self.tcc_curves is not None:
                # Update power at this marginal_price
                marginal_price = find_obj_by_ti(mkt.marginalPrices, time_intervals[i])
                marginal_price = marginal_price.value
                value = production(self, marginal_price, time_intervals[i])  # [avg. kW]

            iv = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ScheduledPower, value)
            self.scheduledPowers.append(iv)

        sp = [(x.timeInterval.name, x.value) for x in self.scheduledPowers]
        _log.debug("TCC scheduledPowers are: {}".format(sp))

    def update_vertices(self, mkt):
        if self.tcc_curves is None:
            super(TccModel, self).update_vertices(mkt)
        else:
            time_intervals = mkt.timeIntervals
            _log.debug("At {}, Tcc market has {} intervals".format(Timer.get_cur_time(),
                                                                   len(time_intervals)))

            # 1st mix-market doesn't have tcc_curves info => keep previous active vertices
            if self.tcc_curves[0] is None:
                first_interval_vertices = [iv for iv in self.activeVertices
                                           if iv.timeInterval.startTime == time_intervals[0].startTime]
                self.activeVertices = first_interval_vertices

            # After 1st mix-market, we always have tcc_curves for 25 market intervals => clear all previous av
            else:
                self.activeVertices = []

            for i in range(len(time_intervals)):
                if self.tcc_curves[i] is None:
                    continue
                point1 = self.tcc_curves[i][0].tuppleize()
                q1 = -point1[0]
                p1 = point1[1]
                point2 = self.tcc_curves[i][1].tuppleize()
                q2 = -point2[0]
                p2 = point2[1]

                v1 = Vertex(p1, 0, q1)
                iv1 = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, v1)
                self.activeVertices.append(iv1)

                if q2 != q1:
                    v2 = Vertex(p2, 0, q2)
                    iv2 = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, v2)
                    self.activeVertices.append(iv2)

        av = [(x.timeInterval.name, x.value.marginalPrice, x.value.power) for x in self.activeVertices]
        _log.debug("TCC active vertices are: {}".format(av))
