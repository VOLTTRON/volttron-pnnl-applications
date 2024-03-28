# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2024, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}


import logging
import sys

import gevent
from volttron.platform.agent import utils

from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.jsonrpc import RemoteError


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '1.0'


class MultiplatformCoordinator(Agent):
    """
    Multiplatform Coordinator
    """

    def __init__(self, config_path, **kwargs):
        super().__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.configured_platforms = self.config.get("connected_platforms")
        self.routing_table = {}
        self.register_subscriptions = {}

    def check_routing(self, platform, identity):
        """
        Check if platform and identity are in the routing table.
        :param platform: external platform
        :type platform: str
        :param identity: vip-identity of agent
        :type identity: str
        :return:
        """
        if platform in self.routing_table and identity in self.routing_table[platform]:
            return True
        else:
            return False

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        for platform in self.configured_platforms:
            try:
                agent_list = self.vip.rpc.call('control', 'peerlist', external_platform=platform).get(timeout=10)
                self.routing_table[platform] = agent_list
            except gevent.Timeout as ex:
                _log.debug(f'Exception connection to {platform} -- {ex}')
                self.routing_table[platform] = []

    @RPC.export
    def relay(self, data) -> dict | float | str | None:
        """
        Relay data to an external platform
        :param data: dict {'platform': str, 'identity': str, 'function': str, 'args': [], 'kwargs': {}}
        :return: bool
        """
        _log.debug(f'Relaying message: {data}')
        identity = data.get('identity', 'unknown')
        platform = data.get('platform', 'unknown')
        function = data.get('function', 'unknown')
        args = data.get('args', [])
        kwargs = data.get('kwargs', {})
        result = {}
        if self.check_routing(platform, identity):
            try:
                result = self.vip.rpc.call(identity, function, *args, **kwargs, external_platform=platform).get(timeout=10)
            except (gevent.Timeout, RemoteError) as ex:
                _log.debug(f'Exception connection to {platform} - identity: {identity} -- function: {function} -- {ex}')
        return result

    @RPC.export
    def register_subscription(self, data) -> bool:
        """
        Register a subscription for a given topic
        :param data: dict {'platform': str, 'topic': str, 'identity': str, 'function': str}
        :return: bool
        """
        _log.debug(f'Registering subscription: {data}')
        try:
            topic = data.pop('topic')
            self.vip.pubsub.subscribe(peer='pubsub', prefix=topic, callback=self.subscription_handler, all_platforms=True).get(timeout=10)
            self.register_subscriptions[topic] = data
            return True
        except (gevent.Timeout, RemoteError) as ex:
            _log.error(f'Failed to set configurations: {ex}', exc_info=True)
            return False

    def subscription_handler(self, peer, sender, bus, topic, headers, message):
        """
        Handle subscriptions from remotes platforms.
        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        :return:
        """
        _log.debug(f'Received message from {peer} on {topic}: {message}')
        if topic in self.register_subscriptions:
            data = self.register_subscriptions[topic]
            identity = data.get('identity', 'unknown')
            platform = data.get('platform', 'unknown')
            function = data.get('function', 'unknown')
            if self.check_routing(platform, identity):
                try:
                    self.vip.rpc.call(identity, function, message, external_platform=platform).get(timeout=10)
                except (gevent.Timeout, RemoteError) as ex:
                    _log.error(f'Failed to call {function} on {identity} on {platform}: {ex}', exc_info=True)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(MultiplatformCoordinator, version=__version__)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
