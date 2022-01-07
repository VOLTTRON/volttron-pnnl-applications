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

import os
import sys
import logging

from datetime import timedelta as td, datetime as dt
import uuid
from dateutil.parser import parse
import numpy as np

import pandas as pd
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod
import dateutil.tz

from volttron.platform.agent.utils import setup_logging, format_timestamp, get_aware_utc_now
from volttron.platform.agent.math_utils import mean, stdev
from volttron.platform.vip.agent import Agent, Core

from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.error_codes import NOT_FORMED, SHORT_OFFERS, BAD_STATE, NO_INTERSECT
from volttron.platform.agent.base_market_agent.buy_sell import BUYER


__version__ = "0.2"

setup_logging()
_log = logging.getLogger(__name__)


class DataHandler:
    def __init__(self, config, parent):
        campus = config.get("campus", "")
        building = config.get("building", "")
        logging_topic = config.get("logging_topic", "record")
        self.parent = parent
        self.target_topic = '/'.join(['record', 'target_agent', campus, building, 'goal'])
        self.logging_topic = '/'.join([logging_topic, campus, building, "TCILC"])

        self.device_topic_list = []
        self.device_topic_map = {}
        all_devices = config.get("zones")
        occupancy_schedule = config.get("occupancy_schedule", False)
        self.device_data = {}
        self.device_points = {}
        for device_name, info in all_devices.items():
            _log.debug("DEVICE %s -- info %s", device_name, info)
            points = info["points"]
            device_topic = topics.DEVICES_VALUE(campus=campus,
                                                building=building,
                                                unit=device_name,
                                                path="",
                                                point="all")

            self.device_topic_list.append(device_topic)
            self.device_topic_map[device_topic] = device_name
            self.device_points[device_name] = points
            self.device_data[device_name] = {}
        oat_data = config.get("oat_data", {})
        self.oat_topic = topics.DEVICES_VALUE(campus=campus,
                                              building=building,
                                              unit=oat_data["topic"],
                                              path="",
                                              point="all")
        self.oat_point = oat_data["point"]
        self.current_oat = 75.0
        self.current_time = None

    # def starting_base(self):
    #     """
    #     Startup method:
    #      - Setup subscriptions to  devices.
    #      - Setup subscription to building power meter.
    #     :param sender:
    #     :param kwargs:
    #     :return:
    #     """
    #     for device_topic in self.device_topic_list:
    #         _log.debug("Subscribing to " + device_topic)
    #         self.parent.vip.pubsub.subscribe(peer="pubsub", prefix=device_topic, callback=self.zone_data)
    #     _log.debug("Subscribing to " + self.oat_topic)
    #     self.parent.vip.pubsub.subscribe(peer="pubsub", prefix=self.oat_topic, callback=self.oat_data)

    def zone_data(self, peer, sender, bus, topic, headers, message):
        """
        Call back method for device data subscription.
        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        :return:
        """
        _log.info("Data Received for {}".format(topic))
        # topic of form:  devices/campus/building/device
        device_name = self.device_topic_map[topic]
        points = self.device_points[device_name]
        data = message[0]
        payload = {}
        for key, value in points.items():
            if value in data:
                payload[key] = data[value]
            else:
                _log.debug("Missing data for %s -- point %s", topic, value)
        self.device_data[device_name].update(payload)

    def oat_data(self, peer, sender, bus, topic, headers, message):
        """
        Call back method for device data subscription.
        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        :return:
        """
        _log.info("Data Received for {}".format(topic))
        # topic of form:  devices/campus/building/device
        data = message[0]
        self.current_oat = data[self.oat_point]
        self.current_time = parse(headers["Date"])
