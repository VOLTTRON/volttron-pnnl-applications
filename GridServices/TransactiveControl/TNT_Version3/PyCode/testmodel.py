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

from vertex import Vertex
from neighbor_model import Neighbor
from local_asset_model import LocalAsset
from market import Market
from time_interval import TimeInterval
from interval_value import IntervalValue
from measurement_type import MeasurementType
from TransactiveNode import TransactiveNode


def test_schedule():
    print('Running AbstractModel.test_schedule()')

    test_mtn = TransactiveNode()

    #   Create a test market test_mkt
    test_mkt = Market()

    #   Create a sample time interval ti
    dt = datetime.now()
    at = dt
    # NOTE: Function Hours() corrects behavior of Matlab hours().
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt
    # NOTE: Function Hours() corrects behavior of Matlab hours().
    st = datetime.combine(date.today(), time()) + timedelta(hours=20)
    ti = TimeInterval(at, dur, mkt, mct, st)

    #   Save the time interval
    test_mkt.timeIntervals = [ti]

    #   Assign a marginal price in the time interval
    test_mkt.check_marginal_prices(test_mtn)

    #   Create a Neighbor test object and give it a default maximum power value
    # test_obj = Neighbor()

    #   Create a corresponding Neighbor.
    test_mdl = Neighbor()
    test_mdl.maximumPower = 100

    #   Make sure that the model and object cross-reference one another
    # test_obj.model = test_mdl
    # test_mdl.object = test_obj

    #   Run a test with a Neighbor object
    print('- running test with a Neighbor:')

    try:
        test_mdl.schedule(test_mkt)
        print('  - the method encountered no errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_mdl.scheduledPowers) == 1, '  - the method did not store a scheduled power'
    assert len(test_mdl.reserveMargins) == 1, '  - the method did not store a reserve margin'
    assert len(test_mdl.activeVertices) == 1, '  - the method did not store an active vertex'

    # Run a test again with a LocalAsset.
    # test_obj = LocalAsset()

    test_mdl = LocalAsset()
    # test_obj.model = test_mdl
    # test_mdl.object = test_obj
    test_mdl.maximumPower = 100

    print('- running test with a LocalAsset:')

    try:
        test_mdl.schedule(test_mkt)
        print('  - the method encountered no errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_mdl.scheduledPowers) == 1, '  - the method did not store a scheduled power'
    assert len(test_mdl.reserveMargins) == 1, '  - the method did not store a reserve margin'
    assert len(test_mdl.activeVertices) == 1, '  - the method did not store an active vertex'

    # Success
    print('test_schedule() ran to completion.\n')


def test_update_costs():
    print('Running AbstractModel.test_update_costs()')

    test_mtn = TransactiveNode()

    #   Create a test market test_mkt
    test_mkt = Market()

    #   Create a sample time interval ti
    dt = datetime.now()
    at = dt
    #   NOTE: Function Hours() corrects behavior of Matlab hours().
    dur = timedelta(hours=1)
    mkt = test_mkt
    mct = dt
    st = datetime.combine(date.today(), time()) + timedelta(hours=20)
    ti = TimeInterval(at, dur, mkt, mct, st)

    #   Save the time interval
    test_mkt.timeIntervals = [ti]

    #   Assign a marginal price in the time interval
    test_mkt.check_marginal_prices(test_mtn)

    #   Create a Neighbor test object and give it a default maximum power value
    # test_obj = Neighbor()
    #     test_obj.maximumPower = 100

    #   Create a corresponding Neighbor.
    test_mdl = Neighbor()

    #   Make sure that the model and object cross-reference one another
    # test_obj.model = test_mdl
    # test_mdl.object = test_obj

    test_mdl.scheduledPowers = [IntervalValue(test_mdl, ti, test_mkt, MeasurementType.ScheduledPower, 100)]
    test_mdl.activeVertices = [IntervalValue(test_mdl, ti, test_mkt,
                                             MeasurementType.ActiveVertex, Vertex(0.05, 0, 100))]

    #   Run a test with a Neighbor object
    print('- running test with a Neighbor:')
    try:
        test_mdl.update_costs(test_mkt)
        print('  - the method encountered no errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_mdl.productionCosts) == 1, '  - the method did not store a production cost'
    assert len(test_mdl.dualCosts) == 1, '  - the method did not store a dual cost'
    assert test_mdl.totalProductionCost == sum([x.value for x in test_mdl.productionCosts]), \
            '  - the method did not store a total production cost'
    assert test_mdl.totalDualCost == sum([x.value for x in test_mdl.dualCosts]), \
            '  - the method did not store a total dual cost'

    # Run a test again with a LocalAsset.
    # test_obj = LocalAsset()
    test_mdl = LocalAsset()
    # test_obj.model = test_mdl
    # test_mdl.object = test_obj
    test_mdl.maximumPower = 100

    test_mdl.scheduledPowers = [IntervalValue(test_mdl, ti, test_mkt, MeasurementType.ScheduledPower, 100)]
    test_mdl.activeVertices = [IntervalValue(test_mdl, ti, test_mkt,
                                             MeasurementType.ActiveVertex, Vertex(0.05, 0, 100))]

    print('- running test with a LocalAsset:')

    try:
        test_mdl.update_costs(test_mkt)
        print('  - the method encountered no errors')
    except RuntimeWarning:
        print('  - ERRORS ENCOUNTERED')

    assert len(test_mdl.productionCosts) == 1, '  - the method did not store a production cost'
    assert len(test_mdl.dualCosts) == 1, '  - the method did not store a dual cost'
    assert test_mdl.totalProductionCost == sum([x.value for x in test_mdl.productionCosts]), \
            '  - the method did not store a total production cost'
    assert test_mdl.totalDualCost == sum([x.value for x in test_mdl.dualCosts]), \
            '  - the method did not store a total dual cost'

    # Success
    print('test_update_costs() ran to completion.\n')


if __name__ == '__main__':
    # Test the sealed AbstractModel methods
    print('Running tests in testmodel.py\n')
    test_schedule()
    test_update_costs()
    print('Tests in testmodel.py ran to completion.\n')
