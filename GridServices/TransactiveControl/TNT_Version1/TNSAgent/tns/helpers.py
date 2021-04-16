# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# 'AS IS' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}


import math
import logging
from datetime import datetime, timedelta

# from volttron.platform.agent import utils
# utils.setup_logging()
# _log = logging.getLogger(__name__)


def format_date(dt):
    return dt.strftime('%Y%m%d')


def format_ts(dt):
    return dt.strftime('%Y%m%dT%H%M%S')


def json_econder(obj):
    if isinstance(obj, datetime):
        return format_ts(obj)
    else:
        return obj.__dict__


def get_duration_in_hour(dur):
    if isinstance(dur, timedelta):
        dur = dur.seconds // 3600
    return dur


def find_objs_by_ti(items, ti):
    found_items = [x for x in items if x.timeInterval.startTime == ti.startTime]
    return found_items


def find_obj_by_ti(items, ti):
    found_items = [x for x in items if x.timeInterval.startTime == ti.startTime]
    return found_items[0] if len(found_items) > 0 else None


def find_objs_by_st(items, value):
    found_items = [x for x in items if x.startTime == value]
    return found_items


def find_obj_by_st(items, value):
    found_items = [x for x in items if x.startTime == value]
    return found_items[0] if len(found_items) > 0 else None


def is_heavyloadhour(datetime_value):
    """True if time is within a HLH hour
    """
    is_hlh = False
    if not isinstance(datetime_value, datetime):
        raise 'Input value has to be an instance of datetime'

    #These holidays are always LLH. If New Year's Day, Independence Day, or
    #Labor Day fall on a Sunday, the following Monday is LLH. These dates
    holidays = [
        "2018-01-01",
        "2018-05-28",
        "2018-07-04",
        "2018-09-03",
        "2018-11-22",
        "2018-12-25"
    ]
    # Should be maintained far into the future.

    # The basic definition of HLH is based on hour and weekday memberships.
    h = datetime_value.hour
    d = datetime_value.weekday()
    d_str = format_date(datetime_value)
    is_holiday = d_str in holidays
    is_in_hlh_hours = 6 <= h <= 21
    is_sunday = d == 6  # Sunday

    if is_in_hlh_hours and not is_sunday and not is_holiday:
        is_hlh = True

    return is_hlh


def order_vertices(uv):
    return sorted(uv, key=lambda x: (x.marginalPrice, x.power))


def prod_cost_from_vertices(obj, ti, pwr):
    # Infer production cost for a power from the
    # vertices that define an object's supply curve
    #
    # If the neighbor is not a "friend" (an insider that is owned by the same
    # business entity), it is probably represented by a production cost that
    # includes both production costs and profits. If, however, the neighbor is
    # a friend, it may offer a blended price that eliminates some, if not all,
    # local profit.
    #
    # PRESUMPTIONS:
    # - This method applies to NeighborModel and LocalAssetModel objects.
    # Method properties must be named identically in these object classes.
    # - A supply curve exists for the object, as defined by a set of active
    # vertices. The vertices are up-to-date. See struct Vertex().
    # - Vertex property "cost" defines the total, accurate production cost
    # for the object at the vertex's power. The marginal price and slope of
    # segment between successive vertices must be used to infer production
    # cost between vertices.
    # - Production costs must be accurate and meaningful. An ideal is that
    # the production costs estimate or displace the dynamic delivered cost
    # of electricity. If production costs are well-tracked, production
    # costs should be equivalent to electricity costs over time.
    #
    # INPUTS:
    # obj - the neighbor model 3object
    # ti - the active time interval
    # pwr - the average power at which the production cost is to be
    # calculated. This will be the scheduled power during scheduling.
    # It may be power at other active vertices for the calculation of
    # flexibility.
    #
    # OUTPUTS:
    # cost - production cost in the time interval ti [$]

    # We presume only generation and importation of electricity (i.e., p>0)
    # contribute to production costs
    if pwr < 0.0:
        cost = 0.0
        return cost

    # Find the active vertices for the object in the given time interval
    v = [x for x in obj.activeVertices if x.timeInterval.startTime == ti.startTime]

    # number of active vertices len in the indexed time interval
    v_len = len(v)

    if v_len == 0:  # No vertices were found in the given time interval
        print(' '.join(['No active vertices are found for',
                        obj.name, '. Returning without finding',
                        'production cost.']))
        return

    elif v_len == 1:  # One vertex was found in the given time interval
        # Extract the vertex from the interval value
        v = v[0].value  # a production vertex

        # There is no flexibility. Assign the production value from the
        # constant production as indicated by the lone vertex.
        cost = v.cost  # production cost [$]
        return cost

    else:  # There is more than one vertex
        # Extract the production vertices from the interval values
        v = [x.value for x in v]  # vertices

        # Sort the vertices in order of increasing marginal price and power
        v = order_vertices(v)

        # Special case when neighbor is at its minimum power.
        if pwr <= v[0].power:

            # Production cost is known from the vertex cost.
            cost = v[0].cost  # production cost [$]
            return cost
        
        # Special case when neighbor is at its maximum power.
        elif pwr >= v[-1].power:
            # Production cost may be inferred from the blended price at the
            # maximum production vertex.
            cost = v[-1].cost  # production cost [$]
            return cost
            # Remaining case is that neighbor power is between defined
            # production indices.

        else:
            # Index through the production vertices v in this time interval
            for k in range(v_len-1):
                if v[k].power <= pwr < v[k+1].power:
                    # The power is found to lie between two of the vertices.

                    # Constant term (an integration constant from lower vertex
                    a0 = v[k].cost  # [$]

                    # First-order term for the segment is based on the
                    # marginal price of the lower vertex and the power
                    # exceeding that of the lower vertex
                    dur = get_duration_in_hour(ti.duration)
                    a1 = v[k].marginalPrice  # [$/kWh]
                    a1 = a1 * (pwr - v[k].power)  # [$/h]
                    a1 = a1 * dur  # [$]

                    # Second-order term is derived from the slope of the
                    # current segment of the supply curve and the square of
                    # the power in excess of the lower vertex
                    if v[k+1].power == v[k].power:
                        # An exception is needed for infinite slope to avoid
                        # division by zero
                        a2 = 0.0  # [$]

                    else:
                        a2 = v[k+1].marginalPrice - v[k].marginalPrice  # [$/kWh]
                        a2 = a2 / (v[k+1].power - v[k].power)  # [$/kWh/kW]
                        a2 = a2 * (pwr - v[k].power) ** 2  # [$/h]
                        a2 = a2 * dur  # [$]

                    # Finally, calculate the production cost for the time
                    # interval by summing the terms
                    cost = a0 + a1 + a2  # production cost [$]

                    # Return. Production cost has been calculated.
                    return cost


def prod_cost_from_formula(obj, ti):
    # Calculate production cost from a quadratic
    # production-cost formula
    #
    # This formulation allows for a quadratic cost function. Objects have cost
    # parameters that allow the calculation of production cost from the power
    # and these cost coefficients
    # production cost = a0 + a1*p + 0.5*a2*p^2
    #
    # INPUTS:
    # obj - Either a NeighborModel or LocalAssetModel object
    # ti - time interval (See TimeInterval class)
    #
    # OUTPUTS:
    # cost - production cost in absolute dollars for time interval ti [$]

    # Get the object's quadratic cost coefficients
    a = obj.costParameters

    # Find the scheduled power sp in time interval ti
    sp = find_obj_by_ti(obj.scheduledPowers, ti)

    # Extract the scheduled-power value
    sp = sp.value  # [avg.kW]

    # Calculate the production cost from the quadratic cost formula
    # Constant term
    cost = a[0]  # [$/h]

    # Add the first-order term
    cost = cost + a[1] * sp  # [$/h]

    # Add the second order term
    cost = cost + 0.5 * a[2] * sp**2  # [$/h]

    # Convert to absolute dollars
    dur = get_duration_in_hour(ti.duration)
    cost = cost * dur  # interval production cost [$]

    return cost


def production(obj, price, ti):
    # Find economic power production for a marginal price and time interval
    # using an object model's demand or supply curve. This is performed as a
    # linear interpolation of a discrete set of price-ordered vertices (see
    # struct Vertex).
    #
    # obj - Asset or neighbor model for which the power production is to be
    # calculated. This model has a set of "active vertices" that define
    # its flexibility via a demand or supply curve.
    # price - marginal price [$/kWh]
    # ti - time interval (see class TimeInterval)
    # [p1] - economic power production in the given time interval   and at
    # the given price (positive for generation) [avg.kW].

    # Find the active production vertices for this time interval (see class IntervalValue).
    pv = find_objs_by_ti(obj.activeVertices, ti)

    # Extract the vertices (see struct Vertex) from the interval values (see IntervalValue class).
    pvv = [x.value for x in pv]  # vertices

    # Number len of vertices in the list.
    pvv_len = len(pvv)
    if pvv_len == 0:  # No active vertices were found in the given time interval
        # _log.debug('Active vertices: %s' % (str(obj.activeVertices)))
        raise Exception(' '.join(['No active vertices were found for', obj.name, 'in time interval', ti.name]))

    # Ensure that the production vertices are ordered by increasing price.
    # Vertices having same price are ordered by power.
    pvv = order_vertices(pvv)  # vertices

    if pvv_len == 1:  # One active vertices were found in the given time interval
        # Presume that using a single production vertex is shorthand for
        # constant, inelastic production.
        p1 = pvv[0].power  # [avg.kW]
        return p1

    else:  # Multiple active vertices were found
        if price < pvv[0].marginalPrice:
            # Special case where marginal price is before first vertex.
            # The power is at its minimum.
            p1 = pvv[0].power  # [kW]
            return p1

        elif price >= pvv[-1].marginalPrice:
            # Special case where marginal price is after the last
            # vertex. The power is at its maximum.
            p1 = pvv[-1].power  # [kW]
            return p1

        else:  # The marginal price lies among the active vertices
            # Index through the active vertices pvv in the given time
            # interval ti
            for i in range(pvv_len-1):
                if pvv[i].marginalPrice <= price < pvv[i+1].marginalPrice:
                    # The marginal price falls between two vertices that
                    # are sloping upward to the right. Interpolate
                    # between the vertices to find the power production.
                    p1 = pvv[i].power \
                         + (price - pvv[i].marginalPrice) \
                           * (pvv[i+1].power - pvv[i].power) \
                           / (pvv[i+1].marginalPrice - pvv[i].marginalPrice)  # [avg.kW]
                    return p1

                elif price == pvv[i].marginalPrice == pvv[i+1].marginalPrice:
                    # The marginal price is the same as for two vertices
                    # that lie vertically at the same marginal price.
                    # Assign the power of the vertex having greater power.
                    p1 = pvv[i+1].power  # [kW]
                    return p1

                elif price == pvv[i].marginalPrice:
                    # The marginal price is the same as the indexed
                    # active vertex. Use its power value.
                    p1 = pvv[i].power  # [kW]
                    return p1


def are_different1(s, r, threshold, calling_neighbor=''):
    # Returns true is two sets of TransactiveRecord objects,
    # representing sent and received messages in a time interval, are
    # significantly different.
    #
    # INPUTS:
    # s - sent TransactiveRecord object(s) (see struct TransactiveRecord)
    # r - received TransactiveRecord object(s)
    # threshold - relative error used as convergence criterion. Two messages
    # differ significantly if the relative distance between the
    # scheduled points (i.e., Record 0) differ by more than this
    # threshold.
    #
    # OUTPUS:
    # tf - Boolean: true if relative distance between scheduled (i.e., Record
    # 0) (price,quantity) pairs in the two messages exceeds the threshold.

    # Pick out the scheduled sent and received records (i.e., the one where record = 0)
    s0 = [x for x in s if x.record == 0]
    s0 = s0[0]  # a TransactiveRecord
    r0 = [x for x in r if x.record == 0]
    r0 = r0[0]  # a TransactiveRecord

    # Calculate the difference dmp in scheduled marginal prices.
    dmp = abs(s0.marginalPrice - r0.marginalPrice)  # [$/kWh]

    # Calculate the average mp_avg of the two scheduled marginal prices.
    mp_avg = 0.5 * abs(s0.marginalPrice + r0.marginalPrice)  # [$/kWh]

    # Calculate the difference dq betweent the scheduled powers.
    dq = abs(-s0.power - r0.power)  # [avg. kW]

    # Calculate the average q_avg of the two scheduled average powers.
    q_avg = 0.5 * abs(r0.power + -s0.power)  # [avg. kW]

    # Calculate the relative Euclidian distance d (a relative error
    # criterion) between the two scheduled (price,quantity) points.
    # try:
    #     if len(s) == 1 or len(r) == 1:
    #         d = dq / q_avg  # dimensionless
    #     else:
    #         d = math.sqrt((dq / q_avg) ** 2 + (dmp / mp_avg) ** 2)  # dimensionless
    # except:
    #     raise Exception("TCC r0.power: {} s0.power: {} dq: {}".format(r0.power, s0.power, dq))

    # _log.debug("TCC neighbor {} has q_avg {}, r0.power {}, s0.power {}, dq {}, dmp {}".format(
    #     calling_neighbor, q_avg, r0.power, s0.power, dq, dmp))
    # _log.debug("TCC neighbor {} s is: {}".format(
    #     calling_neighbor,[(x.timeInterval, x.record, x.power, x.marginalPrice) for x in s]))
    # _log.debug("TCC neighbor {} r is: {}".format(
    #     calling_neighbor, [(x.timeInterval, x.record, x.power, x.marginalPrice) for x in r]))

    if q_avg != 0:
        if len(s) == 1 or len(r) == 1:
            d = dq / q_avg  # dimensionless
        else:
            d = math.sqrt((dq / q_avg) ** 2 + (dmp / mp_avg) ** 2)  # dimensionless
    else:
        d = 0

    if d > threshold:
        # The distance, or relative error, between the two scheduled points
        # exceeds the threshold criterion. Return true to indicate that the
        # two messages are significantly different.
        is_diff = True

    else:
        # The distance, or relative error, between the two scheduled points
        # is less than the threshold criterion. Return false, meaning that
        # the two messages are not significantly different.
        is_diff = False

    # _log.debug("TCC for {} are_different1 returns {}".format(calling_neighbor, is_diff))
    return is_diff


def are_different2(m, s, threshold, calling_neighbor=''):
    # Assess whether two TransactiveRecord messages,
    # representing the calculated and sent messages in an active time interval
    # are significantly different from one another. If the signals are
    # different, this indicates that local conditions have changed, and a
    # revised, updated transactive message shoudl be sent to the Neighbor.
    #
    # INPUTS:
    # m - TransactiveRecord message representing the mySignal, the last
    # message calculated for this transactiveNeighbor.
    # s - TransactiveRecord messge representing the sentSignal, the last
    # message that was sent to this transactive Neighbor.
    # threshold - a dimensionless, relative error that is used as a convergence
    # criterion.
    #
    # OUTPUTS:
    # tf - Boolean: true if the sent and recently calculated transactive
    # messages are significantly different.
    if len(s) != len(m):
        return True

    is_diff = True
    if len(s) == 1 or len(m) == 1:
        # Either the sent or calculated message is a constant, (i.e., one
        # Vertex) meaning its marginal price is probaly NOT meaningful. Use
        # only the power in this case to determine whether they differ.
        # Pick out the scheduled values (i.e., Record 0) from mySignal and
        # sentSignal records.
        s0 = [x for x in s if x.record == 0]
        s0 = s0[0]  # a TransactiveRecord
        m0 = [x for x in m if x.record == 0]
        m0 = m0[0]  # a TransactiveRecord

        # Calculate the difference dq between the scheduled powers in the two sets of records.
        dq = abs(m0.power - s0.power)  # [avg.kW]

        # Calculate the average scheduled power avg_q of the two sets of records.
        avg_q = 0.5 * abs(m0.power + s0.power)  # [avg.kW]

        # _log.debug("TCC neighbor {} has q_avg {}, m0.power {}, s0.power {}, dq {}".format(
        #    calling_neighbor, avg_q, m0.power, s0.power, dq))
        # _log.debug("TCC neighbor {} s is: {}".format(
        #    calling_neighbor, [(x.timeInterval, x.record, x.power, x.marginalPrice) for x in s]))
        # _log.debug("TCC neighbor {} m is: {}".format(
        #    calling_neighbor, [(x.timeInterval, x.record, x.power, x.marginalPrice) for x in m]))

        # Calculate relative distance d between the two scheduled powers.
        # Avoid the unlikely condition that the average power is zero.
        if avg_q != 0:
            d = dq / avg_q
        else:
            d = 0

        if d > threshold:
            # The difference is greater than the criterion. Return true,
            # meaning that the difference is significant.
            is_diff = True
        else:
            # The difference is less than the criterion. Return false,
            # meaning the difference is not significant.
            is_diff = False

    else:
        # There are multiple records, meaning that the Neighbor is price-responsive.

        # Pick out the records that are NOT scheduled points, i.e., are not
        # Record 0. Local convergence of the coordination sub-problem does
        # not require so much that the exact point has been determined as
        # that the flexibility is accurately conveyed to the Neighbor.
        s0 = [x for x in s if x.record != 0]
        m0 = [x for x in m if x.record != 0]

        # _log.debug("TCC neighbor {} s is: {}".format(
        #    calling_neighbor, [(x.timeInterval, x.record, x.power, x.marginalPrice) for x in s]))
        # _log.debug("TCC neighbor {} m is: {}".format(
        #    calling_neighbor, [(x.timeInterval, x.record, x.power, x.marginalPrice) for x in m]))

        # Index through the sent and calculated flexibility records. See if
        # any record cannot be matched with a corresponding member of
        # mySignal m0.
        for i in range(len(s0)):
            is_diff = True

            for j in range(len(m0)):
                # Calculate difference dmp between marginal prices .
                dmp = abs(s0[i].marginalPrice - m0[j].marginalPrice)  # [$/kWh]

                # Calculate average avg_mp of marginal price pair.
                avg_mp = 0.5 * (s0[i].marginalPrice + m0[j].marginalPrice)  # [$/kWh]

                # Calculate difference dq between power values in the two sets of records.
                dq = abs(s0[i].power - m0[j].power)  # [avg.kW]

                # Calculate average avg_q of power pairs in the two sets of records.
                avg_q = abs(s0[i].power + m0[j].power)  # [avg.kW]

                # If no pairing between the flexibility records of the two sets
                # of records can be found within the relative error criterion,
                # things must have changed locally since the transactive message
                # was last sent.


                #[180904DJH-HUNG FOUND CASE WHERE AVERAGES IN DENOMINATORS BECOME ZERO. THE
                #OUTCOME HAD BEEN AN UNRELIABLE CONDITIONAL WITH NAN COMPARISONS. THIS CASE
                #MUST BE AVOIDED WITH THIS CODE:
                # Avoid unlikely divide-by-zero case. If the average marginal price is
                # zero, it is probable they are BOTH zero:
                dmp = 0 if avg_mp == 0 else dmp/avg_mp
                dq = 0 if avg_q == 0 else dq/avg_q

                if math.sqrt(dmp**2 + dq**2) <= threshold:
                        # No pairing was found within the relative error criterion
                        # distance. Things must have changed locally since the
                        # transactive message was last sent to the transactive
                        # Neighbor. Set the flag true.
                        is_diff = False
                        continue

            if is_diff:
                break

    # _log.debug("TCC for {} are_different2 returns {}".format(calling_neighbor, is_diff))
    return is_diff
