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

import logging
from volttron.platform.agent import utils
from time_series_buffer import PointRecord
from data_point import DataPoint
import weakref
from collections import defaultdict

utils.setup_logging()
_log = logging.getLogger(__name__)


# TODO: Actuator should be scheduling the battery to prevent other things from trying to control it.
class BessComponent(object):
    def __init__(self):
        super(BessComponent, self).__init__()
        # TODO: WeakRefList for subscriptions.
        self.subscriptions = defaultdict(list)  # TODO: This should ideally only be created on top level components.
        self.agent = None
        self.point_mapping = {}
        self.repeatable_blocks = {}

    def configure(self, agent, config):
        self.agent = agent
        points = config.get('points', [])
        self.map_component_points(self, points)
        # TODO: Unsubscribe first if existing subscription exists.
        for topic in self.subscriptions:
            self.agent.vip.pubsub.subscribe('pubsub', topic, self.on_topic)
        for block in config.get('repeatable_blocks', []):
            name = block.get('name')
            if name:
                dependency = self.agent.configure_dependency(block)
                if dependency:
                    self.repeatable_blocks[block[name]] = dependency

    def map_component_points(self, obj, points):
        for key, attribute_name in obj.point_mapping.iteritems():
            matches = [x for x in points if x['mesa_name'] == key]
            point = matches[0] if matches else None
            if point:
                buffer_length = point.get('buffer_length')
                if buffer_length and buffer_length != getattr(obj, attribute_name).maxlen:
                    setattr(obj, attribute_name, DataPoint(maxlen=buffer_length, rpc_wait=self.agent.default_rpc_wait))
                attribute = getattr(obj, attribute_name)
                attribute.agent = self.agent
                attribute.point_name = point.get('driver_point_name', attribute.point_name)
                attribute.topic = point.get('topic_prefix', attribute.topic)
                # TODO: Deal with sunspec_sf registers.
                attribute.scale_factor = float(point.get('scale_factor') or attribute.scale_factor)
                attribute.offset = float(point.get('offset') or attribute.offset)
                attribute.unit = point.get('unit', attribute.unit)
                attribute.rpc_attempts = int(point.get('rpc_attempts') or attribute.rpc_attempts)
                attribute.rpc_wait = float(point.get('rpc_wait') or attribute.rpc_wait)
                attribute.max_data_age = float(point.get('max_data_age') or attribute.max_data_age)
                if attribute.topic and attribute.point_name:
                    self.subscriptions['devices/' + attribute.topic + '/all'].append(attribute)

    def on_topic(self, peer, sender, bus, topic, headers, message):
        date_header = headers.get('Date')
        d_time = utils.parse_timestamp_string(date_header) if date_header is not None else None
        for point in self.subscriptions[topic]:
            value = message[0].get(point.point_name)
            if value is not None:
                datum = point.scale_in(value)
                if datum is not None:
                    point.append(PointRecord(datum, d_time))
