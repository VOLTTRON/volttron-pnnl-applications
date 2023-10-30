"""
Copyright (c) 2023, Battelle Memorial Institute
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
import pandas as pd
import dill
from dateutil.parser import parse
from volttron.platform.agent import utils
from volttron.platform.scheduling import cron
from volttron.platform.messaging import topics
from volttron.platform.agent.utils import (setup_logging, format_timestamp, get_aware_utc_now)
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError
import gevent
from .data_utils import Data
from .optimal_start_manager import OptimalStartManager
from .holiday_manager import HolidayManager

pd.set_option('display.max_rows', None)
__author__ = "Robert Lutes, robert.lutes@pnnl.gov"
__version__ = "0.0.1"

setup_logging()
_log = logging.getLogger(__name__)


class OptimalStart(Agent):
    def __init__(self, config_path, **kwargs):
        super(OptimalStart, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        self.identity = self.core.identity
        self.config = config
        # topic for device level data
        campus = config.get("campus", "")
        building = config.get("building", "")
        self.device = config.get("system", "")
        self.system_rpc_path = topics.RPC_DEVICE_PATH(campus=campus,
                                                      building=building,
                                                      unit=self.device,
                                                      path="",
                                                      point=None)
        self.base_device_topic = topics.DEVICES_VALUE(campus=campus,
                                                      building=building,
                                                      unit="",
                                                      path=self.device,
                                                      point="all")
        # Result objects for record topic
        self.base_record_topic = self.base_device_topic.replace('devices', 'record')
        self.base_record_topic = self.base_record_topic.rstrip('/all')
        # Configuration for data handler
        timezone = config.get("local_tz", "UTC")
        self.zone_point_names = config.get("zone_point_names")
        setpoint_offset = config.get('setpoint_offset')
        self.data_handler = Data(self.zone_point_names, timezone, self.device, setpoint_offset=setpoint_offset)
        # No precontrol code yet, this might be needed in future
        self.precontrols = config.get("precontrols", {})
        self.precontrol_flag = False
        # Controller parameters
        self.actuator = config.get("actuator", "platform.actuator")
        self.zone_control = config.get("zone_control", {})
        self.day_map = config.get("day_map", {0: "s", 1: "s", 2: "c", 3: "c", 4: "j"})
        self.earliest_start_time = config.get("earliest_start_time", 180)
        self.latest_start_time = config.get("latest_start_time", 0)
        self.schedule = {}
        self.init_schedule(config.get("schedule", {}))
        if not self.schedule:
            _log.debug("No schedule configured, exiting!")
            self.core.stop()
        self.model_path = os.path.expanduser("~/models")
        # Initialize sub-classes
        self.holiday_manager = HolidayManager()
        self.optimal_start = OptimalStartManager(self)

    @Core.receiver("onstart")
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
        _log.debug("Starting!")

        self.vip.pubsub.subscribe(peer="pubsub",
                                  prefix=self.base_device_topic,
                                  callback=self.update_data)
        _log.debug("Subscribing to %s", self.base_device_topic)
        self.optimal_start.setup_optimal_start()

    def init_schedule(self, schedule):
        """
        Parse weekly occupancy schedule.
        @param schedule:
        @type schedule:
        @return:
        @rtype:
        """
        _log.debug("Schedule!")
        if schedule:
            for day_str, schedule_info in schedule.items():
                _day = parse(day_str).weekday()
                if schedule_info not in ["always_on", "always_off"]:
                    start = parse(schedule_info["start"])
                    earliest = start - td(minutes=self.earliest_start_time)
                    end = parse(schedule_info["end"]).time()
                    self.schedule[_day] = {"earliest": earliest.time(), "start": start.time(), "end": end}
                else:
                    self.schedule[_day] = schedule_info
        _log.debug("Schedule!: %s", self.schedule)

    def get_current_schedule(self):
        """
        Get stored value for current days schedule and return.
        @return: current dates occupancy schedule (entries are datetimes).
        @rtype: dict
        """
        current_time = dt.now()
        current_day = current_time.weekday()
        current_schedule = None
        if self.schedule and current_day in self.schedule:
            current_schedule = self.schedule[current_day]
        return current_schedule

    def update_data(self, peer, sender, bus, topic, header, message):
        """
        Update RTU data from driver publish for optimal start, lockout control, and
        economizer control.
        @param peer:
        @type peer:
        @param sender:
        @type sender:
        @param bus:
        @type bus:
        @param topic:
        @type topic:
        @param header:
        @type header:
        @param message:
        @type message:
        @return:
        @rtype:
        """
        _log.debug("Update data : %s", topic)
        self.data_handler.update_data(message, header)

    def get_system_occupancy(self):
        """
        Call driver get_point to get current RTU occupancy status.
        @return:
        @rtype:
        """
        result = None
        try:
            result = self.vip.rpc.call(self.actuator, "get_point", self.system_rpc_path).get(timeout=30)
            _log.debug("Do system get: {} -- {}".format(self.system_rpc_path, result))
        except (RemoteError, gevent.Timeout) as ex:
            _log.warning("Failed to get {}: {}".format(self.system_rpc_path, str(ex)))
        return result

    def occupancy_control(self, state):
        """
        Makes RPC call to driver agent to change zone control when zone transitions to occupied
        or unoccupied mode.
        @param state: transitioning state (occupied or unoccupied)
        @type state: str
        @return: None
        @rtype:
        """
        control = self.zone_control[state]
        for point, value in control.items():
            topic = self.system_rpc_path(point=point)
            _log.debug(f'{self.identity} - Do occupancy control: {topic} -- {value}')
            if value == "None":
                value = None
            try:
                result = self.vip.rpc.call(self.actuator, "set_point", "optimal_start", topic, value).get(timeout=30)
            except RemoteError as ex:
                _log.warning("Failed to set {} to {}: {}".format(topic, value, str(ex)))
            continue

    def start_precontrol(self):
        """
        Makes RPC call to driver agent to enable any pre-control
        actions needed for optimal start.
        @return:
        @rtype:
        """
        result = None
        for topic, value in self.precontrols.items():
            try:
                _log.debug("Do pre-control: {} -- {}".format(topic, value))
                result = self.vip.rpc.call(self.actuator, "set_point", "optimal_start", topic, value).get(timeout=30)
            except RemoteError as ex:
                _log.warning("Failed to set {} to {}: {}".format(topic, value, str(ex)))
                continue
        self.precontrol_flag = True
        return result

    def end_precontrol(self):
        """
        Makes RPC call to driver agent to end pre-control
        actions needed for optimal start.
        @return:
        @rtype:
        """
        result = None
        for topic, value in self.precontrols.items():
            try:
                _log.debug("Do pre-control: {} -- {}".format(topic, "None"))
                result = self.vip.rpc.call(self.actuator, "set_point", "optimal_start", topic, None).get(timeout=30)
            except RemoteError as ex:
                _log.warning("Failed to set {} to {}: {}".format(topic, value, str(ex)))
                continue
        return result


def main(argv=sys.argv):
    """Main method called by the aip."""
    try:
        utils.vip_main(OptimalStart)
    except Exception as exception:
        _log.exception("unhandled exception")
        _log.error(repr(exception))


if __name__ == "__main__":
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
