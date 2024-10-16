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
from collections import defaultdict
from typing import Dict, Tuple, List, Any

import gevent
from volttron.platform.agent import utils

from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.jsonrpc import RemoteError

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '2.0'


class MultiplatformCoordinator(Agent):
    def __init__(self, config_path: str, **kwargs):
        super().__init__(**kwargs)
        self.config = utils.load_config(config_path) if config_path else {}
        self.vip.config.set_default("config", self.config)
        self.configured_platforms = self.config.get("connected_platforms")
        self.routing_table = {}
        self.subscription_registry = defaultdict(lambda: defaultdict(dict))
        self.vip.config.subscribe(self.configure_main, actions=['NEW', 'UPDATE'], pattern='config')
        self.error = False

    def check_routing(self, platform: str, identity: str) -> bool:
        """

        Checks if the given platform and identity exist in the routing table.

        Args:
            platform (str): The platform to check in the routing table.
            identity (str): The identity to check for within the platform's entry in the routing table.

        Returns:
            bool: True if both the platform and identity are found in the routing table, False otherwise.

        """
        if platform in self.routing_table and identity in self.routing_table[platform]:
            return True
        else:
            return False

    def update_routing_table(self, platform: str):
        """
        Update the routing table with the list of agents found on the specified platform

        Args:
            platform (str): The platform to query for the list of agents

        This method queries control for a list of agents on the specified platform and
        updates the local routing table with this information. If the query fails due to a timeout or
        remote error, the routing table entry for the platform is set to an empty list.

        Raises:
            gevent.Timeout: If the RPC call times out
            RemoteError: If there is an error in the remote call
        """
        try:
            agent_list = self.vip.rpc.call('control', 'peerlist', external_platform=platform).get(timeout=10)
            _log.debug(f'Update routing table for {platform}: {agent_list}')
            self.routing_table[platform] = agent_list
        except (gevent.Timeout, RemoteError) as ex:
            _log.debug(f'Exception on connection to {platform} -- {ex}')
            self.routing_table[platform] = []

    def create_routing_table(self):
        """
        Creates and initializes the routing table for the configured platforms.

        This method sets up an empty routing table and iterates over the list
        of configured platforms to update the routing information for each platform.

        The routing table is a dictionary where routing information such as
        routes and destinations will be stored. The update_routing_table method
        is called for each platform in the list of configured platforms, populating
        the routing table with the necessary data.

        Raises:
            KeyError: If a required key is missing in the platform configuration.
            ValueError: If there is an invalid value in the platform configuration.
        """
        self.routing_table = {}
        for platform in self.configured_platforms:
            self.update_routing_table(platform)

    def configure_main(self, config_name: str, action: str, contents: Dict[str, Any]):
        """
        Configures the main settings for the platform.

        Args:
            config_name (str): The name of the configuration to apply.
            action (str): The action to perform with the configuration.
            contents (dict): The configuration settings to apply.

        Sets:
            self.config: The configuration contents.
            self.configured_platforms: List of connected platforms from the configuration.

        Calls:
            create_routing_table: Method to create the routing table based on the configuration.
        """
        self.config = contents
        self.configured_platforms = self.config.get("connected_platforms")
        self.create_routing_table()

    @RPC.export
    def relay(self, platform: str, identity: str, function: str, *args, **kwargs) -> Any:
        """
            Export method to relay messages between platforms.

            The relay method allows communication between different platforms by routing
            a given function call along with its arguments to the specified platform and
            identity. If the routing check succeeds, the function attempts a remote
            procedure call (RPC) with a specified timeout. Potential exceptions are handled
            and logged.

            Args:
                platform (str): The target platform to which the message is to be relayed.
                identity (str): The identity of the recipient on the target platform.
                function (str): The name of the function to be called remotely.
                *args: Variable length argument list to pass to the remote function.
                **kwargs: Arbitrary keyword arguments to pass to the remote function.

            Returns:
                Any: The result from the remote procedure call, if successful; otherwise, None.
        """
        _log.debug(f'Relaying message: {platform} - identity: {identity}')
        result = None
        if self.check_routing(platform, identity):
            try:
                result = self.vip.rpc.call(identity, function, *args, **kwargs,
                                           external_platform=platform).get(timeout=10)
            except (gevent.Timeout, RemoteError) as ex:
                _log.debug(f'Exception connection to {platform} - identity: {identity} -- function: {function} -- {ex}')
                self.update_routing_table(platform)
        return result

    @RPC.export
    def register_subscription(self, data: Dict[str, str]) -> bool:
        """
        Registers a subscription for the given topic with the pub/sub service.

        Args:
            data (dict): A dictionary containing subscription details:
                         - 'topic' (str): The topic to subscribe to.
                         - 'all_platforms' (bool, optional): Whether to subscribe across all platforms. Defaults to False.

        Returns:
            bool: True if subscription was successful, False otherwise.

        Raises:
            gevent.Timeout: If the subscription attempt times out.
            RemoteError: If there is an error from the remote service.
        """
        _log.debug(f'Registering subscription: {data}')
        try:
            topic = data['topic']
            all_platforms = data.get('all_platforms', False)
            self.vip.pubsub.subscribe(peer='pubsub', prefix=topic, callback=self.subscription_handler,
                                      all_platforms=all_platforms).get(timeout=10)
            self.build_subscription_map(data)
            return True
        except (gevent.Timeout, RemoteError) as ex:
            _log.debug(f'Failed to set configurations: {ex}', exc_info=True)
            return False

    def build_subscription_map(self, data: Dict[str, str]):
        """
        Builds a subscription map from the provided data.

        Unpacks the subscription payload and updates the routing table and register subscriptions.

        Args:
            data: The subscription data to process. Expected to contain topic, identity, platform, and callback information.

        Returns:
            None
        """
        topic, platform, identity, callback = self.unpack_subscription_payload(data)
        self.update_routing_table(platform)
        _log.debug(f'Updating routing table: {self.routing_table}')
        self.subscription_registry[topic][platform][identity] = callback
        self.update_routing_table(platform)
        self.unregister_subscription()

    def unregister_subscription(self):
        """
        Cleans up invalid subscriptions and empty topics from the current subscription list.

        The function performs the following actions:
        - Calls the `cleanup_invalid_subscriptions` method to remove any invalid subscriptions.
        - Calls the `cleanup_empty_topics` method to remove any empty topics.
        """
        _log.debug(f'Running unsubscribe methods!')
        self.cleanup_invalid_subscriptions()
        self.cleanup_empty_topics()

    def cleanup_invalid_subscriptions(self):
        """
        Removes invalid subscriptions from the subscription_registry dictionary.

        Identifies invalid subscriptions by checking if routing exists for each identity in the subscription.
        If routing does not exist, the identity is marked for cleanup.

        This function iterates through each topic, platform, and identity in the subscription_registry dictionary.
        If an identity is found to be invalid, it is added to a temporary cleanup dictionary.
        After identifying all invalid subscriptions, it removes them from the original subscription_registry dictionary.
        """
        cleanup = defaultdict(lambda: defaultdict(list))

        for topic, topic_payload in self.subscription_registry.items():
            for platform, identities in topic_payload.items():
                for identity in identities:
                    if not self.check_routing(platform, identity):
                        cleanup[topic][platform].append(identity)
        _log.debug(f'Running cleanup_invalid_subscriptions {cleanup}')
        for topic, platforms in cleanup.items():
            for platform, identities in platforms.items():
                for identity in identities:
                    self.subscription_registry[topic][platform].pop(identity, None)
        _log.debug(f'Execute cleanup_invalid_subscriptions {self.subscription_registry}')

    def cleanup_empty_topics(self):
        """
        Cleans up empty topics from the subscription registry and unsubscribes them from the pubsub system.

        This method iterates over the registered subscriptions to identify topics with no associated payloads.
        For each identified empty topic, it removes the topic from the subscription registry and unsubscribes from the pubsub system.

        """
        empty_topics = []
        all_topics = list(self.subscription_registry.keys())
        for topic in all_topics:
            if all(not payload for payload in self.subscription_registry[topic].values()):
                empty_topics.append(topic)
        _log.debug(f'Running cleanup_empty_topics {empty_topics}')
        for topic in empty_topics:
            self.subscription_registry.pop(topic, None)
            self.vip.pubsub.unsubscribe(peer='pubsub',
                                        prefix=topic,
                                        callback=self.subscription_handler).get(timeout=10)

    @staticmethod
    def unpack_subscription_payload(data: Dict[str, str]) -> Tuple[str, str, str, str]:
        """
            Unpacks subscription payload from a dictionary and returns individual components.

            Args:
                data (dict[str, str]): The dictionary containing subscription information.

            Returns:
                tuple[str, str, str, str]: A tuple containing the topic, platform, identity, and callback function name.
        """
        topic = data['topic']
        identity = data['identity']
        platform = data['platform']
        callback = data['function']
        return topic, platform, identity, callback

    def subscription_handler(self, peer: str, sender: str, bus: str,
                             topic: str, headers: str, message: Any) -> None:
        """
        Handles incoming subscriptions by forwarding messages to appropriate subscribed platforms and identities.

        Args:
            peer (str): The peer from which the message is received.
            sender (str): The sender of the message.
            bus (str): The bus on which the message is received.
            topic (str): The topic of the message.
            headers (dict): Headers associated with the message.
            message (Any): The message payload.

        Logs:
            Logs debug information about received message and callback routing.

        Exceptions:
            Handles gevent.Timeout and RemoteError exceptions during RPC call and logs errors appropriately.

        """
        _log.debug(f'Received message from {peer} on {topic}')
        on_error = False
        subscriptions = self.subscription_registry.get(topic, {})
        for platform, platform_payload in subscriptions.items():
            for identity, callback in platform_payload.items():
                _log.debug(f'Sending to {platform} -- {identity} with callback {callback}')
                if self.check_routing(platform, identity):
                    try:
                        self.vip.rpc.call(identity, callback, headers, message,
                                          external_platform=platform).get(timeout=10)
                    except (gevent.Timeout, RemoteError) as ex:
                        on_error = True
                        self.update_routing_table(platform)
                        _log.error(f'Failed to call {callback} for {identity} on {platform}: {ex}')
        if on_error:
            self.unregister_subscription()


def main(argv=sys.argv):
    """Main method called by the eggsecutable."""
    try:
        utils.vip_main(MultiplatformCoordinator, version=__version__)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
