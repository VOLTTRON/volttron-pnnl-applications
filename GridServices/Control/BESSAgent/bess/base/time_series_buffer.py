# Copyright 2019 The University of Toledo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import deque, namedtuple
import pytz
from datetime import datetime, tzinfo
from itertools import ifilter

PointRecord = namedtuple('PointRecord', ['value', 'd_time'])


# TODO: Implement comparison methods (__lt__, __eq__, etc)
class TimeSeriesBuffer(deque):
    def __init__(self, iterable=(), maxlen=None, tz='UTC'):
        super(TimeSeriesBuffer, self).__init__(iterable, maxlen)
        self.tz = tz if isinstance(tz, tzinfo) else pytz.timezone(tz)
        self.last = None

    def append(self, value, d_time=None):
        if not isinstance(value, PointRecord):
            d_time = d_time if d_time else datetime.now(pytz.utc).astimezone(self.tz)
            value = PointRecord(value, d_time)
        self.last = value
        super(TimeSeriesBuffer, self).append(value)

    def appendleft(self, value, d_time=None):
        if not isinstance(value, PointRecord):
            d_time = d_time if d_time else datetime.now(pytz.utc).astimezone(self.tz)
            super(TimeSeriesBuffer, self).append(PointRecord(value, d_time))
        else:
            super(TimeSeriesBuffer, self).appendleft(value)

    def extend(self, values):
        if not all(isinstance(x, PointRecord) for x in values):
            if all(len(x) == 2 and isinstance(x[1], datetime) for x in values):
                values = [PointRecord(*x) for x in values]
            else:
                raise ValueError('Values must be iterable and all elements must be compatible with PointRecord.')
        # TODO: How do we know this should really be the last value?
        self.last = values[-1]
        super(TimeSeriesBuffer, self).extend(values)

    def extendleft(self, values):
        if not all(isinstance(x, PointRecord) for x in values):
            if all(len(x) == 2 or isinstance(x[1], datetime)for x in values):
                values = [PointRecord(*x) for x in values]
            else:
                raise ValueError('Values must be iterable and all elements must be compatible with PointRecord.')
        super(TimeSeriesBuffer, self).extendleft(values)

    def get(self, since=None, until=None, columns=False):
        retval = self
        retval = self._since(retval, since) if since else retval
        retval = self._until(retval, until) if until else retval
        retval = zip(*retval) if columns else list(retval)
        return retval

    def get_values(self, since=None, until=None):
        return self.get(since, until)[0]

    def get_times(self, since=None, until=None):
        return self.get(since, until)[1]

    @staticmethod
    def _until(inval, until):
        if not isinstance(until, datetime):
            raise ValueError("If specified, until must be a datetime")
        return ifilter(lambda d: d[1] < until, inval)

    @staticmethod
    def _since(inval, since):
        print("since is: {}, datetime is {}".format(type(since), type(datetime)))
        if not isinstance(since, datetime):
            raise ValueError("If specified, since must be a datetime.")
        return ifilter(lambda d: d[1] > since, inval)

    maxlen = property(lambda self: object(), lambda self, v: None, lambda self: None)


