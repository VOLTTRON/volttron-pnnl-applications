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

from vertex import Vertex
from helpers import *
from measurement_type import MeasurementType
from interval_value import IntervalValue
# from transactive_record import TransactiveRecord
# from meter_point import MeterPoint
from market import Market
from market_state import MarketState
from time_interval import TimeInterval
from neighbor_model import Neighbor
from local_asset_model import LocalAsset
from TransactiveNode import TransactiveNode
from method import Method


def test_assign_system_vertices():
    print('Running test_assign_system_vertices()')
    print('WARNING: this test calls and relies on method sum_vertices().')
    print('**Case 1: Typical case collecting several neighbor and asset vertices.')
    now = datetime.now()
    positive_infinity = float('Inf')
    test_node = TransactiveNode()
    test_market = Market()
    test_market.intervalDuration = timedelta(hours=1)
    test_node.markets = [test_market]
    test_asset = LocalAsset()
    test_node.localAssets = [test_asset]
    test_neighbor = Neighbor()
    test_node.neighbors = [test_neighbor]
    test_interval = TimeInterval(now, test_market.intervalDuration, test_market, now, now)
    test_market.timeIntervals = [test_interval]

    vertex1 = Vertex(0.02, 0, 0)
    interval_value1 = IntervalValue(test_market, test_interval, test_market, None, vertex1)

    vertex2 = Vertex(0.05, 0, 10)
    interval_value2 = IntervalValue(test_market, test_interval, test_market, None, vertex2)
    test_neighbor.activeVertices = [interval_value1, interval_value2]

    vertex3 = Vertex(positive_infinity, 0, -4)
    interval_value3 = IntervalValue(test_market, test_interval, test_market, None, vertex3)
    test_asset.activeVertices = [interval_value3]

    assert vertex1.power == 0, 'The first vertex was configured at 0 kW.'
    assert vertex1.marginalPrice == 0.02, 'The first vertex was configured at 0.02 $/kWh.'
    assert vertex2.power == 10, 'The second vertex was configured at 10 kW.'
    assert vertex2.marginalPrice == 0.05, 'The second vertex was configured at 0.05 $/kWh.'
    assert vertex3.power == -4, 'The third vertex was configured at -4 kW.'

    try:
        test_market.assign_system_vertices(test_node)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print(' - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_market.activeVertices) == 2, \
                ('Two vertices should have been assigned; ' + str(len(test_market.activeVertices)) + ' were assigned.')
    assert test_market.activeVertices[0].value.power == -4, 'The first vertex should have been at -4 kW.'
    assert test_market.activeVertices[1].value.power == 6, 'The second vertex should have been at 6 kW.'
    assert test_market.activeVertices[0].value.marginalPrice == 0.02, 'The first vertex should have been at 0.02 $/kWh.'
    assert test_market.activeVertices[1].value.marginalPrice == 0.05, 'The first vertex should have been at 0.05 $/kWh.'

    print('test_assign_system_vertices() ran to completion\n')


def test_balance():
    print('Running test_balance()')
    print('**Case 1: Find marginal price associated with test_assign_system_vertices(), Case 1.')
    print('  NOTE: The tested method may call assign_system_vertices().')
    now = datetime.now()
    positive_infinity = float('Inf')
    test_node = TransactiveNode()
    test_market = Market()
    test_market.intervalDuration = timedelta(hours=1)
    test_node.markets = [test_market]
    test_asset = LocalAsset()
    test_node.localAssets = [test_asset]
    test_neighbor = Neighbor()
    test_node.neighbors = [test_neighbor]
    test_interval = TimeInterval(now, test_market.intervalDuration, test_market, now, now)
    test_market.timeIntervals = [test_interval]

    vertex1 = Vertex(0.02, 0, 0)
    interval_value1 = IntervalValue(test_market, test_interval, test_market, None, vertex1)

    vertex2 = Vertex(0.05, 0, 10)
    interval_value2 = IntervalValue(test_market, test_interval, test_market, None, vertex2)
    test_neighbor.activeVertices = [interval_value1, interval_value2]

    vertex3 = Vertex(positive_infinity, 0, -4)
    interval_value3 = IntervalValue(test_market, test_interval, test_market, None, vertex3)
    test_asset.activeVertices = [interval_value3]

    test_market.method = Method.Interpolation
    test_market.marginalPrices = [IntervalValue(test_market, test_interval, test_market, 'marginalPrice', 0.06)]

    assert vertex1.power == 0, 'The first vertex was configured at 0 kW.'
    assert vertex1.marginalPrice == 0.02, 'The first vertex was configured at 0.02 $/kWh.'
    assert vertex2.power == 10, 'The second vertex was configured at 10 kW.'
    assert vertex2.marginalPrice == 0.05, 'The second vertex was configured at 0.05 $/kWh.'
    assert vertex3.power == -4, 'The third vertex was configured at -4 kW.'

    try:
        test_market.balance(test_node)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print(' - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_market.activeVertices) == 2, \
                ('Two vertices should have been assigned; ' + str(len(test_market.activeVertices)) + ' were assigned.')
    assert test_market.activeVertices[0].value.power == -4, 'The first vertex should have been at -4 kW.'
    assert test_market.activeVertices[1].value.power == 6, 'The second vertex should have been at 6 kW.'
    assert test_market.activeVertices[0].value.marginalPrice == 0.02, 'The first vertex should have been at 0.02 $/kWh.'
    assert test_market.activeVertices[1].value.marginalPrice == 0.05, 'The first vertex should have been at 0.05 $/kWh.'
    assert len(test_market.marginalPrices) == 1, 'Only one marginal price should have been assigned.'
    assert test_market.marginalPrices[0].value == 0.032, 'The calculated marginal price should have been 0.032 $/kWh.'

    print('test_balance() ran to completion\n')


def test_calculate_blended_prices():
    print('Running test_calculate_blended_prices()')
    print('This test is not complete')
    print('**Case 1:')
    print('test_calculate_blended_prices() ran to completion\n')


def test_check_intervals():
    # This test simply makes sure that the right number of time interval objects are created for a market object.
    print('Running Market.test_check_intervals()')

    test_market = Market()
    test_market.marketClearingTime = datetime(year=2020, month=1, day=1, hour=0, minute=0, second=0)
    test_market.intervalsToClear = 6
    test_market.intervalDuration = timedelta(hours=1)
    test_market.deliveryLeadTime = timedelta(minutes=10)

    try:
        test_market.check_intervals()
        print(' - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_market.timeIntervals) == test_market.intervalsToClear, \
        'The wrong number of time intervals was created.'
    assert test_market.timeIntervals[0].startTime == test_market.marketClearingTime + test_market.deliveryLeadTime, \
        'The time intervals do not begin with the correct start time.'
    assert test_market.timeIntervals[1].startTime == test_market.timeIntervals[0].startTime \
           + test_market.intervalDuration, 'The intervals might not be separated by the correct duration'

    # Success
    print('Method test_check_intervals() ran to completion.\n')


def test_check_marginal_prices():
    """
    1. If the market interval already has a price, stop.
    2. If the same time interval exists from a prior market clearing, its price may be used. This can be the case
       where similar successive markets' delivery periods overlap, e.g., a rolling window of 24 hours.
    3. If this market corrects another prior market, its cleared price should be used, e.g., a real-time market
       that corrects day-ahead market periods.
    4. If there exists a price forecast model for this market, this model should be used to forecast price. See
       method Market.model_prices().
    5. If all above methods fail, market periods should be assigned the market's default price. See property
       Market.defaultPrice.
    """
    print('Running Market.test_check_marginal_prices()')

    # ******************************************************************************************************************
    print("**Case 1: If the market interval already has a price, the existing price should be used.")  # ***************

    # Configure the test.
    test_mkt = Market()
    test_ti = TimeInterval(datetime.now(), timedelta(hours=1), test_mkt, datetime.now(), datetime.now())
    pi = 3.14159
    test_mp = IntervalValue(test_mkt, test_ti, test_mkt, MeasurementType.MarginalPrice, pi)
    test_mkt.timeIntervals = [test_ti]
    test_mkt.marginalPrices = [test_mp]
    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]

    # Check preliminary conditions:
    assert len(test_mkt.timeIntervals) >= 1, "At least one active time interval must exist"
    assert test_mkt.timeIntervals[0] == test_ti, "The active time interval is not as configured"
    assert test_mkt.marginalPrices[0].timeInterval == test_ti, "The marginal price time interval is not as configured"

    try:
        test_mkt.check_marginal_prices(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warnings:
        print('  - ERRORS WERE ENCOUNTERED:', warnings)

    assert len(test_mkt.timeIntervals) == 1, "One active time interval should exist"
    assert test_mkt.timeIntervals[0] == test_ti, "The active time interval should remain unchanged"
    assert test_mkt.marginalPrices[0].timeInterval == test_ti, \
        "The marginal price time interval should not have unchanged"
    assert test_mkt.marginalPrices[0].value == pi, "The marginal price value should not have changed"

    # ******************************************************************************************************************
    print("**Case 2: If the same time interval exists from a prior market clearing, its price may be used.")  # ********

    # Configure the test.
    prior_mkt = Market()
    prior_mkt.marketSeriesName = "Test Market"

    new_mp = 1.234

    test_mkt = Market()
    test_mkt.marketSeriesName = "Test Market"

    test_mkt.intervalsToClear = 2
    test_mkt.priorMarketInSeries = prior_mkt  # Important pointer to the prior market in the series

    test_ti = TimeInterval(datetime.now(), timedelta(hours=1), test_mkt, datetime.now(), datetime.now())

    # NOTE: Test_mkt is assigned no marginal prices for this case. But a marginal price exists in the prior market for
    # the active time interval.
    test_mp = IntervalValue(prior_mkt, test_ti, prior_mkt, MeasurementType.MarginalPrice, new_mp)
    prior_mkt.marginalPrices = [test_mp]

    test_mkt.timeIntervals = [test_ti]

    test_mtn = TransactiveNode()

    test_mtn.markets = [prior_mkt, test_mkt]

    # Check preliminary conditions:
    assert len(test_mkt.timeIntervals) == 1, "One active time interval should be defined"
    assert test_mkt.timeIntervals[0] == test_ti, "The active time interval is not as configured"
    assert len(test_mkt.marginalPrices) == 0, "No marginal price should exist in the test_mkt"
    assert len(test_mtn.markets) == 2, "Two active markets should exist"

    try:
        test_mkt.check_marginal_prices(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warnings:
        print('  - ERRORS WERE ENCOUNTERED:', warnings)

    assert len(test_mkt.timeIntervals) == 1, "One active time interval should exist"
    assert test_mkt.timeIntervals[0] == test_ti, "The active time interval should remain unchanged"
    assert len(test_mkt.marginalPrices) == 1, "One marginal price should have been created in the test_mkt"
    assert test_mkt.marginalPrices[0].timeInterval == test_ti, \
        "The test time interval should have been assigned to the new marginal price"
    assert test_mkt.marginalPrices[0].value == new_mp, \
        "The marginal price should have been assigned from earlier market."
    assert len(test_mtn.markets) == 2, "Two active markets should exist"

    # ******************************************************************************************************************
    print("**Case 3: If this market corrects another prior market, its cleared price should be used.")  # **************

    # Configure the test.
    prior_mkt = Market()
    prior_mkt.marketSeriesName = "Not Test Market"  # The prior market has a different market name
    prior_mkt.marketClearingTime = datetime.now()
    new_mp = 1.234

    test_mkt = Market()
    test_mkt.marketSeriesName = "Test Market"  # This points to the market series that is to be corrected.
    test_mkt.marketClearingTime = prior_mkt.marketClearingTime + timedelta(hours=1)  # Must be after prior market.
    test_mkt.marketToBeRefined = prior_mkt.marketSeriesName  # Assuming here this is not a list.
    test_mkt.marketToBeRefined = prior_mkt  # Important pointer to market that is being refined

    test_ti = TimeInterval(datetime.now(), timedelta(hours=1), test_mkt, datetime.now(), datetime.now())

    # NOTE: Test_mkt is assigned no marginal prices for this case. But a marginal price exists in the prior market for
    # the active time interval.
    test_mp = IntervalValue(prior_mkt, test_ti, prior_mkt, MeasurementType.MarginalPrice, new_mp)
    prior_mkt.marginalPrices = [test_mp]

    test_mkt.timeIntervals = [test_ti]

    test_mtn = TransactiveNode()

    test_mtn.markets = [prior_mkt, test_mkt]

    # Check preliminary conditions:
    assert len(test_mkt.timeIntervals) == 1, "One active time interval should be defined"
    assert test_mkt.timeIntervals[0] == test_ti, "The active time interval is not as configured"
    assert len(test_mkt.marginalPrices) == 0, "No marginal price should exist in the test_mkt"
    assert len(test_mtn.markets) == 2, "Two active markets should exist"
    assert prior_mkt.marketSeriesName != test_mkt.marketSeriesName, \
        "Prior market and current market should not have the same marekt name"
    assert test_mkt.marketToBeRefined is prior_mkt, \
        "The current market must identify its prior market object that is being corrected"
    assert prior_mkt.marketClearingTime < test_mkt.marketClearingTime, \
        "The prior market must clear before the current one"
    assert test_mkt.priorMarketInSeries is None, "An attempt to use current market series must fail"
    assert test_mkt.marketToBeRefined == prior_mkt, "The test market must point to refined market"

    try:
        test_mkt.check_marginal_prices(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warnings:
        print('  - ERRORS WERE ENCOUNTERED:', warnings)

    assert len(test_mkt.timeIntervals) == 1, "One active time interval should exist"
    assert test_mkt.timeIntervals[0] == test_ti, "The active time interval should remain unchanged"
    assert len(test_mkt.marginalPrices) == 1, "One marginal price should have been created in the test_mkt"
    assert test_mkt.marginalPrices[0].timeInterval == test_ti, \
        "The test time interval should have been assigned to the new marginal price"
    assert test_mkt.marginalPrices[0].value == new_mp, "The marginal price should be reassigned from the prior market."
    assert len(test_mtn.markets) == 2, "Two active markets should still exist"

    # ******************************************************************************************************************
    print("**Case 4: If there exists a price forecast model for this market, this model should be used.")  # ***********

    # Configure the test.
    test_mkt = Market()
    test_mkt.marketSeriesName = "Test Market"
    test_mkt.marketClearingTime = datetime.now() + timedelta(hours=1)  # Must be after prior market.
    test_mkt.marketToBeRefined = None  # There should be no prior market to correct
    pi = 3.14159
    test_mkt.priceModel = [pi, 2 * pi] * 24

    test_ti = TimeInterval(datetime.now(), timedelta(hours=1), test_mkt, datetime.now(), datetime.now())

    test_mkt.timeIntervals = [test_ti]

    test_mtn = TransactiveNode()

    test_mtn.markets = [test_mkt]  # Only the one market should be active here

    # Check preliminary conditions:
    assert len(test_mkt.timeIntervals) == 1, "One active time interval should be defined"
    assert test_mkt.timeIntervals[0] == test_ti, "The active time interval is not as configured"
    assert len(test_mkt.marginalPrices) == 0, "No marginal price should exist in the test_mkt"
    assert len(test_mtn.markets) == 1, "A single active market should exist"
    # NOTE: This next requirement may be revised if price models get more sophisticated
    assert len(test_mkt.priceModel) == 24 * 2, "A price model must exist for hours in day"

    try:
        test_mkt.check_marginal_prices(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warnings:
        print('  - ERRORS WERE ENCOUNTERED:', warnings)

    assert len(test_mkt.timeIntervals) == 1, "One active time interval should exist"
    assert test_mkt.timeIntervals[0] == test_ti, "The active time interval should remain unchanged"
    assert len(test_mkt.marginalPrices) == 1, "One marginal price should have been created in the test_mkt"
    assert test_mkt.marginalPrices[0].timeInterval == test_ti, \
        "The test time interval should have been assigned to the new marginal price"
    assert test_mkt.marginalPrices[0].value == pi, \
        "The marginal price should be reassigned from the simple price model."
    assert len(test_mtn.markets) == 1, "Only the original active market should still exist"

    # ******************************************************************************************************************
    print("**Case 5: If all above methods fail, market periods should be assigned the market's default price.")  # *****

    # Configure the test.
    test_mkt = Market()
    test_mkt.marketSeriesName = "Test Market"
    test_mkt.marketClearingTime = datetime.now() + timedelta(hours=1)  # Must be after prior market.
    test_mkt.marketToBeRefined = None  # There should be no prior market to correct
    pi = 3.14159
    test_mkt.defaultPrice = pi
    test_mkt.priceModel = None  # The lack of price model will excite this final method.

    test_ti = TimeInterval(datetime.now(), timedelta(hours=1), test_mkt, datetime.now(), datetime.now())

    test_mkt.timeIntervals = [test_ti]

    test_mtn = TransactiveNode()

    test_mtn.markets = [test_mkt]  # Only the one market should be active here

    # Check preliminary conditions:
    assert len(test_mkt.timeIntervals) == 1, "One active time interval should be defined"
    assert test_mkt.timeIntervals[0] == test_ti, "The active time interval is not as configured"
    assert len(test_mkt.marginalPrices) == 0, "No marginal price should exist in the test_mkt"
    assert len(test_mtn.markets) == 1, "A single active market should exist"
    # NOTE: This next requirement may be revised if price models get more sophisticated
    assert test_mkt.priceModel is None, "There should exist no price model"

    try:
        test_mkt.check_marginal_prices(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as cause:
        print('  ERRORS OCCURRED', cause)

    assert len(test_mkt.timeIntervals) == 1, "One active time interval should exist"
    assert test_mkt.timeIntervals[0] == test_ti, "The active time interval should remain unchanged"
    assert len(test_mkt.marginalPrices) == 1, "One marginal price should have been created in the test_mkt"
    assert test_mkt.marginalPrices[0].timeInterval == test_ti, \
        "The test time interval should have been assigned to the new marginal price"
    assert test_mkt.marginalPrices[0].value == pi, \
        "The marginal price should be reassigned from the market default price value."
    assert len(test_mtn.markets) == 1, "Only the original active market should still exist"

# **********************************************************************************************************************
    print("**Case 6: Finally, if no method has worked, set the marginal price to Null.")  # *****

    # Configure the test.
    test_mkt = Market()
    test_mkt.marketSeriesName = "Test Market"
    test_mkt.marketClearingTime = datetime.now() + timedelta(hours=1)  # Must be after prior market.
    test_mkt.marketToBeRefined = None  # There should be no prior market to correct
    test_mkt.defaultPrice = None
    test_mkt.priceModel = None  # The lack of price model will excite this final method.

    test_ti = TimeInterval(datetime.now(), timedelta(hours=1), test_mkt, datetime.now(), datetime.now())

    test_mkt.timeIntervals = [test_ti]

    test_mtn = TransactiveNode()

    test_mtn.markets = [test_mkt]  # Only the one market should be active here

    # Check preliminary conditions:
    assert len(test_mkt.timeIntervals) == 1, "One active time interval should be defined"
    assert test_mkt.timeIntervals[0] == test_ti, "The active time interval is not as configured"
    assert len(test_mkt.marginalPrices) == 0, "No marginal price should exist in the test_mkt"
    assert len(test_mtn.markets) == 1, "A single active market should exist"
    # NOTE: This next requirement may be revised if price models get more sophisticated
    assert test_mkt.priceModel is None, "There should exist no price model"
    assert test_mkt.defaultPrice is None, "There should be no market default price for this test"

    try:
        test_mkt.check_marginal_prices(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warnings:
        print('  - ERRORS WERE ENCOUNTERED:', warnings)

    assert len(test_mkt.timeIntervals) == 1, "One active time interval should exist"
    assert test_mkt.timeIntervals[0] == test_ti, "The active time interval should remain unchanged"
    assert len(test_mkt.marginalPrices) == 1, "One marginal price should have been created in the test_mkt"
    assert test_mkt.marginalPrices[0].timeInterval == test_ti, \
        "The test time interval should have been assigned to the new marginal price"
    assert test_mkt.marginalPrices[0].value is None, \
        "The marginal price should have been assigned as None."
    assert len(test_mtn.markets) == 1, "Only the original active market should still exist"

    print('Method test_check_marginal_prices() ran to completion.\n')


def test_events():
    """
    Tests transitions within the generalized market state machine:
    STATE               STATE TRANSITION                            STATE PERSISTENCE
    1. Active           market gets instantiated                    while in an activation lead period
    2. Negotiation      negotiation period starts                   while in a negotiation lead period
    3. MarketLead       negotiation period stops                    while in a market lead period
    4. DeliveryLead     market clears                               while in a delivery lead period
    5. Delivery         delivery starts                             while in any market intervals' delivery period
    6. Reconcile        delivery stops                              until reconciled
    7. Expire           market gets reconciled                      forever thereafter
   """

    print("Running test_events().")

    print("**CASE 1a: New market should not be instantiated by an existing one prior to its calculated activation time")
    """
    Market timing of a new market is based on the NEXT market clearing time of the existing market.
    market_clearing_time[1] = next_market_clearing_time[0] 
    activation_time[1] = next_market_clearing_time[0] - market_lead_time - negotiation_lead_time - activation_lead_time
    Therefore, Case 1a tests that no new market is created while 

                                            now < activation_time[1].

    A side condition will be that the existing market should be and remain in its delivery period.
    delivery_start_time[0] = market_clearing_time[0] + delivery_lead_time
    delivery_end_time[0] = market_clearing_time[0] + delivery_lead_time + intervals_to_clear * interval_duration

                             delivery_start_time[0] < now < delivery_end_time[0]
    """

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Delivery

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now - 0.5 * test_mkt.intervalsToClear * test_mkt.intervalDuration

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval
    test_mkt.isNewestMarket = True

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]

    # Check required conditions of Case 1a:
    # On the state of the EXISTING market:
    delivery_start_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime
    delivery_end_time = delivery_start_time + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_start_time < now < delivery_end_time, "The existing market must be in delivery"

    # On the state of the new market:
    activation_time = test_mkt.nextMarketClearingTime - test_mkt.marketLeadTime - test_mkt.negotiationLeadTime \
                      - test_mkt.activationLeadTime
    assert now < activation_time, "The current time must precede the new activation time"

    assert test_mkt.isNewestMarket is True, "The existing market should be the newest for fair test"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert 0 < len(test_mtn.markets) < 2, "There should remain exactly one active market"
    assert test_mtn.markets[0] == test_mkt, "The listed market should not have changed"

    print("**Case 1b: Existing market should remain in this state if it is within the active state period.")  # ********

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Active

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now + 0.5 * test_mkt.activationLeadTime + test_mkt.negotiationLeadTime \
                                  + test_mkt.marketLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval
    test_mkt.isNewestMarket = True

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    # Check required conditions before Case 1b:
    activation_time = test_mkt.marketClearingTime - test_mkt.marketLeadTime - test_mkt.negotiationLeadTime \
                      - test_mkt.activationLeadTime
    negotiation_start_time = activation_time + test_mkt.activationLeadTime
    assert activation_time < now < negotiation_start_time, "The existing market must be in its active state period"

    assert test_mkt.isNewestMarket is True, "Existing market must be newest to trigger instantiation of another market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Active, "The existing market should have remaining in its active state"

    print("**Case 1c: A new market is needed and must be instantiated with its market intervals.")  # ******************

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Active

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now + 0.5 * test_mkt.activationLeadTime + test_mkt.negotiationLeadTime \
                                  + test_mkt.marketLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = now + test_mkt.marketLeadTime + test_mkt.negotiationLeadTime \
                                      + 0.5 * test_mkt.activationLeadTime
    test_mkt.isNewestMarket = True

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    # Check required conditions before Case 1b:
    # While not essential to the test, let's make sure that the existing market does not expire during the test.
    delivery_end_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime \
                        + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert now < delivery_end_time, "The existing market must be in delivery"

    next_activation_time = test_mkt.nextMarketClearingTime - test_mkt.marketLeadTime - test_mkt.negotiationLeadTime \
                           - test_mkt.activationLeadTime
    assert next_activation_time < now, "It mus be later than the needed market activation time to trigger " \
                                       "instantiation of the new market"
    assert test_mkt.isNewestMarket is True, "The existing market must be the newest to trigger new ones"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUTNERED:', warning)

    assert len(test_mtn.markets) == 2, "There should be two active markets"
    assert test_mtn.markets[0] == test_mkt, "The existing market should be in position 0"
    assert test_mtn.markets[1].marketSeriesName == test_mkt.marketSeriesName, \
        "The new market name should be the same as that of the existing market"
    assert test_mtn.markets[1].marketState == MarketState.Active, \
        "The new market should have been created and remain in its active state"
    assert len(test_mtn.markets[1].timeIntervals) == test_mkt.intervalsToClear, \
        "The new market did not create the expected number of market intervals"
    assert test_mkt.isNewestMarket is False, "The existing market should have abdicated the newest market flag"
    assert test_mtn.markets[1].isNewestMarket is True, "The new market should have captured the newest market flag"

    print("**Case 2a: The existing market should transition from the Active to Negotiation state.")  # *****************

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Active

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now + 0.5 * test_mkt.negotiationLeadTime + test_mkt.marketLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    negotiation_start_time = test_mkt.marketClearingTime - test_mkt.marketLeadTime - test_mkt.negotiationLeadTime \
                             - test_mkt.activationLeadTime + test_mkt.activationLeadTime
    negotiation_end_time = negotiation_start_time + test_mkt.negotiationLeadTime
    assert negotiation_start_time < now < negotiation_end_time, \
        "The existing market must be in its negotiation state period"
    assert test_mkt.marketState == MarketState.Active, "The market must be in its Active state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Negotiation, \
        "The existing market should have transitioned to its negotiation state"

    print("**Case 2b: The existing market should remain in its Negotiation state.")  # *********************************

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Negotiation

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now + 0.5 * test_mkt.negotiationLeadTime + test_mkt.marketLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    negotiation_start_time = test_mkt.marketClearingTime - test_mkt.marketLeadTime - test_mkt.negotiationLeadTime \
                             - test_mkt.activationLeadTime + test_mkt.activationLeadTime
    negotiation_end_time = negotiation_start_time + test_mkt.negotiationLeadTime
    assert negotiation_start_time < now < negotiation_end_time, \
        "The existing market must be in its negotiation state period"
    assert test_mkt.marketState == MarketState.Negotiation, "The market must be in its Negotiation state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Negotiation, \
        "The existing market should have remained in its negotiation state"

    print("**Case 3a: The existing market should transition from the Negotiation to its Market Lead state.")  # ********

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Negotiation

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now + 0.5 * test_mkt.marketLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    negotiation_end_time = test_mkt.marketClearingTime - test_mkt.marketLeadTime
    market_clearing_lead_start_time = negotiation_end_time + test_mkt.marketLeadTime
    assert negotiation_end_time < now < market_clearing_lead_start_time, \
        "The existing market must be in its Market Lead state period"
    assert test_mkt.marketState == MarketState.Negotiation, "The market must be in its Negotiation state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.MarketLead, \
        "The existing market should have transitioned to its Market Lead state"

    print("**Case 3b: The existing market should remain in its Market Lead state.")  # *********************************

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.MarketLead

    test_mkt.Series = "Test Market"

    test_mkt.marketClearingTime = now + 0.5 * test_mkt.marketLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    negotiation_end_time = test_mkt.marketClearingTime - test_mkt.marketLeadTime
    market_clearing_lead_start_time = test_mkt.marketClearingTime
    assert negotiation_end_time < now < market_clearing_lead_start_time, \
        "The existing market must be in its Market Lead state period"
    assert test_mkt.marketState == MarketState.MarketLead, "The market must be in its Market Lead state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.MarketLead, \
        "The existing market should have remained in its Market Lead state"

    print("**Case 4a: The existing market should transfer from Market Lead to its Delivery Lead state.")  # ************

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.MarketLead

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now - 0.5 * test_mkt.deliveryLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_start_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime
    assert test_mkt.marketClearingTime < now < delivery_start_time, \
        "The existing market must be in its Delivery Lead state period"
    assert test_mkt.marketState == MarketState.MarketLead, "The market must be in its Market Lead state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.DeliveryLead, \
        "The existing market should have transitioned to its Delivery Lead state"

    print("**Case 4b: The existing market should remain in its Delivery Lead state.")  # *******************************

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.DeliveryLead

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now - 0.5 * test_mkt.deliveryLeadTime

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_start_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime
    assert test_mkt.marketClearingTime < now < delivery_start_time, \
        "The existing market must be in its Delivery Lead state period"
    assert test_mkt.marketState == MarketState.DeliveryLead, "The market must be in its Delivery Lead state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.DeliveryLead, \
        "The existing market should have remained in its Delivery Lead state"

    print("**Case 5a: The existing market should transition into its Delivery state.")  # ******************************

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.DeliveryLead

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now - test_mkt.deliveryLeadTime - 0.5 * test_mkt.intervalDuration

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_start_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime
    delivery_end_time = delivery_start_time + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_start_time < now < delivery_end_time, \
        "The existing market must be in its Delivery state period"
    assert test_mkt.marketState == MarketState.DeliveryLead, "The market must be in its Delivery Lead state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Delivery, \
        "The existing market should have remained in its Delivery Lead state"

    print("**Case 5b: The existing market should remain in its Delivery state.")  # ************************************

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Delivery

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now - test_mkt.deliveryLeadTime - 0.5 * test_mkt.intervalDuration

    test_mkt.reconciled = False
    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + test_mkt.marketClearingInterval

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_start_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime
    delivery_end_time = delivery_start_time + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_start_time < now < delivery_end_time, \
        "The existing market must be in its Delivery state period"
    assert test_mkt.marketState == MarketState.Delivery, "The market must be in its Delivery state"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Delivery, \
        "The existing market should have remained in its Delivery Lead state"

    print("**Case 6a: The existing market should transition into its Reconcile state.")  # *****************************

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Delivery

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now - test_mkt.deliveryLeadTime \
                                  - test_mkt.intervalsToClear * test_mkt.intervalDuration - timedelta(minutes=1)

    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + 2 * test_mkt.marketClearingInterval

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.reconciled = False
    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_end_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime \
                        + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_end_time < now, "The existing market must be in its Reconcile state period"
    assert test_mkt.marketState == MarketState.Delivery, "The market must be in its Delivery state"
    assert test_mkt.reconciled is False, "The market must not be reconciled"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Reconcile, \
        "The existing market should have transitioned to its Reconcile state"

    print("**Case 6b: The existing market should remain in its Reconcile state.")  # ***********************************

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Reconcile

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now - test_mkt.deliveryLeadTime \
                                  - test_mkt.intervalsToClear * test_mkt.intervalDuration - timedelta(minutes=1)

    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + 2 * test_mkt.marketClearingInterval

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.reconciled = False
    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_end_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime \
                        + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_end_time < now, "The existing market must be in its Reconcile state period"
    assert test_mkt.marketState == MarketState.Reconcile, "The market must be in its Reconcile state"
    assert test_mkt.reconciled is False, "The market must not be reconciled"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 1, "There should remain only the one active market"
    assert test_mtn.markets[0].marketClearingTime == test_mkt.marketClearingTime, \
        "The lone market's clearing time was not as expected"
    assert test_mtn.markets[0] == test_mkt, "The active market should not have changed as an object"
    assert test_mkt.marketState == MarketState.Reconcile, \
        "The existing market should have transitioned to its Reconcile state"

    print("**Case 7a: When reconciled, the existing market should transition into its Expired state and terminate.")  #

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Reconcile

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now - test_mkt.deliveryLeadTime \
                                  - test_mkt.intervalsToClear * test_mkt.intervalDuration - timedelta(minutes=1)

    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + 2 * test_mkt.marketClearingInterval

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.reconciled = True  # This is the condition that allows the market to expire.
    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_end_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime \
                        + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_end_time < now, "The existing market must be in its Reconcile state period"
    assert test_mkt.marketState == MarketState.Reconcile, "The market must be in its Reconcile state"
    assert test_mkt.reconciled is True, "The market must be reconciled to allow the transition to Expired"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 0, "The market should have been removed from the agent's list"
    assert test_mkt.marketState == MarketState.Expired, \
        "The existing market should have transitioned to its Expired state"

    print("**Case 7b: When Expired, the existing market should terminate.")  # *****************************************

    now = datetime.now()

    test_mkt = Market()

    test_mkt.activationLeadTime = timedelta(minutes=10)
    test_mkt.negotiationLeadTime = timedelta(minutes=10)
    test_mkt.marketLeadTime = timedelta(hours=10)
    test_mkt.deliveryLeadTime = timedelta(minutes=10)
    test_mkt.intervalsToClear = 24
    test_mkt.intervalDuration = timedelta(hours=1)

    test_mkt.marketState = MarketState.Expired

    test_mkt.marketSeriesName = "Test Market"

    test_mkt.marketClearingTime = now - test_mkt.deliveryLeadTime \
                                  - test_mkt.intervalsToClear * test_mkt.intervalDuration - timedelta(minutes=1)

    test_mkt.marketClearingInterval = timedelta(days=1)
    test_mkt.nextMarketClearingTime = test_mkt.marketClearingTime + 2 * test_mkt.marketClearingInterval

    test_mtn = TransactiveNode()
    test_mtn.markets = [test_mkt]  # %%%%%%%%%%%%%

    test_mkt.reconciled = True  # This is the condition that allows the market to expire.
    test_mkt.converged = True  # Setting convergence true avoids testing all the negotiation unit tests.

    # Check required conditions before Case 1b:
    delivery_end_time = test_mkt.marketClearingTime + test_mkt.deliveryLeadTime \
                        + test_mkt.intervalsToClear * test_mkt.intervalDuration
    assert delivery_end_time < now, "The existing market must be in its Reconcile state period"
    assert test_mkt.marketState == MarketState.Expired, "The market must be in its Expired state"
    assert test_mkt.reconciled is True, "The market must be reconciled"
    assert test_mkt.nextMarketClearingTime > now, \
        "The next market clearing time should not trigger creation of a new market"

    try:
        test_mkt.events(test_mtn)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mtn.markets) == 0, "The market should have been inactivated, removed from the agent's list"
    assert test_mkt.marketState == MarketState.Expired, "The market remains expired until deleted by garbage collection"

    print('test_events() ran to completion.\n')


def test_model_prices():
    print('Running test_model_prices()')
    print('This test is not complete')
    print('**Case 1:')
    print('test_model_prices() ran to completion\n')


def test_schedule():
    print('Running test_schedule()')
    print('WARNING: This test may be affected by method LocalAsset.schedule()')
    print('WARNING: This test may be affected by Neighbor.schedule()')
    print('NOTE: Only the most basic functionality is being tested at this time.')

    # Establish a TransactiveNode object
    mtn = TransactiveNode()

    # Establish a test market
    test_mkt = Market()

    # Create and store one TimeInterval
    dt = datetime(2018, 1, 1, 12, 0, 0)  # Noon Jan 1, 2018
    at = dt
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt
    st = dt
    ti = TimeInterval(at, dur, mkt, mct, st)

    test_mkt.timeIntervals = [ti]

    # Create and store a marginal price in the active interval.
    test_mkt.marginalPrices = [
        IntervalValue(test_mkt, ti, test_mkt, MeasurementType.MarginalPrice, 0.01)]

    print('- configuring a test Neighbor and its Neighbor')

    # Create the corresponding model that is a Neighbor.
    test_mdl1 = Neighbor()
    test_mdl1.defaultPower = 10
    test_mdl1.maximumPower = 100

    mtn.neighbors = [test_mdl1]

    print('- configuring a test LocalAsset and its LocalAsset')

    # Create the corresponding model that is a LocalAsset.
    test_mdl2 = LocalAsset()
    test_mdl2.defaultPower = 10
    test_mdl2.maximumPower = 100

    mtn.localAssets = [test_mdl2]

    try:
        test_mkt.schedule(mtn)
        print('  - The case ran witout errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_mdl1.scheduledPowers) == 1, "The wrong numbers of scheduled powers were stored for the Neighbor"
    assert len(test_mdl2.scheduledPowers) == 1, "The wrong numbers of scheduled powers were stored for the LocalAsset"
    print("Method test_schedule() ran to completion\n")


def test_see_marginal_prices():
    # Tests a method that plots marginal prices.
    print('Running test_see_marginal_prices()')

    positive_infinity = float('Inf')
    now = datetime.now()

    print('**Case 1: Normal plot of several marginal prices.')  # ***************
    test_market = Market()
    test_market.intervalDuration = timedelta(hours=1)

    marginal_prices = [0, 1, 0, -0.2]

    test_interval1 = TimeInterval(now, timedelta(hours=1), test_market, now, now)
    test_interval2 = TimeInterval(now, timedelta(hours=1), test_market, now, now + timedelta(hours=1))
    test_interval3 = TimeInterval(now, timedelta(hours=1), test_market, now, now + timedelta(hours=2))
    test_interval4 = TimeInterval(now, timedelta(hours=1), test_market, now, now + timedelta(hours=3))
    test_market.timeIntervals = [test_interval1, test_interval2, test_interval3, test_interval4]
    test_market.marginalPrices = [IntervalValue(test_market, test_interval1, test_market, None, marginal_prices[0]),
                                  IntervalValue(test_market, test_interval2, test_market, None, marginal_prices[1]),
                                  IntervalValue(test_market, test_interval3, test_market, None, marginal_prices[2]),
                                  IntervalValue(test_market, test_interval4, test_market, None, marginal_prices[3])]

    try:
        test_market.see_marginal_prices(show=False)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    print('test_see_marginal_prices() ran to completion.\n')


def test_see_net_curve():
    """
    Visualizes the market's net supply/demand curve (net power as function of marginal price) for an active time
    interval. This is hard to test because the user must confirm that a useful plot is created. Let's just say that this
    test helps exercise the visualization method.
    :return:
    """
    print('Running test_see_net_curve()')

    positive_infinity = float('Inf')
    now = datetime.now()

    print('**Case 1: Normal plot of net supply/demand for first active time interval, two vertices.')  # ***************
    test_market = Market()
    test_vertex1 = Vertex(0.02, 0, -10)
    test_vertex2 = Vertex(0.03, 0, 10)
    test_interval = TimeInterval(now, timedelta(hours=1), test_market, now, now)
    test_market.timeIntervals = [test_interval]
    test_market.activeVertices = [IntervalValue(test_market, test_interval, test_market, None, test_vertex1),
                                  IntervalValue(test_market, test_interval, test_market, None, test_vertex2)]

    try:
        test_market.see_net_curve(show=False)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    print('test_see_net_curve() ran to completion.\n')


def test_spawn_markets():
    print('Running test_spawn_markets()')
    print('**Case 1: Normal case when the next market is spawned in the same market series.')
    print('  NOTE: The test method will often be replaced to spawn additional, or no, new markets.')
    test_node = TransactiveNode()
    test_market = Market()
    test_market.marketSeriesName = 'Test Market Series'
    test_market.marketClearingTime = datetime(year=2020, month=1, day=1, hour=0, second=0, microsecond=0)
    test_market.marketClearingInterval = timedelta(hours=1)
    new_clearing_time = test_market.marketClearingTime + test_market.marketClearingInterval
    test_market.intervalDuration = timedelta(minutes=15)
    test_market.intervalsToClear = 4
    test_market.isNewestMarket = True
    test_node.markets = [test_market]

    assert test_market.isNewestMarket is True, ''
    assert len(test_node.markets) == 1, ''

    try:
        test_market.spawn_markets(test_node, new_clearing_time)
        print('  - The case ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    assert len(test_node.markets) == 2, 'A second active market should have been added.'
    assert test_node.markets[1].name == (test_market.marketSeriesName.replace(' ', '_')
                                         + '_2020-01-01 01:00:00'), 'Check the new market name.'
    assert test_node.markets[1].isNewestMarket is True, 'The new market should be flagged as newest.'
    assert test_node.markets[1].marketClearingTime == new_clearing_time, 'The new clearing time is wrong.'
    assert len(test_node.markets[1].timeIntervals) == test_market.intervalsToClear, \
        'There should have been four new market intervals.'

    print('test_spawn_markets() ran to completion\n')


def test_sum_vertices():
    print('Running Market.test_sum_vertices().')

    # Create a test TransactiveNode object.
    test_node = TransactiveNode()

    # Create a test Market object.
    test_market = Market()

    # List the test market with the test_node.
    test_node.markets = test_market

    # Create and store a time interval to work with.
    dt = datetime.now()
    at = dt
    dur = timedelta(hours=1)
    mkt = test_market
    mct = dt
    st = dt
    time_interval = TimeInterval(at, dur, mkt, mct, st)
    test_market.timeIntervals = [time_interval]

    # Create test LocalAsset and LocalAsset objects
    test_asset_model = LocalAsset()

    # Add the test_asset to the test node list.
    test_node.localAssets = [test_asset_model]

    # Create and store an active Vertex or two for the test asset
    test_vertex = [
        Vertex(0.2, 0, -110),
        Vertex(0.2, 0, -90)
    ]
    interval_values = [
        IntervalValue(test_node, time_interval, test_market, MeasurementType.ActiveVertex, test_vertex[0]),
        IntervalValue(test_node, time_interval, test_market, MeasurementType.ActiveVertex, test_vertex[1])
    ]
    test_asset_model.activeVertices = [interval_values[0], interval_values[1]]  # interval_value(1:2)

    # Create test Neighbor and Neighbor objects.
    test_neighbor_model = Neighbor()

    # Add the test neighbor to the test node list.
    test_node.neighbors = [test_neighbor_model]

    # Create and store an active Vertex or two for the test neighbor
    test_vertex.append(Vertex(0.1, 0, 0))
    test_vertex.append(Vertex(0.3, 0, 200))
    interval_values.append(IntervalValue(test_node, time_interval, test_market,
                                         MeasurementType.ActiveVertex, test_vertex[2]))
    interval_values.append(IntervalValue(test_node, time_interval, test_market,
                                         MeasurementType.ActiveVertex, test_vertex[3]))
    test_neighbor_model.activeVertices = [interval_values[2], interval_values[3]]

    print('**Case 1: Basic case with interleaved vertices')  # *********************************************************

    # Run the test.
    try:
        vertices = test_market.sum_vertices(test_node, time_interval)
        print('  - The method ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
        vertices = []

    if len(vertices) != 4:
        print('  - an unexpected number of vertices was returned')
    else:
        print('  - the expected number of vertices was returned')

    powers = [x.power for x in vertices]

    if len([x for x in powers if round(x, 4) not in [-110.0000, -10.0000, 10.0000, 110.0000]]) > 0:
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex powers were as expected')

    marginal_prices = [round(x.marginalPrice, 4) for x in vertices]

    if len([x for x in marginal_prices if round(x, 4) not in [0.1000, 0.2000, 0.3000]]) > 0:
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex marginal prices were as expected')

    # CASE 2: NEIGHBOR MODEL TO BE EXCLUDED
    # This case is needed when a demand or supply curve must be created for a
    # transactive Neighbor object. The active vertices of the target Neighbor
    # must be excluded, leaving a residual supply or demand curve against which
    # the Neighbor may plan.
    print('**Case 2: Exclude test Neighbor model')  # ******************************************************************

    # Run the test.
    try:
        # [vertices] = test_market.sum_vertices(test_node, time_interval, test_neighbor_model)
        vertices = test_market.sum_vertices(test_node, time_interval, test_neighbor_model)
        print('  - The method ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)

    if len(vertices) != 2:
        print('  - an unexpected number of vertices was returned')
    else:
        print('  - the expected number of vertices was returned')

    powers = [round(x.power, 4) for x in vertices]

    if len([x for x in powers if x not in [-110.0000, -90.0000]]) > 0:
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex powers were as expected')

    marginal_prices = [x.marginalPrice for x in vertices]

    if len([x for x in marginal_prices if round(x, 4) not in [0.2000]]) > 0:
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex marginal prices were as expected')

    # CASE 3: CONSTANT SHOULD NOT CREATE NEW NET VERTEX
    print('**Case 3: Include a constant vertex. No net vertex should be added')  # *************************************

    # Change the test asset to NOT have any flexibility. A constant should
    # not introduce a net vertex at a constant's marginal price. Marginal
    # price is NOT meaningful for an inelastic device.
    test_asset_model.activeVertices = [interval_values[0]]

    # Run the test.
    try:
        vertices = test_market.sum_vertices(test_node, time_interval)
        print('  - The method ran without errors')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
        vertices = []

    # %[180907DJH: THIS TEST IS CORRECTED. THE NEIGHBOR HAS TWO VERTICES. ADDING AN ASSET WITH ONE VERTEX (NO
    # FLEXIBILITY) SHOULD NOT CHANGE THE NUMBER OF ACTIVE VERTICES, SO THE CORRECTED TEST CONFIRMS TWO VERTICES. THE
    # CODE HAS BEEN CORRECTED ACCORDINGLY.]
    if len(vertices) != 2:
        print('  - an unexpected number of vertices was returned')
    else:
        print('  - the expected number of vertices was returned')

    powers = [x.power for x in vertices]

    if len([x for x in powers if round(x, 4) not in [-110.0000, 90]]) > 0:
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex powers were as expected')

    marginal_prices = [x.marginalPrice for x in vertices]

    if len([x for x in marginal_prices if round(x, 4) not in [0.1000, 0.3000, float("inf")]]) > 0:
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex marginal prices were as expected')

    # CASE 4: More than two vertices at any marginal price
    print('**Case 4: More than two vertices at same marginal price')  # ************************************************

    # Move the two active vertices of the test asset to be at the same
    # marginal price as one of the neighbor active vertices.
    test_vertex = [
        Vertex(0.1, 0, -110),
        Vertex(0.1, 0, -90)
    ]
    interval_values = [
        IntervalValue(test_node, time_interval, test_market, MeasurementType.ActiveVertex, test_vertex[0]),
        IntervalValue(test_node, time_interval, test_market, MeasurementType.ActiveVertex, test_vertex[1])
    ]
    test_asset_model.activeVertices = [interval_values[0], interval_values[1]]  # interval_value(1:2)

    # Run the test.
    try:
        vertices = test_market.sum_vertices(test_node, time_interval)
        print('  - The method ran without errors.')
    except RuntimeWarning as warning:
        print('  - ERRORS WERE ENCOUNTERED:', warning)
        vertices = []

    if len(vertices) != 3:
        print('  - an unexpected number of vertices was returned')
    else:
        print('  - the expected number of vertices was returned')

    powers = [x.power for x in vertices]

    if len([x for x in powers if round(x, 4) not in [-110.0000, -90.0000, 110.0000]]) > 0:
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex powers were as expected')

    marginal_prices = [x.marginalPrice for x in vertices]

    if len([x for x in marginal_prices if round(x, 4) not in [0.1000, 0.3000]]) > 0:
        print('  - the vertex powers were not as expected')
    else:
        print('  - the vertex marginal prices were as expected')

    # Success
    print('test_sum_vertices() ran to completion.\n')


def test_update_costs():
    print('Running test_update_costs()')
    print('This test is not complete')
    print('**Case 1:')
    print('test_update_costs() ran to completion\n')


def test_update_supply_demand():
    print('Running test_update_supply_demand()')
    print('This test is not complete')

    # Success
    print('test_update_supply_demand() ran to completion.\n')


def test_view_marginal_prices():
    print('Running Market.test_view_marginal_prices()')
    pf = 'pass'

    # Establish a test market
    test_mkt = Market

    # Create and store three TimeIntervals
    dt = datetime
    at = dt
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt

    ti = []  # TimeInterval.empty

    st = dt
    ti[0] = TimeInterval(at, dur, mkt, mct, st)

    st = st + dur
    ti[1] = TimeInterval(at, dur, mkt, mct, st)

    st = st + dur
    ti[2] = TimeInterval(at, dur, mkt, mct, st)

    test_mkt.timeIntervals = ti

    # Test using a Market object
    print('- using a Market object')

    iv = []  # IntervalValue.empty
    # Create and store three marginal price values
    iv[0] = IntervalValue(test_mkt, ti[2], test_mkt, MeasurementType.MarginalPrice, 3)
    iv[1] = IntervalValue(test_mkt, ti[0], test_mkt, MeasurementType.MarginalPrice, 1)
    iv[2] = IntervalValue(test_mkt, ti[1], test_mkt, MeasurementType.MarginalPrice, 2)
    test_mkt.marginalPrices = iv

    try:
        test_mkt.view_marginal_prices()
        print('  - function ran without errors')
    except:
        raise ('  - function encountered errors and stopped')

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


def test_view_net_curve():
    print('Running Market.test_view_net_curve()')
    pf = 'pass'

    # Establish a test market
    test_mkt = Market()

    # Create and store one TimeInterval
    dt = datetime(2018, 1, 1, 12, 0, 0)
    at = dt
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt
    st = dt
    ti = [TimeInterval(at, dur, mkt, mct, st)]

    test_mkt.timeIntervals = ti

    # Test using a Market object
    print('- using a Market object')

    # Create and store three active vertices
    v = [Vertex(0.01, 0, -1), Vertex(0.02, 0, 1), Vertex(0.03, 0, 1)]
    iv = [
        IntervalValue(test_mkt, ti[0], test_mkt, MeasurementType.ActiveVertex, v[2]),
        IntervalValue(test_mkt, ti[0], test_mkt, MeasurementType.ActiveVertex, v[0]),
        IntervalValue(test_mkt, ti[0], test_mkt, MeasurementType.ActiveVertex, v[1])
    ]
    test_mkt.activeVertices = [iv]

    test_mkt.view_net_curve(0)
    print('  - function ran without errors')

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


if __name__ == '__main__':
    print('Running tests in testmarket.py\n')
    test_assign_system_vertices()  # Done. Only one set of neighbor and asset vertices are assigned in one case.
    test_balance()  #
    test_calculate_blended_prices()  #
    test_check_intervals()  # Done. Simplest case, only.
    test_check_marginal_prices()  # Done.
    test_events()  # Done.
    test_model_prices()  #
    test_schedule()  # Done. Only basic functionality.
    test_spawn_markets()  #
    test_sum_vertices()  # Done.
    test_update_costs()  #
    test_update_supply_demand()  #
    test_see_net_curve()  # Done. Tests only one simple case. More testing is needed.
    test_see_marginal_prices()  # Done. Tests only one simple case.
    # These next two methods have not been established in Python or cannot be tested due to reliance on Volttron.
    # test_view_net_vertices()  # 200207DJH: Hung created a plot that is dependent upon the Volttron environment.
    # test_view_marginal_prices()
    print("Tests in testmarket.py ran to completion.\n")
