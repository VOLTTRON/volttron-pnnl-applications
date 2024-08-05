"""
Copyright (c) 2024, Battelle Memorial Institute
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
from __future__ import annotations
import sys
import inspect
from dataclasses import asdict, dataclass, is_dataclass
import logging
from typing import Any
import gevent

from volttron.platform.agent import utils
from volttron.platform.agent.utils import setup_logging
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError

from . import DefaultConfig
from .data_utils import Data, DataFileAccess
from .optimal_start_manager import OptimalStartManager
from .holiday_manager import HolidayManager
from .points import DaysOfWeek, OccupancyTypes, Points

__author__ = 'Robert Lutes, robert.lutes@pnnl.gov'
__version__ = '0.0.1'

setup_logging()
_log = logging.getLogger(__name__)


class OptimalStart(Agent):
    def __init__(self, config_path, **kwargs):
        super(OptimalStart, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        default_config = DefaultConfig(**config)
        self.cfg = default_config
        self.identity = self.core.identity
        self.precontrols = config.get('precontrols', {})
        self.precontrol_flag = False
        self.datafile = DataFileAccess(datafile=self.cfg.data_file)
        self.data_handler = Data(timezone=self.cfg.timezone,
                                 data_accessor=self.datafile,
                                 setpoint_offset=self.cfg.setpoint_offset)
        # Initialize sub-classes
        self.holiday_manager = HolidayManager()
        self.optimal_start = OptimalStartManager(schedule=self.cfg.schedule,
                                                 config=self.cfg,
                                                 identity=self.identity,
                                                 scheduler_fn=self.core.schedule,
                                                 holiday_manager=self.holiday_manager,
                                                 data_handler=self.data_handler,
                                                 publish_fn=self.publish,
                                                 change_occupancy_fn=self.change_occupancy,
                                                 config_set_fn=self.config_set,
                                                 config_get_fn=self.config_get)

    @Core.receiver('onstart')
    def starting_base(self, sender, **kwargs):
        """
         Startup method:
         - Setup subscriptions to devices.
        @param sender:
        @type sender:
        @param kwargs:
        @type kwargs:
        @return:
        @rtype:
        """
        _log.debug(f'SETUP DATA SUBSCRIPTIONS FOR {self.identity}')
        self.vip.pubsub.subscribe(peer='pubsub', prefix=self.cfg.base_device_topic,
                                  callback=self.update_data).get(timeout=10.0)
        if self.cfg.outdoor_temperature_topic:
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=self.cfg.outdoor_temperature_topic,
                                      callback=self.update_custom_data).get(timeout=10.0)
        self.optimal_start.setup_optimal_start()

    def config_get(self, name: str):
        """
        A helper method to get the configuration from the configuration store.

        :param name: The name of the configuration to get.
        :type name: str
        :return: The configuration.
        :rtype: dict
        """
        return self.vip.config.get(name)

    def config_set(self, name: str, config: dict[str, Any] | dataclass):
        """
        A helper method to set the configuration in the configuration store.

        :param name: The name of the configuration to set.
        :type name: str
        :param config: The configuration to set.
        :type config: dict
        :return: None
        """
        if is_dataclass(config):
            config = asdict(config)

        self.vip.config.set(name, config, send_update=True)

    def update_data(self, peer, sender, bus, topic, header, message):
        """
        Update RTU data from driver publish for optimal start model training.
        :param peer:
        :type peer:
        :param sender:
        :type sender:
        :param bus:
        :type bus:
        :param topic:
        :type topic:
        :param header:
        :type header:
        :param message:
        :type message:
        :return:
        :rtype:
        """
        _log.debug(f'Update data : {topic}')
        data, meta = message
        self.data_handler.update_data(data, header)

    def update_custom_data(self, peer, sender, bus, topic, header, message):
        """
        Update RTU data for custom data topics, typically when one device
        had OAT for entire building.
        :param peer:
        :type peer:
        :param sender:
        :type sender:
        :param bus:
        :type bus:
        :param topic:
        :type topic:
        :param header:
        :type header:
        :param message:
        :type message:
        :return:
        :rtype:
        """
        _log.debug(f'Update data : {topic}')
        payload = {}
        data, meta = message
        if Points.outdoorairtemperature.value in data:
            payload[Points.outdoorairtemperature.value] = data[Points.outdoorairtemperature.value]
        self.data_handler.update_data(payload, header)

    def change_occupancy(self, state: OccupancyTypes):
        """
        Change RTU occupancy state.

        Makes RPC call to actuator agent to change zone control when zone transitions to occupied/unoccupied mode.

        :param state: str; occupied or unoccupied
        :type state: str
        :return: True if successful, else False
        """

        if isinstance(state, str):
            _log.debug(f'OCCUPANCY STATE IS A STRING Change occupancy state to {state}')
            state = OccupancyTypes[state.upper()]

        # Based upon the values in the configuration, set the occupancy state.
        if state.value in self.cfg.occupancy_values:
            new_occupancy_state = self.cfg.occupancy_values[state.value]
        else:
            new_occupancy_state = state.value

        try:
            result = self.rpc_set_point(Points.occupancy.value, new_occupancy_state)

        except RemoteError as ex:
            _log.warning(f'{self.identity} - Failed to set {self.cfg.system_rpc_path} to {state.value}: {ex}')
            return str(ex)
        return result

    def publish(self, topic: str, headers: dict[str, str], message: dict[str, Any] | dataclass):
        """
        A helper method to publish a message to the message bus.

        :param topic: The topic to publish the message to.
        :type topic: str
        :param headers: The headers to include with the message.
        :type headers: dict
        :param message: The message to publish.
        :type message: dict
        """
        if is_dataclass(message):
            message = asdict(message)

        debug_ref = f'{inspect.stack()[0][3]}()->{inspect.stack()[1][3]}()'
        _log.debug(f'{debug_ref}: {topic} {headers} {message}')
        self.vip.pubsub.publish('pubsub', topic, headers=headers, message=message).get(timeout=10.0)

    def rpc_set_point(self, point: str, value: Any):
        """
        A helper method to call the RPC method on the actuator agent.

        :param point: The point to set the value for.
        :type point: str
        :param value: The value to set the point to.
        :type value: Any
        :return: The result of the RPC call.
        :rtype: Any
        """

        debug_ref = f'{inspect.stack()[0][3]}()->{inspect.stack()[1][3]}()'
        _log.debug(f'Calling: {self.cfg.actuator_identity} set_point -- {self.cfg.system_rpc_path}, {point}, {value}')
        result = self.vip.rpc.call(self.cfg.actuator_identity, 'set_point', self.cfg.system_rpc_path, point,
                                   value).get(timeout=10.0)
        _log.debug(f'{debug_ref}: -> {result}')
        return result

    def rpc_get_point(self, point: str):
        """
        A helper method to call the RPC method on the actuator agent.

        :param point: The point to get the value for.
        :type point: str
        :return: The result of the RPC call.
        :rtype: Any
        """

        result = self.vip.rpc.call(self.cfg.actuator_identity, 'get_point', self.cfg.system_rpc_path,
                                   point).get(timeout=10.0)
        debug_ref = f'{inspect.stack()[0][3]}()->{inspect.stack()[1][3]}()'
        _log.debug(f'{debug_ref}: {self.cfg.system_rpc_path} -- {point} -> {result}')
        return result

    def start_precontrol(self):
        """
        Makes RPC call to driver agent to enable any pre-control
        actions needed for optimal start.
        :return:
        :rtype:
        """
        result = None
        for topic, value in self.precontrols.items():
            try:
                _log.debug('Do pre-control: {} -- {}'.format(topic, value))
                result = self.vip.rpc.call(self.cfg.actuator_identity, 'set_point', topic, value).get(timeout=30)
            except RemoteError as ex:
                _log.warning('Failed to set {} to {}: {}'.format(topic, value, str(ex)))
                continue
        self.precontrol_flag = True
        return result

    def end_precontrol(self):
        """
        Makes RPC call to driver agent to end pre-control
        actions needed for optimal start.
        :return:
        :rtype:
        """
        result = None
        for topic, value in self.precontrols.items():
            try:
                _log.debug('Do pre-control: {} -- {}'.format(topic, 'None'))
                result = self.vip.rpc.call(self.cfg.actuator_identity, 'set_point', 'optimal_start', topic,
                                           None).get(timeout=30)
            except RemoteError as ex:
                _log.warning('Failed to set {} to {}: {}'.format(topic, value, str(ex)))
                continue
        self.precontrol_flag = False
        return result


def main(argv=sys.argv):
    """Main method called by the aip."""
    try:
        utils.vip_main(OptimalStart)
    except Exception as exception:
        _log.exception("unhandled exception")
        _log.error(repr(exception))


if __name__ =='__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
