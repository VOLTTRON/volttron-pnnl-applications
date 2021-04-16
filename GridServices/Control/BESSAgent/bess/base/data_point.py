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

from time_series_buffer import TimeSeriesBuffer, PointRecord
from volttron.platform.agent import utils
from datetime import datetime, timedelta
import pytz
import logging
from gevent import sleep, Timeout

utils.setup_logging()
_log = logging.getLogger(__name__)


class DataPoint(TimeSeriesBuffer):
    def __init__(self, agent=None, maxlen=1, topic=None, point_name=None, scale_factor=1.0, offset=0, unit=None,
                 rpc_attempts=5, rpc_wait=0.9, max_data_age=0):
        iterable = ()
        init_tz = agent.tz if agent else 'UTC'
        super(DataPoint, self).__init__(iterable, maxlen, init_tz)
        self.agent = agent
        self.topic = topic
        self.point_name = point_name
        self.scale_factor = scale_factor
        self.offset = offset
        self.unit = unit
        self.rpc_attempts = rpc_attempts
        self.rpc_wait = rpc_wait
        self.max_data_age = max_data_age
        self.last = PointRecord(None, datetime.now(pytz.utc).astimezone(self.tz))

    def read(self):
        tries_remaining = self.rpc_attempts
        while tries_remaining > 0:
            try:
                value = self.agent.vip.rpc.call(
                    self.agent.actuator_vip,
                    'get_point',
                    self.topic + '/' + self.point_name
                ).get(timeout=1)
                value = self.scale_in(value)
                record = PointRecord(value, datetime.now(pytz.utc).astimezone(self.tz))
                self.append(record)
                return self.last
            except:
                tries_remaining -= 1
                _log.warning("{} tries remaining of {} for {}".format(
                    tries_remaining, self.rpc_attempts, self.point_name))
                sleep(self.rpc_wait)
                continue
        # TODO: should this return self.last?
        return

    # Adjust input data for scale factor and offset if applicable. Data within the object should be in real-world units.
    # This method provides the necessary scaling and offset for use by other methods before storing.
    def scale_in(self, value, use_scale_factor=True, use_offset=True):
        value = value * self.scale_factor if use_scale_factor else value
        value = value + self.offset if use_offset else value
        return value

    def scale_out(self, value, use_scale_factor=True, use_offset=True):
        value = value - self.offset if use_offset else value
        value = value / self.scale_factor if use_scale_factor else value
        return value

    # TODO: How to handle expired data?
    def get(self, since=None, until=None, columns=None):
        if self.max_data_age and not since:
            since = datetime.now(pytz.utc).astimezone(self.tz) - timedelta(seconds=self.max_data_age)
        try:
            retval = super(DataPoint, self).get(since, until, columns)
            retval = retval[-1]
        except IndexError:
            retval = None
        return retval

    # TODO: The value in the object will not update until the next poll. Should it? Corner cases with set_result....
    def set(self, value, check_response=True):
        value = self.scale_out(value)
        failed = False
        set_result = False
        tries_remaining = self.rpc_attempts
        while tries_remaining > 0:
            try:
                set_result = self.agent.vip.rpc.call(
                    self.agent.actuator_vip,
                    'set_point',
                    self.agent.core.identity,
                    self.topic + '/' + self.point_name,
                    value
                ).get(timeout=1)
                break
            except (Exception, Timeout) as e:
                set_result = e
                tries_remaining -= 1
                if tries_remaining > 0:
                    _log.warning('{} tries remaining of {} for {}'.format(
                        tries_remaining, self.rpc_attempts, self.point_name))
                    sleep(self.rpc_wait)
                else:
                    failed = True
                continue
        if check_response and set_result != value:
            failed = True
        if failed:
            _log.error('Failed to set {} to {}. Received {} from set operation.'.format(
                self.point_name, value, set_result))
            return False
        else:
            return set_result

    # TODO: Was making comparison functions really a good idea?  Look for corner cases. How does this override deque?
    # TODO: Does this affect the behavior of the deque in iterative uses?
    def __eq__(self, other):
        if isinstance(other, DataPoint):
            return self.last == other.last
        elif isinstance(other, datetime):
            return self.last.d_time == other
        elif isinstance(self.last.value, (float, int)) and isinstance(other, (float, int)):
            return self.last.value == other
        elif isinstance(other, type(self.last.value)):
            return self.last.value == other
        else:
            raise TypeError("Unsupported operand types for ==: DataPoint and {}".format(type(other)))

    def __ne__(self, other):
        if isinstance(other, DataPoint):
            return self.last != other.last
        elif isinstance(other, datetime):
            return self.last.d_time != other
        elif isinstance(self.last.value, (float, int)) and isinstance(other, (float, int)):
            return self.last.value != other
        elif isinstance(other, type(self.last.value)):
            return self.last.value != other
        else:
            raise TypeError("Unsupported operand types for !=: DataPoint and {}".format(type(other)))

    def __ge__(self, other):
        if isinstance(other, DataPoint):
            return self.last >= other.last
        elif isinstance(other, datetime):
            return self.last.d_time >= other
        elif isinstance(self.last.value, (float, int)) and isinstance(other, (float, int)):
            return self.last.value >= other
        elif isinstance(other, type(self.last.value)):
            return self.last.value >= other
        else:
            raise TypeError("Unsupported operand types for >=: DataPoint and {}".format(type(other)))

    def __gt__(self, other):
        if isinstance(other, DataPoint):
            return self.last > other.last
        elif isinstance(other, datetime):
            return self.last.d_time > other
        elif isinstance(self.last.value, (float, int)) and isinstance(other, (float, int)):
            return self.last.value > other
        elif isinstance(other, type(self.last.value)):
            return self.last.value > other
        else:
            raise TypeError("Unsupported operand types for >: DataPoint and {}".format(type(other)))

    def __le__(self, other):
        if isinstance(other, DataPoint):
            return self.last <= other.last
        elif isinstance(other, datetime):
            return self.last.d_time <= other
        elif isinstance(self.last.value, (float, int)) and isinstance(other, (float, int)):
            return self.last.value <= other
        elif isinstance(other, type(self.last.value)):
            return self.last.value <= other
        else:
            raise TypeError("Unsupported operand types for <=: DataPoint and {}".format(type(other)))

    def __lt__(self, other):
        if isinstance(other, DataPoint):
            return self.last < other.last
        if isinstance(other, datetime):
            return self.last.d_time < other
        elif isinstance(self.last.value, (float, int)) and isinstance(other, (float, int)):
            return self.last.value < other
        elif isinstance(other, type(self.last.value)):
            return self.last.value < other
        else:
            raise TypeError("Unsupported operand types for <: DataPoint and {}".format(type(other)))
