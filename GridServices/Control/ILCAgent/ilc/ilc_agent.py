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
import math
from datetime import timedelta as td, datetime as dt
from dateutil import parser
import gevent
import dateutil.tz
from transitions import Machine
import time

from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import (setup_logging, format_timestamp, get_aware_utc_now, parse_timestamp_string)
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.jsonrpc import RemoteError

from ilc.ilc_matrices import (extract_criteria, calc_column_sums,
                              normalize_matrix, validate_input)
from ilc.control_handler import ControlCluster, ControlContainer
from ilc.criteria_handler import CriteriaContainer, CriteriaCluster
from ilc.utils import sympy_evaluate

# from transitions.extensions import GraphMachine as Machine
__author__ = "Robert Lutes, robert.lutes@pnnl.gov"
__version__ = "2.2.2"

setup_logging()
_log = logging.getLogger(__name__)
APP_CAT = "LOAD CONTROL"
APP_NAME = "ILC"


class ILCAgent(Agent):
    states = ['inactive', 'curtail', 'curtail_holding', 'curtail_releasing', 'augment', "augment_holding", 'augment_releasing']
    transitions = [
        {
            'trigger': 'curtail_load',
            'source': 'inactive',
            'dest': 'curtail'
        },
        {
            'trigger': 'curtail_load',
            'source': 'curtail',
            'dest': '='
        },
        {
            'trigger': 'hold',
            'source': 'curtail',
            'dest': 'curtail_holding'
        },
        {
            'trigger': 'curtail_load',
            'source': 'curtail_holding',
            'dest': 'curtail',
            'conditions': 'confirm_elapsed'
        },
        {
            'trigger': 'release',
            'source': 'curtail_holding',
            'dest': 'curtail_releasing',
            'conditions': 'confirm_start_release',
            "after": "reset_devices"
        },
        {
            'trigger': 'release',
            'source': 'curtail',
            'dest': 'curtail_releasing',
            'conditions': 'confirm_start_release',
            'after': 'reset_devices'
        },
        {
            'trigger': 'release',
            'source': ['curtail_releasing', 'augment_releasing'],
            'dest': None,
            'after': 'reset_devices',
            'conditions': 'confirm_next_release'
        },
        {
            'trigger': 'curtail_load',
            'source': 'curtail_releasing',
            'dest': 'curtail',
            'conditions': 'confirm_next_release'
        },
        {
            'trigger': 'augment_load',
            'source': 'inactive',
            'dest': 'augment'
        },
        {
            'trigger': 'augment_load',
            'source': 'augment',
            'dest': '='
        },
        {
            'trigger': 'hold',
            'source': 'augment',
            'dest': 'augment_holding'
        },
        {
            'trigger': 'augment_load',
            'source': 'augment_holding',
            'dest': 'augment',
            'conditions': 'confirm_elapsed'
        },
        {
            'trigger': 'release',
            'source': 'augment_holding',
            'dest': 'augment_releasing',
            'conditions': 'confirm_start_release',
            "after": "reset_devices"
        },
        {
            'trigger': 'release',
            'source': 'augment',
            'dest': 'augment_releasing',
            'conditions': 'confirm_start_release',
            'after': 'reset_devices'
        },
        {
            'trigger': 'augment_load',
            'source': 'augment_releasing',
            'dest': 'augment',
            'conditions': 'confirm_next_release'
        },
        {
            'trigger': 'curtail_load',
            'source': ['augment', 'augment_holding', 'augment_releasing'],
            'dest': 'curtail_holding',
            'after': 'reinitialize_release'
        },
        {
            'trigger': 'augment_load',
            'source': ['curtail', 'curtail_holding', 'curtail_releasing'],
            'dest': 'augment_holding',
            'after': 'reinitialize_release'
        },
        {
            'trigger': 'finished',
            'source': ['curtail_releasing', 'augment_releasing'],
            'dest': 'inactive',
            "after": 'reinitialize_release'
        },
        {
            'trigger': 'no_target',
            'source': '*',
            'dest': 'inactive',
            "after": 'reinitialize_release'
        }
    ]

    def __init__(self, config_path, **kwargs):
        super(ILCAgent, self).__init__(**kwargs)
        self.state = None
        self.state_machine = Machine(model=self, states=ILCAgent.states,
                                     transitions= ILCAgent.transitions, initial='inactive', queued=True)
        # self.get_graph().draw('my_state_diagram.png', prog='dot')
        self.state_machine.on_enter_curtail('modify_load')
        self.state_machine.on_enter_augment('modify_load')
        self.state_machine.on_enter_curtail_releasing('setup_release')
        self.state_machine.on_enter_augment_releasing('setup_release')

        self.default_config = {
            "campus": "CAMPUS",
            "building": "BUILDING",
            "power_meter": {},
            "agent_id": "ILC",
            "demand_limit": 30.0,
            "control_time": 20.0,
            "curtailment_confirm": 5.0,
            "curtailment_break": 20.0,
            "average_building_power_window": 15.0,
            "stagger_release": True,
            "stagger_off_time": True,
            "simulation_running": False,
            "confirm_time": 5,
            "clusters": []
        }
        self.confirm_time = td(minutes=self.default_config.get("confirm_time"))
        self.current_time = td(minutes=0)
        self.state_machine = Machine(model=self, states=ILCAgent.states,
                                     transitions= ILCAgent.transitions, initial='inactive', queued=True)
        # self.get_graph().draw('my_state_diagram.png', prog='dot')
        self.state_machine.on_enter_curtail('modify_load')
        self.state_machine.on_enter_augment('modify_load')
        self.state_machine.on_enter_curtail_releasing('setup_release')
        self.state_machine.on_enter_augment_releasing('setup_release')

        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure_main,
                                  actions=["NEW", "UPDATE"],
                                  pattern="config")

        self.next_confirm = None
        self.action_end = None
        self.kill_signal_received = False
        self.scheduled_devices = set()
        self.devices = []
        self.bldg_power = []
        self.avg_power = None
        self.device_group_size = None
        self.current_stagger = None
        self.next_release = None
        self.power_meta = None
        self.tasks = {}
        self.tz = None
        self.lock = False
        self.sim_time = 0
        self.config_reload_needed = False
        self.saved_config = None
        self.power_meter_topic = None
        self.kill_device_topic = None
        self.load_control_modes = ["curtail"]
        self.schedule = {}

    def configure_main(self, config_name, action, contents):
        config = self.default_config.copy()
        config.update(contents)
        if action == "NEW" or "UPDATE":
            _log.debug("CONFIG NAME: {}, ACTION: {}, STATE: {}".format(config_name, action, self.state))
            if self.state not in ['curtail', 'curtail_holding', 'curtail_releasing', 'augment', 'augment_holding', 'augment_releasing']:
                self.reset_parameters(config)
            else:
                _log.debug("ENTER CONFIG UPDATE..CURTAIL IN ACTION, UPDATE DEFERRED")
                # Defer reloading of parameters after curtailment operation
                self.config_reload_needed = True
                # self.new_config = self.default_config.copy()
                self.saved_config = self.default_config.copy()
                self.saved_config.update(contents)

    @RPC.export
    def update_configurations(self, data):
        """
        Update configuration for ILC via RPC.
        :param data: dictionary of all ILC configurations.
        :type data: Dict[Dict]
        :return: None
        """
        try:
            config = data.pop('config')
        except KeyError as ex:
            config = {}
            _log.debug(f'Cannot remotely update configurations!  Main config is not in payload!: {ex}')
        for name, data in data.items():
            self.vip.config.set(name, data)
        self.vip.config.set('config', config, send_update=True, trigger_callback=True)
        return True

    def reset_parameters(self, config=None):
        """
        Reset all parameters based on configuration change
        :param config: config
        :return:
        """
        campus = config.get("campus", "")
        building = config.get("building", "")
        self.agent_id = config.get("agent_id", APP_NAME)
        self.load_control_modes = config.get("load_control_modes", ["curtail"])

        campus = config.get("campus", "")
        building = config.get("building", "")
        self.agent_id = config.get("agent_id", APP_NAME)
        ilc_start_topic = self.agent_id
        # --------------------------------------------------------------------------------

        # For Target agent updates...
        update_base_topic = config.get("analysis_prefix_topic", "record")
        self.record_topic = update_base_topic
        self.target_agent_subscription = "{}/target_agent".format(update_base_topic)
        # --------------------------------------------------------------------------------

        if campus:
            update_base_topic = "/".join([update_base_topic, campus])
            ilc_start_topic = "/".join([self.agent_id, campus])

        if building:
            update_base_topic = "/".join([update_base_topic, building])
            ilc_start_topic = "/".join([ilc_start_topic, building])

        self.update_base_topic = update_base_topic
        self.ilc_start_topic = "/".join([ilc_start_topic, "ilc/start"])

        cluster_configs = config["clusters"]
        self.criteria_container = CriteriaContainer()
        self.control_container = ControlContainer()

        for cluster_config in cluster_configs:
            _log.debug("CLUSTER CONFIG: {}".format(cluster_config))
            pairwise_criteria_config = cluster_config["pairwise_criteria_config"]

            criteria_config = cluster_config["device_criteria_config"]
            control_config = cluster_config["device_control_config"]

            cluster_priority = cluster_config["cluster_priority"]
            cluster_actuator = cluster_config.get("cluster_actuator", "platform.actuator")
            # Check that all three parameters are not None
            if pairwise_criteria_config and criteria_config and control_config:
                criteria_labels, criteria_array, self.load_control_modes = extract_criteria(pairwise_criteria_config)
                col_sums = calc_column_sums(criteria_array)
                row_average = normalize_matrix(criteria_array, col_sums)
                _log.debug("VALIDATE - criteria_array {} - col_sums {}".format(criteria_array, col_sums))
                if not validate_input(criteria_array, col_sums):
                    _log.debug("Inconsistent pairwise configuration. Check "
                               "configuration in: {}".format(pairwise_criteria_config))
                    sys.exit()

                criteria_cluster = CriteriaCluster(cluster_priority, criteria_labels, row_average, criteria_config,
                                                   self.record_topic, self)
                self.criteria_container.add_criteria_cluster(criteria_cluster)
                _log.debug("CONTROL config: {}, ------------------- CRITERIA config: {}".format(control_config, criteria_config))
                control_cluster = ControlCluster(control_config, cluster_actuator, self.record_topic, self)
                self.control_container.add_control_cluster(control_cluster)

        self.base_rpc_path = topics.RPC_DEVICE_PATH(campus="",
                                                    building="",
                                                    unit="",
                                                    path=None,
                                                    point="")
        self.device_topic_list = []
        all_devices = self.control_container.get_device_topic_set()
        for device_name in all_devices:
            device_topic = topics.DEVICES_VALUE(campus="",
                                                building="",
                                                unit="",
                                                path=device_name,
                                                point="all")

            self.device_topic_list.append(device_topic)

        power_meter_info = config.get("power_meter", {})
        power_meter = power_meter_info.get("device_topic", None)
        self.power_point = power_meter_info.get("point", None)
        demand_formula = power_meter_info.get("demand_formula")
        self.calculate_demand = False

        if demand_formula is not None:
            self.calculate_demand = True
            try:
                self.demand_expr = demand_formula["operation"]
                self.demand_args = demand_formula["operation_args"]
                _log.debug("Demand calculation - expression: {}".format(self.demand_expr))
            except (KeyError, ValueError):
                _log.debug("Missing 'operation_args' or 'operation' for setting demand formula!")
                self.calculate_demand = False
            except:
                _log.debug("Unexpected error when reading demand formula parameters!")
                self.calculate_demand = False

        self.power_meter_topic = topics.DEVICES_VALUE(campus="",
                                                      building="",
                                                      unit="",
                                                      path=power_meter,
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
            try:
                self.demand_limit = float(demand_limit)
            except ValueError:
                self.demand_limit = None

        self.demand_schedule = config.get("demand_schedule")
        action_time = config.get("control_time", 15)
        self.action_time = td(minutes=action_time)
        self.average_window = td(minutes=config.get("average_building_power_window", 15))
        self.confirm_time = td(minutes=config.get("confirm_time", 5))

        self.actuator_schedule_buffer = td(minutes=config.get("actuator_schedule_buffer", 15)) + self.action_time
        self.longest_possible_curtail = len(all_devices) * self.action_time * 2

        self.stagger_release_time = float(config.get("release_time", action_time))
        self.stagger_release = config.get("stagger_release", False)
        self.need_actuator_schedule = config.get("need_actuator_schedule", False)
        self.demand_threshold = config.get("demand_threshold", 5.0)
        self.sim_running = config.get("simulation_running", False)
        self.starting_base('core')
        self.config_reload_needed = False

#    @Core.receiver("onstart")
    def starting_base(self, sender, **kwargs):
        """
        Startup method:
         - Setup subscriptions to curtailable devices.
         - Setup subscription to building power meter.
        :param sender:
        :param kwargs:
        :return:
        """
        for device_topic in self.device_topic_list:
            _log.debug("Subscribing to " + device_topic)
            self.vip.pubsub.subscribe(peer="pubsub",
                                      prefix=device_topic,
                                      callback=self.new_data)
        if self.power_meter_topic is not None:
            _log.debug("Subscribing to " + self.power_meter_topic)
            self.vip.pubsub.subscribe(peer="pubsub",
                                  prefix=self.power_meter_topic,
                                  callback=self.load_message_handler)

        if self.kill_device_topic is not None:
            _log.debug("Subscribing to " + self.kill_device_topic)
            self.vip.pubsub.subscribe(peer="pubsub",
                                      prefix=self.kill_device_topic,
                                      callback=self.handle_agent_kill)

        if self.demand_schedule is not None and not self.sim_running:
            self.setup_demand_schedule()
        elif self.demand_schedule is not None and self.sim_running:
            self.setup_demand_schedule_sim()

        self.vip.pubsub.subscribe(peer="pubsub",
                                  prefix=self.target_agent_subscription,
                                  callback=self.demand_limit_handler)
        _log.debug("Target agent subscription: " + self.target_agent_subscription)
        self.vip.pubsub.publish("pubsub", self.ilc_start_topic, headers={}, message={})
        self.setup_topics()

    def setup_topics(self):
        self.criteria_topics = self.criteria_container.get_ingest_topic_dict()
        self.control_topics = self.control_container.get_ingest_topic_dict()
        self.all_criteria_topics = []
        self.all_control_topics = []
        for lst in self.criteria_topics.values():
            self.all_criteria_topics.extend(lst)
        for lst in self.control_topics.values():
            self.all_control_topics.extend(lst)

    @Core.receiver("onstop")
    def shutdown(self, sender, **kwargs):
        _log.debug("Shutting down ILC, releasing all controls!")
        self.reinitialize_release()

    def confirm_elapsed(self):
        if self.current_time > self.next_confirm:
            return True
        else:
            return False

    def confirm_end(self):
        if self.action_end is not None and self.current_time >= self.action_end:
            return True
        else:
            return False

    def confirm_next_release(self):
        if self.next_release is not None and self.current_time >= self.next_release:
            return True
        else:
            return False

    def confirm_start_release(self):
        if self.action_end is not None and self.current_time >= self.action_end:
            self.lock = True
            return True
        else:
            return False

    def setup_demand_schedule_sim(self):
        if self.demand_schedule:
            for day_str, schedule_info in self.demand_schedule.items():
                _day = parser.parse(day_str).weekday()
                if schedule_info not in ["always_on", "always_off"]:
                    start = parser.parse(schedule_info["start"]).time()
                    end = parser.parse(schedule_info["end"]).time()
                    target = schedule_info.get("target", None)
                    self.schedule[_day] = {"start": start, "end": end, "target": target}
                else:
                    self.schedule[_day] = schedule_info

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

    def breakout_all_publish(self, topic, message):
        values_map = {}
        meta_map = {}
        topic_parts = topic.split('/')

        start_index = int(topic_parts[0] == "devices")
        end_index = -int(topic_parts[-1] == "all")

        topic = "/".join(topic_parts[start_index:end_index])
        values, meta = message

        for point in values:
            values_map[topic + "/" + point] = values[point]
            if point in meta:
                meta_map[topic + "/" + point] = meta[point]

        return values_map, meta_map

    def sync_status(self):
        # TODO: as data comes in it loops through all criteria for each device.  This causes near continuous execution of these loop.
        for device_name, device_criteria in self.criteria_container.devices.items():
            for (subdevice, state), criteria in device_criteria.criteria.items():
                if not self.devices:
                    status = False
                    device_criteria.criteria_status((subdevice, state), status)
                else:
                    status = False
                    for curtail_info in self.devices:
                        if subdevice == curtail_info[1] and device_name == curtail_info[0]:
                            status = True
                            break
                    device_criteria.criteria_status((subdevice, state), status)
                    _log.debug("Device: {} -- subdevice: {} -- curtail status: {}".format(device_name, subdevice, status))

    def new_criteria_data(self, data_topics, now):
        data_t = list(data_topics.keys())
        device_topics = {}
        device_criteria_topics = self.intersection(self.all_criteria_topics, data_t)
        for topic, values in data_topics.items():
            if topic in device_criteria_topics:
                device_topics[topic] = values
        device_set = set(list(device_topics.keys()))
        for device, topic_lst in self.criteria_topics.items():
            topic_set = set(topic_lst)
            needed_topics = self.intersection(topic_set, device_set)
            if needed_topics:
                device.ingest_data(now, device_topics)

    def new_control_data(self, data_topics, now):
        data_t = list(data_topics.keys())
        device_topics = {}
        device_control_topics = self.intersection(self.all_control_topics, data_t)
        for topic, values in data_topics.items():
            if topic in device_control_topics:
                device_topics[topic] = values
        device_set = set(list(device_topics.keys()))
        for device, topic_lst in self.control_topics.items():
            topic_set = set(topic_lst)
            needed_topics = self.intersection(topic_set, device_set)
            if needed_topics:
                device.ingest_data(now, device_topics)

    def new_data(self, peer, sender, bus, topic, header, message):
        """
        Call back method for curtailable device data subscription.
        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param header:
        :param message:
        :return:
        """
        start = time.time()
        if self.kill_signal_received:
            return
        _log.info("Data Received for {}".format(topic))
        self.sync_status()
        data, meta = message
        now = parse_timestamp_string(header[headers_mod.TIMESTAMP])
        data_topics, meta_topics = self.breakout_all_publish(topic, message)
        self.new_criteria_data(data_topics, now)
        self.new_control_data(data_topics, now)
        end = time.time()
        duration = end - start
        _log.debug("TIME: {} -- {}".format(topic, duration))

    def intersection(self, topics, data):
        topics = set(topics)
        data = set(data)
        return topics.intersection(data)

    def check_schedule(self, current_time):
        """
        Simulation cannot use clock time, this function handles the CBP target scheduling for
        Energy simulations and updating target based on pubsub message for transactive type
        simulation.
        :param current_time:
        :return:
        """
        # Handles load scheduling in configuration file
        if self.schedule:
            current_time = current_time.replace(tzinfo=self.tz)
            current_schedule = self.schedule[current_time.weekday()]
            if "always_off" in current_schedule:
                self.demand_limit = None
                return
            _start = current_schedule["start"]
            _end = current_schedule["end"]
            _target = current_schedule["target"]
            if _start <= current_time.time() < _end:
                self.demand_limit = _target
            else:
                self.demand_limit = None
        # Handles updating the target that is sent via pub-sub by transactive type application
        # and stored in tasks in simulation_demand_limit_handler
        if self.tasks:
            task_list = []
            current_time = current_time.replace(tzinfo=self.tz)
            for key, value in self.tasks.items():
                if value["start"] <= current_time < value["end"]:
                    self.demand_limit = value["target"]
                elif current_time >= value["end"]:
                    self.demand_limit = None
                    task_list.append(key)
            for key in task_list:
                self.tasks.pop(key)

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
            self.device_group_size = [len(self.devices)]
            self.reset_devices()
            sys.exit()

    def calculate_average_power(self, current_power, current_time):
        """
        Calculate the average power.
        :param current_power:
        :param current_time:
        :return:
        """
        if self.sim_running:
            self.check_schedule(current_time)

        if self.bldg_power:
            average_time = self.bldg_power[-1][0] - self.bldg_power[0][0] + td(seconds=15)
        else:
            average_time = td(minutes=0)

        if average_time >= self.average_window and current_power > 0:
            self.bldg_power.append((current_time, current_power))
            self.bldg_power.pop(0)
        elif current_power > 0:
            self.bldg_power.append((current_time, current_power))

        smoothing_constant = 2.0 / (len(self.bldg_power) + 1.0) * 2.0 if self.bldg_power else 1.0
        smoothing_constant = smoothing_constant if smoothing_constant <= 1.0 else 1.0
        power_sort = list(self.bldg_power)
        power_sort.sort(reverse=True)
        exp_power = 0

        for n in range(len(self.bldg_power)):
            exp_power += power_sort[n][1] * smoothing_constant * (1.0 - smoothing_constant) ** n

        exp_power += power_sort[-1][1] * (1.0 - smoothing_constant) ** (len(self.bldg_power))

        norm_list = [float(i[1]) for i in self.bldg_power]
        average_power = mean(norm_list) if norm_list else 0.0

        _log.debug("Reported time: {} - instantaneous power: {}".format(current_time,
                                                                        current_power))
        _log.debug("{} minute average power: {} - exponential power: {}".format(average_time,
                                                                                average_power,
                                                                                exp_power))
        return exp_power, average_power, average_time

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
            self.sim_time += 1
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
                    current_power = sympy_evaluate(self.demand_expr, demand_point_list)
                    _log.debug("Demand calculation - calculated power: {}".format(current_power))
                except:
                    current_power = float(data[self.power_point])
                    _log.debug("Demand calculation - exception using meter value: {}".format(current_power))
            else:
                current_power = float(data[self.power_point])
            self.current_time = parser.parse(headers["Date"])
            self.avg_power, average_power, average_time = self.calculate_average_power(current_power,
                                                                                       self.current_time)

            if self.power_meta is None:
                try:
                    self.power_meta = meta[self.power_point]
                except:
                    self.power_meta = {
                        "tz": "UTC", "units": "kiloWatts", "type": "float"
                    }

            if self.lock:
                return

            if len(self.bldg_power) < 5:
                return
            self.check_load()

        finally:
            try:
                if self.sim_running:
                    headers = {
                        headers_mod.DATE: format_timestamp(self.current_time)
                    }
                else:
                    headers = {
                        headers_mod.DATE: format_timestamp(get_aware_utc_now())
                    }
                load_topic = "/".join([self.update_base_topic, self.agent_id, "BuildingPower"])
                demand_limit = "None" if self.demand_limit is None else self.demand_limit
                power_message = [
                    {
                        "AverageBuildingPower": float(average_power),
                        "AverageTimeLength": int(average_time.total_seconds()/60),
                        "LoadControlPower": float(self.avg_power),
                        "Timestamp": format_timestamp(self.current_time),
                        "Target": demand_limit
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
                        },
                        "Timestamp": {"tz": self.power_meta["tz"], "type": "timestamp", "units": "None"},
                        "Target": {"tz": self.power_meta["tz"], "type": "float", "units": self.power_meta["units"]}
                    }
                ]
                self.vip.pubsub.publish("pubsub", load_topic, headers=headers, message=power_message).get(timeout=30.0)
            except:
                _log.debug("Unable to publish average power information.  Input data may not contain metadata.")
            # TODO: Refactor this code block.  Disparate code paths for simulation and real devices is undesireable
            if self.sim_running:
                gevent.sleep(0.25)
                self.vip.pubsub.publish("pubsub", "applications/ilc/advance", headers={}, message={})

    def check_load(self):
        """
        Check whole building power and manager to this goal.
        :param bldg_power:
        :param current_time:
        :return:
        """
        _log.debug("Checking building load: {}".format(self.demand_limit))

        if self.demand_limit is not None:
            if "curtail" in self.load_control_modes and self.avg_power > self.demand_limit + self.demand_threshold:
                result = "Current load of {} kW exceeds demand limit of {} kW.".format(self.avg_power, self.demand_limit+self.demand_threshold)
                self.curtail_load()
            elif "augment" in self.load_control_modes and self.avg_power < self.demand_limit - self.demand_threshold:
                result = "Current load of {} kW is below demand limit of {} kW.".format(self.avg_power, self.demand_limit-self.demand_threshold)
                self.augment_load()
            else:
                result = "ILC is not active  - Current load: {} kW -- demand goal: {}".format(self.avg_power,
                                                                                              self.demand_limit)
                if self.state != 'inactive':
                    result = "Current load of {} kW meets demand goal of {} kW.".format(self.avg_power,
                                                                                        self.demand_limit)
                    self.release()
        else:
            result = "Demand goal has not been set. Current load: ({load}) kW.".format(load=self.avg_power)
            if self.state != 'inactive':
                self.no_target()
        _log.debug("Result: {}".format(result))
        # self.lock = False
        self.create_application_status(result)

    def modify_load(self):
        """
        Curtail loads by turning off device (or device components),
        :param scored_devices:
        :param bldg_power:
        :param now:
        :return:
        """
        _log.debug("***** ENTERING MODIFY LOADS *****************{}".format(self.state))
        scored_devices = self.criteria_container.get_score_order(self.state)
        _log.debug("SCORED devices: {}".format(scored_devices))
        active_devices = self.control_container.get_devices_status(self.state)
        _log.debug("ACTIVE devices: {}".format(active_devices))
        score_order = [device for scored in scored_devices for device in active_devices if scored in [(device[0], device[1])]]
        _log.debug("SCORED AND ACTIVE devices: {}".format(score_order))
        score_order = self.actuator_request(score_order)

        need_curtailed = abs(self.avg_power - self.demand_limit)
        est_curtailed = 0.0
        remaining_devices = score_order[:]

        for device in self.devices:
            if device[8] != "dollar":
                current_tuple = (device[0], device[1], device[7])
                if current_tuple in remaining_devices:
                    remaining_devices.remove(current_tuple)

        if not remaining_devices:
            _log.debug("Everything available has already been curtailed")
            self.lock = False
            return

        self.lock = True
        self.state_at_actuation = self.state
        self.action_end = self.current_time + self.action_time
        self.next_confirm = self.current_time + self.confirm_time

        for device in remaining_devices:
            device_name, device_id, actuator = device
            action_info = self.control_container.get_device((device_name, actuator)).get_control_info(device_id, self.state)
            _log.debug("State: {} - action info: {} - device {}, {} -- remaining {}".format(self.state, action_info, device_name, device_id, remaining_devices))
            if action_info is None:
                continue
            control_pt, control_value, control_load, revert_priority, revert_value, control_mode, error = self.determine_curtail_parms(action_info, device)
            if error:
                gevent.sleep(1)
                continue
            try:
                if self.kill_signal_received:
                    break
                _log.debug("***** ENTER SET POINT *****************")
                result = self.vip.rpc.call(actuator, "set_point", "ilc_agent", control_pt, control_value).get(timeout=30)
                prefix = self.update_base_topic.split("/")[0]
                topic = "/".join([prefix, control_pt, "Actuate"])
                message = {"Value": control_value, "PreviousValue": revert_value}
                self.publish_record(topic, message)
            except (RemoteError, gevent.Timeout) as ex:
                _log.warning("Failed to set {} to {}: {}".format(control_pt, control_value, str(ex)))
                continue

            est_curtailed += control_load
            self.control_container.get_device((device_name, actuator)).increment_control(device_id)
            if self.update_devices(device_name, device_id):
                self.devices.append(
                    [
                        device_name,
                        device_id,
                        control_pt,
                        revert_value,
                        control_load,
                        revert_priority,
                        format_timestamp(self.current_time),
                        actuator,
                        control_mode
                     ]
                )
            if est_curtailed >= need_curtailed:
                break
        self.lock = False
        self.hold()

    def update_devices(self, device_name, device_id):
        """
        Update devices list with only newly controlled devices.
        """
        for device in self.devices:
            if device_name in device and device_id in device:
                return False
        return True

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
        control_devices = []

        already_handled = dict((device[0], True) for device in self.scheduled_devices)

        for item in score_order:

            device, token, device_actuator = item
            point_device = self.control_container.get_device((device, device_actuator)).get_point_device(token, self.state)
            if point_device is None:
                continue

            control_device = self.base_rpc_path(path=point_device)
            if not self.need_actuator_schedule:
                self.scheduled_devices.add((device, device_actuator, control_device))
                control_devices.append(item)
                continue

            _log.debug("Reserving device: {}".format(device))
            if device in already_handled:
                if already_handled[device]:
                    _log.debug("Skipping reserve device (previously reserved): " + device)
                    control_devices.append(item)
                continue

            schedule_request = [[control_device, start_time_str, end_time_str]]
            try:
                if self.kill_signal_received:
                    break
                result = self.vip.rpc.call(device_actuator, "request_new_schedule",
                                           self.agent_id, control_device, "HIGH", schedule_request).get(timeout=30)
            except RemoteError as ex:
                _log.warning("Failed to schedule device {} (RemoteError): {}".format(device, str(ex)))
                continue

            if result is not None and result["result"] == "FAILURE":
                _log.warning("Failed to schedule device (unavailable) " + device)
                already_handled[device] = False
            else:
                already_handled[device] = True
                self.scheduled_devices.add((device, device_actuator, control_device))
                control_devices.append(item)

        return control_devices

    def determine_curtail_parms(self, control, device_dict):
        """
        Pull stored curtail parameters for devices.
        :param control: dictionary containing device control parameters
        :param device_dict: tuple containing device
        :return:
        """
        device, token, device_actuator = device_dict
        contol_pt = control["point"]
        control_load = control["load"]
        revert_priority = control["revert_priority"]
        control_method = control["control_method"]
        control_mode = control["control_mode"]

        control_pt = self.base_rpc_path(path=contol_pt)

        if isinstance(control_load, dict):
            load_equation = control_load["load_equation"]
            load_point_values = []
            for load_arg in control_load["load_equation_args"]:
                point_to_get = self.base_rpc_path(path=load_arg[1])
                try:
                   value = self.vip.rpc.call(device_actuator, "get_point", point_to_get).get(timeout=30)
                except RemoteError as ex:
                    _log.warning("Failed get point for load calculation {} (RemoteError): {}".format(point_to_get, str(ex)))
                    control_load = 0.0
                    break
                load_point_values.append((load_arg[0], value))
                try:
                    control_load = sympy_evaluate(load_equation, load_point_values)
                except:
                    _log.debug("Could not convert expression for load estimation: ")
        error = False
        try:
            revert_value = self.vip.rpc.call(device_actuator, "get_point", control_pt).get(timeout=30)
        except (RemoteError, gevent.Timeout) as ex:
            error = True
            _log.warning("Failed get point for revert value storage {} (RemoteError): {}".format(control_pt, str(ex)))
            revert_value = None
            return control_pt, None, control_load, revert_priority, revert_value, error

        if control_method.lower() == "offset":
            control_value = revert_value + control["offset"]
        elif control_method.lower() == "equation":
            equation = control["control_equation"]
            equation_point_values = []

            for eq_arg in control["equation_args"]:
                point_get = self.base_rpc_path(path=eq_arg[1])
                value = self.vip.rpc.call(device_actuator, "get_point", point_get).get(timeout=30)
                equation_point_values.append((eq_arg[0], value))

            control_value = sympy_evaluate(equation, equation_point_values)
        else:
            control_value = control["value"]

        if None not in [control["minimum"], control["maximum"]]:
            control_value = max(control["minimum"], min(control_value, control["maximum"]))
        elif control["minimum"] is not None and control["maximum"] is None:
            control_value = max(control["minimum"], control_value)
        elif control["maximum"] is not None and control["minimum"] is None:
            control_value = min(control["maximum"], control_value)

        return control_pt, control_value, control_load, revert_priority, revert_value, control_mode, error

    def setup_release(self):
        if self.stagger_release and self.devices:
            _log.debug("Number or controlled devices: {}".format(len(self.devices)))

            confirm_in_minutes = self.confirm_time.total_seconds()/60.0
            release_steps = int(max(1, math.floor(self.stagger_release_time/confirm_in_minutes + 1)))

            self.device_group_size = [int(math.floor(len(self.devices)/release_steps))] * release_steps
            _log.debug("Current group size:  {}".format(self.device_group_size))

            if len(self.devices) > release_steps:
                for group in range(len(self.devices) % release_steps):
                    self.device_group_size[group] += 1
            else:
                self.device_group_size = [0] * release_steps
                interval = int(math.ceil(float(release_steps)/len(self.devices)))
                _log.debug("Release interval offset: {}".format(interval))
                for group in range(0, len(self.device_group_size), interval):
                    self.device_group_size[group] = 1
                unassigned = len(self.devices) - sum(self.device_group_size)
                for group, value in enumerate(self.device_group_size):
                    if value == 0:
                        self.device_group_size[group] = 1
                        unassigned -= 1
                    if unassigned <= 0:
                        break

            self.current_stagger = [math.floor(self.stagger_release_time / (release_steps - 1))] * (release_steps - 1)
            for group in range(int(self.stagger_release_time % (release_steps - 1))):
                self.current_stagger[group] += 1
        else:
            self.device_group_size = [len(self.devices)]
            self.current_stagger = []

        _log.debug("Current stagger time:  {}".format(self.current_stagger))
        _log.debug("Current group size:  {}".format(self.device_group_size))

    def reset_devices(self):
        """
        Release control of devices.
        :return:
        """
        scored_devices = self.criteria_container.get_score_order(self.state_at_actuation)
        controlled = [device for scored in scored_devices for device in self.devices if scored in [(device[0], device[1])]]

        _log.debug("Controlled devices: {}".format(self.devices))

        currently_controlled = controlled[::-1]
        controlled_iterate = currently_controlled[:]
        index_counter = 0
        _log.debug("Controlled devices for release reverse sort: {}".format(currently_controlled))

        for item in range(self.device_group_size.pop(0)):
            device, device_id, control_pt, revert_val, control_load, revert_priority, modified_time, actuator, control_mode = controlled_iterate[item]
            revert_value = self.get_revert_value(device, revert_priority, revert_val)

            _log.debug("Returned revert value: {}".format(revert_value))

            try:
                if revert_value is not None:
                    result = self.vip.rpc.call(actuator, "set_point", "ilc", control_pt, revert_value).get(timeout=30)
                    _log.debug("Reverted point: {} to value: {}".format(control_pt, revert_value))
                else:
                    result = self.vip.rpc.call(actuator, "revert_point", "ilc", control_pt).get(timeout=30)
                    _log.debug("Reverted point: {} - Result: {}".format(control_pt, result))
                if currently_controlled:
                    _log.debug("Removing from controlled list: {} ".format(controlled_iterate[item]))
                    self.control_container.get_device((device, actuator)).reset_control_status(device_id)
                    index = controlled_iterate.index(controlled_iterate[item]) - index_counter
                    currently_controlled.pop(index)
                    index_counter += 1
            except RemoteError as ex:
                _log.warning("Failed to revert point {} (RemoteError): {}".format(control_pt, str(ex)))
                continue
        self.devices = currently_controlled
        if self.current_stagger:
            self.next_release = self.current_time + td(minutes=self.current_stagger.pop(0))
        elif self.state not in ['curtail_holding', 'augment_holding', 'augment', 'curtail', 'inactive']:
            self.finished()
        self.lock = False

    def get_revert_value(self, device, revert_priority, revert_value):
        """
        If BACnet priority array cannot be used this method will return the
        the revert value for the control point.
        :param device:
        :param revert_priority:
        :param revert_value:
        :return:
        """
        # TODO:  Resolve issue with revert_priority as key to do BACNet release.  This is not ideal solution.
        current_device_list = []
        if revert_priority is None:
            return None

        for controlled_device in self.devices:
            if controlled_device[0] == device:
                current_device_list.append(controlled_device)

        if len(current_device_list) <= 1:
            return revert_value

        index_value = max(current_device_list, key=lambda t: t[4])
        return_value = index_value[3]
        _log.debug("Stored revert value: {} for device: {}".format(return_value, device))
        control_set_index = self.devices.index(index_value)
        self.devices[control_set_index][3] = revert_value
        self.devices[control_set_index][4] = revert_priority

        return return_value

    def reinitialize_release(self):
        if self.devices:
            self.device_group_size = [len(self.devices)]
            self.reset_devices()
        self.devices = []
        self.device_group_size = None
        self.next_release = None
        self.action_end = None
        self.next_confirm = self.current_time + self.confirm_time
        self.reset_all_devices()
        if self.state == 'inactive':
            _log.debug("**********TRYING TO RELOAD CONFIG PARAMETERS*********");
            if self.config_reload_needed:
                self.reset_parameters(self.saved_config)

    def reset_all_devices(self):
        for device in self.scheduled_devices:
            try:
                release_all = self.vip.rpc.call(device[1], "revert_device", "ilc", device[2]).get(timeout=30)
                _log.debug("Revert device: {} with return value {}".format(device[2], release_all))
            except RemoteError as ex:
                _log.warning("Failed revert all on device {} (RemoteError): {}".format(device[2], str(ex)))
            result = self.vip.rpc.call(device[1], "request_cancel_schedule", self.agent_id, device[2]).get(timeout=30)
        self.scheduled_devices = set()

    def create_application_status(self, result):
        """
        Publish application status.
        :param current_time_str:
        :param result:
        :return:
        """
        try:
            topic = "/".join([self.update_base_topic, self.agent_id])
            application_state = "Inactive"
            if self.devices:
                application_state = "Active"
            if self.sim_running:
                headers = {
                    headers_mod.DATE: format_timestamp(self.current_time)
                }
            else:
                headers = {
                    headers_mod.DATE: format_timestamp(get_aware_utc_now()),
                }

            application_message = [
                {
                    "Timestamp": format_timestamp(self.current_time),
                    "Result": result,
                    "ApplicationState": application_state
                },
                {
                    "Timestamp": {"tz": self.power_meta["tz"], "type": "timestamp", "units": "None"},
                    "Result": {"tz": self.power_meta["tz"], "type": "string", "units": "None"},
                    "ApplicationState": {"tz": self.power_meta["tz"], "type": "string", "units": "None"}
                }
            ]
            self.vip.pubsub.publish("pubsub", topic, headers=headers, message=application_message).get(timeout=30.0)
        except:
            _log.debug("Unable to publish application status message.")

    def create_device_status_publish(self, device_time, device_name, data, topic, meta):
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
            device_tokens = self.control_container.devices[device_name].command_status.keys()
            for subdevice in device_tokens:
                control = self.control_container.get_device(device_name).get_control_info(subdevice)
                control_pt = control["point"]
                device_update_topic = "/".join([self.base_rpc_path, device_name[0], subdevice, control_pt])
                previous_value = data[control_pt]
                control_time = None
                device_state = "Inactive"
                for item in self.devices:
                    if device_name[0] == item[0]:
                        previous_value = item[2]
                        control_time = item[4]
                        device_state = "Active"

                if self.sim_running:
                    headers = {
                        headers_mod.DATE: format_timestamp(self.current_time),
                        "ApplicationName": self.agent_id,
                    }
                else:
                    headers = {
                        headers_mod.DATE: format_timestamp(get_aware_utc_now()),
                        "ApplicationName": self.agent_id,
                    }

                device_msg = [
                    {
                        "DeviceState": device_state,
                        "PreviousValue": previous_value,
                        "Timestamp": format_timestamp(device_time),
                        "TimeChanged": control_time
                    },
                    {
                        "PreviousValue": meta[control_pt],
                        "TimeChanged": {
                            "tz": meta[control_pt]["tz"],
                            "type": "datetime"
                        },
                        "DeviceState": {"tz": meta[control_pt]["tz"], "type": "string"},
                        "Timestamp": {"tz": self.power_meta["tz"], "type": "timestamp", "units": "None"},
                    }
                ]
                self.vip.pubsub.publish("pubsub",
                                        device_update_topic,
                                        headers=headers,
                                        message=device_msg).get(timeout=4.0)
        except:
            _log.debug("Unable to publish device status message.")

    def demand_limit_handler(self, peer, sender, bus, topic, headers, message):
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
        self.sim_time = 0
        if isinstance(message, list):
            target_info = message[0]["value"]
            tz_info = message[1]["value"]["tz"]
        else:
            target_info = message
            tz_info = "US/Pacific"

        to_zone = dateutil.tz.gettz(tz_info)
        try:
            start_time = parser.parse(target_info["start"])
            end_time = target_info.get("end")
            end_time = parser.parse(end_time) if end_time is not None else start_time.replace(hour=23, minute=59,
                                                                                              second=59)
            target = target_info["target"]
            demand_goal = float(target) if target is not None else target
            task_id = target_info["id"]
        except (KeyError, ValueError, TypeError) as ex:
            _log.warning("Malformed demand target message, cannot set new target: %s", str(ex))
            return
        if start_time.tzinfo is None or start_time.tzinfo.utcoffset(start_time) is None:
            start_time = start_time.replace(tzinfo=to_zone)
            end_time = end_time.replace(tzinfo=to_zone)
        if self.sim_running:
            self.update_sim_tasklist(start_time, end_time, demand_goal, task_id)
        else:
            self.update_tasklist(start_time, end_time, demand_goal, task_id)

    def update_tasklist(self, start_time, end_time, demand_goal, task_id):
        task_list = []
        for key, value in self.tasks.items():
            if start_time == value["end"]:
                start_time += td(seconds=5)
            if (start_time < value["end"] and end_time > value["start"]) or value["start"] <= start_time <= value["end"]:
                task_list.append(key)
        for task in task_list:
            sched_tasks = self.tasks.pop(task)["schedule"]
            for current_task in sched_tasks:
                current_task.cancel()

        current_task_exists = self.tasks.get(task_id)
        if current_task_exists is not None:
            _log.debug("TARGET: duplicate task - {}".format(task_id))
            for item in self.tasks.pop(task_id)["schedule"]:
                item.cancel()
        _log.debug("TARGET: create schedule - ID: {}".format(task_id))
        self.tasks[task_id] = {
            "schedule": [
                self.core.schedule(start_time,
                                   self.demand_limit_update,
                                   demand_goal,
                                   task_id),
                self.core.schedule(end_time,
                                   self.demand_limit_update,
                                   None,
                                   task_id)
            ],
            "start": start_time,
            "end": end_time,
            "target": demand_goal
        }

    def update_sim_tasklist(self, start_time, end_time, demand_goal, task_id):
        key_list = []
        for key, value in self.tasks.items():
            if (start_time < value["end"] and end_time > value["start"]) or (
                    value["start"] <= start_time < value["end"]):
                key_list.append(key)
        for key in key_list:
            self.tasks.pop(key)

        _log.debug("TARGET: received demand goal schedule - start: {} - end: {} - target: {}.".format(start_time,
                                                                                                      end_time,
                                                                                                      demand_goal))
        self.tasks[task_id] = {"start": start_time, "end": end_time, "target": demand_goal}
        return

    def publish_record(self, topic_suffix, message):
        if self.sim_running:
            headers = {headers_mod.DATE: format_timestamp(self.current_time)}
        else:
            headers = {headers_mod.DATE: format_timestamp(get_aware_utc_now())}
        message["TimeStamp"] = format_timestamp(self.current_time)
        topic = "/".join([self.record_topic, topic_suffix])
        self.vip.pubsub.publish("pubsub", topic, headers, message).get()


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
