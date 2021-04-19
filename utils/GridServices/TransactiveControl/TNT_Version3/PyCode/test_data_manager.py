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

from interval_value import IntervalValue
from neighbor_model import Neighbor
from time_interval import TimeInterval
from datetime import datetime, timedelta
from market import Market
from vertex import Vertex
from measurement_type import MeasurementType
from data_manager import *
from transactive_record import TransactiveRecord


def DIVIDER():
    print(70*'*')


def ran():
    print('- the test ran without errors')


def failed(error):
    print('- THE TEST FAILED:', error)


class TestAppendIntervalValueTable:
    def __init__(self):
        self.test_caller = None
        self.test_market = None
        self.test_interval = None
        self.test_vertex = None
        self.test_value = None
        self.test_iv = None
        self.test_object = None

    def setup(self):
        dt = datetime.now()
        dur = timedelta(hours=1)
        self.test_caller = Neighbor()
        self.test_caller.name = 'test_neighbor'
        self.test_market = Market()
        self.test_market.marketSeriesName = 'test_market_series'
        self.test_market.marketClearingTime = dt
        self.test_vertex = Vertex(marginal_price=0,
                                  prod_cost=0,
                                  power=0)
        self.test_value = 1234.5678
        self.test_interval = TimeInterval(activation_time=dt,
                                          duration=dur,
                                          market=self.test_market,
                                          market_clearing_time=dt,
                                          start_time=dt)
        self.test_iv = IntervalValue(calling_object=self.test_caller,
                                     time_interval=self.test_interval,
                                     market=self.test_market,
                                     measurement_type=MeasurementType.ScheduledPower,
                                     value=self.test_value)

    def case1(self):
        print("\nCASE 1: Single IntervalValue that is not a Vertex.")
        self.setup()
        self.test_object = self.test_iv
        assert type(self.test_object.value) != Vertex, 'This case should test a value that is not a Vertex object.'
        assert not isinstance(self.test_object, list), 'This case is intended to test a single object.'
        try:
            append_table(method=1,
                         obj=self.test_object)
            ran()
        except RuntimeError as error:
            failed(error)
        print("Case 1 ran to completion.\n")

    def case2(self):
        print("\nCASE 2: List of IntervalValue objects that are not Vertices.")
        self.setup()
        self.test_object = [self.test_iv, self.test_iv, self.test_iv]
        assert type(self.test_object[0].value) != Vertex, 'This case should test a value that is not a Vertex object.'
        assert isinstance(self.test_object, list), 'This case is intended to test a list of objects.'
        try:
            append_table(method=1,
                         obj=self.test_object)
            ran()
        except RuntimeError as error:
            failed(error)
        print("Case 2 ran to completion.\n")

    def case3(self):
        print("\nCASE 3: Single IntervalValue that is a Vertex.")
        self.setup()
        self.test_iv.value = self.test_vertex
        self.test_object = self.test_iv
        assert type(self.test_object.value) == Vertex, 'This case should test a value that is a Vertex object.'
        assert not isinstance(self.test_object, list), 'This case is intended to test a single value.'
        try:
            append_table(method=1,
                         obj=self.test_object)
            ran()
        except RuntimeError as error:
            failed(error)
        print("Case 3 ran to completion.\n")

    def case4(self):
        print("\nCASE 4: List of IntervalValue objects that are Vertices.")
        self.setup()
        self.test_iv.value = self.test_vertex
        self.test_object = [self.test_iv, self.test_iv, self.test_iv]
        assert type(self.test_object[0].value) == Vertex, 'This case should test a value that is a Vertex object.'
        assert isinstance(self.test_object, list), 'This case is intended to test a list of objects.'
        try:
            append_table(method=1,
                         obj=self.test_object)
            ran()
        except RuntimeError as error:
            failed(error)
        print("Case 4 ran to completion.\n")


class TestAppendTransactiveRecordTable:
    def __init__(self):
        self.test_neighbor = None
        self.test_market = None
        self.test_interval = None
        self.test_vertex = None
        self.test_value = None
        self.test_iv = None
        self.test_object = None
        self.test_record = None

    def setup(self):
        dt = datetime.now()
        dur = timedelta(hours=1)
        self.test_neighbor = Neighbor()
        self.test_neighbor.name = 'test_neighbor'
        self.test_market = Market()
        self.test_market.marketSeriesName = 'test_market_series'
        self.test_market.marketClearingTime = dt
        self.test_market.name = self.test_market.marketSeriesName.replace(' ', '_') + '_' + str(dt)[:19]
        self.test_vertex = Vertex(marginal_price=0,
                                  prod_cost=0,
                                  power=0)
        self.test_value = 1234.5678
        self.test_interval = TimeInterval(activation_time=dt,
                                          duration=dur,
                                          market=self.test_market,
                                          market_clearing_time=dt,
                                          start_time=dt)
        self.test_iv = IntervalValue(calling_object=self.test_neighbor,
                                     time_interval=self.test_interval,
                                     market=self.test_market,
                                     measurement_type=MeasurementType.ScheduledPower,
                                     value=self.test_value)
        self.test_record = TransactiveRecord(time_interval=self.test_interval,
                                             neighbor_name=self.test_neighbor.name,
                                             direction='sent',
                                             market_name=self.test_market.name,
                                             record=0,
                                             marginal_price=0.0123,
                                             power=123.4)

    def case1(self):
        print("\nCASE 1: Single TransactiveRecord.")
        self.setup()
        self.test_object = self.test_record
        assert not isinstance(self.test_object, list), 'This case is intended to test a single object.'
        try:
            append_table(method=1,
                         obj=self.test_object)
            ran()
        except RuntimeError as error:
            failed(error)
        print("Case 1 ran to completion.\n")

    def case2(self):
        print("\nCASE 2: List of TransactiveRecord objects.")
        self.setup()
        self.test_object = [self.test_record, self.test_record, self.test_record]
        assert isinstance(self.test_object, list), 'This case is intended to test a list of objects.'
        try:
            append_table(method=1,
                         obj=self.test_object)
            ran()
        except RuntimeError as error:
            failed(error)
        print("Case 2 ran to completion.\n")


class TestAppendMarketObjectTable:
    def __init__(self):
        self.test_neighbor = None
        self.test_market = None
        self.test_interval = None
        self.test_vertex = None
        self.test_value = None
        self.test_iv = None
        self.test_object = None
        self.test_record = None

    def setup(self):
        dt = datetime.now()
        dur = timedelta(hours=1)
        self.test_neighbor = Neighbor()
        self.test_neighbor.name = 'test_neighbor'
        self.test_market = Market()
        self.test_market.intervalsToClear=1
        self.test_market.intervalDuration = timedelta(hours=1)
        self.test_market.marketSeriesName = 'test_market_series'
        self.test_market.marketClearingTime = dt
        self.test_market.name = self.test_market.marketSeriesName.replace(' ', '_') + '_' + str(dt)[:19]
        self.test_vertex = Vertex(marginal_price=0,
                                  prod_cost=0,
                                  power=0)
        self.test_value = 1234.5678
        self.test_interval = TimeInterval(activation_time=dt,
                                          duration=dur,
                                          market=self.test_market,
                                          market_clearing_time=dt,
                                          start_time=dt)
        self.test_market.timeIntervals = [self.test_interval]
        self.test_iv = IntervalValue(calling_object=self.test_neighbor,
                                     time_interval=self.test_interval,
                                     market=self.test_market,
                                     measurement_type=MeasurementType.ScheduledPower,
                                     value=self.test_value)
        self.test_record = TransactiveRecord(time_interval=self.test_interval,
                                             neighbor_name=self.test_neighbor.name,
                                             direction='sent',
                                             market_name=self.test_market.name,
                                             record=0,
                                             marginal_price=0.0123,
                                             power=123.4)

    def case1(self):
        print("\nCASE 1: Single Market object.")
        self.setup()
        self.test_object = self.test_market
        assert not isinstance(self.test_object, list), 'This case is intended to test a single object.'
        try:
            append_table(method=1,
                         obj=self.test_object)
            ran()
        except RuntimeError as error:
            failed(error)
        print("Case 1 ran to completion.\n")

    def case2(self):
        print("\nCASE 2: List of Market objects.")
        self.setup()
        self.test_object = [self.test_market, self.test_market, self.test_market]
        assert isinstance(self.test_object, list), 'This case is intended to test a list of objects.'
        try:
            append_table(method=1,
                         obj=self.test_object)
            ran()
        except RuntimeError as error:
            failed(error)
        print("Case 2 ran to completion.\n")


if __name__ == '__main__':
    DIVIDER()  # **********
    print('\nRunning tests in test_data_manager.py')

    DIVIDER()  # **********
    test_fixture = TestAppendIntervalValueTable()
    print('Running test fixture ' + str(test_fixture) + '.')
    test_fixture.case1()
    test_fixture.case2()
    test_fixture.case3()
    test_fixture.case4()
    print('Fixture ' + str(test_fixture) + 'ran to completion.')
    DIVIDER()  # **********

    DIVIDER()  # **********
    test_fixture = TestAppendTransactiveRecordTable()
    print('Running test fixture ' + str(test_fixture) + '.')
    test_fixture.case1()
    test_fixture.case2()
    print('Fixture ' + str(test_fixture) + ' ran to completion.')
    DIVIDER()  # **********
    print("\nTests in test_data_manager.py ran to completion.")
    DIVIDER()  # **********

    DIVIDER()  # **********
    test_fixture = TestAppendMarketObjectTable()
    print('Running test fixture ' + str(test_fixture) + '.')
    test_fixture.case1()
    test_fixture.case2()
    print('Fixture ' + str(test_fixture) + ' ran to completion.')
    DIVIDER()  # **********

    print("\nTests in test_data_manager.py ran to completion.")
    DIVIDER()  # **********
