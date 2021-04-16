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


from auction import Auction
from local_asset_model import LocalAsset
from TransactiveNode import TransactiveNode
from time_interval import TimeInterval
from datetime import datetime, timedelta
from market_state import MarketState
from neighbor_model import Neighbor
from direction import Direction
from vertex import Vertex
from interval_value import IntervalValue
from transactive_record import TransactiveRecord


def test_while_in_negotiation():
    # 200611DJH: This Auction method was improved recently to allow for complex assets that might take long to schedule
    #            themselves. Consequently, scheduling is now initiated in method
    #            transition_from_active_to_negotiation(), and method while_in_negotiation() simply makes sure that each
    #            asset has finished scheduling. The LocalAsset method schedule() was necessarily made to set flag
    #            sheduleCompleted when it is done doing so.
    print('  Running test_while_in_negotiation().')
    print('    CASE: Normal function. Asset should schedule, and market becomes converged')

    test_asset = LocalAsset()
    default_power = 4.321
    test_asset.defaultPower = default_power

    test_market = Auction()
    test_market.converged = False
    test_market.marketState = MarketState.Negotiation

    dt = datetime.now()
    test_interval = TimeInterval(dt,
                                 timedelta(hours=1),
                                 test_market,
                                 dt,
                                 dt)

    test_market.timeIntervals = [test_interval]

    test_agent = TransactiveNode()
    test_agent.markets = [test_market]
    test_agent.localAssets = [test_asset]

    assert test_market.converged is False, 'The test market should start out not converged'
    assert test_market.marketState == MarketState.Negotiation

    try:
        test_market.transition_from_active_to_negotiation(test_agent)
        test_market.while_in_negotiation(test_agent)
        print('    - The method ran without errors')
    except RuntimeWarning:
        print('    - ERRORS ENCOUNTERED')

    assert test_market.converged is True, 'The market should be converged'
    assert test_market.marketState == MarketState.Negotiation, \
            'The market should not have changed from the negotiation state'
    assert len(test_asset.scheduledPowers) == 1, 'Precisely one scheduled power should have been assigned'

    print('  test_while_in_negotiation() ran to completion.\n')
    pass


def test_while_in_market_lead():
    print('  Running test_while_in_market_lead().')
    print('    CASE 1: One neighbor. Its direction is not assigned.')

    test_neighbor = Neighbor()
    test_neighbor.transactive = False
    test_neighbor.upOrDown = Direction.unknown
    test_neighbor.name = 'Test_Neighbor'

    test_market = Auction()
    test_market.marketState = MarketState.MarketLead

    dt = datetime.now()
    test_interval = TimeInterval(dt,
                                 timedelta(hours=1),
                                 test_market,
                                 dt,
                                 dt)

    test_market.timeIntervals = [test_interval]

    test_agent = TransactiveNode()
    test_agent.markets = [test_market]
    test_agent.neighbors = [test_neighbor]

    assert test_market.marketState == MarketState.MarketLead

    try:
        test_market.while_in_market_lead(test_agent)
        print('    - The method ran without errors')
    except RuntimeWarning:
        print('    - ERRORS ENCOUNTERED')

    assert test_market.marketState == MarketState.MarketLead, \
                                                    'The market should not have changed from the market lead state'
    assert test_neighbor.upOrDown == Direction.downstream, \
                                                    'The undefined direction should have been assigned downstream'
    assert len(test_neighbor.scheduledPowers) == 0, \
                                              'One scheduled power should have been scheduled by the test neighbor'

    print('  CASE 2: An upstream neighbor is added.')

    upstream_neighbor = Neighbor()
    upstream_neighbor.upOrDown = Direction.upstream

    test_agent.neighbors.append(upstream_neighbor)

    assert len(test_agent.neighbors) == 2, 'There should be two neighbors'

    try:
        test_market.while_in_market_lead(test_agent)
        print('    - The method ran without errors')
    except RuntimeWarning:
        print('    - ERRORS ENCOUNTERED')

    print('  test_while_in_market_lead() ran to completion.\n')


def test_while_in_delivery_lead():
    # 200702DJH: Drafting unit test. Shwetha found issues with this method: (1) The complex building power-scheduling
    #            process is being unnecessarily restarted. (2) The Auction is not being populated with cleared
    #            locational marginal prices.
    #            In an auction, local assets should be required to use their existing flexibility (i.e., active vertices
    #            that were already bid into the local and upstream auctions.
    print('  Running test_while_in_delivery_lead().')

    # CASE 1 ***********************************************************************************************************
    print('    CASE 1: Typical, simple case, but with the upstream neighbor\'s active vertices already updated.')  # ***
    print('  Note: This also tests method balance().')
    print('  200804DJH: This case is for an upstrean NON-transactive neighbor that gets its vertices '
          'from default vertices')
    pinf = float('inf')
    mtn = TransactiveNode()
    now = datetime.now()
    test_neighbor = Neighbor()
    test_neighbor.transactive = False
    test_neighbor.upOrDown = Direction.upstream
    test_neighbor.scheduledPowers = []
    mtn.neighbors = [test_neighbor]
    test_asset = LocalAsset()
    mtn.localAssets = [test_asset]
    test_auction = Auction()
    test_auction.marginalPrices = []
    mtn.markets = test_auction
    test_time_interval = TimeInterval(now, timedelta(hours=1), test_auction, now, now)
    test_auction.timeIntervals = [test_time_interval]
    test_vertex1 = Vertex(0.1, 0, 0)
    test_vertex2 = Vertex(0.2, 0, 100)
    test_vertex3 = Vertex(pinf, 0, -50)
    test_interval_value1 = IntervalValue(test_neighbor, test_time_interval, test_auction, 'active vertex',
                                         test_vertex1)
    test_interval_value2 = IntervalValue(test_neighbor, test_time_interval, test_auction, 'active vertex',
                                         test_vertex2)
    test_interval_value3 = IntervalValue(test_auction, test_time_interval, test_auction, 'active vertex',
                                         test_vertex3)
    test_neighbor.defaultVertices = [test_vertex1, test_vertex2]
    test_neighbor.activeVertices = []
    test_asset.activeVertices = [test_interval_value3]
    test_neighbor.demand_rate = 0
    test_neighbor.lossFactor = 0

    assert len(test_auction.marginalPrices) == 0, 'The test should start with the auction having no marginal prices'
    assert len(test_neighbor.scheduledPowers) == 0, 'The upstream neighbor should initially have no scheduled powers.'
    assert len(test_asset.scheduledPowers) == 0, 'The local asset should be configured with no scheduled powers.'

    try:
        test_auction.while_in_delivery_lead(mtn)
        print('    - The method ran without errors')
    except RuntimeWarning:
        print('    - ERRORS ENCOUNTERED')

    assert len(test_auction.marginalPrices) == 1, 'The auction should have created precisely one marginal price.'
    assert round(test_auction.marginalPrices[0].value, 4) == 0.1500, \
        ['The interpolated price should be 0.15 in this case, not ' + str(test_auction.marginalPrices[0].value) + '.']
    assert len(test_neighbor.scheduledPowers) == 1, 'The upstream neighbor should have one scheduled power assigned.'
    assert round(test_neighbor.scheduledPowers[0].value, 4) == 50.0000, \
            ['The upstream neighbor\'s scheduled power should be 50 kW, not '
                            + str(round(test_neighbor.scheduledPowers[0].value, 4)) + '']
    assert len(test_asset.scheduledPowers) == 1, 'The local asset should have found a power at the cleared market price.'

    # CASE 2 ***********************************************************************************************************
    print('    CASE 2: Same as Case 1, '
          'but the upstream neighbor\'s active vertices must be found from transactive signals.')
    print('  Note: This also tests method balance().')
    pinf = float('inf')
    mtn = TransactiveNode()
    now = datetime.now()
    test_neighbor = Neighbor()
    test_neighbor.upOrDown = Direction.upstream
    test_neighbor.transactive = True
    test_neighbor.scheduledPowers = []
    test_neighbor.maximumPower = 100  # Assignment of maximumPower = 0 may lead to divide-by-0 error.
    test_neighbor.lossFactor = 0  # Losses are turned off so that the interpolation may be easily calculated.
    mtn.neighbors = [test_neighbor]
    test_asset = LocalAsset()
    mtn.localAssets = [test_asset]
    test_auction = Auction()
    test_auction.marginalPrices = []
    mtn.markets = test_auction
    test_time_interval = TimeInterval(now, timedelta(hours=1), test_auction, now, now)
    test_auction.timeIntervals = [test_time_interval]
    test_vertex1 = Vertex(0.1, 0, 0)
    test_vertex2 = Vertex(0.2, 0, 100)
    test_vertex3 = Vertex(pinf, 0, -50)
    test_interval_value1 = IntervalValue(test_neighbor, test_time_interval, test_auction, 'active vertex',
                                         test_vertex1)
    test_interval_value2 = IntervalValue(test_neighbor, test_time_interval, test_auction, 'active vertex',
                                         test_vertex2)
    test_interval_value3 = IntervalValue(test_auction, test_time_interval, test_auction, 'active vertex',
                                         test_vertex3)
    test_neighbor.activeVertices = []  # THIS IS DIFFERENT FROM CASE 1 ************************************************
    test_neighbor.receivedSignal = [TransactiveRecord(test_time_interval, 1, 0.1, 0),
                                                                TransactiveRecord(test_time_interval, 2, 0.2, 100)]
    test_asset.activeVertices = [test_interval_value3]

    assert len(test_auction.marginalPrices) == 0, 'The test should start with the auction having no marginal prices'
    assert len(test_neighbor.scheduledPowers) == 0, 'The upstream neighbor should initially have no scheduled powers.'
    assert len(test_neighbor.activeVertices) == 0, \
                                        'This case should start with no active vertices for the upstream neighbor'
    assert len(test_neighbor.receivedSignal) == 2, \
                                            'This case should begin with the upstream neighbor assigned 2 records.'

    try:
        test_auction.while_in_delivery_lead(mtn)
        print('    - The method ran without errors')
    except RuntimeWarning:
        print('    - ERRORS ENCOUNTERED')

    assert len(test_auction.marginalPrices) == 1, 'The auction should have created precisely one marginal price.'
    assert round(test_auction.marginalPrices[0].value, 4) == 0.1500, \
        ['The interpolated price should be 0.15 in this case, not ' + str(test_auction.marginalPrices[0].value) + '.']
    assert len(test_neighbor.scheduledPowers) == 1, 'The upstream neighbor should have one scheduled power assigned.'
    assert round(test_neighbor.scheduledPowers[0].value, 4) == 50.0000, \
            ['The upstream neighbor\'s scheduled power should be 50 kW, not '
                            + str(round(test_neighbor.scheduledPowers[0].value, 4)) + '']

    print('  test_while_in_delivery_lead() ran to completion.\n')
    pass


if __name__ == '__main__':
    print('Running tests in testauction.py\n')
    test_while_in_market_lead()
    test_while_in_negotiation()
    test_while_in_delivery_lead()
    print("Tests in testauction.py ran to completion.\n")
