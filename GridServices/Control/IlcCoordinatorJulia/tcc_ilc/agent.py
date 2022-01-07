"""
Copyright (c) 2021, Battelle Memorial Institute
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
import requests
import csv
from datetime import timedelta as td, datetime as dt
import uuid
from dateutil.parser import parse
import numpy as np

import pandas as pd
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod
from .data_handler import DataHandler
from volttron.platform.agent.utils import setup_logging, format_timestamp, get_aware_utc_now
from volttron.platform.vip.agent import Agent, Core


__version__ = "0.1"

setup_logging()
_log = logging.getLogger(__name__)


class JuliaCoordinator(Agent):
    def __init__(self, config_path, **kwargs):
        super(JuliaCoordinator, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        self.device_handler = DataHandler(config, self)
        campus = config.get("campus", "")
        self.url = config.get('url', 'http://127.0.0.1:5000')
        self.current_time = None
        self.simulation = config.get("simulation", True)
        self.weather_file = config.get("weather_file", '')
        self.default_setpoint_schedule = config.get("default_setpoint_schedule", [])
        self.weather_data = None
        building = config.get("building", "")
        logging_topic = config.get("logging_topic", "record")
        self.target_topic = '/'.join(['record', 'target_agent', campus, building, 'goal'])
        self.run_frequency = config.get()
        self.last_modified = None
        if self.simulation:
            self.init_weather_data()
            self.get_weather_data = self.get_forecast_file
        else:
            self.get_weather_data = self.get_forecast_rpc
        self.run_topic = topics.DEVICES_VALUE(campus=campus,
                                              building=building,
                                              unit=config["run_topic"],
                                              path="",
                                              point="all")

    def create_device_subs(self):
        """
        Startup method:
         - Setup subscriptions to  devices.
         - Setup subscription to building power meter.
        :param sender:
        :param kwargs:
        :return:
        """
        for device_topic in self.device_handler.device_topic_list:
            _log.debug("Subscribing to " + device_topic)
            self.vip.pubsub.subscribe(peer="pubsub", prefix=device_topic, callback=self.device_handler.zone_data)
        _log.debug("Subscribing to " + self.device_handler.oat_topic)
        self.vip.pubsub.subscribe(peer="pubsub", prefix=self.device_handler.oat_topic, callback=self.device_handler.oat_data)

    @Core.receiver("onstart")
    def starting_base(self, sender, **kwargs):
        """
        Startup method:
         - Setup subscriptions to  devices.
         - Setup subscription to building power meter.
        :param sender:
        :param kwargs:
        :return:
        """
        self.vip.pubsub.subscribe(peer="pubsub", prefix=self.run_topic, callback=self.check_run)
        self.create_device_subs()

    def check_run(self, peer, sender, bus, topic, headers, message):
        current_time = parse(headers["Date"])
        # make this configurable
        if self.current_time is not None:
            if self.current_time.hour != current_time.hour:
                self.get_target()
        self.current_time = current_time

    def get_target(self):
        data = self.construct_julia_payload()
        _log.debug("Data payload %s", data)
        target = requests.post('{0}/calculate'.format(self.url), data=data).json()
        self.publish_demand_limit(target, str(uuid.uuid1()))

    def construct_julia_payload(self):
        data = {}
        setpoint_trajectory = self.default_setpoint_schedule[self.current_time.hour:]
        setpoint_trajectory.extend(self.default_setpoint_schedule[:self.current_time.hour])
        data["Tproj"] = setpoint_trajectory
        for device, data_dict in self.device_handler.device_data.items():
            for name, value in data_dict.items():
                name_index = name[-1]
                data[name] = value
            tproj_name = "Trzon" + name_index
            data[tproj_name] = setpoint_trajectory
        data.update({self.device_handler.oat_point: self.device_handler.current_oat})
        weather_data = self.get_weather_data()
        data["forecast"] = weather_data
        data["Time"] = self.current_time.timestamp()
        return data

    def publish_demand_limit(self, demand_goal, task_id):
        """
        Publish the demand goal determined by clearing price.
        :param demand_goal:
        :param task_id:
        :return:
        """
        _log.debug("Updating demand limit: {}".format(demand_goal))
        start_time = format(self.current_time)
        end_time = format_timestamp(self.current_time.replace(hour=23, minute=59, second=59))
        _log.debug("Publish target: {}".format(demand_goal))
        headers = {'Date': start_time}
        target_msg = [
            {
                "value": {
                    "target": demand_goal,
                    "start": start_time,
                    "end": end_time,
                    "id": task_id
                    }
            },
            {
                "value": {"tz": "UTC"}
            }
        ]
        self.vip.pubsub.publish('pubsub', self.target_topic, headers, target_msg).get(timeout=15)

    def init_weather_data(self):
        """
        To init or re-init weather data from file.
        :return:
        """
        # Get latest modified time
        cur_modified = os.path.getmtime(self.weather_file)

        if self.last_modified is None or cur_modified != self.last_modified:
            self.last_modified = cur_modified

            # Clear weather_data for re-init
            self.weather_data = []
            try:
                with open(self.weather_file) as f:
                    reader = csv.DictReader(f)
                    self.weather_data = [r for r in reader]
                    for rec in self.weather_data:
                        rec['Timestamp'] = parse(rec['Timestamp']).replace(minute=0, second=0, microsecond=0)
                        rec['Value'] = float(rec['Value'])
            except:
                self.weather_data = []
                _log.debug("WEATHER - problem parsing weather file!")
        #_log.debug("Weather data: %s", self.weather_data)

    def get_forecast_file(self):
        self.init_weather_data()
        data = []
        if self.current_time is None:
            _log.debug("No current time information, cannot get forecast!")
            return
        # Copy weather data to predictedValues
        for x in range(24):
            # Find item which has the same timestamp as ti.timeStamp
            start_time = self.current_time.replace(minute=0, tzinfo=None) + td(hours=x+1)
            items = [x for x in self.weather_data if x['Timestamp'] == start_time]
            # None exist, raise exception
            if len(items) == 0:
                raise Exception('No weather data for time: {}'.format(start_time))
            temp = items[0]['Value']
            data.append(temp)
        return data


def main(argv=sys.argv):
    """Main method called by the aip."""
    try:
        utils.vip_main(JuliaCoordinator)
    except Exception as exception:
        _log.exception("unhandled exception")
        _log.error(repr(exception))


if __name__ == "__main__":
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
