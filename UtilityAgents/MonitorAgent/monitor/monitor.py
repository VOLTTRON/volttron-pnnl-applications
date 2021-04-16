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
jurisdiction or organization that has cooperated in the development of these
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
operated by
BATTELLE
for the
UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
"""

import logging
import datetime
import sys
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import (setup_logging, format_timestamp, get_aware_utc_now, parse_timestamp_string)
from volttron.platform.vip.agent import Agent, Core
from sympy import symbols
from sympy.parsing.sympy_parser import parse_expr

__version__ = "1.0.0"

setup_logging()
_log = logging.getLogger(__name__)


class Rules(object):
    def __init__(self, rule, parent):
        condition = rule.get("condition")
        self.condition = parse_expr(condition)
        # input is a  dictionary where keys are
        # topics and value is list of points
        inputs = rule.get("inputs")
        self.parent = parent
        self.alert_message = rule.get("alert_message", "")

        self.duration = rule.get("duration", 15)
        self.master_topic_list = []
        self.device_topic_values = {}
        self.disable_actuation = rule.get("disable_actuation", False)
        self.disable_actuation_payload = rule.get("disable_actuation_payload", {})
        self.condition_status = {'status': False, "initial_time": datetime.datetime.now(), "current_time": datetime.datetime.now()}
        for _topic, points in inputs.items():
            self.device_topic_values[_topic] = dict.fromkeys(points, None)
            self.master_topic_list.append(_topic)
        self.working_topic_list = list(self.master_topic_list)

    def ingest_data(self, topic, data, timestamp):
        for point in self.device_topic_values[topic]:
            if point in data:
                self.device_topic_values[topic][point] = data[point]
        self.working_topic_list.remove(topic)
        if not self.working_topic_list:
            self.evaluate(timestamp)
            self.working_topic_list = list(self.master_topic_list)

    def evaluate(self, timestamp):
        data_values = []

        for topic in self.device_topic_values:
            data_values.append(self.device_topic_values[topic].items())
        condition_value = bool(self.condition.subs(data_values[0]))
        _log.debug("condition: {} - data {} - evaluate: {}".format(self.condition, data_values, condition_value))
        previous_status = self.condition_status['status']

        if condition_value and not previous_status:
            self.condition_status['status'] = condition_value
            self.condition_status['initial_time'] = timestamp
            self.condition_status['current_time'] = timestamp
        if not condition_value and not previous_status:
            self.condition_status['status'] = condition_value
            self.condition_status['initial_time'] = timestamp
            self.condition_status['current_time'] = timestamp
        if condition_value and previous_status:
            start_time = self.condition_status['initial_time']
            if (timestamp - start_time) > datetime.timedelta(minutes=self.duration):
                self.condition_status['initial_time'] = timestamp
                self.condition_status['current_time'] = timestamp
                message = self.parent.construct_message(self.alert_message)
                self.parent.vip.pubsub.publish("pubsub", topics.PLATFORM_SEND_EMAIL, headers={}, message=message)
                if self.disable_actuation and self.disable_actuation_payload:
                    self.publish_disable_actuation()

    def publish_disable_actuation(self):
        topic = self.disable_actuation_payload.get("topic", "")
        message = self.disable_actuation_payload.get("message", 0)
        header = self.disable_actuation_payload.get("header", {})
        self.parent.vip.pubsub.publish("pubsub", topic, headers=header, message=message)

    def new_data(self, peer, sender, bus, topic, header, message):
        """
        Call back method for curtailable device data subscription.
        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        :return:
        """
        now = parse_timestamp_string(header[headers_mod.TIMESTAMP])
        data = message[0]
        self.ingest_data(topic, data, now)


class Monitor(Agent):
    def __init__(self, config_path, **kwargs):
        super(Monitor, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        rules = config.get("rules")
        self.email_list = config.get("email_list", [])
        self.rules_container = []
        for rule in rules:
            self.rules_container.append(Rules(rule, self))

    @Core.receiver("onstart")
    def starting_base(self, sender, **kwargs):
        """
        Startup method:
         - Setup subscriptions to curtailable devices.
         - Setup subscription to building power meter.
        :param sender:
        :param kwargs:
        :return:
        """
        for rule in self.rules_container:
            for device_topic in rule.device_topic_values:
                _log.debug("Subscribing to " + device_topic)
                self.vip.pubsub.subscribe(peer="pubsub",
                                          prefix=device_topic,
                                          callback=rule.new_data)

    def construct_message(self, alert_message):
        return {
            "to-addresses": self.email_list,
            "subject": alert_message,
            "message": alert_message
        }


def main(argv=sys.argv):
    """Main method called by the aip."""
    try:
        utils.vip_main(Monitor)
    except Exception as exception:
        _log.exception("unhandled exception")
        _log.error(repr(exception))


if __name__ == "__main__":
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass