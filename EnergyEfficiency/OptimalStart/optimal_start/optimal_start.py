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
import csv
from dateutil import parser, tz
from datetime import timedelta as td, datetime as dt

import pandas as pd
import dill
from dateutil.parser import parse
from .model import Johnson, Siemens, Carrier
from volttron.platform.agent import utils
from volttron.platform.scheduling import cron
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.utils import (setup_logging, format_timestamp, get_aware_utc_now, parse_timestamp_string)
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError
import gevent


pd.set_option('display.max_rows', None)
__author__ = "Robert Lutes, robert.lutes@pnnl.gov"
__version__ = "0.0.1"

setup_logging()
_log = logging.getLogger(__name__)


class OptimalStart(Agent):
    def __init__(self, config_path, **kwargs):
        super(OptimalStart, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        # topic for device level data
        self.campus = config.get("campus", "")
        self.building = config.get("building", "")
        self.device = config.get("system", "")
        self.results_topic = "record/{}/{}/{}/OptimalStart".format(self.campus, self.building, self.device)
        self.system_rpc_path = ""
        timezone = config.get("local_tz", "UTC")
        self.controller = config.get("controller", "s")
        try:
            self.local_tz = tz.gettz(timezone)
        except:
            self.local_tz = tz.gettz("UTC")
        # No precontrol code yet, this might be needed in future
        self.precontrols = config.get("precontrols", {})
        self.precontrol_flag = False
        self.system_status_point = config.get("system_status_point", None)
        self.zone_point_names = config.get("zone_point_names")
        self.actuator = config.get("actuator", "platform.actuator")
        self.earliest_start_time = config.get("earliest_start_time", 120)
        self.latest_start_time = config.get("latest_start_time", 10)
        self.t_error = config.get("allowable_setpoint_deviation", 0.5)
        self.system_occ_switch = 0
        self.df = None
        self.run_sched = None
        self.current_time = None
        self.zone_control = config.get("zone_control", {})
        self.start_obj = None
        self.end_obj = None
        self.schedule = {}
        self.init_schedule(config.get("schedule", {}))
        self.day_map = {0: "s", 1: "s", 2: "c", 3: "c", 4: "j"}
        if not self.schedule:
            _log.debug("No schedule configured, exiting!")
            self.core.stop()
        self.model_path = os.path.expanduser("~/models")
        self.models = {"j": None, "s": None, "c": None}
        try:
            for tag in self.models:
                _file = self.model_path + "/{}_{}.pickle".format(self.device, tag)
                with open(_file, 'rb') as f:
                    _cls = dill.load(f)
                self.models[tag] = _cls
        except Exception as ex:
            _log.debug("Exception loading pickle!: {}".format(ex))
            j = Johnson(config, self.schedule)
            s = Siemens(config, self.schedule)
            c = Carrier(config, self.schedule)

            self.models = {"j": j, "s": s, "c": c}

        self.core.schedule(cron('1 0 * * *'), self.set_up_run)
        self.core.schedule(cron('0 9 * * *'), self.train_models)

    def init_schedule(self, schedule):
        """
        Parse schedule for use in determining occupancy.
        :param schedule:
        :return:
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

    @Core.receiver("onstart")
    def starting_base(self, sender, **kwargs):
        """
        Startup method:
         - Setup subscriptions to devices.
        :param sender:
        :param kwargs:
        :return:
        """
        _log.debug("Starting!")
        base_device_topic = topics.DEVICES_VALUE(campus=self.campus,
                                                 building=self.building,
                                                 unit="",
                                                 path=self.device,
                                                 point="all")
        _log.debug("Starting %s", base_device_topic)
        self.system_rpc_path = topics.RPC_DEVICE_PATH(campus=self.campus,
                                                      building=self.building,
                                                      unit=self.device,
                                                      path="",
                                                      point=None)

        self.vip.pubsub.subscribe(peer="pubsub",
                                  prefix=base_device_topic,
                                  callback=self.update_data)
        _log.debug("Subscribing to %s", base_device_topic)

    def train_models(self):
        """
        Run daily after startup to update model coefficients.
        Save each model class as a pickle to allow saving state.
         - train each model with morning startup data.
         - Save model as pickle on disk for saving state.
        :return:
        """
        for tag, model in self.models.items():
            try:
                model.train(self.df)
            except:
                _log.debug("ERROR training model: {}".format(tag))
                continue
            try:
                _file = self.model_path + "/{}_{}.pickle".format(self.device, tag)
                with open(_file, 'wb') as f:
                    dill.dump(model, file=f)
            except Exception as ex:
                _log.debug("Could not store object %s -- %s", tag, ex)
            try:
                msg = model.__dict__
                _log.debug("MODEL: {}".format(msg))
                if 'schedule' in msg:
                    sched = msg.pop('schedule')
                headers = {"Date": format_timestamp(get_aware_utc_now())}
                self.vip.pubsub.publish("pubsub", self.results_topic, headers, msg)
            except:
                _log.debug("ERROR publishing result!")
                continue

    def assign_local_tz(self, _dt):
        """
        Convert UTC time from driver to local time.
        """
        if _dt.tzinfo is None or _dt.tzinfo.utcoffset(_dt) is None:
            _log.debug("TZ: %s", _dt)
            return _dt
        else:
            _dt = _dt.astimezone(self.local_tz)
            _log.debug("TZ: %s", _dt)
            return _dt

    def update_data(self, peer, sender, bus, topic, header, message):
        """
        Store current data measurements in daily data df.
        """
        _log.debug("Update data : %s", topic)
        data, meta = message
        _now = parser.parse(header[headers_mod.TIMESTAMP])
        stored_data = {}
        current_time = self.assign_local_tz(_now)
        self.current_time = current_time
        for point, value in data.items():
            if point in self.zone_point_names.values():
                _key = list(filter(lambda x: self.zone_point_names[x] == point, self.zone_point_names))[0]
                stored_data[_key] = [value]
        if stored_data:
            stored_data['ts'] = [current_time]
            df = pd.DataFrame.from_dict(stored_data)
            df['timeindex'] = df['ts']
            df = df.set_index(df['timeindex'])
            if self.df is not None:
                self.df = pd.concat([self.df, df], axis=0, ignore_index=False)
            else:
                self.df = df
            self.df.to_csv("data.csv")
            _log.debug("Dataframe: {}".format(self.df))

    def process_data(self):
        """
        Save data to disk, save 15 days of data.
        """
        try:
            df = pd.read_pickle('data.pkl')
        except:
            _log.debug("Error parsing df pickle!")
            df = None
        try:
            if df is not None:
                df = pd.concat([df, self.df])
            else:
                df = self.df
            data_window = dt.now() - td(days=15)
            df = df[df['ts'] >= data_window]
            df.to_pickle('data.pkl')
        except:
            _log.debug("Error saving df pickle!")
        self.df = None

    def set_up_run(self):
        """
        Run based daily based on cron schedule.  This method calculates the earliest start time
        and schedules the run_method.
        """
        _log.debug("Setting up run!")
        _now = dt.now()
        _day = _now.weekday()
        if self.schedule:
            sched = self.schedule[_day]
            earliest = sched.get('earliest')
            if earliest is not None:
                e_hour = earliest.hour
                e_minute = earliest.minute
                run_time = _now.replace(hour=e_hour, minute=e_minute)
                _log.debug("Schedule run method: %s", format_timestamp(run_time))
                self.run_sched = self.core.schedule(run_time, self.run_method)
        self.process_data()

    def run_method(self):
        """
        Run at the earliest start time for the day.  Uses models to calculate needed
        prestart time to meet room temperature requirements.
        """
        _now = dt.now()
        _day = _now.weekday()
        result = {}
        if self.schedule:
            sched = self.schedule[_day]
            start = sched.get('start')
            end = sched.get('end')
            s_hour = start.hour
            s_minute = start.minute
            e_hour = end.hour
            e_minute = end.minute
            occupancy_time = _now.replace(hour=s_hour, minute=s_minute)
            unoccupied_time = _now.replace(hour=e_hour, minute=e_minute)
            if start is not None:
                for tag, model in self.models.items():
                    prestart_time = model.calculate_prestart(self.df)
                    result[tag] = prestart_time
                result['occupancy'] = format_timestamp(occupancy_time)
            controller = self.day_map[_day]
            active_minutes = result[controller]
            active_minutes = max(self.latest_start_time, min(active_minutes, self.earliest_start_time))
            prestart_time = occupancy_time - td(minutes=active_minutes)
            _log.debug("Optimal start result: %s", result)
            self.start_obj = self.core.schedule(prestart_time, self.do_zone_control, "occupied")
            self.end_obj = self.core.schedule(unoccupied_time, self.do_zone_control, "unoccupied")

    def get_system_occupancy(self):
        """
        Call actuator get_point on system occupancy.
        :return:
        """
        result = None
        try:
            result = self.vip.rpc.call(self.actuator, "get_point", self.system_rpc_path).get(timeout=30)
            _log.debug("Do system get: {} -- {}".format(self.system_rpc_path, result))
        except (RemoteError, gevent.Timeout) as ex:
            _log.warning("Failed to get {}: {}".format(self.system_rpc_path, str(ex)))
        return result

    def do_zone_control(self, state):
        """
        Makes RPC call to actuator agent to change zone control when zone transition to occupied
            or unoccupied mode.
        :param rpc_path: str; device path used by actuator agent set_point method
        :param control: dict; key - str for control point; value - value to set for control
        :return:
        """
        control = self.zone_control[state]
        for point, value in control.items():
            topic = self.system_rpc_path(point=point)
            _log.debug("Do control: {} -- {}".format(topic, value))
            if value == "None":
                value = None
            try:
                result = self.vip.rpc.call(self.actuator, "set_point", "optimal_start", topic, value).get(timeout=30)
            except RemoteError as ex:
                _log.warning("Failed to set {} to {}: {}".format(topic, value, str(ex)))
            continue

    def do_system_control(self):
        """
        Makes RPC call to actuator agent to change system mode  when there is an occupancy
            mode change
        :return:
        """
        result = None
        try:
            _log.debug("Do system control: {} -- {} -- {}".format(self.rt_time, self.system_rpc_path, self.system_occ_switch))
            result = self.vip.rpc.call(self.actuator, "set_point", "optimal_start", self.system_rpc_path, self.system_occ_switch).get(timeout=30)
        except RemoteError as ex:
            _log.warning("Failed to set {} to {}: {}".format(self.system_rpc_path, self.system_occ_switch, str(ex)))
        return

    def start_precontrol(self):
        """
        Makes RPC call to actuator agent to enable any pre-control actions needed for SBS
        :return:
        """
        result = None
        for topic, value in self.precontrols.items():
            try:
                _log.debug("Do pre-control: {} -- {} -- {}".format(self.rt_time, topic, value))
                result = self.vip.rpc.call(self.actuator, "set_point", "optimal_start", topic, value).get(timeout=30)
            except RemoteError as ex:
                _log.warning("Failed to set {} to {}: {}".format(topic, value, str(ex)))
                continue
        self.precontrol_flag = True
        return

    def end_precontrol(self):
        """
        Makes RPC call to actuator agent to change system mode  when there is an occupancy
            mode change
        :return:
        """
        result = None
        for topic, value in self.precontrols.items():
            try:
                _log.debug("Do pre-control: {} -- {} -- {}".format(self.rt_time, topic, "None"))
                result = self.vip.rpc.call(self.actuator, "set_point", "optimal_start", topic, None).get(timeout=30)
            except RemoteError as ex:
                _log.warning("Failed to set {} to {}: {}".format(topic, value, str(ex)))
                continue
        return


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