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

# from datetime import datetime, timedelta, date, time
# import csv

import logging
import json

from .data_manager import *
from .helpers import *
from .measurement_type import MeasurementType
from .interval_value import IntervalValue
from .transactive_record import TransactiveRecord
from .vertex import Vertex
from .timer import Timer
from .direction import Direction
from copy import copy, deepcopy
from operator import attrgetter
from .market_state import MarketState

from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)

utils.setup_logging()
_log = logging.getLogger(__name__)

# 191217DJH: This class had originally inherited from class Model. Model will be deleted.


class Neighbor(object):
    # The Neighbor class manages the interface with a Neighbor object and represents it for the computational agent.
    # Members of the transactive network must be indicated by setting the "transactive" property true.

    def __init__(self,
                 convergence_threshold=0.05,
                 cost_parameters=[0.0, 0.0, 0.0],
                 demand_month=datetime.today().month,
                 demand_rate=4.5,
                 demand_threshold=1e9,
                 demand_threshold_coef=1,
                 description='',
                 effective_impedance=0.0,
                 friend=False,
                 location='',
                 loss_factor=0.01,
                 maximum_power=0.0,
                 mechanism='consensus',
                 minimum_power=0.0,
                 name='',
                 subclass=None,
                 transactive=False,
                 up_or_down=Direction.unknown):

        super(Neighbor, self).__init__()

        self.convergenceThreshold = convergence_threshold   # [Small positive fraction]: May affect negotiations
        self.costParameters = cost_parameters               # 3x[float]: Parameters of quadratic production cost
        self.demandMonth = demand_month                     # [month number]: Used to reset demand charges
        self.demandRate = demand_rate                       # [$ / kW (/h)]: rate determinant
        self.demandThreshold = demand_threshold             # [kW]; current power above which demand charges accrue
        self.demandThresholdCoef = demand_threshold_coef    # Factor by which threshold is reduced in new month
        self.description = description                      # [text]
        self.effectiveImpedance = effective_impedance       # [Ohms]: (future) may be used for loss effects
        self.friend = friend                                # [boolean]: True for collaborative, friendly Neighbor
        self.location = location                            # [text]
        self.lossFactor = loss_factor                       # [dimensionless] 0.01 = 1% full-load loss
        self.maximumPower = maximum_power                   # [avg.kW, signed] Object's physical "hard" constraint
        self.mechanism = mechanism                          # future, unused
        self.minimumPower = minimum_power                   # [avg.kW, signed] Object's physical "hard" constraint
        self.name = name                                    # [text]
        self.subclass = subclass                            # future, unused
        self.transactive = transactive                      # [boolean]: True for transactive neighbor
        self.upOrDown = up_or_down                          # 'upstream' or 'downstream' direction of this neighbor

        # These static lists are maintained by each neighbor object:
        self.defaultVertices = [Vertex(float("inf"), 0.0, 1)]  # [IntervalValue] Values are [Vertices]
        self.meterPoints = []                               # [MeterPoint] See class MeterPoint

        # These properties and lists are to be dynamically assigned. An implementer would usually not manually assign
        # these properties.
        self.activeVertices = []                            # [IntervalValue] Values are [Vertex]
        self.converged = False                              # [boolean]: True if converged
        self.convergenceFlags = []                          # [IntervalValue] Values are [Boolean]
        self.dualCosts = []                                 # [IntervalValue] Value is [$]
        self.mySignal = []                                  # [TransactiveRecord] Current records ready to send
        self.productionCosts = []                           # [IntervalValue] Values are [$]
        self.receivedSignal = []                            # [TransactiveRecord] Last records received
        self.reserveMargins = []                            # [IntervalValue] Value is [avg.kW]
        self.scheduledPowers = []                           # [IntervalValue] Value is [avg.kW]
        self.sentSignal = []                                # [TransactiveRecord] Last records sent
        self.totalDualCost = 0.0                            # [float] [$]
        self.totalProductionCost = 0.0                      # [float] [$]
        # SN: Added to integrate new state machine logic with VOLTTRON
        self.publishTopic = None
        self.receivedCurves = None

    def calculate_reserve_margin(self, market):
        # CALCULATE_RESERVE_MARGIN() - Estimate the spinning reserve margin in each active time interval
        #
        # RESERVE MARGIN is defined here as additional generation or reduced consumption above the currently scheduled
        # power. The intention is for this to represent "spinning-reserve" power that can be available on short notice.
        #
        # For now, this quantity will be tracked. In the future, treatment of resource commitment may allow meaningful
        # control of reserve margin and the resiliency that it supports.
        #
        # PRESUMPTIONS:
        # - time intervals are up-to-date
        # - scheduled power is up-to-date
        # - the active vertices are up-to-date and correct. One of the vertices represents the maximum power that is
        #   available on short notice (i.e., "spinning reserve") from this neighbor.
        #
        # INPUTS:
        #   market: Market object
        # OUTPUTS:
        # - updates self.reserveMargins

        # Gather active time intervals ti
        time_intervals = market.timeIntervals

        # 200929DJH: This approach is too crude for Version 3. Commenting it out. Instead, reserve margins in expired
        #            markets will be trimmed near the bottom of this method.
        # time_interval_values = [t.startTime for t in time_intervals]
        # self.reserveMargins = [x for x in self.reserveMargins if x.timeInterval.startTime in time_interval_values]

        # Index through active time intervals ti
        for i in range(len(time_intervals)):

            # Find the maximum available power from among the active vertices in the indexed time interval, one of which
            # must represent maximum power.
            maximum_power = find_objs_by_ti(self.activeVertices, time_intervals[i])

            if len(maximum_power) == 0:

                # No active vertex was found. The hard constraint must be used.
                maximum_power = self.maximumPower  # hard constraint [avg.kW, signed]

            else:

                # A vertex was found. Extract its power value.
                maximum_power = [x.value for x in maximum_power]  # Vertices from IntervalValue objects
                maximum_power = [x.power for x in maximum_power]  # real powers from Vertices
                maximum_power = max(maximum_power)  # maximum power [avg.kW]

                # Check that the operational maximum from vertices does not exceed the hard physical constraint. Use the
                # smaller of the two.
                maximum_power = min(maximum_power, self.maximumPower)

            # Find the scheduled power for this asset in the indexed time interval
            scheduled_power = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            scheduled_power = scheduled_power.value  # scheduled power [avg.kW]

            # The available reserve margin is calculated as the difference between the maximum and scheduled powers.
            # Make sure the value is not less than zero.
            value = max(0, maximum_power - scheduled_power)  # reserve margin [avg.kW]

            # Check whether a reserve margin exists in the indexed time interval.
            interval_value = find_obj_by_ti(self.reserveMargins, time_intervals[i])

            if interval_value is None:

                # No reserve margin was found for the indexed time interval. Create a reserve margin interval for the
                # calculated value
                interval_value = IntervalValue(self, time_intervals[i], market, MeasurementType.ReserveMargin, value)

                # Append the reserve margin interval value to the list of reserve margins.
                self.reserveMargins.append(interval_value)  # IntervalValue objects

            else:
                # The reserve margin interval value already exists, simply reassign its value.
                interval_value.value = value  # [avg.kW]

        # 200929DJH: Trim any reserve margins that lie in expired markets.
        self.reserveMargins = [x for x in self.reserveMargins if x.market.marketState != MarketState.Expired]

    def find_last_message_ts(self, signals, ti_name, fallback_value):

        # Create a logical array: true if the received TransactiveRecord is in the indexed active time interval.
        ti_signals = [s for s in signals if s.timeInterval == ti_name]

        # If a signal message was found in the indexed time interval, its timestamp ts is the last time a message was
        # sent. Otherwise, set the ts to the fallback value (eg. current time dt)
        if len(ti_signals) > 0:
            ts = [s.timeStamp for s in ti_signals if s.record == 0]
            ts = ts[0]
        else:
            ts = fallback_value

        return ts, ti_signals

    def check_for_convergence(self, market):
        # Qualifies state of convergence with a transactive Neighor object by active time interval and globally.
        #
        # In respect to the coordination sub-problem, a Neighbor is not converged for a given time interval and a signal
        # should be sent to the transactive Neighbor if
        # - The balancing and scheduling sub-problems are converged, AND
        # - No signal has been sent, OR
        # - A signal has been received from the Neighbor, and no signal has been sent since the signal was received, but
        #   scheduled power and marginal price in the sent and received signals (i.e., Records 0) differ, OR
        # - A timer has elapsed since the last time a signal was sent, and the sent signal differs from one that would
        #   be sent again, based on current conditions.
        #
        # Inputs:
        # market - Market object
        #
        # Uses property convergenceThreshold as a convergence criterion.
        #
        # Compares TransactiveRecord messages in mySignal, sentSignal, and receivedSignal.
        #
        # Updates properties convergenceFlags and converged based on comparison of calculated, received, and sent
        # TransactiveRecord messages.

        # NOTE: this method should not be called unless the balancing sub-problem and all the scheduling sub-problems
        # have been calculated and have converged.

        # Gather active time intervals.
        time_intervals = market.timeIntervals

        # Index through active time intervals to assess their convergence status.
        t_threshold = timedelta(minutes=5)
        for i in range(len(time_intervals)):
            # Capture the current datetime in the same format as for the TransactiveRecord messages.
            dt = Timer.get_cur_time()

            # Initialize a flag true (converged) in this time interval until proven otherwise.
            flag = True

            # Find the TransactiveRecord objects sent from the transactive Neighbor in this indexed active time
            # interval.
            ss_ts, ss = self.find_last_message_ts(self.sentSignal, time_intervals[i].name, dt-t_threshold)
            rs_ts, rs = self.find_last_message_ts(self.receivedSignal, time_intervals[i].name, dt)
            ms_ts, ms = self.find_last_message_ts(self.mySignal, time_intervals[i].name, dt)

            # Now, work through the convergence criteria.
            if len(ss) == 0:
                # No signal has been sent in this time interval. This is the first convergence requirement. Set the
                # convergence flag false.
                _log.debug("Signal for time interval {} ({}). Enable send flag.".format(i, time_intervals[i].name))
                flag = False

            # received and received AFTER last sent and there is a big diff b/w ss and rs
            elif len(rs) > 0 and rs_ts > ss_ts and are_different1(ss, rs, self.convergenceThreshold, self.name):
                # One or more TransactiveRecord objects has been received in the indexed time interval and it has been
                # received AFTER the last time a message was sent. These are preconditions for the second convergence
                # requirement. Function are_different1() checks whether the sent and received signals differ
                # significantly. If all these conditions are true, the Neighbor is not converged.
                _log.debug("TCC for {} are_different1 returned True? Check: rs={}, ss={}, "
                                "rs_ts={}, ss_ts={}, threshold={}".format(
                                self.name,
                                [(x.timeInterval, x.record, x.power, x.marginalPrice) for x in rs],
                                [(x.timeInterval, x.record, x.power, x.marginalPrice) for x in ss],
                                rs_ts, ss_ts, self.convergenceThreshold))

                flag = False

            # TODO: Find out why the timing does not work with t_threshold.
            # elif dt - ss_ts >= t_threshold and are_different2(ms, ss, self.convergenceThreshold, self.name):
            elif are_different2(ms, ss, self.convergenceThreshold, self.name):
                # Delay 5 min after last send AND More than 5 minutes have passed since the last time a signal was sent.
                # This is a precondition to the third convergence criterion. Function are_different2() returns true if
                # mySignal (ms) and the sentSignal (ss) differ significantly, meaning that local conditions have changed
                # enough that a new, revised signal should be sent.
                _log.debug("TCC for {} are_different2 returned True? Check: ms={}, ss={}, "
                           "rs_ts={}, ss_ts={}, threshold={}".format(
                    self.name,
                    [(x.timeInterval, x.record, x.power, x.marginalPrice) for x in ms],
                    [(x.timeInterval, x.record, x.power, x.marginalPrice) for x in ss],
                    rs_ts, ss_ts, self.convergenceThreshold))
                flag = False

            # Check whether a convergence flag exists in the indexed time interval.
            iv = find_obj_by_ti(self.convergenceFlags, time_intervals[i])

            if iv is None:

                # No convergence flag was found in the indexed time interval.
                # Create one and append it to the list.
                iv = IntervalValue(self, time_intervals[i], market, MeasurementType.ConvergenceFlag, flag)
                self.convergenceFlags.append(iv)

            else:
                # A convergence flag was found to exist in the indexed time interval. Simply reassign it.
                iv.value = flag

        # If any of the convergence flags in active time intervals is false, the overall convergence flag should be set
        # false, too. Otherwise, true, meaning the coordination sub-problem is converged with this Neighbor.
        if any([not x.value for x in self.convergenceFlags]):
            self.converged = False
        else:
            self.converged = True

        _log.debug("TCC convergence flags for {} are {}".format(
            self.name, [(format_ts(f.timeInterval.startTime), f.value) for f in self.convergenceFlags]))
        _log.debug("TCC convergence flag for {} is {}.".format(self.name, self.converged))


    def marginal_price_from_vertices(self, power, vertices):
        # Given a power, determine the corresponding marginal price from a set of supply- or demand-curve vertices.
        #
        # INPUTS:
        # power - scheduled power [avg.kW]
        # vertices - array of supply- or demand-curve vertices
        #
        # OUTPUTS:
        # mp - a marginal price that corresponds to p [$/kWh]

        # Sort the supplied vertices by power and marginal price.
        vertices = order_vertices(vertices)

        # number of supplied vertices len
        v_len = len(vertices)

        if power < vertices[0].power:
            # The power is below the first vertex. Marginal price is indeterminate. Assign the marginal price of the
            # first vertex, create a warning, and return. (This should be an unlikely condition.)
            Warning('power was lower than first vertex')  # This had been commented out.
            marginal_price = vertices[0].marginalPrice  # price [$/kWh]
            return marginal_price

        elif power >= vertices[-1].power:
            # The power is above the last vertex. Marginal price is indeterminate. Assign the marginal price of the last
            # vertex, create a warning, and return. (This should be an unlikely condition.)
            Warning('power was greater than last vertex')
            marginal_price = vertices[-1].marginalPrice  # price [$/kWh]
            return marginal_price

        # There are multiple vertices v. Index through them.
        for i in range(v_len - 1):  # for i = 1:(len - 1)
            if vertices[i].power <= power < vertices[i + 1].power:

                # The power lies on a segment between two defined vertices.
                if vertices[i].power == vertices[i + 1].power:

                    # The segment is horizontal. Marginal price is indefinite. Assign the marginal price of the second
                    # vertex and return.
                    _log.warning('segment is horizontal')
                    marginal_price = vertices[i + 1].marginalPrice
                    return marginal_price
                else:
                    # The segment is not horizontal. Interpolate on the segment.
                    # First, determine the segment's slope.
                    slope = (vertices[i + 1].marginalPrice - vertices[i].marginalPrice) \
                            / (vertices[i + 1].power - vertices[i].power)  # [$/kWh/kW]

                    # Then interpolate to find marginal price.
                    marginal_price = vertices[i].marginalPrice + (power - vertices[i].power) * slope  # [$/kWh]
                    return marginal_price

    # SEALED - DONOT MODIFY
    # Have object schedule its power in active time intervals
    def schedule(self, market):
        self.update_dc_threshold(market)

        # If the object is a Neighbor give its vertices priority
        self.update_vertices(market)
        self.schedule_power(market)

        # Have the objects estimate their available reserve margin
        self.calculate_reserve_margin(market)

    def schedule_power(self, market):
        # Calculate power for each time interval
        #
        # This is a basic method for calculating power generation of consumption in each active time interval. It infers
        # power generation or consumption from the supply or demand curves that are represented by the neighbor's active
        # vertices in the active time intervals.
        #
        # This strategy should is anticipated to work for most neighbor model objects. If additional features are
        # needed, child neighbor models must be created and must redefine this method.
        #
        # PRESUMPTIONS:
        # - All active vertices have been created and updated.
        # - Marginal prices have been updated and exist for all active intervals.
        #
        # INPUTS:
        # market - Market object
        #
        # OUTPUTS:
        # updates array self.scheduledPowers

        # Gather the active time intervals.
        time_intervals = market.timeIntervals  # TimeInterval

        # 200929DJH: Commenting out these lines that are too crude for Version 3. Instead, scheduled powers in expired
        #            markets will be trimmed near the bottom of this method.
        # time_interval_values = [t.startTime for t in time_intervals]
        # self.scheduledPowers = [x for x in self.scheduledPowers if x.timeInterval.startTime in time_interval_values]

        # Index through active time intervals ti
        # NOTE 1911DJH: In Version 2, the range of this following for-loop started at 1 (i.e., at the second value). I
        # believe this had been done to avoid having building models schedule in the first time interval, which was
        # usually already within its delivery period. In Version 3, the market state transition machine should be used
        # to make sure that no negotiations take place after a market has cleared and begun delivery of its market
        # periods.
        for i in range(len(time_intervals)):

            # Find the marginal price for the indexed time interval
            marginal_price = find_obj_by_ti(market.marginalPrices, time_intervals[i])  # an IntervalValue
            marginal_price = marginal_price.value

            # Find the power that corresponds to the marginal price according to the set of active vertices in the
            # indexed time interval. Function Production() works for any power that is determined by its supply curve or
            # demand curve, as represented by the object's active vertices.
            value = production(self, marginal_price, time_intervals[i])  # [avg. kW]

            # Check to see if a scheduled power already exists in the indexed time interval.
            interval_value = find_obj_by_ti(self.scheduledPowers, time_intervals[i])  # an IntervalValue

            if interval_value is None:

                # No scheduled power was found in the indexed time interval. Create the interval value and assign it the
                # scheduled power.
                interval_value = IntervalValue(self, time_intervals[i], market,
                                               MeasurementType.ScheduledPower, value)

                # Append the scheduled power to the list of scheduled powers
                self.scheduledPowers.append(interval_value)

            else:

                # A scheduled power already exists in the indexed time interval. Simply reassign its value.
                interval_value.value = value  # [avg. kW]

        # 200929DJH: Trim values in expired markets so the list does not grow indefinitely.
        self.scheduledPowers = [x for x in self.scheduledPowers if x.market.marketState != MarketState.Expired]

        sp = [(x.timeInterval.name, x.value) for x in self.scheduledPowers]

    def schedule_engagement(self):
        # Required from AbstractModel, but not particularly useful for any Neighbor.
        return

    def update_dc_threshold(self, market):
        # Keep track of the month's demand-charge threshold
        #
        # Pseudocode:
        # 1. This method should be called prior to using the demand threshold. In reality, the threshold will change
        #    only during peak periods.
        # 2a. (preferred) Read a meter (see MeterPoint) that keeps track of an averaged power. For example, a
        #    determinant may be based on the average demand in a half hour period, so the MeterPoint would ideally track
        #    that average.
        # 2b. (if metering unavailable) Update the demand threshold based on the average power in the current time
        #    interval.

        # Find the MeterPoint that is configured to measure average demand for this Neighbor. The determination is
        # based on the meter's MeasurementType.
        mtr = [x for x in self.meterPoints if x.measurementType == MeasurementType.AverageDemandkW]
        mtr = mtr[0] if len(mtr) > 0 else None

        if mtr is None:

            # No appropriate MeterPoint was found. The demand threshold must be inferred.
            # 200731DJH: In Version 3, this is  improved to update the demand threshold using the peak power from the
            #            neighbor during the prior market object.
            '''  # Original replaced logic in this comment block
            time_intervals = market.timeIntervals
            time_intervals.sort(key=lambda x: x.startTime)

            # Find current demand d that corresponds to the nearest time interval.
            cur_demand = find_obj_by_ti(self.scheduledPowers, time_intervals[0])

            # Update the inferred demand
            # d = None if cur_demand == [] else cur_demand.value
            # d = cur_demand.value if len(cur_demand > 0) else 0.0
            if cur_demand is None:
                d = 0.0
            elif type(cur_demand) == 'list' and len(cur_demand) == 0:
                d = 0.0
            else:
                d = cur_demand.value

            self.demandThreshold = max([0, self.demandThreshold, d])  # [avg.kW]
            '''  # begin new logic to replace the above block ***
            prior_market = market.priorMarketInSeries
            if prior_market is None:
                return
            prior_market_powers = [x.value for x in self.scheduledPowers
                                   if x.market == prior_market]
            if prior_market_powers is not None and len(prior_market_powers) != 0:
                prior_peak = max(prior_market_powers)
                self.demandThreshold = max([0, self.demandThreshold, prior_peak])
            else:
                self.demandThreshold = float("inf")

            # _log.debug("measurement: {} threshold: {}".format(d, self.demandThreshold))
        else:
            # An appropriate MeterPoint was found. The demand threshold may be updated from the MeterPoint.

            # Update the demand threshold.
            self.demandThreshold = max([0, self.demandThreshold, mtr.currentMeasurement])  # [avg.kW]
            #_log.debug("Meter: {} measurement: {} threshold: {}".format(mtr.name,
            #                                                            mtr.current_measurement,
            #                                                            self.demandThreshold))

        # The demand threshold should be reset in a new month. First find the current month number mon.
        mon = Timer.get_cur_time().month

        if mon != self.demandMonth:
            # This must be the start of a new month. The demand threshold must be reset. For now, "resetting" means
            # using a fraction (e.g., 80%) of the final demand threshold in the prior month.
            self.demandThreshold = self.demandThresholdCoef * self.demandThreshold
            self.demandMonth = mon

    def update_dual_costs(self, market):

        # Gather the active time intervals.
        time_intervals = market.timeIntervals

        # 200929DJH: Commenting out this approach that is too crude for Version 3. Instead, dual costs in expired
        #            markets will be removed near the bottom of this method.
        # time_interval_values = [t.startTime for t in time_intervals]
        # self.dualCosts = [x for x in self.dualCosts if x.timeInterval.startTime in time_interval_values]

        # 101213DJH: This next loop had been corrupted in Version 1 by starting with the second value (i.e., 1). This
        # should no longer be needed in Version 2 and the market state machine. This was found by the failure of the
        # method's test.
        for i in range(0, len(time_intervals)):

            # Find the marginal price mp for the indexed time interval in the given market
            marginal_price = find_obj_by_ti(market.marginalPrices, time_intervals[i])
            marginal_price = marginal_price.value

            # Find the scheduled power for the neighbor in the indexed time interval.
            scheduled_power = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            scheduled_power = scheduled_power.value

            # Find the production cost in the indexed time interval.
            production_cost = find_obj_by_ti(self.productionCosts, time_intervals[i])
            production_cost = production_cost.value

            # Dual cost in the time interval is calculated as production cost, minus the product of marginal price,
            # scheduled power, and the duration of the time interval.
            interval_duration = get_duration_in_hour(time_intervals[i].duration)

            dual_cost = production_cost - (marginal_price * scheduled_power * interval_duration)  # a dual cost [$]

            # Check whether a dual cost exists in the indexed time interval
            interval_value = find_obj_by_ti(self.dualCosts, time_intervals[i])

            if interval_value is None:

                # No dual cost was found in the indexed time interval. Create an interval value and assign it the
                # calculated value.
                interval_value = IntervalValue(self, time_intervals[i], market, MeasurementType.DualCost, dual_cost)

                # Append the new interval value to the list of active interval values.
                self.dualCosts.append(interval_value)

            else:

                # The dual cost value was found to already exist in the indexed time interval. Simply reassign it the
                # new calculated value.
                interval_value.value = dual_cost  # a dual cost [$]

        # Ensure that only active time intervals are in the list of dual costs.
        # NOTE: This was found to have been commented out for some reason. ????????????????????????????????????????
        # 200929DJH: Fixed to work in Version 3. Values in expired markets are trimmed.
        # self.dualCosts = [x for x in self.dualCosts if x.timeInterval in time_intervals]
        self.dualCosts = [x for x in self.dualCosts if x.market.marketState != MarketState.Expired]

        # Sum the total dual cost and save the value
        # 200929DJH: This sum should be for only values in the current market.
        # self.totalDualCost = sum([x.value for x in self.dualCosts])  # total dual cost [$]
        self.totalDualCost = sum([x.value for x in self.dualCosts if x.market.marketState != MarketState.Expired])

        dc = [(x.timeInterval.name, x.value) for x in self.dualCosts]
        _log.debug("{} neighbor model dual costs are: {}".format(self.name, dc))

    def update_production_costs(self, market):
        time_intervals = market.timeIntervals

        # 200929DJH: Commenting out this approach that is too crude for Version 3. Instead, values in expired markets
        #            will be trimmed near the bottom of this method.
        # time_interval_values = [t.startTime for t in time_intervals]
        # self.productionCosts = [x for x in self.productionCosts if x.timeInterval.startTime in time_interval_values]

        # This range had been corrupted in Version 1 making it start with the second value. Doing so should no longer be
        # necessary in Version 2 with it market state machine. This issue was found from a failed test.
        for i in range(0, len(time_intervals)):

            # Get the scheduled power in the indexed time interval.
            scheduled_power = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            scheduled_power = scheduled_power.value

            # Call on function that calculates production cost pc based on the vertices of the supply or demand curve.
            production_cost = prod_cost_from_vertices(self, time_intervals[i], scheduled_power)  # prod cost [$]

            # Check to see if the production cost value has been defined for the indexed time interval.
            interval_value = find_obj_by_ti(self.productionCosts, time_intervals[i])

            if interval_value is None:

                # The production cost value has not been defined in the indexed time interval. Create it and assign its
                # value pc.
                interval_value = IntervalValue(self, time_intervals[i], market,
                                               MeasurementType.ProductionCost,
                                               production_cost)

                # Append the production cost to the list of active production cost values.
                self.productionCosts.append(interval_value)

            else:

                # The production cost value already exists in the indexed time interval. Simply reassign its value.
                interval_value.value = production_cost  # production cost [$]

        # Ensure that only active time intervals are in the list of active production costs.
        # NOTE: This was found to have been commented out. ??????????????????????????????????????????????
        # 200929DJH: Corrected to work in Version 3.
        # self.productionCosts = [x for x in self.productionCosts if x.timeInterval in time_intervals]
        self.productionCosts = [x for x in self.productionCosts if x.market.marketState != MarketState.Expired]

        # Sum the total production cost.
        # 200929DJH: Corrected for Version 3. Sum must be taken only for values in current market.
        # self.totalProductionCost = sum([x.value for x in self.productionCosts])  # total production cost [$]
        self.totalProductionCost = sum([x.value for x in self.productionCosts if x.market == market])

        pc = [(x.timeInterval.name, x.value) for x in self.productionCosts]
        _log.debug("{} neighbor model production costs are: {}".format(self.name, pc))

    def update_vertices(self, market):
        # Update the active vertices that define Neighbors' residual flexibility in the form of supply or demand curves.
        #
        # The active vertices of non-transactive neighbors are relatively constant. Active vertices must be created for
        # new active time intervals. Vertices may be affected by demand charges, too, as new demand-charge thresholds
        # are becoming established.
        #
        # The active vertices of transactive neighbors are also relatively constant. New vertices must be created for
        # new active time intervals. But active vertices must also be checked and updated whenever a new transactive
        # signal is received.
        #
        # PRESUMPTIONS:
        # - time intervals are up-to-date
        # - at least one default vertex has been defined, should all other efforts to establish meaningful vertices fail
        #
        # INPUTS:
        # market - Market object
        #
        # OUTPUTS:
        # Updates self.activeVertices - an array of IntervalValues that contain Vertex() structs
        #
        # 200731DJH: Streamlining and simplifying this method. The demand-charges, especially, were found to be bad in
        #            non-iterative market clearings. The new approach is to simply define active vertices from received
        #            signals, then apply methods to include and remove the impacts of marginal losses and demand
        #            charges.

        # (1) Generate active vertices for the non-transactive or transactive neighbor object.

        # Extract and sort active market time intervals.
        time_intervals = set(market.timeIntervals)
        time_intervals = sorted(time_intervals, key=attrgetter('startTime'))

        # Get the default vertices.
        default_vertices = self.defaultVertices

        if len(default_vertices) == 0:
            # No default vertices are found. Warn and return.
            Warning('No default vertices were found for neighbor object ' + str(self.name)
                    + '. No active vertices can be created.')
            """
            _log.warning('At least one default vertex must be defined for neighbor model %s. '
                         'Scheduling was not performed' % (self.name))
            """
            return

        for i in range(len(time_intervals)):

            # Pick out the indexed time interval. Corresponding time interval names are used in the received signals.
            time_interval = time_intervals[i]
            time_interval_name = time_interval.name

            # Clean up the neighbor's active vertices. Remove any vertices that happen to exist already in this time
            # interval. These will be re-created. (This makes for simpler code logic that first determining if the
            # vertex exists and alternatively replacing its value or creating a new vertex.)
            # 200925DJH: Checked this logic for Version 3. It should be fine because the time interval is unique both to
            #            the starting time and a market.
            self.activeVertices = [x for x in self.activeVertices if x.timeInterval != time_interval]

            if not self.transactive:
                # 200702DJH: Implementers, please replace this method for non-transactive neighbor boundary conditions
                #            that are more sophisticated than this.

                # The neighbor is not transactive. Default vertices were found. Index through the default vertices.
                for k in range(len(default_vertices)):

                    # Pick out the indexed default vertex.
                    default_vertex = default_vertices[k]

                    # Check for and correct treatment of a lone default vertex marginal price.
                    if len(default_vertices) == 1:
                        default_vertex.marginalPrice = float('inf')
                        default_vertex.record = 0

                    # Create an active vertex interval value in the indexed time interval.
                    self.activeVertices.append(IntervalValue(calling_object=self,
                                                             time_interval=time_interval,
                                                             market=market,
                                                             measurement_type=MeasurementType.ActiveVertex,
                                                             value=default_vertex
                                                             )
                                               )

            elif self.transactive:

                # The neighbor is transactive. Check for transactive records in the indexed time interval and market.
                received_vertices = [x for x in self.receivedSignal if x.timeInterval == time_interval_name]

                if len(received_vertices) == 0:

                    # No received transactive records were found for the indexed time interval. Default value(s) must
                    # be used. This should be an abnormal condition except upon startup of iterative market methods.
                    # Raise a warning.
                    Warning('No received transactive signal was found for transactive neighbor '
                                         + str(self.name) + ' in time interval ' + str(time_interval.name))

                    # Index through the default vertices.
                    for k in range(len(default_vertices)):

                        # Pick out the indexed default vertex
                        default_vertex = default_vertices[k]

                        # Check for and correct treatment of a lone default vertex marginal price.
                        if len(default_vertices) == 1:
                            default_vertex.marginalPrice = float('inf')
                            default_vertex.record = 0

                        # Create an active vertex interval value in the indexed time interval and append it to the
                        # neighbor's list of active vertices.
                        self.activeVertices.append(IntervalValue(calling_object=self,
                                                                 time_interval=time_interval,
                                                                 market=market,
                                                                 measurement_type=MeasurementType.ActiveVertex,
                                                                 value=default_vertex
                                                                 )
                                                   )

                else:

                    # At least 1 vertex received. One or more transactive records have been received concerning the
                    # indexed time interval. Use these to re-create active vertices.

                    # Sort the received_vertices (which happen to be TransactiveRecords) by increasing price and power.
                    received_vertices = order_vertices(received_vertices)

                    # Index through the vertices in the received transactive records for the indexed time interval.
                    for k in range(len(received_vertices)):

                        # Pick out the indexed received vertex.
                        received_vertex = received_vertices[k]

                        # Create working values of power and prices from the received vertices.
                        power = received_vertex.power
                        cost = received_vertex.cost
                        marginal_price = received_vertex.marginalPrice
                        record = received_vertex.record

                        # Check for and correct treatment of a lone default vertex marginal price.
                        if len(received_vertices) == 1:
                            marginal_price = float('inf')
                            record = 0

                        # Create a corresponding (price,power) pair (aka "active vertex") using the received power and
                        # marginal price. See struct Vertex(). Then append the vertex to the neighbor's active vertices.
                        # 200803DJH: I've added property 'record' to Vertex.
                        self.activeVertices.append(IntervalValue(calling_object=self,
                                                                 time_interval=time_interval,
                                                                 market=market,
                                                                 measurement_type=MeasurementType.ActiveVertex,
                                                                 value=Vertex(marginal_price=marginal_price,
                                                                              prod_cost=cost,
                                                                              power=power,
                                                                              record=record
                                                                              )
                                                                 )
                                                   )

            else:

                # Logic should not arrive here. Error.
                raise RuntimeWarning('Neighbor ' + self.name + ' must be either transactive or not.')

        # **************************************************************************************************************
        # Update active vertices to include the impacts of marginal losses and demand charges. *************************
        # At this point, active vertices have been created, regardless whether the neighbor is transactive.

        # Recall the current demand threshold that applies to this neighbor in this month, and assign it to the active
        # threshold that may increase while indexing through the time intervals.
        demand_threshold = self.demandThreshold
        active_threshold = copy(demand_threshold)

        # Index again through the active market time intervals.
        for t in range(len(time_intervals)):

            # Pick out the indexed time interval.
            time_interval = time_intervals[t]

            # Collect the active vertices that are in this time interval (and market). These will be acted upon to
            # include effects of losses and demand charges.
            active_vertices = [x.value for x in self.activeVertices if x.timeInterval == time_interval]

            # clean up the active vertices by removing any of its interval values that are in this time interval. These
            # vertices will be re-created once they have become updated.
            self.activeVertices = [x for x in self.activeVertices if x.timeInterval != time_interval]

            # Include the impacts of marginal losses for power that is RECEIVED from this neighbor.
            # Note: This impact can be turned off by assigning property the neighbor 'lossFactor' = 0.
            if self.lossFactor != 0:
                active_vertices = self.include_marginal_losses(vertices=active_vertices)

            #_log.debug("update_vertices: active_threshold: {}".format(active_threshold))
            #_log.debug("update_vertices: time interval: {}".format(time_interval.startTime))
            #for x in active_vertices:
            #    _log.debug("update_vertices: ({}, {}, {})".format(x.record, x.marginalPrice, x.power))
            # Include the impacts of demand charges that are imposed on any power that is RECEIVED from this neighbor.
            # Check to see if the neighbor has a scheduled power in this time interval.
            # Note that this logic may be turned off by simply setting property demandRate = 0.
            if self.demandRate != 0:
                # 201009DJH: I found this error in these commented lines. The conditional is trying to compare a string
                # and time interval object. How was this permitted by PyCharm?
                # current_scheduled_power = [x.value for x in self.scheduledPowers
                #                            if x.timeInterval.name == time_interval]
                current_scheduled_power = [x.value for x in self.scheduledPowers
                                           if x.timeInterval == time_interval]
                if current_scheduled_power is not None and len(current_scheduled_power) != 0:
                    active_threshold = max(active_threshold, current_scheduled_power[0])
                active_vertices = self.include_demand_charges(vertices=active_vertices, threshold=active_threshold)

            # Return the corrected vertices back to the neighbor's list of active vertices.
            for av in range(len(active_vertices)):

                # Pick out the indexed vertex.
                active_vertex = active_vertices[av]

                # Store the vertex as an active vertex interval value.
                self.activeVertices.append(IntervalValue(calling_object=self,
                                                         time_interval=time_interval,
                                                         market=market,
                                                         measurement_type=MeasurementType.ActiveVertex,
                                                         value=active_vertex)
                                           )

        # 200929DJH: Trim any active vertices that lie in expired markets so that the list will not grow indefinitely.
        self.activeVertices = [x for x in self.activeVertices if x.market.marketState != MarketState.Expired]

    def old_update_vertices(self, market):
        # Update the active vertices that define Neighbors' residual flexibility in the form of supply or demand curves.
        #
        # The active vertices of non-transactive neighbors are relatively constant. Active vertices must be created for
        # new active time intervals. Vertices may be affected by demand charges, too, as new demand-charge thresholds
        # are becoming established.
        #
        # The active vertices of transactive neighbors are also relatively constant. New vertices must be created for
        # new active time intervals. But active vertices must also be checked and updated whenever a new transactive
        # signal is received.
        #
        # PRESUMPTIONS:
        # - time intervals are up-to-date
        # - at least one default vertex has been defined, should all other efforts to establish meaningful vertices fail
        #
        # INPUTS:
        # market - Market object
        #
        # OUTPUTS:
        # Updates self.activeVertices - an array of IntervalValues that contain Vertex() structs
        # TODO: Consider eliminating the try-catch pairs in "update_vertices" to improve code structure.

        # Extract active time intervals.
        time_intervals = market.timeIntervals

        for i in range(len(time_intervals)):

            # Flag for logging demand charge 1st time only
            # TODO: Check this logic for logging demand charge
            dc_logged = False

            # Get the default vertices.
            default_vertices = self.defaultVertices

            if len(default_vertices) == 0:
                # No default vertices are found. Warn and return.
                _log.warning('At least one default vertex must be defined for neighbor model %s. '
                             'Scheduling was not performed' % (self.name))
                return

            if not self.transactive:
                # 200702DJH: Implementers, please replace this method for non-transctive neighbor boundary conditions
                #            that are more sophisticated than this.

                # Neighbor is not transactive. Default vertices were found. Index through the default vertices.
                for k in range(len(default_vertices)):

                    # Get the indexed default vertex.
                    value = default_vertices[k]

                    # Create an active vertex interval value in the indexed time interval.
                    interval_value = IntervalValue(self, time_intervals[i], market, MeasurementType.ActiveVertex, value)

                    # Append the active vertex to the list of active vertices
                    self.activeVertices.append(interval_value)

            elif self.transactive:

                # Neighbor is transactive. Check for transactive records in the indexed time interval.
                received_vertices = [x for x in self.receivedSignal if x.timeInterval == time_intervals[i].name]

                if len(received_vertices) == 0:

                    # No received transactive records address the indexed time interval. Default value(s) must be used.
                    # Default vertices were found. Index through the default vertices.
                    for k in range(len(default_vertices)):  # for k = 1:len(default_vertices)

                        # Get the indexed default vertex
                        value = default_vertices[k]

                        # Create an active vertex interval value in the indexed time interval.
                        interval_value = IntervalValue(self, time_intervals[i], market, MeasurementType.ActiveVertex,
                                                       value)  # an IntervalValue

                        # Append the active vertex to the list of active vertices.
                        self.activeVertices.append(interval_value)

                else:

                    # at least 1 vertex received. One or more transactive records have been received concerning the
                    # indexed time interval. Use these to re-create active Vertices.

                    # Sort the received_vertices (which happen to be TransactiveRecords) by increasing price and power.
                    received_vertices = order_vertices(received_vertices)

                    # Prepare for demand charge vertices.

                    # This flag will be replace by its preceding ordered vertex index if any of the vertices are found
                    # to exceed the current demand threshold.
                    demand_charge_flag = 0  # simply a flag

                    # The demand-charge threshold is based on the actual measured peak this month, but it may also be
                    # superseded in predicted time intervals prior to the currently indexed one.
                    # Start with the metered demand threshold.
                    demand_charge_threshold = self.demandThreshold  # [avg.kW]

                    # Calculate the peak in time intervals that come before the one now indexed by i.
                    # Get all the scheduled powers.
                    prior_power = self.scheduledPowers  # [avg.kW]
                    #_log.debug("neighbor_model.py, update_vertices, scheduledPowers: {}".format([x.value for x in self.scheduledPowers]))

                    if len(prior_power) < i + 1:

                        # Especially the first iteration can encounter missing scheduled power values. Place these out
                        # of the way by assigning them as small as possible. The current demand threshold will always
                        # trump this value.
                        prior_power = [float("-inf")]  # -inf

                    else:

                        # The scheduled powers look fine. Pick out the ones that are indexed prior to the currently
                        # indexed value.
                        prior_power = [x.value for x in prior_power[0:i + 1]]

                    # Pick out the maximum power from the prior scheduled power values.
                    predicted_prior_peak = max(prior_power)  # [avg.kW]

                    # The demand-charge threshold for the indexed time interval should be the larger of the current and
                    # predicted peaks.
                    demand_charge_threshold = max([demand_charge_threshold, predicted_prior_peak])  # [avg.kW]

                    # Index through the vertices in the received transactive records for the indexed time interval.
                    for k in range(len(received_vertices)):

                        # Create working values of power and marginal price from the received vertices.
                        power = received_vertices[k].power
                        marginal_price = received_vertices[k].marginalPrice

                        # If the Neighbor power is positive (importation of electricity), then the value may be affected
                        # by losses. The available power is diminished (compared to what was sent), and the effective
                        # marginal price is increased (because myTransactiveNode is paying for electricity that it does
                        # not receive).
                        if power > 0:
                            try:
                                factor1 = (power / self.maximumPower) ** 2
                                factor2 = 1 + factor1 * self.lossFactor
                                power = power / factor2
                                marginal_price = marginal_price * factor2
                                '''
                                if (self.this_transactive_node is not None
                                    and self.system_loss_topic != ''
                                    and received_vertices[k].record == 0):
                                    msg = {
                                        'ts': received_vertices[k].timeInterval,
                                        'predicted_clear_power': power,
                                        'max_power': self.maximumPower,
                                        'factor1': factor1,
                                        'factor2': factor2,
                                        'vertex_record': received_vertices[k].record,
                                        'demand_charge_threshold': demand_charge_threshold
                                    }
                                    self.this_transactive_node.vip.pubsub.publish(peer='pubsub',
                                                                topic=self.system_loss_topic,
                                                                message=msg)
                                '''

                                # If there are multiple transactive records in the indexed time interval, we don't need
                                # to create a vertex for Record #0. Record #0 is the balance point, which must lie on
                                # existing segments of the supply or demand curve. This is moved here instead of staying
                                # at the beginning of the loop is because we want to log system loss
                                if len(received_vertices) >= 3 and received_vertices[k].record == 0:
                                    continue  # jumps out of for loop to next iteration

                                if power > demand_charge_threshold:
                                    # The power is greater than the anticipated demand threshold. Demand charges are in
                                    # play. Set a flag.
                                    demand_charge_flag = k

                                # Publish to db
                                '''
                                if self.this_transactive_node is not None and self.dc_threshold_topic != '' \
                                        and k == len(received_vertices)-1:
                                    dc_flag = "has demand charge"
                                    if not demand_charge_flag:
                                        dc_flag = "no demand charge"
                                    dc_msg = {
                                        'ts': received_vertices[k].timeInterval,
                                        'dc_flag': dc_flag,
                                        'demand_charge_threshold': demand_charge_threshold,
                                        'predicted_power_peak': predicted_prior_peak,
                                        'max_predicted_power': power
                                    }
                                    self.this_transactive_node.vip.pubsub.publish(peer='pubsub',
                                                                topic=self.dc_threshold_topic,
                                                                message=dc_msg)
                                '''
                                # Debug negative price & demand charge
                                _log.debug("power: {} - demand charge threshold: {} - predicted power peak: {}"
                                           .format(power, demand_charge_threshold, predicted_prior_peak))
                                _log.debug("prior power: {}".format(prior_power))
                                _log.debug("received vertices: {}"
                                           .format([(v.timeInterval, v.power) for v in received_vertices]))
                            except:
                                _log.error("{} has power {} AND object ({}) maxPower {} and minPower {}"
                                           .format(self.name, power,
                                                   self.name,
                                                   self.maximumPower,
                                                   self.minimumPower))
                                raise
                        # Create a corresponding (price,power) pair (aka "active vertex") using the received power and
                        # marginal price. See struct Vertex().
                        value = Vertex(marginal_price, received_vertices[k].cost, power, None)

                        # Create an active vertex interval value for the vertex in the indexed time interval.
                        interval_value = IntervalValue(self, time_intervals[i], market,
                                                       MeasurementType.ActiveVertex, value)

                        # Append the active vertex to the list of active vertices.
                        self.activeVertices.append(interval_value)

                    # DEMAND CHARGES
                    # Check whether the power of any of the vertices was found to be larger than the current demand-
                    # charge threshold, as would be indicated by this flag being a value other than 0.
                    if demand_charge_flag != 0:

                        # log.debug("DEMAND CHARGE 1")
                        # Demand charges are in play. Get the newly updated active vertices for this transactive
                        # Neighbor again in the indexed time interval.
                        vertices = [x.value for x in self.activeVertices if
                                    x.timeInterval.startTime == time_intervals[i].startTime]

                        # Find the marginal price that would correspond to the demand-charge threshold, based on the
                        # newly updated (but excluding the effects of demand charges) active vertices in the indexed
                        # time interval.
                        marginal_price = self.marginal_price_from_vertices(demand_charge_threshold, vertices)  # [$/kWh]

                        # Create the first of two vertices at the intersection of the demand-charge threshold and the
                        # supply or demand curve from prior to the application of demand charges.
                        vertex = Vertex(marginal_price, 0, demand_charge_threshold)

                        # Create an IntervalValue for the active vertex.
                        interval_value = IntervalValue(self, time_intervals[i], market,
                                                       MeasurementType.ActiveVertex, vertex)

                        # Store the new active vertex interval value
                        self.activeVertices.append(interval_value)

                        # Create the marginal price of the second of the two new vertices, augmented by the demand rate.
                        marginal_price = marginal_price + self.demandRate  # [$/kWh]

                        # Create the second vertex.
                        vertex = Vertex(marginal_price, 0, demand_charge_threshold)

                        # ... and the interval value for the second vertex,
                        interval_value = IntervalValue(self, time_intervals[i], market,
                                                       MeasurementType.ActiveVertex, vertex)

                        # ... and finally store the active vertex.
                        self.activeVertices.append(interval_value)

                        # Check that vertices having power greater than the demand threshold have their marginal prices
                        # reflect the demand charges. Start by picking out those in the currently indexed time interval.
                        interval_values = [x for x in self.activeVertices
                                           if x.timeInterval.startTime == time_intervals[i].startTime]

                        # Index through the current active vertices in the indexed time interval. At this point, these
                        # include vertices from both prior to and after the introduction of demand-charge vertices.
                        for k in range(len(interval_values)):

                            # Extract the indexed vertex.
                            vertex = interval_values[k].value

                            # Extract the power of the indexed vertex.
                            vertex_power = vertex.power  # [avg.kW]

                            if vertex_power > demand_charge_threshold:

                                # The indexed vertex's power exceeds the demand-charge threshold. Increment the vertex's
                                # marginal price with the demand rate.
                                vertex.marginalPrice = vertex.marginalPrice + self.demandRate

                                # ... and re-store the vertex in its IntervalValue
                                interval_values[k].value = vertex  # an IntervalValue

                    else:
                        pass
                        _log.debug("NO DEMAND CHARGE 1")

            else:

                # Logic should not arrive here. Error.
                raise ('Neighbor %s must be either transactive or not.' % (self.name))

        av = [(x.timeInterval.name, x.value.marginalPrice, x.value.power) for x in self.activeVertices]
        #_log.debug("{} neighbor model active vertices are: {}".format(self.name, av))

    def prep_transactive_signal(self, market, this_transactive_node):
        # Prepare transactive records to send to a transactive neighbor. The prepared transactive signal should
        # represent the residual flexibility offered to the transactive neighbor in the form of a supply or demand
        # curve.
        # NOTE: the flexibility of the prepared transactive signals refers to LOCAL value. Therefore this method does
        # not make modifications for power losses or demand charges, both of which are being modeled as originating with
        # the RECIPIENT of power.
        # FUTURE: The numbers of vertices may be restricted to emulate various auction mechanisms.
        #
        # ASSUMPTIONS:
        # - The local system has converged, meaning that all asset and neighbor powers have been calculated
        # - Neighbor and asset demand and supply curves have been updated and are accurate. Active vertices will be used
        #   to prepare transactive records.
        #
        # INPUTS:
        # tnm - Transactive Neighbor - target node to which a transactive signal is to be sent
        # market - Market object
        # this_transactive_node - Agent's TransactiveNode object
        #
        # OUTPUTS:
        # - Updates mySignal property, which contains transactive records that are ready to send to the transactive
        # neighbor
        #
        # 200529DJH: Simplifying the structure for Version 3. The net market vertices representing the current balance
        #            point--indicated by Record #0--is not easily identified in an auction because marginal prices are
        #            speculative, and modeled neighbor objects do not truly schedule before a price is returned from an
        #            auction. It is still easy to find the soft extremes of the offered flexibility though. In this
        #            revision,
        #            (1) all the summed vertices in a viable range are turned into transactive records,
        #            (2) a lone vertex is presumed to be Record #0 and is assigned to infinity (i.e., no flexibility),
        #            (2) make sure that a vertex exists at the minimum soft constraint and assign Record #1
        #            (3) make sure that a vertex exists at the maximum soft constraint and assign Record #2
        #            (2) assign record numbers to other transactive records in range [3, 4, ...]. (Not worrying about
        #                numbering continuity and hoping this will not be problematic.
        # 200611DJH: Completed troubleshooting. Errors were found.
        #            (1) Check that residual vertices are in range should have tested powers, not prices.
        #            (2) Tests were found to have relied on scheduled powers, which dependency has been reduced. The
        #                method now makes the prepared transactive records much more like the residual active vertices.
        #                Tests were necessarily changed to achieve consistency.
        #            (3) There may have been an issue in original code that used hard constraints instead of the soft
        #                ones. The minimum and maximum powers will now be limited to either the hard constraint or the
        #                soft constraint from the active vertices, whichever is narrower.
        # 200803DJH: The effects of marginal losses and demand charges that were incorporated into this neighbor's
        #            active vertices should be removed during the creation of mySignal that is ready to send. The
        #            general principle is that all sent, prepared, and received transactive signals should remain always
        #            in the perspective of the remote neighbor.
        #            - Losses of local power due to inefficient importation should be re-added for the perspective of
        #              the remote neighbor as power is IMPORTED from the remote neighbor.
        #            - Increased marginal price of imported power from this remote neighbor should be restored again
        #              to lower prices at the remote neighbor. This refers now to energy that is IMPORTED from the
        #              remote neighbor.
        #            - Demand charges added to peak power supply must be removed from peak power to be imported from
        #              the remote neighbor.
        #            A general principle should be that an equilibrium point is unchanged by the importation and
        #            exportation of signals until an actual perturbation occurs. The steps are, in each time interval,
        #            (1) Use method 'sum_vertices()' to find the supplementary response vertices for the neighbor.
        #            (2) Act on the vertices to REMOVE impacts of demand charges and marginal losses in this copy.
        #            (3) Use the modified vertices to create transactive records stored in 'mySignal' ready to send to
        #                the remote neighbor.

        # Ensure that object tnm is a transactive neighbor.
        if not self.transactive:
            # log.warning('Neighbor must be transactive')
            return

        # Gather unique active market time intervals.
        time_intervals = market.timeIntervals

        # These thresholds are initialized here and used during the assessment of demand charges.
        demand_threshold = -self.demandThreshold
        active_threshold = demand_threshold

        # 210303DJH: Create a list to gather new signal records.
        new_signal = []

        # Index through the active time intervals.
        for i in range(len(time_intervals)):

            # Pick out the indexed market time interval.
            time_interval = time_intervals[i]
            time_interval_name = time_interval.name

            # Create the vertices of the net supply or demand curve, EXCLUDING this transactive neighbor (i.e., "tnm").
            # NOTE: It is important that the transactive neighbor is excluded.
            vertices = market.sum_vertices(this_transactive_node, time_interval, self)

            # This should be rare, Warn if no vertices are found.
            if vertices is None:
                RuntimeError('No summed vertices were found in method prep_transactive_signal for neighbor '
                               + self.name + ' in time interval ' + time_interval_name)

            # Find the minimum and maximum powers from the summed vertices. These are soft constraints that represent a
            # range of flexibility. The range will usually be excessively large from the supply side, much smaller from
            # the demand side.

            vertex_powers = [x.power for x in vertices]  # [avg.kW]
            minimum_power = max(-self.maximumPower, min(vertex_powers))  # [avg.kW]
            maximum_power = min(-self.minimumPower, max(vertex_powers))  # [avg.kW]

            # If flexibility is being offered (i.e., more than one vertex), then we must make sure there exist vertices
            # at the extrema of the flexibility range.
            if minimum_power != maximum_power:

                # Find the vertex conditions at the minimum and create a vertex if none currently exists.
                minimum_record = [x for x in vertices if x.power == minimum_power]
                if minimum_record is None or len(minimum_record) == 0:
                    minimum_price = self.marginal_price_from_vertices(minimum_power, vertices)
                    vertices.append(Vertex(marginal_price=minimum_price,
                                           prod_cost=0,
                                           power=minimum_power
                                           )
                                    )
                # Find the vertex conditions at the maximum and create a vertex if none currently exists.
                maximum_record = [x for x in vertices if x.power == maximum_power]
                if maximum_record is None or len(maximum_record) == 0:

                    maximum_price = self.marginal_price_from_vertices(maximum_power, vertices)
                    vertices.append(Vertex(marginal_price=maximum_price,
                                           prod_cost=0,
                                           power=maximum_power
                                           )
                                    )

            else:
                if len(vertices) == 1:
                    _log.warning('Unexpected flexibility logic in module {self.name} method prep_transactive_signal()')
                vertices[0].marginalPrice = float('inf')
                vertices[0].record = 0


            # Trim the list of vertices to remove any that are outside the soft flexibility range.
            vertices = [x for x in vertices if minimum_power <= x.power <= maximum_power]

            # At this point, the vertices include any flexibility, stated from the perspective of the local agent.

            # Remove the impacts of any demand charges that were included at the local node but are not relevant at the
            # remote agent location. Note that the effects of demand charges may be ignored if the demand rate is set to
            # 0.
            # NOTE: This correction should be done before correcting for marginal losses because demand charges are
            # presumed to apply to actual metered demand.
            if self.demandRate != 0:
                scheduled_power = [x.value for x in self.scheduledPowers if x.timeInterval == time_interval]
                if scheduled_power is not None and len(scheduled_power) != 0:
                    active_threshold = min(active_threshold, scheduled_power[0])
                vertices = self.remove_demand_charges(vertices=vertices, threshold=active_threshold)

            # Remove the impacts of marginal losses to place the vertices into the perspective of the remote neighbor to
            # which a transactive signal will be sent. Note that the effects of losses can be ignored by making the loss
            # factor = 0.
            if self.lossFactor != 0:
                vertices = self.remove_marginal_losses(vertices=vertices)

            # The vertices are now suitable for creating transactive records that represent the remote agent
            # perspective.

            # Keep only the transactive records that are NOT in the indexed time interval. The ones in the indexed time
            # interval will be recreated.
            # 20103DJH: Time interval names have been prepended with the market series name to make them unique to their
            #           market series.
            #           TODO: Revisit this issue for the case when successive markets in a market series overlap. But
            #            maybe this is OK if only the active ones are recorded, even if they overlap.
            self.mySignal = [x for x in self.mySignal if x.timeInterval != time_interval_name]

            # Represent the corrected vertices as transactive records and store them in mySignal, where they are ready
            # to send to the remote neighbor.
            # 200804DJH: TENT used to apply much value to a transactive record's record number. I have not been able to
            #            maintain this practice for Version 3 because auction markets do not resolve their scheduled
            #            powers before sending transactive signals.

            for v in range(len(vertices)):

                # Pick out the indexed vertex.
                vertex = vertices[v]

                # 210126DJH: Appending Transactive Record with new properties that help with data collection provenance.
                new_record = TransactiveRecord(time_interval=time_interval_name,
                                               record=int(v),
                                               marginal_price=vertex.marginalPrice,
                                               power=vertex.power,
                                               cost=0
                                               )
                # 210303DJH: These assignments are being made explicitly to ensure that the correct parameter names are
                #            assigned. TODO: Check that class TransactiveRecord was updated.
                new_record.neighborName = self.name
                new_record.direction = 'prepared'
                new_record.marketName = market.name

                new_signal.append(new_record)

        # 210303DJH: Extend the new signal records to mySignal.
        self.mySignal.extend(new_signal)

        # 210303DJH: Save a copy of the newly prepared signal records to a CSV file.
        if new_signal:
            append_table(obj=new_signal)

        # 201013DJH: Trim the list of transactive records in mySignal if they reference time intervals that are no
        #            longer in active markets.
        all_markets = [x for x in this_transactive_node.markets]
        valid_time_interval_names = []
        for i in range(len(all_markets)):
            valid_time_interval_names.extend([x.name for x in all_markets[i].timeIntervals])
        self.mySignal = [x for x in self.mySignal
                                            if x.timeInterval in valid_time_interval_names]

    def send_transactive_signal(self, market, this_transactive_node, topic, start_of_cycle=False, fail_to_converged=False):
        # Send transactive records to a transactive neighbor.
        #
        # Retrieves the current transactive records, formats them into a table, and "sends" them to a text file for the
        # transactive neighbor. The property mySignal is a storage location for the current transactive records, which
        # should capture at least the active time intervals' local marginal prices and the power that is scheduled to be
        # received from or sent to the neighbor.
        # Records can also capture flex vertices for this neighbor, which are the supply or demand curve, less any
        # contribution from the neighbor. Transactive record #0 is the scheduled power, and other record numbers are
        # flex vertices. This approach anticipates that transactive signal might not include all time intervals or
        # replace all records. The neighbor similarly prepares and sends transactive signals to this location.
        # this_transactive_node - Agent's TransactiveNode object
        # **************************************************************************************************************
        # 191212DJH: This appears to bypass most of my original code and dumps transactive records into some sort of
        # message that is probably meaningful to Volttron. This may work for a Volttron environment, but agents cannot
        # all be presumed to be run on Volttron platforms.

        # If neighbor is non-transactive, warn and return. Non-transactive neighbors do not communicate transactive
        # signals.
        if not self.transactive:
            _log.warning(
                'Non-transactive neighbors do not send transactive signals. No signal is sent to %s.' % self.name)
            return

        # Collect current transactive records concerning myTransactiveNode.
        # 210127DJH: Adding parameter 'market" to those sent to send_transactive_signal(). The market should be used to
        #            make sure that only transactive records that are relevant to the current market are sent.
        transactive_records = [x for x in self.mySignal if x.marketName == market.name]

        if len(transactive_records) == 0:  # No signal records are ready to send
            _log.warning("No transactive records were found. No transactive signal can be sent to %s." % self.name)
            return

        # 210127DJH: These new parameters will help us keep track of record provenance.
        for transactive_record in transactive_records:
            transactive_record.direction = 'sent'
            transactive_record.neighborName = self.name
            transactive_record.marketName = market.name

        msg = json.dumps(transactive_records, default=json_econder)
        msg = json.loads(msg)

        #_log.debug("At {}, {} sends signal from {} on topic {} message {}"
        #           .format(Timer.get_cur_time(),
        #                   self.name,
        #                   self.location, topic, msg))
        if topic:
            this_transactive_node.vip.pubsub.publish(peer='pubsub',
                                                 topic=topic,
                                                 message={'source': self.location,
                                                          'curves': msg,
                                                          'start_of_cycle': start_of_cycle,
                                                          'fail_to_converged': fail_to_converged,
                                                          'tnt_market_name': market.name})

        topic = this_transactive_node.transactive_record_topic

        headers = {headers_mod.DATE: format_timestamp(Timer.get_cur_time())}
        this_transactive_node.vip.pubsub.publish(peer='pubsub', topic=topic,
                                                     headers=headers, message=msg)

        # Save the sent TransactiveRecord messages (i.e., sentSignal) as a copy of the calculated set that was drawn
        # upon by this method (i.e., mySignal).
        self.sentSignal.extend(transactive_records)

        # 210127DJH: Save the newly sent transactive records to a formatted csv table.
        if transactive_records:
            append_table(obj=transactive_records)

        # 210127DJH: Trim any records in the sentSignal list if their markets and time intervals are no longer active.
        active_markets = [x for x in this_transactive_node.markets]
        active_time_intervals = []
        for active_market in active_markets:
            active_time_intervals.extend(active_market.timeIntervals)
        active_time_interval_names = [x.name for x in active_time_intervals]
        self.sentSignal = [x for x in self.sentSignal if x.timeInterval in active_time_interval_names]

    def receive_transactive_signal(self, this_transactive_node, market, curves=None):
        # Receive and save transactive records from a transactive Neighbor.
        # this_transactive_node = Agent's TransactiveNode object
        #
        # The process of receiving a transactive signal is emulated by reading an available text table that is presumed
        # to have been created by the transactive neighbor. This process may change in field settings and using Python
        # and other code environments.

        # If trying to receive a transactive signal from a non-transactive neighbor, create a warning and return.
        if not self.transactive:
            _log.warning('Transactive signals are not expected to be received from non-transactive neighbors. '
                         'No signal is read.')
            return

        if curves is None:
            _log.warning(f'{market.name} Received Transactive signal is None. {this_transactive_node.name}')
            return

        # 201013DJH: The neighbor's list of received transactive records must be reinitialized so that it will not grow
        #            indefinitely. Only the latest records are relevant. See the end of method prep_transactive_signal()
        #            if more sophistication is warranted.
        #self.receivedSignal = []
        # 210126DJH: TODO: Robert or Shwetha, class curves must be updated with the new properties of TransactiveRecord
        #            class, please, to keep data collection straight. The new properties are
        #             (1) TransactiveRecord.neighborName  # text name of Neighbor object
        #             (2) TransactiveRecord.direction  # Indication from among {'sent', 'received', or 'prepared'}
        #             (3) TransactiveRecord.marketName  # text reference to Market.name.
        #             IMPORTANT: The first two can be inferred, but the marketName must be confirmed to be the same.
        #                        Otherwise, there will be confusion between market series between agents.
        newly_received_records = []

        for curve in curves:
            # 210303DJH: This trick is not needed if the market is received as a parameter. The market name can be used
            #            directly.
            # market_name = curve['timeInterval'].split(':')
            # market_name = market_name[0]
            if curve['marketName'] == market.name:
                new_record = TransactiveRecord(time_interval=curve['timeInterval'],
                                               record=int(curve['record']),
                                                marginal_price=float(curve['marginalPrice']),
                                                power=float(curve['power']),
                                                cost=float(curve['cost'])
                                                )
                # 210303DJH: I'm separating out this assignment because the passed parameters don't seem to be used
                #            properly.
                #            TODO: Please recheck the initialization of class TransactiveRecord to make sure the new
                #             properties were included.
                new_record.neighborName = self.name
                new_record.direction = 'received'
                new_record.marketName = market.name

                newly_received_records.append(new_record)

        self.receivedSignal.extend(newly_received_records)

        # 210127DJH: Save the newly received records to a formatted csv table.
        if newly_received_records:
            append_table(obj=newly_received_records)

        # 210127DJH: Trim the receviedSignal list to remove any expired markets and time intervals.
        active_markets = [x for x in this_transactive_node.markets]
        active_time_intervals = []
        for active_market in active_markets:
            active_time_intervals.extend(active_market.timeIntervals)
        active_time_interval_names = [x.name for x in active_time_intervals]

        self.receivedSignal = [x for x in self.receivedSignal if x.timeInterval in active_time_interval_names]

    def update_costs(self, market):
        """
        Have model object update and store its costs
        191217DJH: This method was originally in an abstract Model class. The class structure is being simplified. Class
        Model will be deleted.
        NOTE: THIS METHOD DRIVES THE UPDATING OF COSTS BY CALLING OTHER METHODS. THERE SHOULD BE NO REASON TO CHANGE
        THIS METHOD. CHANGES TO THIS METHOD MAY MAKE THE SYSTEM (EVEN MORE) UNSTABLE!
        :param self:
        :param market: Agent's Market object
        :return:
        """

        # Initialize sums of production and dual costs.
        self.totalProductionCost = 0.0
        self.totalDualCost = 0.0

        # Have object update and store its production and dual costs in each active time interval
        self.update_production_costs(market)
        self.update_dual_costs(market)

        # Sum total production and dual costs through all time intervals.
        # 200929DJH: These sums must occur in the same market.
        # self.totalProductionCost = sum([x.value for x in self.productionCosts])
        #         # self.totalDualCost = sum([x.value for x in self.dualCosts])
        self.totalProductionCost = sum([x.value for x in self.productionCosts if x.market == market])
        self.totalDualCost = sum([x.value for x in self.dualCosts if x.market == market])

    def include_marginal_losses(self, vertices):
        # This method corrects supply from neighbors based on transport inefficiency and the impact of transport losses
        # the effective marginal price. While all transactive signals should be stated from the perspective of the
        # remote neighbor, the active vertices should reflect the following modifications:
        # (1) Supply power is reduced to remove transport energy losses.
        # (2) Marginal price in increased to include the impact of marginal losses.
        # INPUTS:
        # - vertices: A list of vertex struct objects. Typically, these would be a set of raw vertex objects that have
        #             been derived from received transactive records. The remote neighbor supplies these records from
        #             its own perspective at the border of its circuit, excluding transport. This method will modify and
        #             return updated vertices. NOTE: the set of vertices should be for precisely one time interval.
        # - threshold: Power demand threshold this time interval.88
        #
        # USES:
        # - self.maximumPower:
        # - self.lossFactor
        #
        # OUTPUTS:
        # - corrected_vertices: Vertex objects as corrected by this method to have reduced supply power and increased
        #                       marginal price. The caller is responsible to store these values as active vertices.
        #
        # 200702DJH: I had originally included the implications of transport losses within the base neighbor class
        #            methods. I'm finding that a more modular approach may be useful if the template methods are to
        #            facilitate diverse market rules and procedures. Therefore, I am introducing methods to include and
        #            later remove implications of losses and demand charges. These effects do not exist upstream of the
        #            local transactive node agent, but they must be accounted in the local prices. I'm concluding that
        #            the effects should be removed for the upstream neighbor's perspective. Furthermore, the three local
        #            transactive signal representations ("my," "received," and "sent" signals) should always be stated
        #            in respect to the neighbor's, not the local agent's, perspective. These modular methods should be
        #            invoked to correct this neighbor model's active vertices, which should be stated in respect to the
        #            local transactive node and agent.
        #            The method is being defined as a function to help make sure it is not applied multiple times.
        #            This revision corrects some errors implemented in prior versions. The impact on LMP is now properly
        #            formulated from marginal losses.
        #            The price and power corrections are based on a careful review of this impacts in a white paper
        #            "Addressing the Marginal Value of Transport Losses."

        # Create a deep copy of the provided list of vertices so that they will not be corrupted.
        corrected_vertices = deepcopy(vertices)

        if self.maximumPower is None or self.maximumPower <= 0:
            print('WARNING: Method Neighbor.include_losses requires that a full maximum power value > 0 be assigned. '
                                 'No losses were applied.')
            return corrected_vertices

        if type(self.lossFactor) != float or self.lossFactor <= 0:
            print('WARNING: Property lossFactor must be a small positive number. No losses were applied.')
            return corrected_vertices

        if any([type(x) != Vertex for x in corrected_vertices]):
            print('WARNING: This method acts on Vertex objects. No losses were applied.')
            return corrected_vertices

        # Get on with the business of reviewing and correcting the input vertices.
        for x in range(len(corrected_vertices)):
            vertex = corrected_vertices[x]
            # Losses apply to only imported, not exported, power in the current practice. Calculate the effective
            # received power and price.
            # Assumptions:
            # - The supplier agrees with the value of lossFactor.
            # - corrected_vertex.power is currently the power delivered from the supply side.
            # - maximumPower is the full-load transport capacity, stated from the supplier's perspective.
            # - corrected_vertex.marginalPrice is currently the LMP of delivered supply, excluding effects of transport
            #   losses.
            if vertex.power > 0:
                power = vertex.power * (1 - self.lossFactor * (vertex.power / self.maximumPower))
                # Make sure that the reduced power is not greater than the maximum capacity referred to the demand side.
                if power > self.maximumPower * (1 - self.lossFactor):
                    power = self.maximumPower * (1 - self.lossFactor)
                # Correct the supplier's LMP to include marginal losses.
                vertex.marginalPrice = vertex.marginalPrice \
                                       / (1 - 2 * (vertex.power / self.maximumPower) * self.lossFactor)
                vertex.power = power

        return corrected_vertices

    def remove_marginal_losses(self, vertices):
        # Remove impacts of marginal losses from method include_marginal_losses(). This is usually done while preparing
        # the transactive signal and its transactive records from the neighbor's active vertices. By practice,
        # transactive signals should always be sent and received using the remote neighbor's perspective. Impacts exist
        # only among vertices with demand (i.e., p < 0).

        corrected_vertices = deepcopy(vertices)

        for x in range(len(corrected_vertices)):
            vertex = corrected_vertices[x]

            if vertex.power < 0:
                # ASSUMPTIONS:
                # - self.maximumPower is the transport actual constraint power magnitude from the supply perspective.
                # - self.lossFactor is the same for both supply and demand.
                # - vertex.power is received as the received demand-side power, excluding losses.
                # - vertex.marginalPrice is the local marginal price that has been increased to account for marginal
                #   losses.
                # Calculated the supplied power from the supply-side perspective. It is a negative value because of the
                # sign convention for demand.

                power = -(self.maximumPower / (2 * self.lossFactor)) \
                        * (1 - (1 - 4 * (-vertex.power/self.maximumPower) * self.lossFactor) ** 0.5)

                if power < -self.maximumPower:
                    power = -self.maximumPower

                vertex.marginalPrice = vertex.marginalPrice * (1 - 2 * (-power / self.maximumPower) * self.lossFactor)
                vertex.power = power

        return corrected_vertices

    def include_demand_charges(self, vertices, threshold):
        # 200731DJH: This method acts on and modifies a set of vertices to include demand charges.
        # Important: This method should be called no more than once. It will typically be called once as a transactive
        #            signal is being RECEIVED from a neighbor and applied to only imported supply powers.
        # Note: The impacts from demand charges are removed by method Neighbor.remove_demand_charges() which should be
        #       applied once while preparing transactive signals to send to the neighbor.
        # INPUTS:
        # - vertices: A set of Vertex objects in the same time interval.
        # - threshold: A power level at which demand charges will be applied to power that is received from a given
        #              neighbor object. [kW]
        # RETURNS:
        # - corrected_vertices: A set of corresponding Vertex objects that has demand charges applied to peak powers in
        #   this time interval.

        # Make a deep copy of the vertices that are to be corrected and returned. This method should not change the set
        # of input vertices.
        corrected_vertices = deepcopy(vertices)

        # Find the minimum and maximum powers represented in the received vertices.
        powers = [x.power for x in corrected_vertices]
        maximum_power = max(powers[:])
        minimum_power = min(powers[:])

        # If the demand threshold power lies above the maximum vertex power, this is all moot. Return the received
        # vertices unchanged.
        if threshold > maximum_power:
            return order_vertices(corrected_vertices)

        # Demand charges only apply to supply from this remote neighbor.
        if threshold < 0:
            threshold = 0

        # Interpolate a price at the threshold power for these vertices. This should be determined using the original
        # vertices before any of their marginal prices have been changed.
        if minimum_power <= threshold <= maximum_power:
            threshold_price = self.marginal_price_from_vertices(threshold, corrected_vertices)

        # If there was only one vertex, its marginal price will also be the threshold price.
        if minimum_power == maximum_power:
            threshold_price = corrected_vertices[0].marginalPrice

        # Regardless, the default condition is that the other threshold price is the same as the first. (The other
        # threshold price may be needed for the second vertex that may become created at the threshold.)
        other_threshold_price = threshold_price

        # Find the active supply vertices (i.e., p > 0) in this time interval that lie ABOVE the threshold. Simply add
        # the demand rate to their marginal prices.
        affected_vertices = [x for x in corrected_vertices if x.power > threshold]
        for av in range(len(affected_vertices)):
            affected_vertex = affected_vertices[av]
            affected_vertex.marginalPrice = affected_vertex.marginalPrice + self.demandRate

        # Find unaffected vertices that lie below the threshold.
        unaffected_vertices = [x for x in corrected_vertices if x.power < threshold]

        # Find any existing vertices that lie ON the threshold.
        threshold_vertex_prices = [x.marginalPrice for x in corrected_vertices if x.power == threshold]

        # If any vertex exists on the threshold, a vertex will need to be created at the minimum marginal price of the
        # vertex or vertices, not necessarily the same value as was found above.
        if len(threshold_vertex_prices) > 0:
            threshold_price = min(threshold_vertex_prices[:])
            other_threshold_price = max(threshold_vertex_prices[:])

        # Trim the list of vertices. This can eliminate one or more vertices AT the threshold, which are re-created in
        # the next step.
        corrected_vertices = affected_vertices + unaffected_vertices

        # Create vertices at the threshold. The two criteria make sure that no redundant vertices are created.
        if minimum_power < threshold <= maximum_power:
            corrected_vertices.append(Vertex(marginal_price=threshold_price,
                                             prod_cost=0,
                                             power=threshold
                                             )
                                      )

        if minimum_power <= threshold < maximum_power:
            corrected_vertices.append(Vertex(marginal_price=other_threshold_price + self.demandRate,
                                             prod_cost=0,
                                             power=threshold
                                             )
                                      )

        return order_vertices(corrected_vertices)

    def remove_demand_charges(self, vertices, threshold):
        # 200804DJH: If the demand lies at or below the threshold, the demand rate is removed from the vertex's marginal
        #            price. This is done in preparation of transactive signals that are to be sent to the remote
        #            neighbor.
        #            Demand charges were included when the neighbor's supply to this agent exceeded a threshold power;
        #            Therefore, the demand charges must be removed from this agent's demand if it lies at or below the
        #            threshold.
        #            The threshold is always stated from the local agent's perspective.

        # Make a deep copy of provided vertices to correct and return.
        corrected_vertices = deepcopy(vertices)

        # Find the minimum and maximum powers represented among the vertices.
        powers = [x.power for x in corrected_vertices]
        _log.debug("remove_demand_charges: powers: {}".format(powers))

        minimum_power = min(powers[:])
        maximum_power = max(powers[:])

        # This is all moot if the threshold is so low that it will not cause demand prices to be affected. Return with
        # vertices unchanged.
        if threshold < minimum_power:
            return order_vertices(corrected_vertices)

        # Demand charges only apply to demand from this remote neighbor.
        if threshold > 0:
            threshold = 0

        _log.debug("remove_demand_charges: min power: {}, threshold: {}, max power: {}".format(minimum_power,
                                                                                               threshold,
                                                                                               maximum_power))
        threshold_price = corrected_vertices[0].marginalPrice
        # Determine the price that corresponds to the threshold power for this set of vertices. This should be done
        # before any of the vertices' marginal prices have been changed.
        if minimum_power <= threshold <= maximum_power:
            threshold_price = self.marginal_price_from_vertices(vertices=corrected_vertices, power=threshold)

        # If there was only one vertex, its marginal price will also be the threshold price.
        if minimum_power == maximum_power:
            threshold_price = corrected_vertices[0].marginalPrice

        # Regardless, the default condition is that the other threshold price is the same as the first. (The other
        # threshold price may be needed for the second vertex that may become created at the threshold.)
        other_threshold_price = threshold_price

        # Find the affected vertices that have demand below the threshold. Note: the threshold should normally be
        # negative, meaning it is a demand level.
        affected_vertices = [x for x in corrected_vertices if x.power < threshold]
        for av in range(len(affected_vertices)):
            affected_vertex = affected_vertices[av]
            affected_vertex.marginalPrice = affected_vertex.marginalPrice - self.demandRate

        # Find unaffected vertices that lie above the threshold.
        unaffected_vertices = [x for x in corrected_vertices if x.power > threshold]

        # Find any existing vertices that lie ON the threshold.
        threshold_vertex_prices = [x.marginalPrice for x in corrected_vertices if x.power == threshold]

        # If any vertex exists on the threshold, a vertex will need to be created at the maximum marginal price of the
        # vertex or vertices, not necessarily the same value as was found above.
        if len(threshold_vertex_prices) > 0:
            threshold_price = max(threshold_vertex_prices[:])
            other_threshold_price = min(threshold_vertex_prices[:])
        else:
            other_threshold_price = threshold_price

        # Trim the list of vertices. This can eliminate one or more vertices AT the threshold, which are re-created in
        # the next step.
        corrected_vertices = affected_vertices + unaffected_vertices

        # Create vertices at the threshold. The two criteria make sure that no redundant vertices are created.
        if minimum_power <= threshold < maximum_power:
            corrected_vertices.append(Vertex(marginal_price=threshold_price,
                                             prod_cost=0,
                                             power=threshold
                                             )
                                      )

        if minimum_power < threshold <= maximum_power:
            corrected_vertices.append(Vertex(marginal_price=other_threshold_price - self.demandRate,
                                             prod_cost=0,
                                             power=threshold
                                             )
                                      )

        return order_vertices(corrected_vertices)

    @staticmethod
    def curves_to_vertices(curves):
        # 200803DJH: This static method converts building curves into Vertex objects. This was needed because many TENT
        #            methods have been standardized to act on Vertex objects. Since a Vertex is not assigned a specific
        #            time interval, the set of curves sent to this method should all reside in the same time interval.

        # Find the set of unique time intervals among the list curves.
        time_intervals = set([x.timeInterval for x in curves])

        if len(time_intervals) != 1:
            raise Warning('The curves sent to Neighbor.curves_to_curves should all be in the same time interval.')

        # Initialize the list of vertices that is to be returned.
        vertices = []

        # Index through each curves and convert its properties into Vertex properties.
        for c in range(len(curves)):
            # Pick out indexed curve.
            curve = curves[c]

            # Make and append a vertex to the list of Vertex objects that is to be returned.
            vertices.append(Vertex(record=int(curve['record']),
                                   marginal_price=float(curve['marginalPrice']),
                                   power=float(curve['power']),
                                   prod_cost=float(curve['cost'])
                                   )
                            )

        return vertices

    def getDict(self):
        scheduled_powers = [(utils.format_timestamp(x.timeInterval.startTime), x.value) for x in self.scheduledPowers]
        received_signal = [(x.timeInterval, x.marginalPrice, x.power) for x in self.receivedSignal]
        sent_signal = [(x.timeInterval, x.marginalPrice, x.power) for x in self.sentSignal]

        neighbor_dict = {
            "isTransactive": self.transactive,
            "name": self.name,
            "scheduled_power": scheduled_powers,
            "received_signal": received_signal,
            "sent_signal": sent_signal
        }

        return neighbor_dict


if __name__ == '__main__':
    nm = Neighbor()


