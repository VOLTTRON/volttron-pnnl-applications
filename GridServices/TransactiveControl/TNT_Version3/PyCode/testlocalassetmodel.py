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


from datetime import date, time
# from dateutil import relativedelta    # NOT AVAILABLE??

from vertex import Vertex
from interval_value import IntervalValue
from measurement_type import MeasurementType
from helpers import *
from market import Market
from time_interval import TimeInterval
from local_asset_model import LocalAsset
from TransactiveNode import TransactiveNode


def test_assign_transition_costs():
    print('Running LocalAsset.test_assign_transition_costs()')

    print('  The test is not completed.')

    # Success.
    print('Method test_assign_transition_costs() ran to completion.\n')
    # print('\nResult: #s\n\n', pf)


def test_calculate_reserve_margin():
    # TEST_LAM_CALCULATE_RESERVE_MARGIN() - a LocalAsset ("LAM") class
    # method NOTE: Reserve margins are introduced but not fully integrated into
    # code in early template versions.
    # CASES:
    # 1. uses hard maximum if no active vertices exist
    # 2. vertices exist
    # 2.1 uses maximum vertex power if it is less than hard power constraint
    # 2.2 uses hard constraint if it is less than maximum vertex power
    # 2.3 upper flex power is greater than scheduled power assigns correct
    # positive reserve margin
    # 2.4 upperflex power less than scheduled power assigns zero value to
    # reserve margin.
    print('Running LocalAsset.test_calculate_reserve_margin()')

    # Establish test market
    test_mkt = Market()

    # Establish test market with an active time interval
    # Note: modified 1/29/18 due to new TimeInterval constructor
    dt = datetime.now()
    at = dt
    # NOTE: def Hours() corrects behavior of Matlab hours().
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt
    # st = datetime(date)
    st = datetime.combine(date.today(), time())

    ti = TimeInterval(at, dur, mkt, mct, st)

    # Store time interval
    test_mkt.timeIntervals = [ti]

    # Establish test object that is a LocalAsset.
    test_model = LocalAsset()
    test_model.scheduledPowers = [
        IntervalValue(test_model, ti, test_mkt, MeasurementType.ScheduledPower, 0.0)]
    test_model.maximumPower = 100

    # Run the first test case.
    print("  Case 1:")
    try:
        test_model.calculate_reserve_margin(test_mkt)
        print('  The test ran without errors')
    except RuntimeWarning as cause:
        print('  The test encountered errors', cause)

    assert len(test_model.reserveMargins) == 1, 'An unexpected number of results were stored'

    assert test_model.reserveMargins[0].value == test_model.maximumPower, \
                                                                'The method did not use the available maximum power'

    # create some vertices and store them
    iv = [
        IntervalValue(test_model, ti, test_mkt, MeasurementType.Vertex, Vertex(0, 0, -10)),
        IntervalValue(test_model, ti, test_mkt, MeasurementType.Vertex, Vertex(0, 0, 10))
    ]
    test_model.activeVertices = iv

    print("  Case 2: test with maximum power greater than maximum vertex")
    test_model.maximumPower = 100
    try:
        test_model.calculate_reserve_margin(test_mkt)
        print('  The test ran without errors')
    except RuntimeWarning as cause:
        print('  The test encountered errors', cause)

    assert test_model.reserveMargins[0].value == 10, 'The method should have used vertex for comparison'

    print("  Case 3: test with maximum power less than maximum vertex")
    test_model.maximumPower = 5
    try:
        test_model.calculate_reserve_margin(test_mkt)
        print('  The test ran without errors')
    except RuntimeWarning as cause:
        print('  The test encountered errors', cause)

    assert test_model.reserveMargins[0].value == 5, 'The method should have used maximum power for comparison'

    print("  Case 4: test with scheduled power greater than maximum vertex")
    test_model.scheduledPowers[0].value = 20
    test_model.maximumPower = 500
    try:
        test_model.calculate_reserve_margin(test_mkt)
        print('  The test ran without errors')
    except RuntimeWarning as cause:
        print('  The test encountered errors', cause)

    assert test_model.reserveMargins[0].value == 0, 'The method should have assigned zero for a neg. result'

    # Success.
    print('Method test_calculate_reserve_margin() ran to completion.\n')


def test_cost():
    print('Running LocalAsset.test_cost()')

    print('  Case 1: Use default costParameters')
    test_asset = LocalAsset()
    power = 10

    try:
        production_cost = test_asset.cost(power)
        print('  - The method ran without errors')
    except RuntimeWarning as cause:
        print('  - ERRORS ENCOUNTERED', cause)
        production_cost = []

    assert production_cost == 0, 'The production cost should have been 0'

    print('  Case 2: No power parameter is used')
    test_value = 1.234
    immutable_trio = (test_value, 0, 0)
    test_asset.costParameters = immutable_trio

    try:
        production_cost = test_asset.cost()
        print('  - The method ran without errors')
    except RuntimeWarning as cause:
        print('  - ERRORS ENCOUNTERED', cause)

    assert production_cost == test_value, 'The production cost should have been provided test value'

    print('  Case 3: Full calculation')
    test_asset.costParameters = [1, 1, 1]
    power = 10

    try:
        production_cost = test_asset.cost(power)
        print('  - The method ran without errors')
    except RuntimeWarning as cause:
        print('  - ERRORS ENCOUNTERED', cause)

    assert production_cost == 111, 'The production cost should have been 111'

    # Success.
    print('Method test_cost() ran to completion.\n')


def test_engagement_cost():
    print('Running LocalAsset.test_engagement_cost()')

    #   Create a test LocalAsset object.
    test_model = LocalAsset()

    #   Assign engagement costs for [dissengagement, hold, engagement]
    test_model.engagementCost = [1, 2, 3]

    # TEST 1
    print('  Test 1a: Normal transition input arguments [-1,0,1]')

    transition = 0  # false - false  # a hold transition, unchanged

    try:
        cost = test_model.engagement_cost(transition)
        print('The case ran without errors')
    except RuntimeWarning as cause:
        print('The case encountered errors', cause)
        cost = []

    assert cost == 2, '  The method miscalculated the cost of a hold'

    print("  Test 1b: Test disengagement cost")
    transition = -1  # false - true  # an disengagement transition

    try:
        cost = test_model.engagement_cost(transition)
        print('The case ran without errors')
    except RuntimeWarning as cause:
        print('The case encountered errors', cause)

    assert cost == 1, 'The method miscalculated the cost of a disengagement'

    print("  Test 1c: Test cost of engagement")
    transition = 1  # true - false  # an disengagement transition

    try:
        cost = test_model.engagement_cost(transition)
        print('The case ran without errors')
    except RuntimeWarning as cause:
        print('The case encountered errors', cause)

    assert cost == 3, 'The method miscalculated the cost of an engagement'

    # TEST 2
    print('- Test 2: Unexpected, dissallowed input argument')

    transition = 7  # a disallowed transition

    try:
        cost = test_model.engagement_cost(transition)
        print('The case ran without errors')
    except RuntimeWarning as cause:
        print('The case encountered errors', cause)
        cost = []

    assert cost is None, 'The method should not assign a cost for a disallowed transition'

    # Success.
    print('Method test_engagement_cost() ran to completion.\n')


def test_schedule_engagement():
    # TEST_SCHEDULE_ENGAGEMENT() - tests a LocalAsset method called schedule_engagment()

    print('Running LocalAsset.test_schedule_engagement()')

    #   Establish test market
    test_mkt = Market()

    #   Establish test market with two distinct active time intervals
    # Note: This changed 1/29/18 due to new TimeInterval constructor
    dt = datetime.now()
    at = dt
    #   NOTE: def Hours() corrects behavior of Matlab hours().
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt
    st = datetime.combine(date.today(), time())  # datetime(date)

    ti = [TimeInterval(at, dur, mkt, mct, st)]

    st = ti[0].startTime + dur
    ti.append(TimeInterval(at, dur, mkt, mct, st))

    #   store time intervals
    test_mkt.timeIntervals = ti

    #   Establish test model that is a LocalAsset.
    test_model = LocalAsset()

    #   Run the first test case.
    print("  Case 1: Generate engagement schedule for two time intervals.")
    try:
        test_model.schedule_engagement(test_mkt)
        print("  The case ran without errors.")
    except RuntimeWarning as cause:
        print("  The case encountered errors.", cause)

    #   Were the right number of engagement schedule values created?
    assert len(test_model.engagementSchedule) == 2, 'The method did not store the engagement schedule'

    # Where the correct scheduled engagement values stored?
    assert len([x.value for x in test_model.engagementSchedule if x.value != 1]) == 0, \
        'The stored engagement schedule was not as expected'
    """
    if len([x.value for x in test_model.engagementSchedule if x.value != 1]) > 0:
        pf = 'fail'
        raise Exception('- the stored engagement schedule was not as expected')
    else:
        print('- the result values were as expected')
        """

    # Create and store another active time interval.
    st = ti[1].startTime + dur
    ti.append(TimeInterval(at, dur, mkt, mct, st))

    #   Re-store time intervals
    test_mkt.timeIntervals = ti

    #   Run next test case.
    print("  Case 2: Adding a third time interval.")
    try:
        test_model.schedule_engagement(test_mkt)
        print("  The method ran without errors.")
    except RuntimeWarning as cause:
        print("  The method encountered errors.", cause)

    #   Was the new time interval used?
    assert len(test_model.engagementSchedule) == 3, 'The method apparently failed to create a new engagement'

    # Were the existing time interval values reassigned properly?
    # if any([test_model.engagementSchedule.value] != true * ones(1, 3)):
    assert all([x.value == 1 for x in test_model.engagementSchedule]), \
        'The existing list was not augmented as expected'

    # Success.
    print('Method test_schedule_engagement() ran to completion.\n')
    # print('\nResult: #s\n\n', pf)


def test_schedule_power():
    # TEST_SCHEDULE_POWER() - tests a LocalAsset method called
    # schedule_power().

    print('Running LocalAsset.test_schedule_power()')

    #   Establish test market
    test_mkt = Market()

    #   Establish test market with two distinct active time intervals
    # Note: This changed 1/29/19 due to new TimeInterval constructor
    dt = datetime.now()
    at = dt
    #   NOTE: def Hours() corrects behavior of Matlab hours().
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt
    st = datetime.combine(date.today(), time())  # datetime(date)

    ti = [TimeInterval(at, dur, mkt, mct, st)]
    st = ti[0].startTime + dur
    ti.append(TimeInterval(at, dur, mkt, mct, st))

    #   Store time intervals
    test_mkt.timeIntervals = ti

    #   Establish test model that is a LocalAsset with a default power
    #   property.
    test_model = LocalAsset()
    test_model.defaultPower = 3.14159

    #   Run the first test case.
    print("  Case 1: Power is scheduled for two time intervals.")
    try:
        test_model.schedule_power(test_mkt)
        print("  The method ran without errors")
    except RuntimeWarning as cause:
        print("  The method encountered errors", cause)

    #   Were the right number of scheduled power values created?
    assert len(test_model.scheduledPowers) == 2, 'The method did not store the right number of results'

    # Where the correct scheduled power values stored?
    # if any([test_model.scheduledPowers.value] != test_model.defaultPower * ones(1, 2))
    assert all([x.value == test_model.defaultPower for x in test_model.scheduledPowers]), \
        'The stored scheduled powers were not as expected'

    # Change the default power.
    test_model.defaultPower = 6

    #   Create and store another active time interval.
    st = ti[1].startTime + dur
    ti.append(TimeInterval(at, dur, mkt, mct, st))

    #   Re-store time intervals
    test_mkt.timeIntervals = ti

    #   Run next test case.
    print("  Case 2: Power is scheduled for three time intervals.")
    try:
        test_model.schedule_power(test_mkt)
        print("  The method ran without errors")
    except RuntimeWarning as cause:
        print("  The method encountered errors", cause)

    #   Was the new time interval used?
    assert len(test_model.scheduledPowers) == 3, 'The method failed to create a new scheduled power'

    # Were the existing time intervals reassigned properly?
    assert all([x.value == test_model.defaultPower for x in test_model.scheduledPowers]), \
        '- existing scheduled powers were not reassigned properly'

    # Success.
    print('Method test_schedule_power() ran to completion.\n')


def test_update_dual_costs():
    # TEST_UPDATE_DUAL_COSTS() - test method update_dual_costs() that creates or revises the dual costs in active time
    # intervals using active vertices, scheduled powers, and marginal prices.
    # NOTE: This test is virtually identical to the Neighbor test of the same name.
    print('Running LocalAsset.test_update_dual_costs()')

    #   Create a test Market object.
    test_market = Market()

    #   Create and store a TimeInterval object.
    dt = datetime.now()  # datetime that may be used for most datetime arguments
    time_interval = TimeInterval(dt, timedelta(hours=1), test_market, dt, dt)
    test_market.timeIntervals = [time_interval]

    #   Create and store a marginal price IntervalValue object.
    test_market.marginalPrices = [
        IntervalValue(test_market, time_interval, test_market, MeasurementType.MarginalPrice, 0.1)]

    #   Create a test LocalAsset.
    test_model = LocalAsset()

    #   Create and store a scheduled power IntervalValue in the active time interval.
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, 100)]

    #   Create and store a production cost IntervalValue in the active time interval.
    test_model.productionCosts = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ProductionCost, 1000)]

    # TEST 1
    print('- Test 1: First calculation of a dual cost')

    try:
        test_model.update_dual_costs(test_market)
        print('  The test ran without errors')
    except RuntimeWarning as cause:
        print('  The test encountered errors', cause)

    assert len(test_model.dualCosts) == 1, 'The wrong number of dual cost values was created'

    dual_cost = test_model.dualCosts[0].value

    assert dual_cost == (1000 - 100 * 0.1), 'An unexpected dual cost value was found'

    # TEST 2
    print('- Test 2: Reassignment of an existing dual cost')

    #   Configure the test by modifying the marginal price value.
    test_market.marginalPrices[0].value = 0.2

    try:
        test_model.update_dual_costs(test_market)
        print('  The test ran without errors')
    except RuntimeWarning as cause:
        print('  The test encountered errors', cause)

    assert len(test_model.dualCosts) == 1, 'The wrong number of dual cost values was created'

    dual_cost = test_model.dualCosts[0].value

    assert dual_cost == (1000 - 100 * 0.2), 'An unexpected dual cost value was found'

    # Success.
    print('Method test_update_dual_costs() ran to completion.\n')


def test_update_production_costs():
    # TEST_UPDATE_PRODUCTION_COSTS() - test method update_production_costs() that calculates production costs from
    # active vertices and scheduled powers.
    # NOTE: This test is virtually identical to the Neighbor test of the same name.
    print('Running LocalAsset.test_update_production_costs()')

    #   Create a test Market.
    test_market = Market()

    #   Create and store a TimeInterval.
    dt = datetime.now()  # datetime that may be used for most datetime arguments
    time_interval = TimeInterval(dt, timedelta(hours=1), test_market, dt, dt)
    test_market.timeIntervals = [time_interval]

    #   Create a test LocalAsset.
    test_model = LocalAsset()

    #   Create and store a scheduled power IntervalValue in the active time interval.
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, 50)]

    #   Create and store some active vertices IntervalValues in the active time interval.
    vertices = [
        Vertex(0.1, 1000, 0),
        Vertex(0.2, 1015, 100)]
    interval_values = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ActiveVertex, vertices[0]),
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ActiveVertex, vertices[1])]
    test_model.activeVertices = interval_values

    # TEST 1
    print('- Test 1: First calculation of a production cost')

    try:
        test_model.update_production_costs(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning as cause:
        print('  - the method encountered errors', cause)

    assert len(test_model.productionCosts) == 1, 'The wrong number of production costs was created'

    production_cost = test_model.productionCosts[0].value
    assert production_cost == 1007.5, 'An unexpected production cost value was found'

    # TEST 2
    print('- Test 2: Reassignment of an existing production cost')

    #   Configure the test by modifying the scheduled power value.
    test_model.scheduledPowers[0].value = 150

    try:
        test_model.update_production_costs(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning as cause:
        print('  - the method encountered errors', cause)

    assert len(test_model.productionCosts) == 1, 'The wrong number of productions was created'

    production_cost = test_model.productionCosts[0].value

    assert production_cost == 1015, 'An unexpected dual cost value was found'

    # Success.
    print('Method test_update_production_costs() ran to completion.\n')


def test_update_vertices():
    # TEST_UPDATE_VERTICES() - test method update_vertices(), which for this base class of LocalAsset does
    # practically nothing and must be redefined by child classes that represent flesible assets.
    print('Running LocalAsset.test_update_vertices()')

    #   Create a test Market.
    test_market = Market()

    #   Create and store a TimeInterval.
    dt = datetime.now()  # datetime that may be used for most datetime arguments
    time_interval = TimeInterval(dt, timedelta(hours=1), test_market, dt, dt)
    test_market.timeIntervals = [time_interval]

    #   Create a test LocalAsset.
    test_model = LocalAsset()

    #   Create and store a scheduled power IntervalValue in the active time interval.
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, 50)]

    #   Create maximum and minimum powers.
    test_model.maximumPower = 200
    test_model.minimumPower = 0

    # TEST 1
    print('- Test 1: Basic operation')

    try:
        test_model.update_vertices(test_market)
        print('  - the method ran without errors')
    except RuntimeWarning as cause:
        print('  - the method encountered errors', cause)

    assert len(test_model.activeVertices) == 1, 'There were an unexpected number of active vertices'

    # Success.
    print('Method test_update_vertices ran to completion.\n')


def test_get_extended_prices():
    print("Running test_get_extended_prices()")
    """
    This base method uses the following prioritization to populate the price horizon needed by this local asset:
        1. Actual marginal prices offered by the market.
        2. Actual marginal prices in prior sequential markets that are similar to the market.
        3. Actual marginal prices in prior markets that are being corrected by the market.
        4. Modeled prices using the market's price model
        5. The market's default price value.
        6. Nothing
    """
    # ******************************************************************************************************************
    print("  Case 1. Actual marginal prices offered by the market.")  # *****************************************
    # The test setup is such that the local asset should use Methods 1 to find an existing marginal price in its market.
    now = datetime.now()
    # test_asset = LocalAsset()
    test_asset_model = LocalAsset()
    # test_asset = test_asset_model
    # test_asset_model.object = test_asset
    test_asset_model.schedulingHorizon = timedelta(hours=0.5)
    test_market = Market()
    test_interval = TimeInterval(now, timedelta(hours=1), test_market, now, now)
    price = 3.14159
    test_price = IntervalValue(None, test_interval, test_market, 'test', price)
    test_market.timeIntervals = [test_interval]
    test_market.marginalPrices = [test_price]
    test_mtn = TransactiveNode()
    test_mtn.markets = [test_market]
    test_mtn.localAssets = [test_asset_model]

    assert len(test_market.marginalPrices) == 1, 'The market was supposed to have a marginal price'
    assert datetime.now() + test_asset_model.schedulingHorizon \
           < test_market.timeIntervals[0].startTime + test_market.intervalDuration, \
        'For this test, the existing marginal price intervals should not extend beyond the scheduling horizon.'

    try:
        price_set = test_asset_model.get_extended_prices(test_market)
        print("  The case ran without errors.")
    except RuntimeWarning as cause:
        print("  The case encountered errors.", cause)
        price_set = []

    assert len(price_set) == 1, 'An unexpected number of prices was found'
    assert price_set[0].value == price, 'The price was no correct'

    # ******************************************************************************************************************
    print("  Case 2. Actual marginal prices in prior sequential market that is similar to the market.")  # ****
    # The test setup is such that the local asset should sequentially use Methods 1, & 2 to find two marginal prices.
    now = datetime.now()

    test_asset_model = LocalAsset()

    test_asset_model.schedulingHorizon = timedelta(hours=1.5)  # Should cause asset to use prior market

    test_market = Market()

    test_interval0 = TimeInterval(now, timedelta(hours=1), test_market, now, now)
    price0 = 3.14159
    test_price0 = IntervalValue(None, test_interval0, test_market, 'test', price0)
    test_market.timeIntervals = [test_interval0]
    test_market.marginalPrices = [test_price0]
    test_market.marketSeriesName = "Test Market"
    test_market.marketClearingTime = now

    prior_market = Market()
    test_interval1 = TimeInterval(now, timedelta(hours=1), prior_market, now, now)
    test_interval2 = TimeInterval(now, timedelta(hours=1), prior_market, now, now + timedelta(hours=1))
    price1 = 10
    test_price1 = IntervalValue(None, test_interval1, prior_market, 'test', price1)
    test_price2 = IntervalValue(None, test_interval2, prior_market, 'test', price1)
    prior_market.timeIntervals = [test_interval1, test_interval2]
    prior_market.marginalPrices = [test_price1, test_price2]
    prior_market.marketSeriesName = test_market.marketSeriesName
    prior_market.marketClearingTime = test_market.marketClearingTime - timedelta(hours=1)

    test_market.priorMarketInSeries = prior_market  # Important pointer to preceding market interval in market series.

    test_mtn = TransactiveNode()
    test_mtn.markets = [prior_market, test_market]
    test_mtn.localAssets = [test_asset_model]

    assert len(test_market.marginalPrices) == 1, 'The market was supposed to have a marginal price'
    assert len(prior_market.marginalPrices) == 2, "The prior market should have had two prices"
    assert test_market.marketSeriesName == prior_market.marketSeriesName, 'The market names must be the same'
    assert test_market.priorMarketInSeries == prior_market, "The market must point to its predecessor in market series"

    try:
        price_set = test_asset_model.get_extended_prices(test_market)
        print("  The case ran without errors.")
    except RuntimeWarning as result:
        print("  The case encountered errors.", result)

    assert len(price_set) == 2, 'An unexpected number of prices was found'
    assert price_set[0].value == price0, 'The first price was not correct'
    assert price_set[1].value == price1, 'The second price was not correct'

    # ******************************************************************************************************************
    print("  Case 3. Actual marginal prices in prior markets that are being corrected by the market.")  # *******
    # The test setup is such that the local asset should sequentially use Methods 1, 2, & 3 to find three marginal
    # prices.
    now = datetime.now()
    # test_asset = LocalAsset()
    test_asset_model = LocalAsset()
    # test_asset.model = test_asset_model
    # test_asset_model.object = test_asset
    test_asset_model.schedulingHorizon = timedelta(hours=2.5)  # Should cause asset to use prior market

    test_market = Market()

    test_interval0 = TimeInterval(now, timedelta(hours=1), test_market, now, now)
    price0 = 3.14159
    test_price0 = IntervalValue(None, test_interval0, test_market, 'test', price0)
    test_market.timeIntervals = [test_interval0]
    test_market.marginalPrices = [test_price0]
    test_market.marketSeriesName = "Test Market"
    test_market.marketClearingTime = now

    prior_market = Market()
    test_interval1 = TimeInterval(now, timedelta(hours=1), prior_market, now, now)
    test_interval2 = TimeInterval(now, timedelta(hours=1), prior_market, now, now + timedelta(hours=1))
    price1 = 10
    test_price1 = IntervalValue(None, test_interval1, prior_market, 'test', price1)
    test_price2 = IntervalValue(None, test_interval2, prior_market, 'test', price1)
    prior_market.timeIntervals = [test_interval1, test_interval2]
    prior_market.marginalPrices = [test_price1, test_price2]
    prior_market.marketSeriesName = test_market.marketSeriesName
    prior_market.marketClearingTime = test_market.marketClearingTime - timedelta(hours=1)

    test_market.priorMarketInSeries = prior_market

    corrected_market = Market()
    price2 = 20
    test_interval3 = TimeInterval(now, timedelta(hours=1), corrected_market, now, now + timedelta(hours=2))
    test_price3 = IntervalValue(None, test_interval1, corrected_market, 'test', price2)
    test_price4 = IntervalValue(None, test_interval2, corrected_market, 'test', price2)
    test_price5 = IntervalValue(None, test_interval3, corrected_market, 'test', price2)
    corrected_market.timeIntervals = [test_interval1, test_interval2, test_interval3]
    corrected_market.marginalPrices = [test_price3, test_price4, test_price5]
    corrected_market.marketSeriesName = "Corrected Market"
    corrected_market.marketClearingTime = test_market.marketClearingTime - timedelta(hours=2)
    corrected_market.intervalDuration = timedelta(hours=1)

    test_market.priorRefinedMarket = corrected_market

    test_mtn = TransactiveNode()
    test_mtn.markets = [corrected_market, prior_market, test_market]
    test_mtn.localAssets = [test_asset_model]

    assert len(test_market.marginalPrices) == 1, 'The market was supposed to have a marginal price'
    assert len(prior_market.marginalPrices) == 2, "The prior market should have had two prices"
    assert len(corrected_market.marginalPrices) == 3, 'The corrected market should have three prices'
    assert test_market.marketSeriesName == prior_market.marketSeriesName, 'The market names must be the same'

    try:
        price_set = test_asset_model.get_extended_prices(test_market)
        print("  The case ran without errors.")
    except RuntimeWarning as result:
        print("  The case encountered errors.", result)
        price_set = []

    assert len(price_set) == 3, 'An unexpected number of prices was found'
    assert price_set[0].value == price0, 'The first price was not correct'
    assert price_set[1].value == price1, 'The second price was not correct'
    assert price_set[2].value == price2, 'The third price was not correct'

    # ******************************************************************************************************************
    print("  Case 4. Modeled prices using the market's price model.")  # ***********************************************
    # The test setup is such that the local asset should use Methods 1 & 4 to find four marginal prices.
    now = datetime.now()
    test_asset_model = LocalAsset()
    test_asset_model.schedulingHorizon = timedelta(hours=3.5)  # Should cause asset to use prior market

    test_market = Market()

    test_interval0 = TimeInterval(now, timedelta(hours=1), test_market, now, now)
    price0 = 3.14159
    test_price0 = IntervalValue(None, test_interval0, test_market, 'test', price0)
    test_market.timeIntervals = [test_interval0]
    test_market.marginalPrices = [test_price0]
    test_market.marketSeriesName = "Test Market"
    test_market.marketClearingTime = now
    test_market.priorMarketInSeries = None
    test_market.priorRefinedMarket = None
    avg_price = 30
    std_price = 0.1
    test_market.priceModel = [avg_price, std_price] * 24  # Critical to this test
    test_mtn = TransactiveNode()
    test_mtn.markets = [test_market]
    test_mtn.localAssets = [test_asset_model]

    assert len(test_market.marginalPrices) == 1, 'The market was supposed to have a marginal price'
    assert len(test_market.priceModel) == 48, 'A price model must exist for all 2 * 24 hours'

    try:
        price_set = test_asset_model.get_extended_prices(test_market)
        print("  The case ran without errors.")
    except RuntimeWarning as result:
        print("  The case encountered errors.", result)
        price_set = []

    # 200207DJH: The assignment of modeled prices now completes the prior successful method to the top of the next hour.
    #            Thereafter, modeled prices are assigned through the top of the hour that exceeds the scheduling
    #            horizon. Therefore, there is some variability in the count of
    assert len(price_set) == 4 or len(price_set) == 5, \
                                                    ('An unexpected number', len(price_set), ' of prices was found')
    assert price_set[0].value == price0, 'The first price was not correct'
    assert all([price_set[x].value == avg_price for x in range(1, len(price_set))]), \
                                                                                        'Prices 1 - 4 were not correct'

    # ******************************************************************************************************************
    print("  Case 5. The market's default price value.")  # ************************************************************

    test_asset_model = LocalAsset()

    test_asset_model.schedulingHorizon = timedelta(hours=4.5)

    test_market = Market()
    default_price = 1.2345
    test_market.defaultPrice = default_price
    test_market.priceModel = None
    test_market.intervalsToClear = 24
    test_market.intervalDuration = timedelta(hours=1)
    test_market.activationLeadTime = timedelta(days=2)
    test_market.priorRefinedMarket = None

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_market]

    assert type(test_market.defaultPrice) == float, 'A valid default price must be defined'

    try:
        price_set = test_asset_model.get_extended_prices(test_market)
        print("  The case ran without errors.")
    except RuntimeWarning:
        print("  The case encountered errors.")

    assert len(price_set) == 5, 'The number of horizon prices was unexpected'
    assert all([price_set[x].value == default_price for x in range(1, len(price_set))]), \
        'The default prices were not used'

    print("Method test_get_extended_prices() ran to completion.\n")


if __name__ == '__main__':
    print('Running tests in testlocalasset.py\n')
    test_assign_transition_costs()
    test_calculate_reserve_margin()  # Done
    test_cost()  # Missing - low priority
    test_engagement_cost()  # Missing - low priority
    test_schedule_engagement()  # Done - low priority
    test_schedule_power()  # Done - high priority
    test_update_dual_costs()  # Missing - high priority
    test_update_production_costs()  # Missing - high priority
    test_update_vertices()  # Missing - high priority
    test_get_extended_prices()
    print('Tests in testlocalasset.py ran to completion.\n')
