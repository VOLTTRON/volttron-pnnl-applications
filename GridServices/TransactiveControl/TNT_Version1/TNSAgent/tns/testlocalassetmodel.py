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



from datetime import datetime, timedelta, date, time
from dateutil import relativedelta

from .model import Model
from .vertex import Vertex
from .interval_value import IntervalValue
from .measurement_type import MeasurementType
from .helpers import *
from .market import Market
from .time_interval import TimeInterval
from .local_asset import LocalAsset
from .local_asset_model import LocalAssetModel


def test_all():
    print('Running LocalAssetModel.test_all()')
    test_assign_transition_costs()
    test_calculate_reserve_margin()  # Done
    test_cost()  # Missing - low priority
    test_engagement_cost()  # Missing - low priority
    test_schedule_engagement()  # Done - low priority
    test_schedule_power()  # Done - high priority  
    test_update_dual_costs()  # Missing - high priority
    test_update_production_costs()  # Missing - high priority
    test_update_vertices()  # Missing - high priority


def test_assign_transition_costs():
    print('Running LocalAssetModel.test_assign_transition_costs()')

    pf = 'test not completed'

    # Success.
    print('- the test ran to completion')
    print('\nResult: #s\n\n', pf)


def test_calculate_reserve_margin():
    # TEST_LAM_CALCULATE_RESERVE_MARGIN() - a LocalAssetModel ("LAM") class
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

    print('Running LocalAssetModel.test_calculate_reserve_margin()')

    pf = 'pass'

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

    # Establish a test object that is a LocalAsset with assigned maximum power
    test_object = LocalAsset()
    test_object.maximumPower = 100

    # Establish test object that is a LocalAssetModel
    test_model = LocalAssetModel()
    test_model.scheduledPowers = [
        IntervalValue(test_model, ti, test_mkt, MeasurementType.ScheduledPower, 0.0)]

    # Allow object and model to cross-reference one another.
    test_object.model = test_model
    test_model.object = test_object

    # Run the first test case.
    test_model.calculate_reserve_margin(test_mkt)
    print('- method ran without errors')

    if len(test_model.reserveMargins) != 1:
        raise Exception('- an unexpected number of results were stored')
    else:
        print('- one reserve margin was stored, as expected')

    if test_model.reserveMargins[0].value != test_object.maximumPower:
        pf = 'fail'
        raise Exception('- the method did not use the available maximum power')
    else:
        print('- the method used maximum power value, as expected')

    # create some vertices and store them
    iv = [
        IntervalValue(test_model, ti, test_mkt, MeasurementType.Vertex, Vertex(0, 0, -10)),
        IntervalValue(test_model, ti, test_mkt, MeasurementType.Vertex, Vertex(0, 0, 10))
    ]
    test_model.activeVertices = iv

    # run test with maximum power greater than maximum vertex
    test_object.maximumPower = 100
    test_model.calculate_reserve_margin(test_mkt)

    if test_model.reserveMargins[0].value != 10:
        pf = 'fail'
        raise Exception('- the method should have used vertex for comparison')
    else:
        print('- the method correctly chose to use the vertex power')

    # run test with maximum power less than maximum vertex
    test_object.maximumPower = 5
    test_model.calculate_reserve_margin(test_mkt)

    if test_model.reserveMargins[0].value != 5:
        pf = 'fail'
        raise Exception('- method should have used maximum power for comparison')
    else:
        print('- the method properly chose to use the maximum power')

    # run test with scheduled power greater than maximum vertex
    test_model.scheduledPowers[0].value = 20
    test_object.maximumPower = 500
    test_model.calculate_reserve_margin(test_mkt)

    if test_model.reserveMargins[0].value != 0:
        pf = 'fail'
        raise Exception('- method should have assigned zero for a neg. result')
    else:
        print('- the method properly assigned 0 for a negative result')

    # Success.
    print('- the test ran to completion')
    print('\nResult: #s\n\n', pf)


def test_cost():
    print('Running LocalAssetModel.test_cost()')

    pf = 'test not completed'

    # Success.
    print('- the test ran to completion')
    print('\nResult: #s\n\n', pf)

def test_engagement_cost():
    print('Running LocalAssetModel.test_engagement_cost()')
    pf = 'pass'

    #   Create a test LocalAssetModel object.
    test_model = LocalAssetModel()

    #   Assign engagement costs for [dissengagement, hold, engagement]
    test_model.engagementCost = [1, 2, 3]

    ## TEST 1
    print('- Test 1: Normal transition input arguments [-1,0,1]')

    transition = 0  # false - false  # a hold transition, unchanged

    cost = test_model.engagement_cost(transition)
    print('  - the method ran without errors')

    if cost != 2:
        pf = 'fail'
        print('  - the method miscalculated the cost of a hold')
    else:
        print('  - the method correctly calculated the cost of a hold')

    transition = -1  # false - true  # an disengagement transition

    cost = test_model.engagement_cost(transition)

    if cost != 1:
        pf = 'fail'
        print('  - the method miscalculated the cost of a disengagement')
    else:
        print('  - the method correctly calculated the cost of a disengagement')

    transition = 1  # true - false  # an disengagement transition

    cost = test_model.engagement_cost(transition)

    if cost != 3:
        pf = 'fail'
        print('  - the method miscalculated the cost of an engagement')
    else:
        print('  - the method correctly calculated the cost of an engagement')

    ## TEST 2
    print('- Test 2: Unexpected, dissallowed input argument')

    transition = 7  # a disallowed transition

    cost = test_model.engagement_cost(transition)
    print('  - method warned and returned gracefully')

    if cost != 0:
        pf = 'fail'
        print('  - the method assigned a cost value other than zero')
    else:
        print('  - the method correctly assigned zero to the cost')

    # Success.
    print('- the test ran to completion')
    print('\nResult: #s\n\n', pf)


def test_schedule_engagement():
    # TEST_SCHEDULE_ENGAGEMENT() - tests a LocalAssetModel method called
    # schedule_engagment()

    print('Running LocalAssetModel.test_schedule_engagement()')

    pf = 'pass'

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

    #   Establish test object that is a LocalAssetModel
    test_object = LocalAssetModel()

    #   Run the first test case.
    test_object.schedule_engagement(test_mkt)

    #   Were the right number of engagement schedule values created?
    if len(test_object.engagementSchedule) != 2:
        pf = 'fail'
        raise Exception('- the method did not store the engagement schedule')
    else:
        print('- the method stored the right number of results')

    # Where the correct scheduled engagement values stored?
    if len([x.value for x in test_object.engagementSchedule if x.value != 1]) > 0:
        pf = 'fail'
        raise Exception('- the stored engagement schedule was not as expected')
    else:
        print('- the result values were as expected')

    # Create and store another active time interval.
    st = ti[1].startTime + dur
    ti.append(TimeInterval(at, dur, mkt, mct, st))

    #   Re-store time intervals
    test_mkt.timeIntervals = ti

    #   Run next test case.
    test_object.schedule_engagement(test_mkt)

    #   Was the new time interval used?
    if len(test_object.engagementSchedule) != 3:
        pf = 'fail'
        raise Exception('- the method apparently failed to create a new engagement')
    else:
        print('- the method created and stored new values')

    # Were the existing time interval values reassigned properly?
    # if any([test_object.engagementSchedule.value] != true * ones(1, 3)):
    if any([x.value != 1 for x in test_object.engagementSchedule]):
        pf = 'fail'
        raise Exception('- the existing list was not augmented as expected')

    # Success.
    print('- the test ran to completion')
    print('\nResult: #s\n\n', pf)


def test_schedule_power():
    # TEST_SCHEDULE_POWER() - tests a LocalAssetModel method called
    # schedule_power().

    print('Running LocalAssetModel.test_schedule_power()')

    pf = 'pass'

    #   Establish test market
    test_mkt = Market

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

    #   Establish test object that is a LocalAssetModel with a default power
    #   property.
    test_object = LocalAssetModel()
    test_object.defaultPower = 3.14159

    #   Run the first test case.
    test_object.schedule_power(test_mkt)

    #   Were the right number of schduled power values created?
    if len(test_object.scheduledPowers) != 2:
        pf = 'fail'
        raise Exception('- the method did not store the right number of results')
    else:
        print('- the method stored the right number of results')

    # Where the correct scheduled power valules stored?
    # if any([test_object.scheduledPowers.value] != test_object.defaultPower * ones(1, 2))
    if any([x.value != test_object.defaultPower for x in test_object.scheduledPowers]):
        pf = 'fail'
        raise Exception('- the stored scheduled powers were not as expected')
    else:
        print('- the result value was as expected')

    # Change the default power.
    test_object.defaultPower = 6

    #   Create and store another active time interval.
    st = ti[1].startTime + dur
    ti.append(TimeInterval(at, dur, mkt, mct, st))

    #   Re-store time intervals
    test_mkt.timeIntervals = ti

    #   Run next test case.
    test_object.schedule_power(test_mkt)

    #   Was the new time interval used?
    if len(test_object.scheduledPowers) != 3:
        pf = 'fail'
        raise Exception('- the method failed to create a new scheduled power')

    # Were the existing time intervals reassigned properly?
    # if any([test_object.scheduledPowers.value] != test_object.defaultPower * ones(1, 3))
    if any([x.value != test_object.defaultPower for x in test_object.scheduledPowers]):
        pf = 'fail'
        raise Exception('- existing scheduled powers were not reassigned properly')

    # Success.
    print('- the test ran to completion')
    print('\nResult: #s\n\n', pf)


def test_update_dual_costs():
    # TEST_UPDATE_DUAL_COSTS() - test method update_dual_costs() that creates
    # or revises the dual costs in active time intervals using active vertices,
    # scheduled powers, and marginal prices.
    # NOTE: This test is virtually identical to the NeighborModel test of the
    # same name.
    print('Running LocalAssetModel.test_update_dual_costs()')
    pf = 'pass'

    #   Create a test Market object.
    test_market = Market()

    #   Create and store a TimeInterval object.
    dt = datetime.now()  # datetime that may be used for most datetime arguments
    time_interval = TimeInterval(dt, timedelta(hours=1), test_market, dt, dt)
    test_market.timeIntervals = [time_interval]

    #   Create and store a marginal price IntervalValue object.
    test_market.marginalPrices = [
        IntervalValue(test_market, time_interval, test_market, MeasurementType.MarginalPrice, 0.1)]

    #   Create a test LocalAssetModel object.
    test_model = LocalAssetModel()

    #   Create and store a scheduled power IntervalValue in the active time
    #   interval.
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, 100)]

    #   Create and store a production cost IntervalValue object in the active
    #   time interval.
    test_model.productionCosts = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ProductionCost, 1000)]

    # TEST 1
    print('- Test 1: First calculation of a dual cost')

    test_model.update_dual_costs(test_market)
    print('  - the method ran without errors')

    if len(test_model.dualCosts) != 1:
        pf = 'fail'
        print('  - the wrong number of dual cost values was created')
    else:
        print('  - the right number of dual cost values was created')

    dual_cost = test_model.dualCosts[0].value

    if dual_cost != (1000 - 100 * 0.1):
        pf = 'fail'
        print('  - an unexpected dual cost value was found')
    else:
        print('  - the expected dual cost value was found')

    # TEST 2
    print('- Test 2: Reassignment of an existing dual cost')

    #   Configure the test by modifying the marginal price value.
    test_market.marginalPrices[0].value = 0.2

    test_model.update_dual_costs(test_market)
    print('  - the method ran without errors')

    if len(test_model.dualCosts) != 1:
        pf = 'fail'
        print('  - the wrong number of dual cost values was created')
    else:
        print('  - the right number of dual cost values was created')

    dual_cost = test_model.dualCosts[0].value

    if dual_cost != (1000 - 100 * 0.2):
        pf = 'fail'
        print('  - an unexpected dual cost value was found')
    else:
        print('  - the expected dual cost value was found')

    # Success.
    print('- the test ran to completion')
    print('\nResult: #s\n\n', pf)


def test_update_production_costs():
    # TEST_UPDATE_PRODUCTION_COSTS() - test method update_production_costs()
    # that calculates production costs from active vertices and scheduled
    # powers.
    # NOTE: This test is virtually identical to the NeighborModel test of the
    # same name.
    print('Running LocalAssetModel.test_update_production_costs()')
    pf = 'pass'

    #   Create a test Market object.
    test_market = Market

    #   Create and store a TimeInterval object.
    dt = datetime.now()  # datetime that may be used for most datetime arguments
    time_interval = TimeInterval(dt, timedelta(hours=1), test_market, dt, dt)
    test_market.timeIntervals = [time_interval]

    #   Create a test LocalAssetModel object.
    test_model = LocalAssetModel()

    #   Create and store a scheduled power IntervalValue in the active time
    #   interval.
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, 50)]

    #   Create and store some active vertices IntervalValue objects in the
    #   active time interval.
    vertices = [
        Vertex(0.1, 1000, 0),
        Vertex(0.2, 1015, 100)
    ]
    interval_values = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ActiveVertex, vertices[0]),
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ActiveVertex, vertices[1])
    ]
    test_model.activeVertices = interval_values

    # TEST 1
    print('- Test 1: First calculation of a production cost')

    test_model.update_production_costs(test_market)
    print('  - the method ran without errors')

    if len(test_model.productionCosts) != 1:
        pf = 'fail'
        print('  - the wrong number of production costs was created')
    else:
        print('  - the right number of production cost values was created')

    production_cost = test_model.productionCosts[0].value

    if float(production_cost) != float(1007.5):
        pf = 'fail'
        print('  - an unexpected production cost value was found')
    else:
        print('  - the expected production cost value was found')

    # TEST 2
    print('- Test 2: Reassignment of an existing production cost')

    #   Configure the test by modifying the scheduled power value.
    test_model.scheduledPowers[0].value = 150

    test_model.update_production_costs(test_market)
    print('  - the method ran without errors')

    if len(test_model.productionCosts) != 1:
        pf = 'fail'
        print('  - the wrong number of productions was created')
    else:
        print('  - the right number of production cost values was created')

    production_cost = test_model.productionCosts[0].value

    if float(production_cost) != float(1015):
        pf = 'fail'
        print('  - an unexpected dual cost value was found')
    else:
        print('  - the expected dual cost value was found')

    # Success.
    print('- the test ran to completion')
    print('\nResult: #s\n\n', pf)


def test_update_vertices():
    # TEST_UPDATE_VERTICES() - test method update_vertices(), which for this
    # base class of LocalAssetModel does practically nothing and must be
    # redefined by child classes that represent flesible assets.
    print('Running LocalAssetModel.test_update_vertices()')
    pf = 'pass'

    #   Create a test Market object.
    test_market = Market

    #   Create and store a TimeInterval object.
    dt = datetime.now()  # datetime that may be used for most datetime arguments
    time_interval = TimeInterval(dt, timedelta(hours=1), test_market, dt, dt)
    test_market.timeIntervals = [time_interval]

    #   Create a test LocalAssetModel object.
    test_model = LocalAssetModel()

    #   Create and store a scheduled power IntervalValue in the active time interval.
    test_model.scheduledPowers = [
        IntervalValue(test_model, time_interval, test_market, MeasurementType.ScheduledPower, 50)]

    #   Create a LocalAsset object and its maximum and minimum powers.
    test_object = LocalAsset()
    test_object.maximumPower = 200
    test_object.minimumPower = 0

    #   Have the LocalAsset model and object cross reference one another.
    test_object.model = test_model
    test_model.object = test_object

    ## TEST 1
    print('- Test 1: Basic operation')

    test_model.update_vertices(test_market)
    print('  - the method ran without errors')

    if len(test_model.activeVertices) != 1:
        pf = 'fail'
        print('  - there is an unexpected number of active vertices')
    else:
        print('  - the expected number of active vertices was found')

    # Success.
    print('- the test ran to completion')
    print('\nResult: #s\n\n', pf)


if __name__ == '__main__':
    test_all()
