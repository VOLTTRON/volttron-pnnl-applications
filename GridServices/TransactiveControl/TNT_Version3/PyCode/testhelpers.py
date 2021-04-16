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


from datetime import datetime, timedelta

from helpers import *
from vertex import Vertex
from time_interval import TimeInterval
from interval_value import IntervalValue
from measurement_type import MeasurementType


def test_is_hlh():
    from dateutil import parser

    holidays = [
        "2018-01-01",
        "2018-05-28",
        "2018-07-04",
        "2018-09-03",
        "2018-11-22",
        "2018-12-25"
    ]

    hlhs = [
        "2018-01-03 06:00:00",
        "2018-01-04 21:59:59",
        "2018-01-05 10:00:00",
    ]

    llhs = [
        "2018-01-07 21:00:00",
        "2018-01-04 05:59:59",
        "2018-01-04 22:00:00",
        "2018-06-22 00:00:40"
    ]

    for ts in holidays:
        dt = parser.parse(ts)
        actual = is_heavyloadhour(dt)
        assert actual == False

    for ts in hlhs:
        dt = parser.parse(ts)
        actual = is_heavyloadhour(dt)
        assert actual == True

    for ts in llhs:
        dt = parser.parse(ts)
        actual = is_heavyloadhour(dt)
        assert actual == False


def test_order_vertices():
    try:
        from vertex import Vertex
    except (SystemError, ImportError):
        from .vertex import Vertex

    p = [-100, 0, 100, 0]  # power vector
    c = [0.4, 0.3, 0.3, 0.2]  # marginal price vector
    uv = [
        Vertex(0.4, 0, -100),
        Vertex(0.3, 0, 0),
        Vertex(0.3, 0, 100),
        Vertex(0.2, 0, 0)
    ]
    ov = order_vertices(uv)
    assert ov[0] == uv[3]
    assert ov[1] == uv[1]
    assert ov[2] == uv[2]
    assert ov[3] == uv[0]


def test_production():
    from local_asset_model import LocalAsset
    from market import Market

    print('Running test_production()')
    pf = 'pass'

    #   Create a test object
    test_object = LocalAsset()

    #   Create a test market
    test_market = Market()

    #   Create several active vertices av
    av = [Vertex(0.0200, 5.00, 0.0),
          Vertex(0.0200, 7.00, 100.0),
          Vertex(0.0250, 9.25, 200.0)]

    # Create a time interval ti
    dt = datetime.now()
    at = dt
    #   NOTE: Function Hours() corrects the behavior of Matlab hours().
    dur = timedelta(hours=1)
    mkt = test_market
    mct = dt
    st = dt
    ti = TimeInterval(at, dur, mkt, mct, st)

    # Assign activeVertices, which are IntervalValues
    test_object.activeVertices = [
        IntervalValue(test_object, ti, test_market, MeasurementType.ActiveVertex, av[0]),
        IntervalValue(test_object, ti, test_market, MeasurementType.ActiveVertex, av[1]),
        IntervalValue(test_object, ti, test_market, MeasurementType.ActiveVertex, av[2])]

    # CASE: Various marginal prices when there is more than one vertex
    test_prices = [-0.010, 0.000, 0.020, 0.0225, 0.030]

    p = [0] * len(test_prices)  # zeros(1, length(test_prices))
    for i in range(len(test_prices)):  # for i = 1:length(test_prices)
        p[i] = production(test_object, test_prices[i], ti)

    print('- the function ran without errors')

    # p(1) = 0: below first vertex
    # p(2) = 0: below first vertex
    # p(3) = 100: at first vertex, which has identical marginal price as second
    # p(4) = 150: interpolate between vertices
    # p(5) = 200: exceeds last vertex

    # if ~all(abs(p - [0, 0, 100, 150, 200]) < 0.001):
    expected = [0, 0, 100, 150, 200]
    if not all([p[i] - expected[i] < 0.001 for i in range(len(p))]):
        pf = 'fail'
        raise Exception('- the production cost was incorrectly calculated')
    else:
        print('- the production cost was correctly calculated')

    # CASE: One vertex (inelastic case, a constant)
    test_object.activeVertices = [IntervalValue(test_object, ti, test_market, MeasurementType.ActiveVertex, av[2])]

    for i in range(5):
        p[i] = production(test_object, test_prices[i], ti)

    # if ~all(p == 200 * ones(1, length(p))):
    if not all(x == 200 for x in p):
        pf = 'fail'
        raise Exception('the vertex power should be assigned when there is one vertex')
    else:
        print('- the correct power was assigned when there is one vertex')

    # CASE: No active vertices (error case):
    test_object.activeVertices = []

    try:
        p = production(test_object, test_prices[4], ti)
        pf = 'fail'
        raise Exception('- an error should have occurred with no active vertices')
    except:
        print('- with no vertices, system returned with warnings, as expected')

    #   Success
    print('- the test function ran to completion')
    print('Result: #s\n\n', pf)


def test_prod_cost_from_formula():
    from local_asset_model import LocalAsset
    from market import Market

    print('Running test_prod_cost_from_formula()')
    pf = 'pass'

    #   Create a test object
    test_object = LocalAsset()

    #   Create a test market
    test_market = Market()

    #   Create and store the object's cost parameters
    test_object.costParameters = [4, 3, 2]

    #   Create and store three hourly TimeIntervals
    #   Modified to use the TimeInterval constructor.
    dt = datetime.now()
    at = dt
    dur = timedelta(hours=1)
    mkt = test_market
    mct = dt

    st = dt
    ti = [TimeInterval(at, dur, mkt, mct, st)]

    st = st + dur
    ti.append(TimeInterval(at, dur, mkt, mct, st))

    st = st + dur
    ti.append(TimeInterval(at, dur, mkt, mct, st))

    test_market.timeIntervals = ti

    # Create and store three corresponding scheduled powers
    iv = [IntervalValue(test_object, ti[0], test_market, MeasurementType.ScheduledPower, 100),
          IntervalValue(test_object, ti[1], test_market, MeasurementType.ScheduledPower, 200),
          IntervalValue(test_object, ti[2], test_market, MeasurementType.ScheduledPower, 300)]
    test_object.scheduledPowers = iv

    #   Run the test
    pc = [0] * 3
    for i in range(3):
        pc[i] = prod_cost_from_formula(test_object, ti[i])

    # pc(1) = 4 + 3 * 100 + 0.5 * 2 * 100^2 = 10304
    # pc(2) = 4 + 3 * 200 + 0.5 * 2 * 200^2 = 40604
    # pc(3) = 4 + 3 * 300 + 0.5 * 2 * 300^2 = 90904

    # if all(pc ~=[10304, 40604, 90904])
    expected = [10304, 40604, 90904]
    if all([pc[i] != expected[i] for i in range(len(pc))]):
        pf = 'fail'
        raise Exception('- production cost was incorrectly calculated')
    else:
        print('- production cost was correctly calculated')

    #   Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


def test_prod_cost_from_vertices():
    from local_asset_model import LocalAsset
    from market import Market

    # TEST_PROD_COST_FROM_VERTICES - tests function prod_cost_from_vertices()
    print('Running test_prod_cost_from_vertices()')
    pf = 'pass'

    # Create a test object
    test_object = LocalAsset

    # Create a test market
    test_market = Market()

    # Create several active vertices av
    av = [Vertex(0.02, 5, 0),
          Vertex(0.02, 7, 100),
          Vertex(0.025, 9.25, 200)]

    # Create a time interval
    dt = datetime.now()
    at = dt
    #   NOTE: Function Hours() corrects behavior of Matlab function hours().
    dur = timedelta(hours=1)
    mkt = test_market
    mct = dt
    st = dt
    ti = TimeInterval(at, dur, mkt, mct, st)

    # Create and store the activeVertices, which are IntervalValues
    test_object.activeVertices = [IntervalValue(test_object, ti, test_market, MeasurementType.ActiveVertex, av[0]),
                                  IntervalValue(test_object, ti, test_market, MeasurementType.ActiveVertex, av[1]),
                                  IntervalValue(test_object, ti, test_market, MeasurementType.ActiveVertex, av[2])]

    # CASE: Various signed powers when there is more than one vertex
    test_powers = [-50, 0, 50, 150, 250]
    pc = []
    for p in test_powers:
        pc.append(prod_cost_from_vertices(test_object, ti, p))

    # pc(1) = 0: value is always 0 for power < 0
    # pc(2) = 5.0: assign cost from first vertex
    # pc(3) = 6.0: interpolate between vertices
    # pc(4) = 8.125: interpolate between vertices
    # pc(5) = 9.25: use last vertex cost if power > last vertex power

    # if ~all(pc == [0, 5.0, 6.0, 8.125, 9.25])
    expected = [0, 5.0, 6.0, 8.125, 9.25]
    if not all([pc[i] == expected[i] for i in range(len(pc))]):
        pf = 'fail'
        raise Exception('- the production cost was incorrectly calculated')
    else:
        print('- the production cost was correctly calculated')

    # CASE: One vertex (inelastic case, a constant)
    test_object.activeVertices = [
        IntervalValue(test_object, ti, test_market, MeasurementType.ActiveVertex, av[0])]

    # pc[i] = prod_cost_from_vertices(test_object, ti, test_powers[i])
    pc = []
    for p in test_powers:
        pc.append(prod_cost_from_vertices(test_object, ti, p))

    expected = [0.0, 5.0, 5.0, 5.0, 5.0]
    # if ~all(pc == [0.0, 5.0, 5.0, 5.0, 5.0])
    if not all([pc[i] == expected[i] for i in range(len(pc))]):
        pf = 'fail'
        raise Exception('- made an incorrect assignment when there is one vertex')
    else:
        print('- made a correct assignment when there is one vertex')

    # CASE: No active vertices (error case):
    test_object.activeVertices = []

    # print('off', 'all')
    try:
        pc = prod_cost_from_vertices(test_object, ti, test_powers[4])
        pf = 'fail'
        # print('on', 'all')
        raise Exception('- the function should have warned and continued when there were no active vertices')
    except:
        print('- the function returned gracefully when there were no active vertices')
        # print('on', 'all')

    #   Success
    print('- the test function ran to completion')
    print('Result: #s\n\n', pf)


def test_are_different2():
    from transactive_record import TransactiveRecord

    print('Running test_production()')
    pf = 'pass'

    # Create a time interval ti
    dt = datetime.now()
    at = dt
    dur = timedelta(hours=1)
    mkt = None
    mct = dt
    st = dt
    ti = TimeInterval(at, dur, mkt, mct, st)

    transactive_records = [
        TransactiveRecord(ti, 0, 0.5, 100),
        TransactiveRecord(ti, 0, 0.5, 105),
        TransactiveRecord(ti, 1, 0.022, -0.0),
        TransactiveRecord(ti, 2, 0.022, 16400),
        TransactiveRecord(ti, 2, 0.023, 16400)
    ]

    # CASE 0: SIGNAL SETS DIFFER IN NUMBERS OF RECORDS
    print('Case 0: Signals have different record counts.')
    prepped_records = [transactive_records[0]]
    sent_records = [transactive_records[0], transactive_records[1]]
    threshold = 0.02
    response = False

    try:
        response = are_different2(prepped_records, sent_records, threshold)
        print('  The method ran without errors')
    except Exception as ex:
        pf = 'fail'
        print(ex.message)

    if not response:
        pf = 'fail'
        print('  The method said the signals are the same which is wrong')
    else:
        print('  The method correctly said the signals differ')

    # CASE 1: No flexibility. One signal each. Powers of Records 0 match.
    print('Case 1: No flexibility. One signal each. Powers of Records 0 match.')
    prepped_records = [transactive_records[0]]
    sent_records = [transactive_records[0]]
    threshold = 0.02

    try:
        response = are_different2(prepped_records, sent_records, threshold)
        print('  The method ran without errors')
    except:
        pf = 'fail'
        print('  The method encountered errors and stopped')

    if response:
        pf = 'fail'
        print('  The method said the signals were different which is wrong')
    else:
        print('  The method correctly said the signals were the same')

    # CASE 2 - No flexibiltiy. One signal each. Powers of Records 0 do not
    # match.
    print('Case 2: No flexibility. One signal each. Powers of Records 0 do NOT match.')
    prepped_records = [transactive_records[0]]
    sent_records = [transactive_records[1]]
    threshold = 0.02

    try:
        response = are_different2(prepped_records, sent_records, threshold)
        print('  The method ran without errors')
    except:
        pf = 'fail'
        print('  The method encountered errors and stopped')

    if not response:
        pf = 'fail'
        print('  The method said the signals were the same which is wrong')
    else:
        print('  The method correctly said the signals differ')

    # CASE 3 - (Hung's case) Flexibility, but identical signals.
    # NOTE: Hung had found a case where powers had become zero, causing logic
    # problems. Code has been revised to avoid this possiblity.
    print('Case 3: Flexibility. Signals are identical')
    prepped_records = [transactive_records[2], transactive_records[3]]
    sent_records = [transactive_records[2], transactive_records[3]]
    threshold = 0.02

    try:
        response = are_different2(prepped_records, sent_records, threshold)
        print('  The method ran without errors')
    except:
        pf = 'fail'
        print('  The method encountered errors and stopped')

    if response:
        pf = 'fail'
        print('  The method said the signals differ which is wrong')
    else:
        print('  The method correctly said the signals are the same')

    # CASE 4 - Flexibility, but different signals.
    print('Case 4: Flexibility. Signals are different')
    prepped_records = [transactive_records[2], transactive_records[3]]
    sent_records = [transactive_records[2], transactive_records[3], transactive_records[4]]
    threshold = 0.02

    try:
        response = are_different2(prepped_records, sent_records, threshold)
        print('  The method ran without errors')
    except:
        pf = 'fail'
        print('  The method encountered errors and stopped')

    if not response:
        pf = 'fail'
        print('  The method said the signals are the same which is wrong')
    else:
        print('  The method correctly said the signals differ')

    # Success
    print('- the test ran to completion')
    print('Result: {}\n\n'.format(pf))


if __name__ == "__main__":
    # test_is_hlh()  # Relies on date parser this is not available.
    test_order_vertices()
    test_production()
    test_prod_cost_from_formula()
    test_prod_cost_from_vertices()
    test_are_different2()
