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

from .vertex import Vertex
from datetime import datetime, date
from .measurement_type import MeasurementType


VERBOSE = True
METHOD = 1  # Comma-Separated Value method
# METHOD = 2  # Database methods
MAX_ROWS = 1000  # Maximum number of table rows allowed. Old rows are removed. Use float('Inf') for unlimited rows.
CSV_DIRECTORY = './CSV_DATA'  # Static csv data directory relative to working directory.
DATE_FORMAT = "%Y-%m-%d"  # Simple date format like '2021-01-26'.
TIME_FORMAT = "%H:%M:%S"  # Simple time format like '13:14:15'.


def append_information_service_table(method=METHOD, obj=None):
    if VERBOSE:
        print("Made it to append_information_service_table().")


def append_interval_value_table(method=METHOD, objects=None):
    """
    Receive a list of IntervalValue objects and make a row for each in a data table.
    :param method: {1: CSV, 2: DATABASE} Only CSV is implemented.
    :param objects: List of IntervalValue objects
    :return:
    """
    import csv
    import os
    if VERBOSE:
        print("Made it to append_interval_value_table().")
    if not isinstance(objects, list):
        objects = [objects]
    header = ['TIMESTAMP', 'SOURCE_TYPE', 'SOURCE_NAME', 'MARKET_SERIES', 'MARKET_CLEARING_DATE',
              'MARKET_CLEARING_TIME', 'INTERVAL_STARTING_DATE', 'INTERVAL_STARTING_TIME', 'MEASUREMENT_TYPE',
              'VALUE_1', 'VALUE_2', 'VALUE_3']
    data_folder = "./CSV_DATA"
    datafile = "./CSV_DATA/IntervalValues.csv"
    TIMESTAMP = format(datetime.now())

    if not os.path.isfile(datafile):
        # The data file does not exist.
        if VERBOSE:
            print("File './CSV_DATA/IntervalValues.csv' does not exist.")
        if not os.path.isdir(data_folder):
            # The data directory does not exist either.
            if VERBOSE:
                print("Directory './CSV_DATA' does not exist. Create it.")
            os.mkdir(data_folder)
        with open(datafile, 'w', newline='') as write_obj:  # Open the new file and write its header row.
            if VERBOSE:
                print("Creating the file './CSV_DATA/IntervalValues.csv' with header.")
            csv_writer = csv.writer(write_obj, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(header)
            write_obj.close()

    file = open(datafile, 'a', newline='')
    if VERBOSE:
        print("Opening './CSV_DATA/IntervalValues.csv' to append row(s).")
    appender = csv.writer(file)

    for obj in objects:
        SOURCE_TYPE = obj.associatedClass
        SOURCE_NAME = obj.associatedObject
        MARKET_SERIES = obj.market.marketSeriesName
        MARKET_CLEARING_DATE = obj.market.marketClearingTime.strftime(DATE_FORMAT)
        MARKET_CLEARING_TIME = obj.market.marketClearingTime.strftime(TIME_FORMAT)
        INTERVAL_STARTING_DATE = obj.timeInterval.startTime.strftime(DATE_FORMAT)
        INTERVAL_STARTING_TIME = obj.timeInterval.startTime.strftime(TIME_FORMAT)
        MEASUREMENT_TYPE = MeasurementType.get(obj.measurementType)
        value_type = type(obj.value)
        if value_type != Vertex:
            VALUE_1 = obj.value
            VALUE_2 = ''
            VALUE_3 = ''
        else:
            VALUE_1 = obj.value.marginalPrice
            VALUE_2 = obj.value.power
            VALUE_3 = obj.value.record
        record = [TIMESTAMP, SOURCE_TYPE, SOURCE_NAME, MARKET_SERIES, MARKET_CLEARING_DATE, MARKET_CLEARING_TIME,
                  INTERVAL_STARTING_DATE, INTERVAL_STARTING_TIME, MEASUREMENT_TYPE, VALUE_1, VALUE_2, VALUE_3]

        appender.writerow(record)
        if VERBOSE:
            print('Appending record.')

    file.close()
    if VERBOSE:
        print('Closing file.')
    return None


def append_local_asset_table(method=METHOD, obj=None):
    if VERBOSE:
        print("Made it to append_local_asset_table().")


def append_market_object_table(method=METHOD, objects=None):
    """
    Receive a list of Market objects and make a row for each in a data table.
    :param method: {1: CSV, 2: DATABASE} Only CSV is curently implemented as of January 2021.
    :param objects: List of Market objects
    :return:
    """
    import csv
    import os
    VERBOSE = True
    if VERBOSE:
        print("Made it to append_market_object_table().")
    if not isinstance(objects, list):
        objects = [objects]
    header = ['TIMESTAMP', 'MARKET_NAME', 'MARKET_SERIES', 'NUMBER_INTERVALS', 'MARKET_CLEARING_DATE',
              'MARKET_CLEARING_TIME', 'DELIVERY_START_DATE', 'DELIVERY_START_TIME', 'TOTAL_DELIVERY_HOURS',
              'TOTAL_GENERATION', 'TOTAL_DEMAND', 'TOTAL_PRODUCTION_COST', 'TOTAL_DUAL_COST']
    data_folder = "./CSV_DATA"
    datafile = "./CSV_DATA/MarketObjects.csv"
    dt = datetime.now()
    TIMESTAMP = format(dt, DATE_FORMAT) + ' ' + format(dt, TIME_FORMAT)

    if not os.path.isfile(datafile):
        # The data file does not exist.
        if VERBOSE:
            print('File ' + datafile + ' does not exist.')
        if not os.path.isdir(data_folder):
            # The data directory does not exist either.
            if VERBOSE:
                print('Directory ' + data_folder + ' does not exist. Creating it.')
            os.mkdir(data_folder)
        with open(datafile, 'w', newline='') as write_obj:  # Open the new file and write its header row.
            if VERBOSE:
                print('Creating the file ' + datafile + ' with header.')
            csv_writer = csv.writer(write_obj, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(header)
            write_obj.close()

    file = open(datafile, 'a', newline='')
    if VERBOSE:
        print('Opening ' + datafile + ' to append row(s).')
    appender = csv.writer(file)

    for obj in objects:
        MARKET_NAME = obj.name
        MARKET_SERIES = obj.marketSeriesName
        NUMBER_INTERVALS = obj.intervalsToClear
        MARKET_CLEARING_DATE = format(obj.marketClearingTime, DATE_FORMAT)
        MARKET_CLEARING_TIME = format(obj.marketClearingTime, TIME_FORMAT)
        start_time = min([x.startTime for x in obj.timeIntervals])
        DELIVERY_START_DATE = format(start_time, DATE_FORMAT)
        DELIVERY_START_TIME = format(start_time, TIME_FORMAT)
        TOTAL_DELIVERY_HOURS = obj.intervalsToClear * obj.intervalDuration
        TOTAL_GENERATION = None
        TOTAL_DEMAND = None
        TOTAL_PRODUCTION_COST = None
        TOTAL_DUAL_COST = None

        record = [TIMESTAMP, MARKET_NAME, MARKET_SERIES, NUMBER_INTERVALS, MARKET_CLEARING_DATE,
                  MARKET_CLEARING_TIME, DELIVERY_START_DATE, DELIVERY_START_TIME, TOTAL_DELIVERY_HOURS,
                  TOTAL_GENERATION, TOTAL_DEMAND, TOTAL_PRODUCTION_COST, TOTAL_DUAL_COST]

        appender.writerow(record)
        if VERBOSE:
            print('Appending record.')

    file.close()
    if VERBOSE:
        print('Closing file.')
    return None


def append_meter_point_table(method=METHOD, obj=None):
    if VERBOSE:
        print("Made it to append_meter_point_table().")


def append_neighbor_table(method=METHOD, obj=None):
    if VERBOSE:
        print("Made it to append_neighbor_table().")


def append_time_interval_table(method=METHOD, obj=None):
    if VERBOSE:
        print("Made it to append_time_interval_table().")


def append_transactive_record_table(method=METHOD, objects=None):
    """
    Receive a list of TransactiveRecord objects and make a row for each in a data table.
    :param method: {1: CSV, 2: DATABASE} Only CSV is implemented.
    :param objects: List of TransactiveRecord objects
    :return:
    """
    import csv
    import os
    VERBOSE = True
    if VERBOSE:
        print("Made it to append_transactive_record_table().")
    if not isinstance(objects, list):
        objects = [objects]
    header = ['TIMESTAMP', 'NEIGHBOR_NAME', 'DIRECTION', 'MARKET_SERIES', 'MARKET_CLEARING_DATE',
              'MARKET_CLEARING_TIME', 'INTERVAL_STARTING_DATE', 'INTERVAL_STARTING_TIME', 'RECORD',
              'PRICE', 'POWER']
    data_folder = "./CSV_DATA"
    datafile = "./CSV_DATA/TransactiveRecords.csv"
    dt = datetime.now()
    TIMESTAMP = format(dt, DATE_FORMAT) + ' ' + format(dt, TIME_FORMAT)

    if not os.path.isfile(datafile):
        # The data file does not exist.
        if VERBOSE:
            print('File ' + datafile + ' does not exist.')
        if not os.path.isdir(data_folder):
            # The data directory does not exist either.
            if VERBOSE:
                print('Directory ' + data_folder + ' does not exist. Creating it.')
            os.mkdir(data_folder)
        with open(datafile, 'w', newline='') as write_obj:  # Open the new file and write its header row.
            if VERBOSE:
                print('Creating the file ' + datafile + ' with header.')
            csv_writer = csv.writer(write_obj, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(header)
            write_obj.close()

    file = open(datafile, 'a', newline='')
    if VERBOSE:
        print('Opening ' + datafile + ' to append row(s).')
    appender = csv.writer(file)

    for obj in objects:
        NEIGHBOR_NAME = obj.neighborName
        DIRECTION = obj.direction
        parts1 = obj.timeInterval.split(':')  # The record time interval is prepended with the market series name
        MARKET_SERIES = parts1[0]
        INTERVAL_STARTING_DATE = parts1[1][:4] + '-' + parts1[1][4:6] + '-' + parts1[1][6:8]
        INTERVAL_STARTING_TIME = parts1[1][9:11] + ':' + parts1[1][11:13] + ':' + parts1[1][13:15]
        parts2 = obj.marketName.split(':')
        MARKET_CLEARING_DATE = parts2[0][-13:-3]
        MARKET_CLEARING_TIME = parts2[0][-2:] + ':' + parts2[1] + ':' + parts2[2]
        print(f"MARKET_CLEARING_DATE: {MARKET_CLEARING_DATE}, MARKET_CLEARING_TIME: {MARKET_CLEARING_TIME}")
        RECORD = obj.record
        PRICE = obj.marginalPrice
        POWER = obj.power

        record = [TIMESTAMP, NEIGHBOR_NAME, DIRECTION, MARKET_SERIES, MARKET_CLEARING_DATE,
                  MARKET_CLEARING_TIME, INTERVAL_STARTING_DATE, INTERVAL_STARTING_TIME, RECORD,
                  PRICE, POWER]

        appender.writerow(record)
        if VERBOSE:
            print('Appending record.')

    file.close()
    if VERBOSE:
        print('Closing file.')
    return None


def append_vertex_table(method=METHOD, obj=None):
    if VERBOSE:
        print("Made it to append_vertex_table().")


def append_table(method=METHOD, obj=None):
    if VERBOSE:
        print("Made it to append_table method.")
    if obj is None:
        RuntimeWarning("No object was passed.")
        return
    tables = {
        'InformationServiceModel': append_information_service_table,
        'IntervalValue': append_interval_value_table,
        'LocalAsset': append_local_asset_table,
        'Market': append_market_object_table,
        'MeterPoint': append_meter_point_table,
        'Neighbor': append_neighbor_table,
        'TimeInterval': append_time_interval_table,
        'TransactiveRecord': append_transactive_record_table,
        'Vertex': append_vertex_table
        }
    if isinstance(obj, list):
        object_class = obj[0].__class__
        if any([type(x) != object_class for x in obj]):
            RuntimeWarning("An object list must contain objects of the same class.")
            return
    else:
        object_class = obj.__class__

    object_class_name = object_class.__name__
    selection = [x for x in tables if object_class_name == x]

    if len(selection) == 0:  # no table selection was identified
        object_bases = object_class.__bases__  # list of class parents
        object_classes = [object_bases[x] for x in range(len(object_bases))]  # list of parent classes
        selection = [x.__name__ for x in object_classes if x.__name__ in tables]  # table selection
        if len(selection) == 0:
            object_bases = []
            for object_class in object_classes:
                object_bases.extend(object_class.__bases__)
            object_classes = [object_bases[x] for x in range(len(object_bases))]
            selection = [x.__name__ for x in object_classes if x.__name__ in tables]
            if len(selection) == 0:
                object_bases = []
                for object_class in object_classes:
                    object_bases.extend(object_class.__bases__)
                object_classes = [x.__class__ for x in object_bases]
                selection = [x.__name__ for x in object_classes if x.__name__ in tables]
                if len(selection) == 0:
                    raise RuntimeWarning('No base class was identified.')
                    return
                return
            else:
                func = tables[selection[0]]
                return func(method, obj)
        else:
            func = tables[selection[0]]
            return func(method, obj)
    else:
        func = tables[selection[0]]
        return func(method, obj)


def lookup_neighbor_key(method=METHOD, obj=None):
    pass


def lookup_vertex_key(method=METHOD, obj=None):
    pass


def lookup_primary_key(method=METHOD, obj=None):
    pass
