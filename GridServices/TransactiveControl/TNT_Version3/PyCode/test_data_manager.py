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
