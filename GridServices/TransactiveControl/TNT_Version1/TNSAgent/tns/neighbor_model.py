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

from datetime import datetime, timedelta, date, time
import csv

import logging
import json

from .model import Model
from .helpers import *
from .measurement_type import MeasurementType
from .interval_value import IntervalValue
from .transactive_record import TransactiveRecord
from .vertex import Vertex
from .timer import Timer

from volttron.platform.agent import utils
utils.setup_logging()
_log = logging.getLogger(__name__)


class NeighborModel(Model, object):
    # The NeighborModel manages the interface with a Neighbor object and
    # represents it for the computational agent. There is a one-to-one
    # correspondence between a Neighbor object and its NeighborModel object.
    # Members of the transactive network must be indicated by setting the
    # "transactive" property true.

    def __init__(self):
        super(NeighborModel, self).__init__()
        self.converged = False
        self.convergenceFlags = []  # IntervalValue.empty  # values are Boolean
        self.convergenceThreshold = 0.05  # [0.01 = 1#]
        self.demandMonth = datetime.today().month  # used to re-set demand charges
        self.demandRate = 4.5  # 4.5  # [$ / kW (/h)]
        self.demandThreshold = 1e9  # power that causes demand charges [kW]
        self.demand_threshold_coef = 1  # 0.8
        self.effectiveImpedance = 0.0  # Ohms for future use
        self.friend = False  # friendly Neighbors might get preferred rates
        self.mySignal = []  # TransactiveRecord.empty  # current records ready to send
        self.receivedSignal = []  # TransactiveRecord.empty  # last records received
        # NOTE: Realized late that sentSignal is needed as part of the
        # event-driven timing of the system. This allows a comparison
        # between a recent calculation (mySignal) and the last calculation
        # that was revealed to the Neighbor (sentSignal).
        self.sentSignal = []  # TransactiveRecord.empty  # last records sent
        self.transactive = False

    def calculate_reserve_margin(self, mkt):
        # CALCULATE_RESERVE_MARGIN() - Estimate the spinning reserve margin
        # in each active time interval
        #
        # RESERVE MARGIN is defined here as additional generation or reduced
        # consumption above the currently scheduled power. The intention is for
        # this to represent "spinning-reserve" power that can be available on short
        # notice.
        #
        # For now, this quantity will be tracked. In the future, treatment of
        # resource commitment may allow meaningful control of reserve margin and
        # the resiliency that it supports.
        #
        # PRESUMPTIONS:
        # - time intervals are up-to-date
        # - scheduled power is up-to-date
        # - the active vertices are up-to-date and correct. One of the vertices
        # represents the maximum power that is available on short notice (i.e.,
        # "spinning reserve") from this neighbor.
        #
        # INPUTS:
        # mkt - Market object
        #
        # OUTPUTS:
        # - updated self.reserveMargins

        # Gather active time intervals ti
        time_intervals = mkt.timeIntervals
        time_interval_values = [t.startTime for t in time_intervals]
        self.reserveMargins = [x for x in self.reserveMargins if x.timeInterval.startTime in time_interval_values]

        # Index through active time intervals ti
        for i in range(len(time_intervals)):  # for i = 1:len(time_intervals)
            # Find the maximum available power from among the active vertices in
            # the indexed time interval, one of which must represent maximum power
            maximum_power = find_objs_by_ti(self.activeVertices, time_intervals[i])
            if len(maximum_power) == 0:
                # No active vertex was found. The hard constraint must be used.
                maximum_power = self.object.maximumPower  # hard constraint [avg.kW]

            else:
                # A vertex was found. Extract its power value.
                maximum_power = [x.value for x in maximum_power]  # [maximum_power.value]  # Vertice objects
                maximum_power = [x.power for x in maximum_power]  # real powers [avg.kW]
                maximum_power = max(maximum_power)  # maximum power [avg.kW]

                # Check that the operational maximum from vertices does not
                # exceed the hard physical constraint. Use the smaller of the two.
                maximum_power = min(maximum_power, self.object.maximumPower)

            # Find the scheduled power for this asset in the indexed time interval
            # scheduled_power = findobj(self.scheduledPowers, 'timeInterval', time_intervals[i])  # an IntervalValue
            # scheduled_power = scheduled_power.value  # scheduled power[avg.kW]
            scheduled_power = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            scheduled_power = scheduled_power.value  # scheduled power [avg.kW]

            # The available reserve margin is calculated as the difference
            # between the maximum and scheduled powers. Make sure the value is
            # not less than zero.
            value = max(0, maximum_power - scheduled_power)  # reserve margin [avg.kW]

            # Check whether a reserve margin exists in the indexed time interval.
            interval_value = find_obj_by_ti(self.reserveMargins, time_intervals[i])
            if interval_value is None:
                # No reserve margin was found for the indexed time interval.
                # Create a reserve margin interval for the calculated value
                # interval_value = IntervalValue(self, time_intervals[i], mkt, 'ReserveMargin', value)  # an IntervalValue
                interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ReserveMargin, value)

                # Append the reserve margin interval value to the list of reserve margins.
                self.reserveMargins.append(interval_value)  # IntervalValue objects

            else:
                # The reserve margin interval value already exists, simply
                # reassign its value.
                interval_value.value = value  # [avg.kW]

    def find_last_message_ts(self, signals, ti_name, fallback_value):
        # Create a logical array: true if the received TransactiveRecord is in the indexed active time interval
        ti_signals = [s for s in signals if s.timeInterval == ti_name]

        # If a signal message was found in the indexed time interval,
        # its timestamp ts is the last time a message was sent. Otherwise,
        # set the ts to the fallback value (eg. current time dt)
        if len(ti_signals) > 0:
            ts = [s.timeStamp for s in ti_signals if s.record == 0]
            ts = ts[0]
        else:
            ts = fallback_value

        return ts, ti_signals

    def check_for_convergence(self, mkt):
        # Qualifies state of convergence with a transactive Neighor object by active time interval and globally.
        #
        # In respect to the coordination sub-problem, a Neighbor is not converged
        # for a given time interval and a signal should be sent to the transactive
        # Neighbor if
        # - The balancing and scheduling sub-problems are converged, AND
        # - No signal has been sent, OR
        # - A signal has been received from the Neighbor, and no signal has been
        # sent since the signal was received, but scheduled power and marginal
        # price in the sent and received signals (i.e., Records 0) differ, OR
        # - A timer has elapsed since the last time a signal was sent, and the
        # sent signal differs from one that would be sent again, based on
        # current conditions.
        #
        # Inputs:
        # mkt - Market object
        #
        # Uses property convergenceThreshold as a convergence criterion.
        #
        # Compares TransactiveRecord messages in mySignal, sentSignal, and
        # receivedSignal.
        #
        # Updates properties convergenceFlags and converged based on comparison of
        # calculated, received, and sent TransactiveRecord messages.

        # NOTE: this method should not be called unless the balancing sub-problem
        # and all the scheduling sub-problems have been calculated and have
        # converged.

        # Gather active time intervals.
        time_intervals = mkt.timeIntervals

        # Index through active time intervals to assess their convergence status.
        t_threshold = timedelta(minutes=5)
        for i in range(len(time_intervals)):
            # Capture the current datetime in the same format as for the TransactiveRecord messages.
            dt = Timer.get_cur_time()

            # Initialize a flag true (converged) in this time interval until proven otherwise.
            flag = True

            # Find the TransactiveRecord objects sent from the transactive
            # Neighbor in this indexed active time interval.
            ss_ts, ss = self.find_last_message_ts(self.sentSignal, time_intervals[i].name, dt-t_threshold)
            rs_ts, rs = self.find_last_message_ts(self.receivedSignal, time_intervals[i].name, dt)
            ms_ts, ms = self.find_last_message_ts(self.mySignal, time_intervals[i].name, dt)

            # Now, work through the convergence criteria.
            if len(ss) == 0:
                # No signal has been sent in this time interval. This is the
                # first convergence requirement. Set the convergence flag false.
                _log.debug("Signal for time interval {} ({}). Enable send flag.".format(i, time_intervals[i].name))
                flag = False

            # received and received AFTER last sent and there is a big diff b/w ss and rs
            elif len(rs) > 0 and rs_ts > ss_ts and are_different1(ss, rs, self.convergenceThreshold, self.name):
                # One or more TransactiveRecord objects has been received in the
                # indexed time interval and it has been received AFTER the last
                # time a message was sent. These are preconditions for the second
                # convergence requirement. Function are_different1() checks
                # whether the sent and received signals differ significantly. If
                # all these conditions are true, the Neighbor is not converged.
                _log.debug("TCC for {} are_different1 returned True? Check: rs={}, ss={}, "
                           "rs_ts={}, ss_ts={}, threshold={}".format(
                    self.name,
                    [(x.timeInterval, x.record, x.power, x.marginalPrice) for x in rs],
                    [(x.timeInterval, x.record, x.power, x.marginalPrice) for x in ss],
                    rs_ts, ss_ts, self.convergenceThreshold))
                flag = False

            #elif dt - ss_ts >= t_threshold and are_different2(ms, ss, self.convergenceThreshold, self.name):
            elif are_different2(ms, ss, self.convergenceThreshold, self.name):
                # Delay 5 min after last send AND
                # More than 5 minutes have passed since the last time a signal
                # was sent. This is a precondition to the third convergence
                # criterion. Function are_different2() returns true if mySignal
                # (ms) and the sentSignal (ss) differ significantly, meaning that
                # local conditions have changed enough that a new, revised signal
                # should be sent.
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
                iv = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ConvergenceFlag, flag)
                self.convergenceFlags.append(iv)

            else:
                # A convergence flag was found to exist in the indexed time
                # interval. Simply reassign it.
                iv.value = flag

        # If any of the convergence flags in active time intervals is false, the
        # overall convergence flag should be set false, too. Otherwise, true,
        # meaning the coordination sub-problem is converged with this Neighbor.
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
            # The power is below the first vertex. Marginal price is
            # indeterminate. Assign the marginal price of the first vertex,
            # create a warning, and return. (This should be an unlikely
            # condition.)
            # warning('power was lower than first vertex')
            marginal_price = vertices[0].marginalPrice  # price [$/kWh]
            return marginal_price

        elif power >= vertices[-1].power:
            # The power is above the last vertex. Marginal price is
            # indeterminate. Assign the marginal price of the last vertex, create
            # a warning, and return. (This should be an unlikely condition.)
            # warning('power was greater than last vertex')
            marginal_price = vertices[-1].marginalPrice  # price [$/kWh]
            return marginal_price

        # There are multiple vertices v. Index through them.
        for i in range(v_len - 1):  # for i = 1:(len - 1)
            if vertices[i].power <= power < vertices[i + 1].power:
                # The power lies on a segment between two defined vertices.
                if vertices[i].power == vertices[i + 1].power:
                    # The segment is horizontal. Marginal price is indefinite.
                    # Assign the marginal price of the second vertex and return.
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
    def schedule(self, mkt):
        self.update_dc_threshold(mkt)

        # If the object is a NeighborModel give its vertices priority
        self.update_vertices(mkt)
        self.schedule_power(mkt)

        # Have the objects estimate their available reserve margin
        self.calculate_reserve_margin(mkt)

    def schedule_power(self, mkt):
        # Calculate power for each time interval
        #
        # This is a basic method for calculating power generation of consumption in
        # each active time interval. It infers power
        # generation or consumption from the supply or demand curves that are
        # represented by the neighbor's active vertices in the active time
        # intervals.
        #
        # This strategy should is anticipated to work for most neighbor model
        # objects. If additional features are needed, child neighbor models must be
        # created and must redefine this method.
        #
        # PRESUMPTIONS:
        # - All active vertices have been created and updated.
        # - Marginal prices have been updated and exist for all active intervals.
        #
        # INPUTS:
        # mkt - Market object
        #
        # OUTPUTS:
        # updates array self.scheduledPowers

        # Gather the active time intervals ti
        time_intervals = mkt.timeIntervals  # TimeInterval objects
        time_interval_values = [t.startTime for t in time_intervals]
        self.scheduledPowers = [x for x in self.scheduledPowers if x.timeInterval.startTime in time_interval_values]

        # Index through active time intervals ti
        for i in range(len(time_intervals)):
            # Find the marginal price for the indexed time interval
            marginal_price = find_obj_by_ti(mkt.marginalPrices, time_intervals[i])  # an IntervalValue
            marginal_price = marginal_price.value

            # Find the power that corresponds to the marginal price according
            # to the set of active vertices in the indexed time interval.
            # Function Production() works for any power that is determined by
            # its supply curve or demand curve, as represented by the object's
            # active vertices.
            value = production(self, marginal_price, time_intervals[i])  # [avg. kW]

            # Check to see if a scheduled power already exists in the indexed
            # time interval
            interval_value = find_obj_by_ti(self.scheduledPowers, time_intervals[i])  # an IntervalValue

            if interval_value is None:
                # No scheduled power was found in the indexed time interval.
                # Create the interval value and assign it the scheduled power
                interval_value = IntervalValue(self, time_intervals[i], mkt,
                                               MeasurementType.ScheduledPower, value)

                # Append the scheduled power to the list of scheduled powers
                self.scheduledPowers.append(interval_value)

            else:
                # A scheduled power already exists in the indexed time interval.
                # Simply reassign its value.
                interval_value.value = value  # [avg. kW]

        sp = [(x.timeInterval.name, x.value) for x in self.scheduledPowers]
        _log.debug("{} neighbor model scheduledPowers are: {}".format(self.name, sp))

    def schedule_engagement(self):
        # Required from AbstractModel, but not particularly useful for any NeighborModel.
        return

    def update_dc_threshold(self, mkt):
        # Keep track of the month's demand-charge threshold
        #
        # Pseudocode:
        # 1. This method should be called prior to using the demand threshold. In
        #  reality, the threshold will change only during peak periods.
        # 2a. (preferred) Read a meter (see MeterPoint) that keeps track of an
        # averaged power. For example, a determinant may be based on the
        # average demand in a half hour period, so the MeterPoint would ideally
        # track that average.
        # 2b. (if metering unavailable) Update the demand threshold based on the
        # average power in the current time interval.

        # Find the MeterPoint object that is configured to measure average demand
        # for this NeighborModel. The determination is based on the meter's
        # MeasurementType.
        mtr = [x for x in self.meterPoints if x.measurementType == MeasurementType.AverageDemandkW]
        mtr = mtr[0] if len(mtr) > 0 else None

        if mtr is None:
            # No appropriate MeterPoint object was found. The demand threshold
            # must be inferred.

            # Gather the active time intervals ti and find the current (soonest) one.
            time_intervals = mkt.timeIntervals
            time_intervals.sort(key=lambda x: x.startTime)

            # Find current demand d that corresponds to the nearest time interval.
            cur_demand = find_obj_by_ti(self.scheduledPowers, time_intervals[0])

            # Update the inferred demand
            d = 0.0 if cur_demand is None else cur_demand.value
            self.demandThreshold = max([0, self.demandThreshold, d])  # [avg.kW]
            _log.debug("measurement: {} threshold: {}".format(d, self.demandThreshold))
        else:
            # An appropriate MeterPoint object was found. The demand threshold
            # may be updated from the MeterPoint object.

            # Update the demand threshold.
            measurement = mtr.current_measurement if mtr.current_measurement is not None else 0.0
            self.demandThreshold = max([0, self.demandThreshold, measurement])  # [avg.kW]
            _log.debug("Meter: {} measurement: {} threshold: {}".format(mtr.name,
                                                                        mtr.current_measurement,
                                                                        self.demandThreshold))

        # The demand threshold should be reset in a new month. First find the current month number mon.
        mon = Timer.get_cur_time().month

        if mon != self.demandMonth:
            # This must be the start of a new month. The demand threshold must be
            # reset. For now, "resetting" means using a fraction (e.g., 80#) of
            # the final demand threshold in the prior month.
            self.demandThreshold = self.demand_threshold_coef * self.demandThreshold
            self.demandMonth = mon

    def update_dual_costs(self, mkt):
        # Gather the active time intervals.
        time_intervals = mkt.timeIntervals
        time_interval_values = [t.startTime for t in time_intervals]
        self.dualCosts = [x for x in self.dualCosts if x.timeInterval.startTime in time_interval_values]

        for i in range(1, len(time_intervals)):
            # Find the marginal price mp for the indexed time interval in the given market
            marginal_price = find_obj_by_ti(mkt.marginalPrices, time_intervals[i])
            marginal_price = marginal_price.value

            # Find the scheduled power for the neighbor in the indexed time interval.
            scheduled_power = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            scheduled_power = scheduled_power.value

            # Find the production cost in the indexed time interval.
            production_cost = find_obj_by_ti(self.productionCosts, time_intervals[i])
            production_cost = production_cost.value

            # Dual cost in the time interval is calculated as production cost,
            # minus the product of marginal price, scheduled power, and the
            # duration of the time interval.
            interval_duration = get_duration_in_hour(time_intervals[i].duration)

            dual_cost = production_cost - (marginal_price * scheduled_power * interval_duration)  # a dual cost [$]

            # Check whether a dual cost exists in the indexed time interval
            # interval_value = findobj(self.dualCosts, 'timeInterval', time_intervals[i])  # an IntervalValue
            interval_value = find_obj_by_ti(self.dualCosts, time_intervals[i])

            if interval_value is None:
                # No dual cost was found in the indexed time interval. Create an
                # interval value and assign it the calculated value.
                interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.DualCost, dual_cost)

                # Append the new interval value to the list of active interval values.
                self.dualCosts.append(interval_value)
            else:
                # The dual cost value was found to already exist in the indexed
                # time interval. Simply reassign it the new calculated value.
                interval_value.value = dual_cost  # a dual cost [$]

        # Ensure that only active time intervals are in the list of dual costs.
        #self.dualCosts = [x for x in self.dualCosts if x.timeInterval in time_intervals]

        # Sum the total dual cost and save the value
        self.totalDualCost = sum([x.value for x in self.dualCosts])  # total dual cost [$]

        dc = [(x.timeInterval.name, x.value) for x in self.dualCosts]
        _log.debug("{} neighbor model dual costs are: {}".format(self.name, dc))

    def update_production_costs(self, mkt):
        time_intervals = mkt.timeIntervals
        time_interval_values = [t.startTime for t in time_intervals]
        self.productionCosts = [x for x in self.productionCosts if x.timeInterval.startTime in time_interval_values]

        for i in range(1, len(time_intervals)):
            # Get the scheduled power in the indexed time interval.
            scheduled_power = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            scheduled_power = scheduled_power.value

            # Call on function that calculates production cost pc based on the
            # vertices of the supply or demand curve.
            production_cost = prod_cost_from_vertices(self, time_intervals[i], scheduled_power)  # prod cost [$]

            # Check to see if the production cost value has been defined for the
            # indexed time interval.
            # interval_value = findobj(self.productionCosts, 'timeInterval', time_intervals[i])  # an IntervalValue
            interval_value = find_obj_by_ti(self.productionCosts, time_intervals[i])

            if interval_value is None:
                # The production cost value has not been defined in the indexed
                # time interval. Create it and assign its value pc.
                interval_value = IntervalValue(self, time_intervals[i], mkt,
                                               MeasurementType.ProductionCost,
                                               production_cost)

                # Append the production cost to the list of active production cost values.
                self.productionCosts.append(interval_value)
            else:

                # The production cost value already exists in the indexed time
                # interval. Simply reassign its value.
                interval_value.value = production_cost  # production cost [$]

        # Ensure that only active time intervals are in the list of active
        # production costs.
        #self.productionCosts = [x for x in self.productionCosts if x.timeInterval in time_intervals]

        # Sum the total production cost.
        # self.totalProductionCost = sum([self.productionCosts.value])  # total production cost [$]
        self.totalProductionCost = sum([x.value for x in self.productionCosts])  # total production cost [$]

        pc = [(x.timeInterval.name, x.value) for x in self.productionCosts]
        _log.debug("{} neighbor model production costs are: {}".format(self.name, pc))

    def update_vertices(self, mkt):
        # Update the active vertices that define Neighbors'
        # residual flexibility in the form of supply or demand curves.
        #
        # The active vertices of non-transactive neighbors are relatively constant.
        # Active vertices must be created for new active time intervals. Vertices
        # may be affected by demand charges, too, as new demand-charge thresholds
        # are becoming established.
        #
        # The active vertices of transactive neighbors are also relatively
        # constant. New vertices must be created for new active time intervals. But
        # active vertices must also be checked and updated whenever a new
        # transactive signal is received.
        #
        # PRESUMPTIONS:
        # - time intervals are up-to-date
        # - at least one default vertex has been defined, should all other
        # efforts to establish meaningful vertices fail
        #
        # INPUTS:
        # mkt - Market object
        #
        # OUTPUTS:
        # Updates self.activeVertices - an array of IntervalValues that contain
        # Vertex() structs

        # Extract active time intervals
        time_intervals = mkt.timeIntervals
        time_interval_values = [t.startTime for t in time_intervals]

        # Delete any active vertices that are not in active time intervals. This
        # prevents time intervals from accumulating indefinitely.
        self.activeVertices = [x for x in self.activeVertices if x.timeInterval.startTime in time_interval_values]

        for i in range(len(time_intervals)):
            # Flag for logging demand charge 1st time only
            dc_logged = False

            # Keep active vertices that are not in the indexed time interval, but
            # discard the one(s) in the indexed time interval. These shall be
            # recreated in this iteration.
            self.activeVertices = [x for x in self.activeVertices if
                                   x.timeInterval.startTime != time_interval_values[i]]

            # Get the default vertices.
            default_vertices = self.defaultVertices

            if len(default_vertices) == 0:
                # No default vertices are found. Warn and return.
                _log.warning('At least one default vertex must be defined for neighbor model object %s. '
                             'Scheduling was not performed' % (self.name))
                return

            if not self.transactive:  # Neighbor is non-transactive
                # Default vertices were found. Index through the default vertices.
                for k in range(len(default_vertices)):
                    # Get the indexed default vertex.
                    value = default_vertices[k]

                    # Create an active vertex interval value in the indexed time
                    # interval.
                    interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex, value)

                    # Append the active vertex to the list of active vertices
                    self.activeVertices.append(interval_value)

            elif self.transactive:  # a transactive neighbor
                # Check for transactive records in the indexed time interval.
                received_vertices = [x for x in self.receivedSignal if x.timeInterval == time_intervals[i].name]

                if len(received_vertices) == 0:
                    # No received transactive records address the indexed time
                    # interval. Default value(s) must be used.

                    # Default vertices were found. Index through the default
                    # vertices.
                    for k in range(len(default_vertices)):  # for k = 1:len(default_vertices)

                        # Get the indexed default vertex
                        value = default_vertices[k]

                        # Create an active vertex interval value in the indexed
                        # time interval
                        interval_value = IntervalValue(self, time_intervals[i], mkt, MeasurementType.ActiveVertex,
                                                       value)  # an IntervalValue

                        # Append the active vertex to the list of active
                        # vertices.
                        # self.activeVertices = [self.activeVertices, interval_value]  # IntervalValue objects
                        self.activeVertices.append(interval_value)
                else:  # at least 1 vertex received
                    # One or more transactive records have been received
                    # concerning the indexed time interval. Use these to
                    # re-create active Vertices.

                    # Sort the received_vertices (which happen to be
                    # TransactiveRecord objects) by increasing price and power.
                    received_vertices = order_vertices(received_vertices)

                    # Prepare for demand charge vertices.

                    # This flag will be replace by its preceding ordered vertex
                    # index if any of the vertices are found to exceed the
                    # current demand threshold.
                    demand_charge_flag = 0  # simply a flag

                    # The demand-charge threshold is based on the actual measured
                    # peak this month, but it may also be superseded in predicted
                    # time intervales prior to the currently indexed one.
                    # Start with the metered demand threshold
                    demand_charge_threshold = self.demandThreshold  # [avg.kW]

                    # Calculate the peak in time intervals that come before the
                    # one now indexed by i.
                    # Get all the scheduled powers.
                    prior_power = self.scheduledPowers  # [avg.kW]

                    if len(prior_power) < i + 1:
                        # Especially the first iteration can encounter missing
                        # scheduled power values. Place these out of the way by
                        # assigning then as small as possible. The current demand
                        # threshold will always trump this value.
                        prior_power = [float("-inf")]  # -inf

                    else:
                        # The scheduled powers look fine. Pick out the ones that
                        # are indexed prior to the currently indexed value.
                        # prior_power = [prior_power(1:i).value]  # [avg.kW]
                        prior_power = [x.value for x in prior_power[0:i + 1]]

                    # Pick out the maximum power from the prior scheduled power values.
                    predicted_prior_peak = max(prior_power)  # [avg.kW]

                    # The demand-charge threshold for the indexed time interval
                    # should be the larger of the current and predicted peaks.
                    #demand_charge_threshold = max([demand_charge_threshold, predicted_prior_peak])  # [avg.kW]

                    # Index through the vertices in the received transactive
                    # records for the indexed time interval.
                    for k in range(len(received_vertices)):
                        # Create working values of power and marginal price from
                        # the received vertices.
                        power = received_vertices[k].power
                        marginal_price = received_vertices[k].marginalPrice

                        # If the Neighbor power is positive (importation of
                        # electricity), then the value may be affected by losses.
                        # The available power is diminished (compared to what was
                        # sent), and the effective marginal price is increased
                        # (because myTransactiveNode is paying for electricity
                        # that it does not receive).
                        if power > 0:
                            try:
                                factor1 = (power / self.object.maximumPower) ** 2
                                factor2 = 1 + factor1 * self.object.lossFactor
                                power = power / factor2
                                marginal_price = marginal_price * factor2

                                if (self.mtn is not None
                                    and self.system_loss_topic != ''
                                    and received_vertices[k].record == 0):
                                    msg = {
                                        'ts': received_vertices[k].timeInterval,
                                        'predicted_clear_power': power,
                                        'max_power': self.object.maximumPower,
                                        'factor1': factor1,
                                        'factor2': factor2,
                                        'vertex_record': received_vertices[k].record,
                                        'demand_charge_threshold': demand_charge_threshold
                                    }
                                    self.mtn.vip.pubsub.publish(peer='pubsub',
                                                                topic=self.system_loss_topic,
                                                                message=msg)

                                # If there are multiple transactive records in the
                                # indexed time interval, we don't need to create a vertex
                                # for Record #0. Record #0 is the balance point, which
                                # must lie on existing segments of the supply or demand curve.
                                # This is moved here instead of staying at the beginning of the loop
                                # is because we want to log system loss
                                if len(received_vertices) >= 3 and received_vertices[k].record == 0:
                                    continue  # jumps out of for loop to next iteration

                                if power > demand_charge_threshold:
                                    # The power is greater than the anticipated
                                    # demand threshold. Demand charges are in play.
                                    # Set a flag.
                                    demand_charge_flag = k

                                # Publish to db
                                if self.mtn is not None and self.dc_threshold_topic != '' \
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
                                    self.mtn.vip.pubsub.publish(peer='pubsub',
                                                                topic=self.dc_threshold_topic,
                                                                message=dc_msg)

                                # Debug negative price & demand charge
                                _log.debug("power: {} - demand charge threshold: {} - predicted power peak: {}"
                                           .format(power, demand_charge_threshold, predicted_prior_peak))
                                _log.debug("prior power: {}".format(prior_power))
                                _log.debug("received vertices: {}"
                                           .format([(v.timeInterval, v.power) for v in received_vertices]))

                            except:
                                _log.error("{} has power {} AND object ({}) maxPower {} and minPower {}"
                                           .format(self.name, power,
                                                   self.object.name,
                                                   self.object.maximumPower,
                                                   self.object.minimumPower))
                                raise
                        # Create a corresponding (price,power) pair (aka "active
                        # vertex") using the received power and marginal price.
                        # See struct Vertex().
                        # value = Vertex(marginal_price, received_vertices[k].cost,
                        #                power, received_vertices[k].powerUncertainty)
                        value = Vertex(marginal_price, received_vertices[k].cost, power, None)

                        # Create an active vertex interval value for the vertex
                        # in the indexed time interval.
                        interval_value = IntervalValue(self, time_intervals[i], mkt,
                                                       MeasurementType.ActiveVertex, value)

                        # Append the active vertex to the list of active vertices.
                        self.activeVertices.append(interval_value)

                    # DEMAND CHARGES
                    # Check whether the power of any of the vertices was found to
                    # be larger than the current demand-charge threshold, as
                    # would be indicated by this flag being a value other than 0.
                    if demand_charge_flag != 0:
                        _log.debug("DEMAND CHARGE 1")
                        # Demand charges are in play.
                        # Get the newly updated active vertices for this
                        # transactive Neighbor again in the indexed time interval.
                        vertices = [x.value for x in self.activeVertices if
                                    x.timeInterval.startTime == time_intervals[i].startTime]

                        # Find the marginal price that would correspond to the
                        # demand-charge threshold, based on the newly updated
                        # (but excluding the effects of demand charges) active
                        # vertices in the indexed time interval.
                        marginal_price = self.marginal_price_from_vertices(demand_charge_threshold, vertices)  # [$/kWh]

                        # Create the first of two vertices at the intersection of
                        # the demand-charge threshold and the supply or demand
                        # curve from prior to the application of demand charges.
                        vertex = Vertex(marginal_price, 0, demand_charge_threshold)

                        # Create an IntervalValue for the active vertex.
                        interval_value = IntervalValue(self, time_intervals[i], mkt,
                                                       MeasurementType.ActiveVertex, vertex)

                        # Store the new active vertex interval value
                        self.activeVertices.append(interval_value)

                        # Create the marginal price of the second of the two new
                        # vertices, augmented by the demand rate.
                        marginal_price = marginal_price + self.demandRate  # [$/kWh]

                        # Create the second vertex.
                        vertex = Vertex(marginal_price, 0, demand_charge_threshold)

                        # ... and the interval value for the second vertex,
                        interval_value = IntervalValue(self, time_intervals[i], mkt,
                                                       MeasurementType.ActiveVertex, vertex)

                        # ... and finally store the active vertex.
                        self.activeVertices.append(interval_value)

                        # Check that vertices having power greater than the
                        # demand threshold have their marginal prices reflect the
                        # demand charges. Start by picking out those in the
                        # currently indexed time interval.
                        interval_values = [x for x in self.activeVertices
                                           if x.timeInterval.startTime == time_intervals[i].startTime]

                        # Index through the current active vertices in the
                        # indexed time interval. At this point, these include
                        # vertices from both prior to and after the introduction
                        # of demand-charge vertices.
                        for k in range(len(interval_values)):
                            # Extract the indexed vertex.
                            vertex = interval_values[k].value

                            # Extract the power of the indexed vertex.
                            vertex_power = vertex.power  # [avg.kW]

                            if vertex_power > demand_charge_threshold:
                                # The indexed vertex's power exceeds the
                                # demand-charge threshold. Increment the vertex's
                                # marginal price with the demand rate.
                                vertex.marginalPrice = vertex.marginalPrice + self.demandRate

                                # ... and re-store the vertex in its IntervalValue
                                interval_values[k].value = vertex  # an IntervalValue object
                    else:
                        _log.debug("NO DEMAND CHARGE 1")

            else:
                # Logic should not arrive here. Error.
                raise ('Neighbor %s must be either transactive or not.' % (self.name))

        av = [(x.timeInterval.name, x.value.marginalPrice, x.value.power) for x in self.activeVertices]
        _log.debug("{} neighbor model active vertices are: {}".format(self.name, av))

    def prep_transactive_signal(self, mkt, mtn):
        # Prepare transactive records to send
        # to a transactive neighbor. The prepared transactive signal should
        # represent the residual flexibility offered to the transactive neighbor in
        # the form of a supply or demand curve.
        # NOTE: the flexibility of the prepared transactive signals refers to LOCAL
        # value. Therefore this method does not make modifications for power losses
        # or demand charges, both of which are being modeled as originating with
        # the RECIPIENT of power.
        # FUTURE: The numbers of vertices may be restricted to emulate various
        # auction mechanisms.
        #
        # ASSUMPTIONS:
        # - The local system has converged, meaning that all asset and neighbor
        # powers have been calculated
        # - Neighbor and asset demand and supply curves have been updated and are
        # accurate. Active vertices will be used to prepare transactive
        # records.
        #
        # INPUTS:
        # tnm - Transactive NeighborModel object - target node to which a
        # transactive signal is to be sent
        # mkt - Market object
        # mtn - myTransactiveNode object
        #
        # OUTPUTS:
        # - Updates mySignal property, which contains transactive records that
        # are ready to send to the transactive neighbor

        # Ensure that object tnm is a transactive neighbor object.
        if not self.transactive:
            _log.warning('NeighborModel must be transactive')
            return

        # Gather active time intervals.
        time_intervals = mkt.timeIntervals  # active TimeInterval objects
        time_interval_names = [x.name for x in time_intervals]

        #[180830DJH: ENSURE THAT mySignal PROPERTY IS TRIMMED TO CONTAIN SIGNALS
        #FROM ONLY THE ACTIVE TIME INTERVALS USING THIS NEXT LINE.]
        self.mySignal = [x for x in self.mySignal if x.timeInterval in time_interval_names]

        # Index through active time intervals.
        for i in range(len(time_intervals)):
            # Keep only the transactive records that are NOT in the indexed time
            # interval. The ones in the indexed time interval shall be recreated
            # in this iteration.
            self.mySignal = [x for x in self.mySignal if x.timeInterval != time_intervals[i].name]

            # Create the vertices of the net supply or demand curve, EXCLUDING
            # this transactive neighbor (i.e., "tnm"). NOTE: It is important that
            # the transactive neighbor is excluded.
            vertices = mkt.sum_vertices(mtn, time_intervals[i], self)  # Vertices

            # Find the minimum and maximum powers from the vertices. These are
            # soft constraints that represent a range of flexibility. The range
            # will usually be excessively large from the supply side much
            # smaller from the demand side.
            vertex_powers = [x.power for x in vertices]  # [avg.kW]

            maximum_vertex_power = max(vertex_powers)  # [avg.kW]
            minimum_vertex_power = min(vertex_powers)  # [avg.kW]

            # Find the transactive Neighbor's (i.e., "tnm") scheduled power in
            # the indexed time interval.
            scheduled_power = find_obj_by_ti(self.scheduledPowers, time_intervals[i])
            scheduled_power = scheduled_power.value

            # Because the supply or demand curve of this transactive neighbor
            # model was excluded, an offset is created between it and the one
            # that had included the neighbor. The new balance point is mirrored
            # equal to, but of opposite sign from, the scheduled power.
            scheduled_power = -scheduled_power

            # Record #0: Balance power point
            # Find the marginal price of the modified supply or demand curve that
            # corresponds to the balance point.
            try:
                # [180830DJH: NEW CONDITIONAL ENSURES THAT A LONE REMNANT VERTEX HAS ITS MARGINAL PRICE SET TO INFINITY.]
                if len(vertices) == 1:
                    marginal_price_0 = float('inf')
                else:
                    marginal_price_0 = self.marginal_price_from_vertices(scheduled_power, vertices)
            except:
                _log.error('errors/warnings with object ' + self.name)

            # Create transactive record #0 to represent that balance point, and
            # populate its properties.
            transactive_record = TransactiveRecord(time_intervals[i], 0, marginal_price_0, scheduled_power)

            # Append the transactive signal to those that are ready to be sent.
            self.mySignal.append(transactive_record)

            if len(vertices) > 1:
                # Transactive Record #1: Minimum neighbor power
                # Find the minimum power. For transactive neighbors, the minimum may
                # be based on the physical constraint of the line between neighbors.
                # A narrower range may be used if the full range is infeasible. For
                # example, it might not be feasible for a neighbor to change from a
                # power importer to exporter, given it limited generation resources.
                minimum_power = -self.object.maximumPower  # power [avg.kW]
                minimum_power = max(minimum_power, minimum_vertex_power)

                # Find the marginal price on the modified net suppy or demand curve
                # that corresponds to the minimum power
                marginal_price_1 = self.marginal_price_from_vertices(minimum_power, vertices)

                # Create transactive record #1 to represent the minimum power, and
                # populate its properties.
                transactive_record = TransactiveRecord(time_intervals[i], 1, marginal_price_1, minimum_power)

                # Append the transactive signal to those that are ready to be sent.
                self.mySignal.append(transactive_record)

                # Transactive Record #2: Maximum neighbor power
                # Find the maximum power. For transactive neighbors, the maximum may
                # be based on the physical constraint of the line between neighbors.
                maximum_power = -self.object.minimumPower  # power [avg.kW]
                maximum_power = min(maximum_power, maximum_vertex_power)

                # Find the marginal price on the modified net supply or demand curve
                # that corresponds to the neighbor's maximum power p
                marginal_price_2 = self.marginal_price_from_vertices(maximum_power, vertices)  # price [$/kWh]

                # Create Transactive Record #2 and populate its properties.
                transactive_record = TransactiveRecord(time_intervals[i], 2, marginal_price_2, maximum_power)

                # Append the transactive signal to the list of transactive signals
                # that are ready to be sent to the transactive neighbor.
                self.mySignal.append(transactive_record)  # transactive records

                # Additional Transactive Records: Search for included vertices.
                # Some of the vertices of the modified net supply or demand curve may lie
                # between the vertices that have been defined. These additional vertices
                # should be included to correctly convey the system's flexibiltiy to its
                # neighbor.
                # Create record index counter index. This must be incremented before
                # adding a transactive record.
                index = 2

                # Index through the vertices of the modified net supply or demand
                # curve to see if any of their marginal prices lie within the
                # vertices that have been defined for this neighbor's miminum power
                # (at marginal_price_1) and maximum power (at marginal_price_2).
                for j in range(len(vertices) - 1):
                    if marginal_price_1 < vertices[j].marginalPrice < marginal_price_2:
                        # The vertex lies in the range defined by this neighbor's
                        # minimum and maximum power range and corresponding marginal
                        # prices and should be included.

                        # Create a new transactive record and assign its propteries.
                        # See struct TransactiveRecord. NOTE: The vertex already
                        # resided on the modified net supply or demand curve and does
                        # not need to be offset.
                        # NOTE: A TransactiveRecord constructor is being used.
                        index = index + 1  # new transactive record number
                        transactive_record = TransactiveRecord(time_intervals[i],
                                                               index,
                                                               vertices[j].marginalPrice,
                                                               vertices[j].power)

                        # Append the transactive record to the list of transactive
                        # records that are ready to send.
                        self.mySignal.append(transactive_record)

    def send_transactive_signal(self, mtn, topic, start_of_cycle=False, fail_to_converged=False):
        # Send transactive records to a transactive neighbor.
        #
        # Retrieves the current transactive records, formats them into a table, and
        # "sends" them to a text file for the transactive neighbor. The property
        # mySignal is a storage location for the current transactive records, which
        # should capture at least the active time intervals' local marginal prices
        # and the power that is scheduled to be received from or sent to the
        # neighbor.
        # Records can also capture flex vertices for this neighbor, which are the
        # supply or demand curve, less any contribution from the neighbor.
        # Transactive record #0 is the scheduled power, and other record numbers
        # are flex vertices. This approach anticipates that transactive signal
        # might not include all time intervals or replace all records. The neighbor
        # similarly prepares and sends transactive signals to this location.
        # mtn - myTransactiveNode object

        # If neighbor is non-transactive, warn and return. Non-transactive
        # neighbors do not communicate transactive signals.
        if not self.transactive:
            _log.warning(
                'Non-transactive neighbors do not send transactive signals. No signal is sent to %s.' % self.name)
            return

        # Collect current transactive records concerning myTransactiveNode.
        transactive_records = self.mySignal

        if len(transactive_records) == 0:  # No signal records are ready to send
            _log.warning("No transactive records were found. No transactive signal can be sent to %s." % self.name)
            return

        msg = json.dumps(transactive_records, default=json_econder)
        msg = json.loads(msg)
        _log.debug("At {}, {} sends signal from {} on topic {} message {}"
                   .format(Timer.get_cur_time(),
                           self.name,
                           self.location, topic, msg))
        mtn.vip.pubsub.publish(peer='pubsub',
                               topic=topic,
                               message={'source': self.location,
                                        'curves': msg,
                                        'start_of_cycle': start_of_cycle,
                                        'fail_to_converged': fail_to_converged})

        # Save the sent TransactiveRecord messages (i.e., sentSignal) as a copy
        # of the calculated set that was drawn upon by this method (i.e., mySignal).
        self.sentSignal = self.mySignal

    def receive_transactive_signal(self, mtn, curves):
        # Receive and save transactive records from a transactive Neighbor object.
        # mtn = myTransactiveNode object
        #
        # The process of receiving a transactive signal is emulated by reading an
        # available text table that is presumed to have been created by the
        # transactive neighbor. This process may change in field settings and using
        # Python and other code environments.

        # If trying to receive a transactive signal from a non-transactive neighbor,
        # create a warning and return.
        if not self.transactive:
            _log.warning('Transactive signals are not expected to be received from non-transactive neighbors. '
                         'No signal is read.')
            return

        self.receivedSignal = []
        for curve in curves:
            transative_record = TransactiveRecord(ti=curve['timeInterval'],
                                                  rn=int(curve['record']),
                                                  mp=float(curve['marginalPrice']),
                                                  p=float(curve['power']),
                                                  cost=float(curve['cost']))
                                                  # pu=float(curve['powerUncertainty']),
                                                  # rp=float(curve['reactivePower']),
                                                  # rpu=float(curve['reactivePowerUncertainty']),
                                                  # v=float(curve['voltage']),
                                                  # vu=float(curve['voltageUncertainty']))

            # Save each transactive record
            self.receivedSignal.append(transative_record)


if __name__ == '__main__':
    nm = NeighborModel()
    