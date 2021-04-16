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
from .helpers import *
from .measurement_type import MeasurementType
from .interval_value import IntervalValue
from .transactive_record import TransactiveRecord
from .meter_point import MeterPoint
from .market import Market
from .time_interval import TimeInterval
from .neighbor import Neighbor
from .neighbor_model import NeighborModel
from .local_asset import LocalAsset
from .local_asset_model import LocalAssetModel
from .myTransactiveNode import myTransactiveNode
from .bulk_supplier_dc import BulkSupplier_dc
from .const import *


def test_all():
    print('Running BulkSupplier_dc.test_all()')
    test_update_dc_threshold()
    test_update_vertices()


def test_update_dc_threshold():
    print('Running BulkSupplier_dc.test_update_dc_threshold()')
    pf = 'pass'

    ## Basic configuration for tests:
    # Create a test object and initialize demand-realted properties
    test_obj = BulkSupplier_dc()
    test_obj.demandMonth = datetime.now().month  # month(datetime)
    test_obj.demandThreshold = 1000

    # Create a test market   
    test_mkt = Market()

    # Create and store two time intervals
    dt = datetime.now()
    at = dt
    dur = timedelta(hours=1)  # Hours(1)
    mkt = test_mkt
    mct = dt
    st = dt
    ti = [TimeInterval(at, dur, mkt, mct, st)]
    st = st + dur
    ti.append(TimeInterval(at, dur, mkt, mct, st))
    test_mkt.timeIntervals = ti

    ##  Test case when there is no MeterPoint object  
    test_obj.demandThreshold = 1000
    test_obj.demandMonth = datetime.now().month  # month(datetime)
    test_obj.meterPoints = []  # MeterPoint.empty

    # Create and store a couple scheduled powers
    # iv(1) = IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 900)
    # iv(2) = IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    iv = [
        IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 900),
        IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    ]
    test_obj.scheduledPowers = iv

    try:
        test_obj.update_dc_threshold(test_mkt)
        print('- the method ran without errors')
    except:
        pf = 'fail'
        print('- the method encountered errors when called')

    if test_obj.demandThreshold != 1000:
        pf = 'fail'
        print('- the method inferred the wrong demand threshold value')
    else:
        print('- the method properly kept the old demand threshold value with no meter')

    iv = [
        IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 1100),
        IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    ]
    test_obj.scheduledPowers = iv

    try:
        test_obj.update_dc_threshold(test_mkt)
        print('- the method ran without errors when there is no meter')
    except:
        pf = 'fail'
        print('- the method encountered errors when there is no meter')

    if test_obj.demandThreshold != 1100:
        pf = 'fail'
        print('- the method did not update the inferred demand threshold value')
    else:
        print('- the method properly updated the demand threshold value with no meter')

    ## Test with an appropriate MeterPoint meter
    # Create and store a MeterPoint test object
    test_mtr = MeterPoint()
    test_mtr.measurementType = MeasurementType.AverageDemandkW
    test_mtr.currentMeasurement = 900
    test_obj.meterPoints = [test_mtr]

    # Reconfigure the test object for this test:
    iv = [
        IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 900),
        IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    ]
    test_obj.scheduledPowers = iv

    test_obj.demandThreshold = 1000
    test_obj.demandMonth = datetime.now().month

    # Run the test. Confirm it runs.
    try:
        test_obj.update_dc_threshold(test_mkt)
        print('- the method ran without errors when there is a meter')
    except:
        pf = 'fail'
        print('- the method encountered errors when there is a meter')

    # Check that the old threshold is correctly retained.
    if test_obj.demandThreshold != 1000:
        pf = 'fail'
        print('- the method failed to keep the correct demand threshold value when there is a meter')
    else:
        print('- the method properly kept the old demand threshold value when there is a meter')

    # Reconfigure the test object with a lower current threshold
    iv = [
        IntervalValue(test_obj, ti[0], test_mkt, MeasurementType.ScheduledPower, 900),
        IntervalValue(test_obj, ti[1], test_mkt, MeasurementType.ScheduledPower, 900)
    ]
    test_obj.scheduledPowers = iv
    test_obj.demandThreshold = 800

    # Run the test.
    test_obj.update_dc_threshold(test_mkt)

    # Check that a new, higher demand threshold was set.
    if test_obj.demandThreshold != 900:
        pf = 'fail'
        print(['- the method failed to update the demand threshold value when there is a meter'])
    else:
        print('- the method properly updated the demand threshold value when there is a meter')

    ## Test rollover to new month
    # Configure the test object
    test_obj.demandMonth = dt + relativedelta.relativedelta(months=-1)  # month(datetime - days(31))  # prior month
    test_obj.demandThreshold = 1000
    test_obj.scheduledPowers[0].value = 900
    test_obj.scheduledPowers[1].value = 900
    test_obj.meterPoints = []  # MeterPoint.empty

    # Run the test
    test_obj.update_dc_threshold(test_mkt)

    # See if the demand threshold was reset at the new month.
    if test_obj.demandThreshold != 0.8 * 1000:
        pf = 'fail'
        print('- the method did not reduce the threshold properly in a new month')
    else:
        print('- the method reduced the threshold properly in a new month')

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


def test_update_vertices():
    print('Running BulkSupplier_dc.test_update_vertices()')
    pf = 'test is not completed yet'

    # Success
    print('- the test ran to completion')
    print('Result: #s\n\n', pf)


if __name__ == '__main__':
    test_all()
