"""
-*- coding: utf-8 -*- {{{
vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

Copyright (c) 2017, Battelle Memorial Institute
All rights reserved.

1.  Battelle Memorial Institute (hereinafter Battelle) hereby grants
    permission to any person or entity lawfully obtaining a copy of this
    software and associated documentation files (hereinafter "the Software")
    to redistribute and use the Software in source and binary forms, with or
    without modification.  Such person or entity may use, copy, modify, merge,
    publish, distribute, sublicense, and/or sell copies of the Software, and
    may permit others to do so, subject to the following conditions:

    -   Redistributions of source code must retain the above copyright notice,
        this list of conditions and the following disclaimers.

    -	Redistributions in binary form must reproduce the above copyright
        notice, this list of conditions and the following disclaimer in the
        documentation and/or other materials provided with the distribution.

    -	Other than as used herein, neither the name Battelle Memorial Institute
        or Battelle may be used in any form whatsoever without the express
        written consent of Battelle.

2.	THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
    AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
    IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
    ARE DISCLAIMED. IN NO EVENT SHALL BATTELLE OR CONTRIBUTORS BE LIABLE FOR
    ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
    DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
    SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
    CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
    LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
    OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
    DAMAGE.

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
BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
}}}
"""
import os
import sys
import logging
import math
from datetime import timedelta as td, datetime as dt
from dateutil import parser
import gevent
import dateutil.tz
from sympy.parsing.sympy_parser import parse_expr
from sympy import symbols
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import (setup_logging, format_timestamp, get_aware_utc_now, parse_timestamp_string)
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError
from ilc.ilc_matrices import (extract_criteria, calc_column_sums,
                              normalize_matrix, validate_input)
from ilc.curtailment_handler import CurtailmentCluster, CurtailmentContainer
from ilc.criteria_handler import CriteriaContainer, CriteriaCluster, parse_sympy


__version__ = "2.0.0"

setup_logging()
_log = logging.getLogger(__name__)


class ILCAgent(Agent):

    def __init__(self, config_path, **kwargs):
        super(ILCAgent, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        campus = config.get("campus", "")
        building = config.get("building", "")

        # For dash board message publishes
        self.agent_id = config.get("agent_id", "Intelligent Load Control Agent")

        dashboard_topic = config.get("dashboard_topic")
        self.application_category = config.get("application_category", "Load Control")
        self.application_name = config.get("application_name", "Intelligent Load Control")

        ilc_start_topic = self.agent_id
        # --------------------------------------------------------------------------------

        # For Target agent updates...
        analysis_prefix_topic = config.get("analysis_prefix_topic", "record")
        self.target_agent_subscription = "{}/target_agent".format(analysis_prefix_topic)
        # --------------------------------------------------------------------------------

        self.update_base_topic = "/".join([analysis_prefix_topic, self.agent_id])
        if campus:
            self.update_base_topic = "/".join([self.update_base_topic, campus])
            ilc_start_topic = "/".join([self.agent_id, campus])
            if dashboard_topic is not None:
                dashboard_topic = "/".join([dashboard_topic, self.agent_id, campus])
        if building:
            self.update_base_topic = "/".join([self.update_base_topic, building])
            ilc_start_topic = "/".join([ilc_start_topic, building])
            if dashboard_topic is not None:
                dashboard_topic = "/".join([dashboard_topic, building])

        self.ilc_topic = dashboard_topic if dashboard_topic is not None else self.update_base_topic
        self.ilc_start_topic = "/".join([ilc_start_topic, "ilc/start"])
        cluster_configs = config["clusters"]
        self.criteria_container = CriteriaContainer()
        self.curtailment_container = CurtailmentContainer()

        for cluster_config in cluster_configs:
            criteria_file_name = cluster_config["pairwise_criteria_file"]

            if criteria_file_name.startswith("~"):
                criteria_file_name = os.path.expanduser(criteria_file_name)

            device_criteria_config = cluster_config["device_criteria_file"]
            device_curtailment_config = cluster_config["device_curtailment_file"]

            cluster_priority = cluster_config["cluster_priority"]
            cluster_actuator = cluster_config.get("cluster_actuator", "platform.actuator")

            criteria_labels, criteria_array = extract_criteria(criteria_file_name)
            col_sums = calc_column_sums(criteria_array)
            row_average = normalize_matrix(criteria_array, col_sums)

            if not validate_input(criteria_array, col_sums):
                _log.debug("Inconsistent criteria matrix. Check configuration "
                           "in: {}" .format(criteria_file_name))
                sys.exit()

            if device_criteria_config[0] == "~":
                device_criteria_config = os.path.expanduser(device_criteria_config)

            criteria_config = utils.load_config(device_criteria_config)
            criteria_cluster = CriteriaCluster(cluster_priority, criteria_labels, row_average, criteria_config)
            self.criteria_container.add_criteria_cluster(criteria_cluster)

            if device_curtailment_config[0] == "~":
                device_curtailment_config = os.path.expanduser(device_curtailment_config)

            curtailment_config = utils.load_config(device_curtailment_config)
            curtailment_cluster = CurtailmentCluster(curtailment_config, cluster_actuator)
            self.curtailment_container.add_curtailment_cluster(curtailment_cluster)
        _log.debug("CURTAILMENT_CONTAINER: {}".format(self.curtailment_container.devices.keys()))
        _log.debug("CRITERIA_CONTAINER: {}".format(self.criteria_container.devices.keys()))

        self.base_rpc_path = topics.RPC_DEVICE_PATH(campus="",
                                                    building="",
                                                    unit="",
                                                    path=None,
                                                    point="")
        self.device_topic_list = []
        all_devices = self.curtailment_container.get_device_topic_set()
        for device_name in all_devices:
            device_topic = topics.DEVICES_VALUE(campus="",
                                                building="",
                                                unit="",
                                                path=device_name,
                                                point="all")

            self.device_topic_list.append(device_topic)

        power_token = config["power_meter"]
        power_meter = power_token["device"]
        self.power_point = power_token["point"]
        demand_formula = power_token.get("demand_formula")
        self.calculate_demand = False

        if demand_formula is not None:
            self.calculate_demand = True
            try:
                demand_operation = parse_sympy(demand_formula["operation"])
                _log.debug("Demand calculation - expression: {}".format(demand_operation))
                self.demand_expr = parse_expr(parse_sympy(demand_operation))
                self.demand_args = parse_sympy(demand_formula["operation_args"])
                self.demand_points = symbols(self.demand_args)
            except (KeyError, ValueError):
                _log.debug("Missing 'operation_args' or 'operation' for setting demand formula!")
                self.calculate_demand = False
            except:
                _log.debug("Unexpected error when reading demand formula parameters!")
                self.calculate_demand = False

        self.power_meter_topic = topics.DEVICES_VALUE(campus=campus,
                                                      building=building,
                                                      unit=power_meter,
                                                      path="",
                                                      point="all")
        self.kill_device_topic = None
        kill_token = config.get("kill_switch")
        if kill_token is not None:
            kill_device = kill_token["device"]
            self.kill_pt = kill_token["point"]
            self.kill_device_topic = topics.DEVICES_VALUE(campus=campus,
                                                          building=building,
                                                          unit=kill_device,
                                                          path="",
                                                          point="all")
        demand_limit = config["demand_limit"]
        if isinstance(demand_limit, (int, float)):
            self.demand_limit = float(demand_limit)
        else:
            self.demand_limit = None
        self.demand_schedule = config.get("demand_schedule")

        self.curtail_time = td(minutes=config.get("curtailment_time", 15))
        self.average_building_power_window = td(minutes=config.get("average_building_power_window", 15))
        self.curtail_confirm = td(minutes=config.get("curtailment_confirm", 5))
        self.curtail_break = td(minutes=config.get("curtailment_break", 15))
        self.actuator_schedule_buffer = td(minutes=config.get("actuator_schedule_buffer", 15)) + self.curtail_break
        self.reset_curtail_count_time = td(hours=config.get("reset_curtail_count_time", 6))
        self.longest_possible_curtail = len(all_devices) * self.curtail_time * 2

        maximum_time_without_release = config.get("maximum_time_without_release")
        self.maximum_time_without_release = td(minutes=maximum_time_without_release) if maximum_time_without_release is not None else None

        self.stagger_release_time = float(config.get("curtailment_break", 15.0))
        self.stagger_release = config.get("stagger_release", False)
        self.stagger_off_time = config.get("stagger_off_time", True)
        self.need_actuator_schedule = config.get("need_actuator_schedule", False)

        self.running_ahp = False
        self.next_curtail_confirm = None
        self.curtail_end = None
        self.break_end = None
        self.reset_curtail_count = None
        self.kill_signal_received = False
        self.scheduled_devices = set()
        self.devices_curtailed = []
        self.bldg_power = []
        self.device_group_size = None
        self.current_stagger = None
        self.next_release = None
        self.power_meta = None
        self.tasks = {}
        self.tz = None
        self.simulation_running = config.get("simulation_running", False)

    @Core.receiver("onstart")
    def starting_base(self, sender, **kwargs):
        """
        Startup method:
         - Extract Criteria Matrix from excel file.
         - Setup subscriptions to curtailable devices.
         - Setup subscription to building power meter.
        :param sender:
        :param kwargs:
        :return:
        """
        for device_topic in self.device_topic_list:
            _log.debug("Subscribing to " + device_topic)
            self.vip.pubsub.subscribe(peer="pubsub", prefix=device_topic, callback=self.new_data)
        _log.debug("Subscribing to " + self.power_meter_topic)
        self.vip.pubsub.subscribe(peer="pubsub", prefix=self.power_meter_topic, callback=self.load_message_handler)

        if self.kill_device_topic is not None:
            _log.debug("Subscribing to " + self.kill_device_topic)
            self.vip.pubsub.subscribe(peer="pubsub", prefix=self.kill_device_topic, callback=self.handle_agent_kill)

        demand_limit_handler = self.demand_limit_handler if not self.simulation_running else self.simulation_demand_limit_handler

        if self.demand_schedule is not None:
            self.setup_demand_schedule()

        self.vip.pubsub.subscribe(peer="pubsub", prefix=self.target_agent_subscription, callback=demand_limit_handler)
        _log.debug("Target agent subscription: " + self.target_agent_subscription)
        self.vip.pubsub.publish("pubsub", self.ilc_start_topic, headers={}, message={})

    @Core.receiver("onstop")
    def shutdown(self, sender, **kwargs):
        _log.debug("Shutting down ILC, releasing all controls!")
        self.reinitialize_stagger()

    def setup_demand_schedule(self):
        self.tasks = {}
        current_time = dt.now()
        demand_goal = self.demand_schedule[0]

        start = parser.parse(self.demand_schedule[1])
        end = parser.parse(self.demand_schedule[2])

        start = current_time.replace(hour=start.hour, minute=start.minute) + td(days=1)
        end = current_time.replace(hour=end.hour, minute=end.minute) + td(days=1)
        _log.debug("Setting demand goal target {} -  start: {} - end: {}".format(demand_goal, start, end))
        self.tasks[start] = {
            "schedule": [
                self.core.schedule(start, self.demand_limit_update, demand_goal, start),
                self.core.schedule(end, self.demand_limit_update, None, start)
            ]
        }

    def breakout_all_publish(self, topic, message):
        values_map = {}
        meta_map = {}

        topic_parts = topic.split('/')

        start_index = int(topic_parts[0] == "devices")
        end_index = -int(topic_parts[-1] == "all")

        topic = "/".join(topic_parts[start_index:end_index])

        values, meta = message

        values = parse_sympy(values)
        meta = parse_sympy(meta)

        for point in values:
            values_map[topic+"/"+point] = values[point]
            if point in meta:
                meta_map[topic + "/" + point] = meta[point]

        return values_map, meta_map

    def sync_status(self):
        for (device_name, actuator), curtailment_device in self.curtailment_container.devices.iteritems():
            criteria_device = self.criteria_container.get_device(device_name)
            subdevices = curtailment_device.curtailments.keys()
            for subdevice in subdevices:
                status = curtailment_device.curtailments[subdevice].device_status.command_status
                _log.debug("Device: {} -- subdevice: {} -- status: {}".format(device_name, subdevice, status))
                criteria_device.criteria_status(subdevice, status)

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
        if self.kill_signal_received:
            return

        _log.info("Data Received for {}".format(topic))
        self.sync_status()

        now = parse_timestamp_string(header[headers.TIMESTAMP])
        data_topics, meta_topics = self.breakout_all_publish(topic, message)
        self.criteria_container.ingest_data(now, data_topics)
        self.curtailment_container.ingest_data(data_topics)

    def create_curtailment_publish(self, current_time_str, device_name, meta):
        try:
            headers = {
                "Date": current_time_str,
                "min_compatible_version": "3.0",
                "MessageType": "Control"
            }
            subdevices = self.curtailment_container.get_device(device_name).command_status.keys()

            for subdevice in subdevices:
                currently_curtailed = self.curtailment_container.get_device(device_name).currently_curtailed[subdevice]
                curtailment_topic = "/".join([self.update_base_topic, device_name[0], subdevice])
                curtailment_status = "Active" if currently_curtailed else "Inactive"
                curtailment_message = [
                    {
                        "DeviceState": curtailment_status
                    },
                    {
                        "DeviceState": {"tz": "US/Pacific", "type": "string"}
                    }
                ]
                self.vip.pubsub.publish('pubsub', curtailment_topic, headers=headers, message=curtailment_message).get(timeout=15.0)
        except:
            _log.debug("Unable to publish device/subdevice curtailment status message.")

    def demand_limit_handler(self, peer, sender, bus, topic, headers, message):
        if isinstance(message, list):
            target_info = message[0]["value"]
            tz_info = message[1]["value"]["tz"]
        else:
            target_info = message
            tz_info = "US/Pacific"

        self.tz = to_zone = dateutil.tz.gettz(tz_info)
        start_time = parser.parse(target_info["start"]).astimezone(to_zone)
        end_time = parser.parse(target_info.get("end", start_time.replace(hour=23, minute=59, second=45))).astimezone(to_zone)

        demand_goal = float(target_info["target"])
        task_id = target_info["id"]
        _log.debug("TARGET - id: {} - start: {} - goal: {}".format(target_info["id"], start_time, demand_goal))
        for key, value in self.tasks.items():
            if start_time == value["end"]:
                start_time += td(seconds=15)
            if (start_time < value["end"] and end_time > value["start"]) or value["start"] <= start_time <= value["end"]:
                for item in self.tasks.pop(key)["schedule"]:
                    item.cancel()

        current_task_exits = self.tasks.get(target_info["id"])
        if current_task_exits is not None:
            _log.debug("TARGET: duplicate task received - {}".format(target_info["id"]))
            for item in self.tasks.pop(target_info["id"])["schedule"]:
                item.cancel()
        _log.debug("TARGET: create schedule for id: {}".format(target_info["id"]))
        self.tasks[target_info["id"]] = {
            "schedule": [self.core.schedule(start_time, self.demand_limit_update, demand_goal, task_id),
                         self.core.schedule(end_time, self.demand_limit_update, None, task_id)],
            "start": start_time,
            "end": end_time,
            "target": demand_goal
        }
        return

    def check_schedule(self, current_time):
        """
        Simulation cannot use clock time, this function handles the CBP target scheduling
        Energy simulations.
        :param current_time:
        :return:
        """
        if self.tasks:
            current_time = current_time.replace(tzinfo=self.tz)
            for key, value in self.tasks.items():
                if value["start"] <= current_time < value["end"]:
                    self.demand_limit = value["target"]
                elif current_time >= value["end"]:
                    self.demand_limit = None
                    self.tasks.pop(key)

    def demand_limit_update(self, demand_goal, task_id):
        """
        Sets demand_goal based on schedule and corresponding demand_goal value received from TargetAgent.
        :param demand_goal:
        :param task_id:
        :return:
        """
        _log.debug("Updating demand limit: {}".format(demand_goal))
        self.demand_limit = demand_goal
        if demand_goal is None and self.tasks and task_id in self.tasks:
            self.tasks.pop(task_id)
            if self.demand_schedule is not None:
                self.setup_demand_schedule()

    def handle_agent_kill(self, peer, sender, bus, topic, headers, message):
        """
        Locally implemented override for ILC application.
        When an override is detected the ILC application will return
        operations for all units to normal.
        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        :return:
        """
        data = message[0]
        _log.info("Checking kill signal")
        kill_signal = bool(data[self.kill_pt])
        _now = parser.parse(headers["Date"])
        if kill_signal:
            _log.info("Kill signal received, shutting down")
            self.kill_signal_received = True
            gevent.sleep(8)
            self.device_group_size = [len(self.devices_curtailed)]
            self.reset_devices()
            sys.exit()

    def calculate_average_power(self, current_power, current_time):
        """
        Calculate the average power.
        :param current_power:
        :param current_time:
        :return:
        """
        if self.simulation_running:
            self.check_schedule(current_time)

        if self.bldg_power:
            current_average_window = self.bldg_power[-1][0] - self.bldg_power[0][0] + td(seconds=15)
        else:
            current_average_window = td(minutes=0)

        if current_average_window >= self.average_building_power_window and current_power > 0:
            self.bldg_power.append((current_time, current_power))
            self.bldg_power.pop(0)
        elif current_power > 0:
            self.bldg_power.append((current_time, current_power))

        smoothing_constant = 2.0/(len(self.bldg_power) + 1.0)*2.0 if self.bldg_power else 1.0
        smoothing_constant = smoothing_constant if smoothing_constant <= 1.0 else 1.0
        power_sort = list(self.bldg_power)
        power_sort.sort(reverse=True)
        average_power = 0

        for n in xrange(len(self.bldg_power)):
            average_power += power_sort[n][1] * smoothing_constant * (1.0 - smoothing_constant) ** n

        average_power += power_sort[-1][1]*(1.0 - smoothing_constant)**(len(self.bldg_power))

        norm_list = [float(i[1]) for i in self.bldg_power]
        normal_average_power = mean(norm_list) if norm_list else 0.0

        _log.debug("Reported time: {} - instantaneous power: {}".format(current_time, current_power))
        _log.debug(
            "{} minute average power: {} - exponential power: {}".format(current_average_window, normal_average_power,
                                                                         average_power))
        return average_power, normal_average_power, current_average_window

    def load_message_handler(self, peer, sender, bus, topic, headers, message):
        """
        Call back method for building power meter. Calculates the average
        building demand over a configurable time and manages the curtailment
        time and curtailment break times.
        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        :return:
        """
        try:

            if self.kill_signal_received:
                return
            data = message[0]
            meta = message[1]

            _log.debug("Reading building power data.")
            if self.calculate_demand:
                try:
                    demand_point_list = []
                    for point in self.demand_args:
                        _log.debug("Demand calculation - point: {} - value: {}".format(point, data[point]))
                        demand_point_list.append((point, data[point]))
                    current_power = self.demand_expr.subs(demand_point_list)
                    _log.debug("Demand calculation - calculated power: {}".format(current_power))
                except:
                    current_power = float(data[self.power_point])
                    _log.debug("Demand calculation - exception using meter value: {}".format(current_power))
            else:
                current_power = float(data[self.power_point])
            current_time = parser.parse(headers["Date"])
            average_power, normal_average_power, current_average_window = self.calculate_average_power(current_power,
                                                                                                       current_time)

            if self.power_meta is None:
                try:
                    self.power_meta = meta[self.power_point]
                except:
                    self.power_meta = {
                        "tz": "UTC", "units": "kiloWatts", "type": "float"
                    }

            if self.reset_curtail_count is not None:
                if self.reset_curtail_count <= current_time:
                    _log.debug("Resetting curtail count")
                    self.curtailment_container.reset_curtail_count()

            if self.running_ahp:
                if current_time >= self.next_curtail_confirm and (self.devices_curtailed or self.stagger_off_time):
                    self.confirm_curtail(average_power, current_time)
                    _log.debug("Current reported time: {} ------- Next Curtail Confirm: {}".format(current_time,
                                                                                                   self.next_curtail_confirm))
                if current_time >= self.curtail_end:
                    _log.debug("Running end curtail method")
                    self.end_curtail(current_time)

                if self.maximum_time_without_release is not None and current_time > self.maximum_time_without_release:
                    _log.debug("Maximum time without curtail release reached!")
                    self.end_curtail(current_time)
                return

            if self.break_end is not None and current_time < self.break_end:
                return

            if len(self.bldg_power) < 15:
                return
            self.check_load(average_power, current_time)

        finally:
            try:
                headers = {
                    "Date": format_timestamp(current_time),
                    "min_compatible_version": "3.0",
                    "ApplicationCategory": self.application_category,
                    "ApplicationName": self.application_name,
                    "MessageType": "Average Building Load"
                }
                load_topic = "/".join([self.update_base_topic, "AverageBuildingPower"])
                power_message = [
                    {
                        "AverageBuildingPower": float(normal_average_power),
                        "AverageTimeLength": int(current_average_window.total_seconds()/60),
                        "LoadControlPower": float(average_power)
                    },
                    {
                        "AverageBuildingPower": {
                            "tz": self.power_meta["tz"],
                            "type": "float",
                            "units": self.power_meta["units"]
                        },
                        "AverageTimeLength": {
                            "tz": self.power_meta["tz"],
                            "type": "integer",
                            "units": "minutes"
                        },
                        "LoadControlPower": {
                            "tz": self.power_meta["tz"],
                            "type": "float",
                            "units": self.power_meta["units"]
                        }
                    }
                ]
                self.vip.pubsub.publish("pubsub", load_topic, headers=headers, message=power_message).get(timeout=15.0)
            except:
                _log.debug("Unable to publish average power information.  Input data may not contain metadata.")
            if self.simulation_running:
                self.vip.pubsub.publish("pubsub", "applications/ilc/advance", headers={}, message={})

    def check_load(self, bldg_power, current_time):
        """
        Check whole building power and if the value is above the
        the demand limit (demand_limit) then initiate the ILC (AHP)
        sequence.
        :param bldg_power:
        :param current_time:
        :return:
        """
        _log.debug("Checking building load.")

        if self.demand_limit is None:
            result = "Demand goal has not been set. Current load: ({load}) kW.".format(load=bldg_power)
        else:
            result = "Current load: ({load}) kW is below demand limit of {limit} kW.".format(load=bldg_power,
                                                                                             limit=self.demand_limit)

        if self.demand_limit is not None and bldg_power > self.demand_limit:
            result = "Current load of {} kW exceeds demand limit of {} kW.".format(bldg_power, self.demand_limit)
            scored_devices = self.criteria_container.get_score_order()
            on_devices = self.curtailment_container.get_on_devices()
            score_order = [device for scored in scored_devices for device in on_devices if scored in [(device[0], device[1])]]

            _log.debug("Scored devices: {}".format(scored_devices))
            _log.debug("On devices: {}".format(on_devices))
            _log.debug("Scored and on devices: {}".format(score_order))

            if not score_order:
                _log.info("All devices are off, nothing to curtail.")
                return

            self.device_group_size = None
            scored_devices = self.actuator_request(score_order)
            self.curtail(scored_devices, bldg_power, current_time)
        self.create_application_status(format_timestamp(current_time), result)

    def actuator_request(self, score_order):
        """
        Request schedule to interact with devices via rpc call to actuator agent.
        :param score_order: ahp priority for devices (curtailment priority).
        :return:
        """
        current_time = get_aware_utc_now()
        start_time_str = format_timestamp(current_time)
        end_curtail_time = current_time + self.longest_possible_curtail + self.actuator_schedule_buffer
        end_time_str = format_timestamp(end_curtail_time)
        curtailable_device = []

        already_handled = dict((device[0], True) for device in self.scheduled_devices)

        for item in score_order:

            device, token, device_actuator = item
            curtail_point_device = self.curtailment_container.get_device((device, device_actuator)).get_point_device(token)
            _log.debug("Reserving device: {}".format(device))

            if device in already_handled:
                if already_handled[device]:
                    _log.debug("Skipping reserve device (previously reserved): " + device)
                    curtailable_device.append(item)
                continue

            curtailed_device = self.base_rpc_path(path=curtail_point_device)
            schedule_request = [[curtailed_device, start_time_str, end_time_str]]
            try:
                if self.kill_signal_received:
                    break
                if self.need_actuator_schedule:
                    result = self.vip.rpc.call(device_actuator, "request_new_schedule",
                                               self.agent_id, curtailed_device, "HIGH", schedule_request).get(timeout=5)
                else:
                    result = None
            except RemoteError as ex:
                _log.warning("Failed to schedule device {} (RemoteError): {}".format(device, str(ex)))
                continue

            if result is not None and result["result"] == "FAILURE":
                _log.warn("Failed to schedule device (unavailable) " + device)
                already_handled[device] = False
            else:
                already_handled[device] = True
                self.scheduled_devices.add((device, device_actuator, curtailed_device))
                curtailable_device.append(item)

        return curtailable_device

    def curtail(self, scored_devices, bldg_power, current_time):
        """
        Curtail loads by turning off device (or device components),
        :param scored_devices:
        :param bldg_power:
        :param now:
        :return:
        """
        need_curtailed = bldg_power - self.demand_limit
        est_curtailed = 0.0
        remaining_devices = scored_devices[:]
        
        for device in self.devices_curtailed:
            current_tuple = (device[0], device[1], device[5])
            if current_tuple in remaining_devices:
                remaining_devices.remove(current_tuple)

        if not self.running_ahp:
            _log.info("Starting AHP")
            self.running_ahp = True

        if not remaining_devices:
            _log.debug("Everything available has already been curtailed")
            return

        self.break_end = current_time + self.curtail_time + self.curtail_break
        self.curtail_end = current_time + self.curtail_time
        self.reset_curtail_count = self.curtail_end + self.reset_curtail_count_time
        self.next_curtail_confirm = current_time + self.curtail_confirm

        for device in remaining_devices:
            device_name, device_id, actuator = device
            curtail = self.curtailment_container.get_device((device_name, actuator)).get_curtailment(device_id)
            curtail_point, curtail_value, curtail_load, revert_priority, revert_value = self.determine_curtail_parms(curtail, device)
            try:
                if self.kill_signal_received:
                    break
                result = self.vip.rpc.call(actuator, "set_point", "ilc_agent", curtail_point, curtail_value).get(timeout=5)
            except RemoteError as ex:
                _log.warning("Failed to set {} to {}: {}".format(curtail_point, curtail_value, str(ex)))
                continue

            est_curtailed += curtail_load
            self.curtailment_container.get_device((device_name, actuator)).increment_curtail(device_id)
            self.devices_curtailed.append(
                [device_name, device_id, revert_value, revert_priority, format_timestamp(current_time), actuator]
            )
            if est_curtailed >= need_curtailed:
                break

    def determine_curtail_parms(self, curtail, device_dict):
        """
        Pull stored curtail parameters for devices.
        :param curtail:
        :param device_dict:
        :return:
        """
        device, token, device_actuator = device_dict
        curtail_pt = curtail["point"]
        curtail_load = curtail["load"]
        revert_priority = curtail["revert_priority"]
        curtailment_method = curtail["curtailment_method"]

        curtail_point = self.base_rpc_path(path=curtail_pt)

        if isinstance(curtail_load, dict):
            load_equation = curtail_load["load_equation"]
            load_point_values = []

            for point in curtail_load["load_equation_args"]:
                point_to_get =  self.base_rpc_path(path=curtail_pt)
                value = self.vip.rpc.call(device_actuator, "get_point", point_to_get).get(timeout=5)
                load_point_values.append((point, value))
            curtail_load = load_equation.subs(load_point_values)

        revert_value = self.vip.rpc.call(device_actuator, "get_point", curtail_point).get(timeout=5)

        if curtailment_method.lower() == "offset":
            curtail_value = revert_value + curtail["offset"]
        elif curtailment_method.lower() == "equation":
            equation = curtail["curtail_equation"]
            equation_point_values = []

            for point in curtail["curtail_equation_args"]:
                point_get =  self.base_rpc_path(path=curtail_pt)
                value = self.vip.rpc.call(device_actuator, "get_point", point_get).get(timeout=5)
                equation_point_values.append((point, value))

            curtail_value = float(equation.subs(equation_point_values))
        else:
            curtail_value = curtail["value"]

        if None not in [curtail["minimum"], curtail["maximum"]]:
            curtail_value = max(curtail["minimum"], min(curtail_value, curtail["maximum"]))
        elif curtail["minimum"] is not None and curtail["maximum"] is None:
            curtail_value = max(curtail["minimum"], curtail_value)
        elif curtail["maximum"] is not None and curtail["minimum"] is None:
            curtail_value = min(curtail["maximum"], curtail_value)

        return curtail_point, curtail_value, curtail_load, revert_priority, revert_value

    def confirm_curtail(self, cur_pwr, now):
        """
        Check if load shed has been met.  If the demand goal is not
        met and there are additional devices to curtail then the ILC will shed
        additional load by curtailing more devices
        :param cur_pwr: [float]] - current power calculated using exponential smoothing average.
        :param now: [datetime] - current local time or simulation time.
        :return:
        """
        if self.demand_limit is not None:
            if cur_pwr < self.demand_limit:
                _log.info("Curtail goal for building load met.")
            else:
                _log.info("Curtail goal for building load NOT met.")
                self.check_load(cur_pwr, now)

    def end_curtail(self, current_time):
        _log.info("Stagger release: {}".format(self.stagger_release))

        if self.stagger_release:
            _log.info("Stagger release enabled.")

            if self.device_group_size is None:
                _log.debug("Run stagger release setup.")
                self.next_curtail_confirm = current_time + self.curtail_confirm
                self.stagger_release_setup()
                self.next_release = current_time + td(minutes=self.current_stagger.pop(0))
                self.reset_devices()

            if current_time >= self.next_release and self.current_stagger:
                _log.debug("Release group stagger.")
                self.reset_devices()
                self.next_release = current_time + td(minutes=self.current_stagger.pop(0))
                _log.debug("Next scheduled release: {}".format(self.next_release))

            if current_time >= self.break_end:
                _log.debug("Release all in contingency.")
                self.reinitialize_stagger()
            return

        _log.debug("Current devices held curtailed: {}".format(self.devices_curtailed))
        self.reinitialize_stagger()

    def stagger_release_setup(self):
        _log.debug("Number or curtailed devices: {}".format(len(self.devices_curtailed)))

        confirm_in_minutes = self.curtail_confirm.total_seconds()/60.0
        release_steps = int(max(1, math.floor(self.stagger_release_time / confirm_in_minutes + 1)))

        self.device_group_size = [int(math.floor(len(self.devices_curtailed) / release_steps))]*release_steps
        _log.debug("Current group size:  {}".format(self.device_group_size))

        if len(self.devices_curtailed) > release_steps:
            for group in range(len(self.devices_curtailed) % release_steps):
                self.device_group_size[group] += 1
        else:
            self.device_group_size = [0]*release_steps
            interval = int(math.ceil(float(release_steps) / len(self.devices_curtailed)))
            _log.debug("Release interval offset: {}".format(interval))
            for group in range(0, len(self.device_group_size), interval):
                self.device_group_size[group] = 1
            unassigned = len(self.devices_curtailed) - sum(self.device_group_size)
            for group, value in enumerate(self.device_group_size):
                if value == 0:
                    self.device_group_size[group] = 1
                    unassigned -= 1
                if unassigned <= 0:
                    break

        self.current_stagger = [math.floor(self.stagger_release_time / (release_steps - 1))]*(release_steps - 1)
        for group in range(int(self.stagger_release_time % (release_steps - 1))):
            self.current_stagger[group] += 1

        _log.debug("Current stagger time:  {}".format(self.current_stagger))
        _log.debug("Current group size:  {}".format(self.device_group_size))

    def reset_devices(self):
        _log.info("Resetting Devices: {}".format(self.devices_curtailed))

        scored_devices = self.criteria_container.get_score_order()
        curtailed = [device for scored in scored_devices for device in self.devices_curtailed if scored in [(device[0], device[1])]]

        _log.debug("Curtailed devices: {}".format(self.devices_curtailed))

        currently_curtailed = curtailed[::-1]
        curtailed_iterate = currently_curtailed[:]
        index_counter = 0
        _log.debug("Curtailed devices for release reverse sort: {}".format(currently_curtailed))

        for item in range(self.device_group_size.pop(0)):
            device, device_id, revert_val, revert_priority, modified_time, actuator = curtailed_iterate[item]
            curtail = self.curtailment_container.get_device((device, actuator)).get_curtailment(device_id)
            curtail_point = curtail["point"]
            curtailed_point = self.base_rpc_path(path=curtail_point)
            revert_value = self.get_revert_value(device, revert_priority, revert_val)

            _log.debug("Returned revert value: {}".format(revert_value))

            try:
                if revert_value is not None:
                    result = self.vip.rpc.call(actuator, "set_point", "ilc", curtailed_point, revert_value).get(timeout=5)
                    _log.debug("Reverted point: {} to value: {}".format(curtailed_point, revert_value))
                else:
                    result = self.vip.rpc.call(actuator, "revert_point", "ilc", curtailed_point).get(timeout=5)
                    _log.debug("Reverted point: {} - Result: {}".format(curtailed_point, result))
                if currently_curtailed:
                    _log.debug("Removing from curtailed list: {} ".format(curtailed_iterate[item]))
                    self.curtailment_container.get_device((device, actuator)).reset_curtail_status(device_id)
                    index = curtailed_iterate.index(curtailed_iterate[item]) - index_counter
                    currently_curtailed.pop(index)
                    index_counter += 1
            except RemoteError as ex:
                _log.warning("Failed to revert point {} (RemoteError): {}".format(curtailed_point, str(ex)))
                continue
        self.devices_curtailed = currently_curtailed

    def get_revert_value(self, device, revert_priority, revert_value):
        """
        If BACnet priority array cannot be used this method will return the
        the revert value for the control point.
        :param device:
        :param revert_priority:
        :param revert_value:
        :return:
        """
        current_device_list = []
        if revert_priority is None:
            return None

        for curtailed in self.devices_curtailed:
            if curtailed[0] == device:
                current_device_list.append(curtailed)

        if len(current_device_list) <= 1:
            return None

        index_value = max(current_device_list, key=lambda t: t[2])
        return_value = index_value[2]
        _log.debug("Stored revert value: {} for device: {}".format(return_value, device))
        curtail_set_index = self.devices_curtailed.index(index_value)
        self.devices_curtailed[curtail_set_index][2] = revert_value
        self.devices_curtailed[curtail_set_index][3] = revert_priority

        return return_value

    def reinitialize_stagger(self):
        if self.devices_curtailed:
            self.device_group_size = [len(self.devices_curtailed)]
            self.reset_devices()
        self.devices_curtailed = []
        self.running_ahp = False
        self.device_group_size = None
        self.reset_all_devices()

    def reset_all_devices(self):
        for device in self.scheduled_devices:
            try:
                release_all = self.vip.rpc.call(device[1], "revert_device", "ilc", device[2]).get(timeout=10)
                _log.debug("Revert device: {} with return value {}".format(device[2], release_all))
            except RemoteError as ex:
                _log.warning("Failed revert all on device {} (RemoteError): {}".format(device[2], str(ex)))
            result = self.vip.rpc.call(device[1], "request_cancel_schedule", self.agent_id, device[2]).get(timeout=10)
        self.scheduled_devices = set()

    def create_application_status(self, current_time_str, result):
        """
        Publish application status.
        :param current_time_str:
        :param result:
        :return:
        """
        try:
            application_state = "Inactive"
            if self.devices_curtailed:
                application_state = "Active"

            headers = {
                "Date": current_time_str,
                "min_compatible_version": "3.0",
                "ApplicationCategory": self.application_category,
                "ApplicationName": self.application_name,
                "MessageType": "Result",
                "TimeStamp": current_time_str
            }

            application_message = [
                {
                    "Result": result,
                    "ApplicationState": application_state
                },
                {
                    "Result": {"tz": self.power_meta["tz"], "type": "string", "units": "None"},
                    "ApplicationState": {"tz": self.power_meta["tz"], "type": "string", "units": "None"}
                }
            ]
            self.vip.pubsub.publish("pubsub", self.ilc_topic, headers=headers, message=application_message).get(timeout=15.0)
        except:
            _log.debug("Unable to publish application status message.")

    def create_device_status_publish(self, current_time_str, device_name, data, topic, meta):
        """
        Publish device status.
        :param current_time_str:
        :param device_name:
        :param data:
        :param topic:
        :param meta:
        :return:
        """
        try:
            device_tokens = self.curtailment_container.devices[device_name].command_status.keys()
            for subdevice in device_tokens:
                curtail = self.curtailment_container.get_device(device_name).get_curtailment(subdevice)
                curtail_pt = curtail["point"]
                device_update_topic = "/".join([self.ilc_topic, device_name[0], subdevice, curtail_pt])
                previous_value = data[curtail_pt]
                control_time = None
                device_state = "Inactive"
                for item in self.devices_curtailed:
                    if device_name[0] == item[0]:
                        previous_value = item[2]
                        control_time = item[4]
                        device_state = "Active"

                headers = {
                    "Date": current_time_str,
                    "min_compatible_version": "3.0",
                    "ApplicationCategory": self.application_category,
                    "ApplicationName": self.application_name,
                    "MessageType": "Control",
                    "TimeStamp": current_time_str
                }

                device_message = [
                    {
                        "DeviceState": device_state,
                        "PreviousValue": previous_value,
                        "TimeChanged": control_time
                    },
                    {
                        "PreviousValue": meta[curtail_pt],
                        "TimeChanged": {"tz": meta[curtail_pt]["tz"], "type": "datetime"},
                        "DeviceState": {"tz": meta[curtail_pt]["tz"], "type": "string"}
                    }
                ]
                self.vip.pubsub.publish("pubsub", device_update_topic, headers=headers, message=device_message).get(timeout=4.0)
        except:
            _log.debug("Unable to publish device status message.")

    def simulation_demand_limit_handler(self, peer, sender, bus, topic, headers, message):
        """
        Simulation handler for TargetAgent.
        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        :return:
        """
        if isinstance(message, list):
            target_info = message[0]["value"]
            tz_info = message[1]["value"]["tz"]
        else:
            target_info = message
            tz_info = "US/Pacific"

        self.tz = to_zone = dateutil.tz.gettz(tz_info)
        start_time = parser.parse(target_info["start"]).astimezone(to_zone)
        end_time = parser.parse(target_info.get("end", start_time.replace(hour=23, minute=59, second=59))).astimezone(to_zone)

        demand_goal = target_info["target"]
        task_id = target_info["id"]

        _log.debug("TARGET: Simulation running.")
        for key, value in self.tasks.items():
            if (start_time < value["end"] and end_time > value["start"]) or (value["start"] <= start_time <= value["end"]):
                self.tasks.pop(key)

        _log.debug("TARGET: received demand goal schedule - start: {} - end: {} - target: {}.".format(start_time,
                                                                                                      end_time,
                                                                                                      demand_goal))
        self.tasks[target_info["id"]] = {"start": start_time, "end": end_time, "target": demand_goal}
        return


def main(argv=sys.argv):
    """Main method called by the aip."""
    try:
        utils.vip_main(ILCAgent)
    except Exception as exception:
        _log.exception("unhandled exception")
        _log.error(repr(exception))


if __name__ == "__main__":
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
