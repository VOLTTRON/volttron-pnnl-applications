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
operated by
BATTELLE
for the
UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
"""

import sys
import logging
import dateutil.tz
from datetime import timedelta as td
from dateutil import parser
import gevent
from volttron.platform.agent import utils
from volttron.platform.jsonapi import dumps
from volttron.platform.messaging import (headers as headers_mod, topics)
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import setup_logging, format_timestamp
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.jsonrpc import RemoteError
from .diagnostics import common
from .diagnostics.sat_aircx import SupplyTempAIRCx
from .diagnostics.schedule_reset_aircx import SchedResetAIRCx
from .diagnostics.stcpr_aircx import DuctStaticAIRCx

__version__ = "2.0.0"

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.debug, format="%(asctime)s   %(levelname)-8s %(message)s",
                    datefmt="%m-%d-%y %H:%M:%S")


class AirsideAgent(Agent):
    """
     Agent that starts all of the Airside diagnostics
    """

    def __init__(self, config_path, **kwargs):
        super(AirsideAgent, self).__init__(**kwargs)

        # list of class attributes.  Default values will be filled in from reading config file
        # string attributes
        self.analysis_name = ""
        self.config = None
        self.device = {}
        self.campus = ""
        self.building = ""
        self.units = {}
        self.sensitivity = ""
        self.fan_status_name = ""
        self.fan_sp_name = ""
        self.duct_stcpr_stpt_name = ""
        self.duct_stcpr_name = ""
        self.sa_temp_name = ""
        self.sat_stpt_name = ""
        self.zn_damper_name = ""
        self.zn_reheat_name = ""
        self.initialize_time = None
        self.timezone = ""

        # int attributes
        self.no_required_data = 0
        self.warm_up_time = 0
        self.data_window = 0
        self.fan_speed = None
        self.interval = 0

        # float attributes
        self.stcpr_retuning = 0.0
        self.min_stcpr_stpt = 0.0
        self.max_stcpr_stpt = 0.0
        self.sat_retuning = 0.0
        self.min_sat_stpt = 0.0
        self.max_sat_stpt = 0.0
        self.low_sf_thr = 0.0
        self.high_sf_thr = 0.0
        self.stcpr_stpt_deviation_thr = 0.0
        self.zn_high_damper_thr = 0.0
        self.zn_low_damper_thr = 0.0
        self.hdzn_damper_thr = 0.0
        self.stcpr_reset_thr = 0.0
        self.sat_stpt_deviation_thr = 0.0
        self.sat_high_damper_thr = 0.0
        self.rht_on_thr = 0.0
        self.percent_reheat_thr = 0.0
        self.percent_damper_thr = 0.0
        self.reheat_valve_thr = 0.0
        self.sat_reset_thr = 0.0
        self.unocc_time_thr = 0.0
        self.unocc_stp_thr = 0.0
        self.missing_data_threshold = 0.0

        # list attributes
        self.device_list = []
        self.publish_list = []
        self.master_devices = []
        self.needed_devices = []
        self.missing_data = []
        self.units = []
        self.arguments = []
        self.point_mapping = []
        self.monday_sch = []
        self.tuesday_sch = []
        self.wednesday_sch = []
        self.thursday_sch = []
        self.friday_sch = []
        self.saturday_sch = []
        self.sunday_sch = []
        self.fan_status_data = []
        self.stcpr_stpt_data = []
        self.stcpr_data = []
        self.sat_stpt_data = []
        self.sat_data = []
        self.zn_rht_data = []
        self.zn_dmpr_data = []
        self.fan_sp_data = []
        self.device_values = {}
        self.stcpr_stpt_deviation_thr_dict = {}
        self.sat_stpt_deviation_thr_dict = {}
        self.percent_reheat_thr_dict = {}
        self.percent_damper_thr_dict = {}
        self.reheat_valve_thr_dict = {}
        self.sat_high_damper_thr_dict = {}
        self.zn_high_damper_thr_dict = {}
        self.zn_low_damper_thr_dict = {}
        self.hdzn_damper_thr_dict = {}
        self.unocc_stp_thr_dict = {}
        self.unocc_time_thr_dict = {}
        self.sat_reset_threshold_dict = {}
        self.stcpr_reset_threshold_dict = {}
        self.command_tuple = []
        self.device_topic_dict = {}

        # bool attributes
        self.auto_correct_flag = None
        self.warm_up_start = None
        self.warm_up_flag = True
        self.unit_status = None
        self.low_sf_condition = None
        self.high_sf_condition = None
        self.actuation_mode = None
        self.diagnostic_done_flag = True

        # diagnostics
        self.stcpr_aircx = None
        self.sat_aircx = None
        self.sched_reset_aircx = None

        # read configuration file
        self.read_config(config_path)

    def read_config(self, config_path):
        """
        Use volttrons config reader to grab and parse out configuration file
        config_path: The path to the agents configuration file
        """
        file_config = utils.load_config(config_path)
        default_config = self.setup_default_config()
        if file_config:
            self.config = file_config
        else:
            self.config = default_config

        self.vip.config.set_default("config", self.config)
        self.vip.config.subscribe(self.configure_main, actions=["NEW", "UPDATE"], pattern="config")

    def setup_device_list(self):
        """Setup the device subscriptions"""
        self.analysis_name = self.config.get("analysis_name", "AirsideAIRCx")
        self.actuation_mode = self.config.get("actuation_mode", "passive")
        self.timezone = self.config.get("local_timezone", "US/Pacific")
        self.interval = self.config.get("interval", 60)
        self.missing_data_threshold = self.config.get("missing_data_threshold", 15.0) / 100.0

        self.device = self.config.get("device", {})
        if not self.device:
            _log.warning("device parameters are not present in configuration file for {}".format(self.core.identity))
            self.core.stop()

        self.campus = self.device.get("campus", "")
        self.building = self.device.get("building", "")
        self.units = self.device.get("unit", {})
        if not self.units:
            _log.warning("device unit parameters are not present in configuration file for {}".format(self.core.identity))
            self.core.stop()
        has_zone_information = False
        for u in self.units:
            # building the connection string for each unit
            device_topic = topics.DEVICES_VALUE(campus=self.campus, building=self.building, unit=u, path="",
                                                point="all")
            self.device_list.append(device_topic)
            self.publish_list.append("/".join([self.campus, self.building, u]))
            self.device_topic_dict.update({device_topic: u})
            self.master_devices.append(u)
            # loop over subdevices and add them
            if "subdevices" in self.units[u]:
                for sd in self.units[u]["subdevices"]:
                    has_zone_information = True
                    subdevice_topic = topics.DEVICES_VALUE(campus=self.campus, building=self.building,
                                                           unit=u, path=sd, point="all")
                    self.device_list.append(subdevice_topic)
                    sd_string = u + "/" + sd
                    self.master_devices.append(sd_string)
                    self.device_topic_dict.update({subdevice_topic: sd_string})
        if not has_zone_information:
            _log.warning("subdevice (VAV zone information) is missing from device unit configuration for {}".format(self.core.identity))
            self.core.stop()
        self.initialize_devices()

    def configure_main(self, config_name, action, contents):
        """This triggers configuration via the VOLTTRON configuration store.
        :param config_name: canonical name is config
        :param action: on instantiation this is "NEW" or
        "UPDATE" if user uploads update config to store
        :param contents: configuration contents
        :return: None
        """
        _log.info("Update %s for %s", config_name, self.core.identity)
        self.config.update(contents)
        if action == "NEW" or "UPDATE":
            while not self.diagnostic_done_flag:
                gevent.sleep(0.25)
                _log.info("Waiting for Diagnostics to finish before updating configuration!")
            self.update_configuration()

    def update_configuration(self):
        """Update configurations for agent"""
        self.device_unsubscribe()
        self.device_list = []
        self.publish_list = []
        self.master_devices = []
        self.needed_devices = []
        self.setup_device_list()
        self.read_argument_config()
        self.read_point_mapping()
        self.configuration_value_check()
        self.create_thresholds()
        self.create_diagnostics()
        self.onstart_subscriptions(None)

    def setup_default_config(self):
        """Setup a default configuration object"""
        default_config = {
            "device": {
                "campus": "campus",
                "building": "building",
                "unit": {

                    "AHU3": {
                        "subdevices": [
                            "VAV107", "VAV104",
                            "VAV116", "VAV105"
                        ]
                    }
                }
            },
            "analysis_name": "AirsideAIRCx",
            "actuation_mode": "passive",
            "arguments": {
                "point_mapping": {
                    "fan_status": "supplyfanstatus",
                    "zone_reheat": "heatingsignal",
                    "zone_damper": "damperposition",
                    "duct_stp": "ductstaticpressure",
                    "duct_stp_stpt": "ductstaticpressuresetpoint",
                    "sa_temp": "dischargeairtemperature",
                    "fan_speedcmd": "supplyfanspeed",
                    "sat_stpt": "dischargeairtemperaturesetpoint"
                }
                #### Uncomment to customize thresholds (thresholds have single #)

                # "no_required_data": 10,
                # "sensitivity": custom

                ### auto_correct_flag can be set to false, "low", "normal", or "high" ###
                # "auto_correct_flag": false,
                # "warm_up_time": 5,

                ### data_window - time duration for data collection prior to analysis_name
                ### if data_window is ommitted from configuration defaults to run on the hour.

                ### Static Pressure AIRCx Thresholds ###
                # "stcpr_stpt_deviation_thr": 20
                # "warm_up_time": 5,
                # "duct_stcpr_retuning": 0.1,
                # "max_duct_stcpr_stpt": 2.5,
                # "high_sf_thr": 95.0,
                # "low_sf_thr": 20.0,
                # "zn_high_damper_thr": 90.0,
                # "zn_low_damper_thr": 10.0,
                # "min_duct_stcpr_stpt": 0.5,
                # "hdzn_damper_thr": 30.0,

                ### SAT AIRCx Thresholds ###
                # "sat_stpt_deviation_thr": 5,
                # "percent_reheat_thr": 25.0,
                # "rht_on_thr": 10.0,
                # "sat_high_damper_thr": 80.0,
                # "percent_damper_thr": 60.0,
                # "min_sat_stpt": 50.0,
                # "sat_retuning": 1.0,
                # "reheat_valve_thr": 50.0,
                # "max_sat_stpt": 75.0,

                #### Schedule/Reset AIRCx Thresholds ###
                # "unocc_time_thr": 40.0,
                # "unocc_stcpr_thr": 0.2,
                # "monday_sch": ["5:30","18:30"],
                # "tuesday_sch": ["5:30","18:30"],
                # "wednesday_sch": ["5:30","18:30"],
                # "thursday_sch": ["5:30","18:30"],
                # "friday_sch": ["5:30","18:30"],
                # "saturday_sch": ["0:00","0:00"],
                # "sunday_sch": ["0:00","0:00"],

                # "sat_reset_thr": 5.0,
                # "stcpr_reset_thr": 0.25
            }
        }
        return default_config

    def device_unsubscribe(self):
        """Method used to unsubscribe devices"""
        self.vip.pubsub.unsubscribe("pubsub", None, None)

    def initialize_devices(self):
        """Set which devices are needed and blank out the values"""
        self.needed_devices = self.master_devices[:]
        self.device_values = {}

    def read_argument_config(self):
        """read all the config arguments section
        no return
        """
        self.arguments = self.config.get("arguments", {})
        self.no_required_data = self.read_argument("no_required_data", 10)
        self.warm_up_time = self.read_argument("warm_up_time", 15)
        self.data_window = self.read_argument("data_window", None)
        self.stcpr_retuning = self.read_argument("duct_stcpr_retuning", 0.1)
        self.min_stcpr_stpt = self.read_argument("min_duct_stcpr_stpt", 0.5)
        self.max_stcpr_stpt= self.read_argument("max_duct_stcpr_stpt", 2.5)
        self.sat_retuning = self.read_argument("sat_retuning", 1.0)
        self.min_sat_stpt = self.read_argument("min_sat_stpt", 50.0)
        self.max_sat_stpt = self.read_argument("max_sat_stpt", 70.0)
        self.low_sf_thr = self.read_argument("low_sf_thr", 20.0)
        self.high_sf_thr = self.read_argument("high_sf_thr", 95.0)
        self.auto_correct_flag = self.read_argument("auto_correct_flag", False)
        self.stcpr_stpt_deviation_thr = self.read_argument("stcpr_stpt_deviation_thr", 20.0)
        self.zn_high_damper_thr = self.read_argument("zn_high_damper_thr", 90.0)
        self.zn_low_damper_thr = self.read_argument("zn_low_damper_thr", 25.0)
        self.hdzn_damper_thr = self.read_argument("hdzn_damper_thr", 30.0)
        self.stcpr_reset_thr = self.read_argument("stcpr_reset_thr", 0.25)
        self.sat_stpt_deviation_thr = self.read_argument("sat_stpt_deviation_thr", 5.0)
        self.sat_high_damper_thr = self.read_argument("sat_high_damper_thr", 80.0)
        self.rht_on_thr = self.read_argument("rht_on_thr", 10.0)
        self.percent_reheat_thr = self.read_argument("percent_reheat_thr", 25.0)
        self.percent_damper_thr = self.read_argument("percent_damper_thr", 60.0)
        self.reheat_valve_thr = self.read_argument("reheat_valve_thr", 50.0)
        self.sat_reset_thr = self.read_argument("sat_reset_thr", 2.0)
        self.unocc_time_thr = self.read_argument("unocc_time_thr", 40.0)
        self.unocc_stp_thr = self.read_argument("unocc_stcpr_thr", 0.2)
        self.monday_sch = self.read_argument("monday_sch", ["5:30", "18:30"])
        self.tuesday_sch = self.read_argument("tuesday_sch", ["5:30", "18:30"])
        self.wednesday_sch = self.read_argument("wednesday_sch", ["5:30", "18:30"])
        self.thursday_sch = self.read_argument("thursday_sch", ["5:30", "18:30"])
        self.friday_sch = self.read_argument("friday_sch", ["5:30", "18:30"])
        self.saturday_sch = self.read_argument("saturday_sch", ["0:00", "0:00"])
        self.sunday_sch = self.read_argument("saturday_sch", ["0:00", "0:00"])
        self.analysis_name = self.read_argument("analysis_name", "AirsideAIRCx")
        self.sensitivity = self.read_argument("sensitivity", "default")
        self.point_mapping = self.read_argument("point_mapping", {})

    def read_argument(self, config_key, default_value):
        """Method that reads an argument from the config file and returns the value or returns the default value if key is not present in config file
        return mixed (string or float or int or dict)
        """
        return_value = default_value
        if config_key in self.arguments:
            return_value = self.arguments[config_key]
        return return_value

    def read_point_mapping(self):
        """Method that reads the point mapping and sets the values
        no return
        """
        self.fan_status_name = self.get_point_mapping_or_none("fan_status")
        self.fan_sp_name = self.get_point_mapping_or_none("fan_speedcmd")
        self.duct_stcpr_stpt_name = self.get_point_mapping_or_none("duct_stcpr_stpt")
        self.duct_stcpr_name = self.get_point_mapping_or_none("duct_stcpr")
        self.sa_temp_name = self.get_point_mapping_or_none("sa_temp")
        self.sat_stpt_name = self.get_point_mapping_or_none("sat_stpt")
        self.zn_damper_name = self.get_point_mapping_or_none("zone_damper")
        self.zn_reheat_name = self.get_point_mapping_or_none("zone_reheat")

    def get_point_mapping_or_none(self, name):
        """ Get the item from the point mapping, or return None
        return mixed (string or float or int or dic
        """
        value = self.point_mapping.get(name, None)
        return value

    def configuration_value_check(self):
        """Method goes through the configuration values and checks them for correctness.  Will error if values are not correct. Some may change based on specific settings
        no return
        """
        if self.sensitivity is not None and self.sensitivity == "custom":
            self.stcpr_stpt_deviation_thr = max(10.0, min(self.stcpr_stpt_deviation_thr, 30.0))
            self.zn_high_damper_thr = max(70.0, min(self.zn_high_damper_thr, 70.0))
            self.zn_low_damper_thr = max(0.0, min(self.zn_low_damper_thr, 35.0))
            self.hdzn_damper_thr = max(20.0, min(self.hdzn_damper_thr, 50.0))
            self.stcpr_reset_thr = max(0.1, min(self.stcpr_reset_thr, 0.5))

            self.sat_stpt_deviation_thr = max(2.0, min(self.sat_stpt_deviation_thr, 10.0))
            self.rht_on_thr = max(5.0, min(self.rht_on_thr, 30.0))
            self.sat_high_damper_thr = max(70.0, min(self.sat_high_damper_thr, 90.0))
            self.percent_reheat_thr = max(10.0, min(self.percent_reheat_thr, 40.0))
            self.percent_damper_thr = max(45.0, min(self.percent_damper_thr, 75.0))
            self.reheat_valve_thr = max(25.0, min(self.reheat_valve_thr, 75.0))
            self.sat_reset_thr = max(1.0, min(self.sat_reset_thr, 5.0))

            self.unocc_time_thr = max(20.0, min(self.unocc_time_thr, 60.0))
            self.unocc_stp_thr = max(0.125, min(self.unocc_stp_thr, 0.3))

            self.stcpr_retuning = max(0.1, min(self.stcpr_retuning, 0.25))
            self.sat_retuning = max(1.0, min(self.sat_retuning, 3.0))
        else:
            self.stcpr_stpt_deviation_thr = 20.0
            self.zn_high_damper_thr = 90.0
            self.zn_low_damper_thr = 25.0
            self.hdzn_damper_thr = 30.0
            self.stcpr_reset_thr = 0.25

            self.sat_stpt_deviation_thr = 5.0
            self.rht_on_thr = 10.0
            self.sat_high_damper_thr = 80.0
            self.percent_reheat_thr = 25.0
            self.percent_damper_thr = 60.0
            self.reheat_valve_thr = 50.0
            self.sat_reset_thr = 2.0

            self.unocc_time_thr = 40.0
            self.unocc_stp_thr = 0.2

            self.stcpr_retuning = 0.15
            self.sat_retuning = 1

        self.data_window = td(minutes=self.data_window) if self.data_window is not None else None
        self.no_required_data = int(self.no_required_data)
        self.low_sf_thr = float(self.low_sf_thr)
        self.high_sf_thr = float(self.high_sf_thr)
        self.warm_up_time = td(minutes=self.warm_up_time)
        self.initialize_time = None

        if self.actuation_mode.lower() == "active":
            self.actuation_mode = True
        else:
            self.actuation_mode = False

        if self.fan_sp_name is None and self.fan_status_name is None:
            _log.error("SupplyFanStatus or SupplyFanSpeed are required to verify AHU status.")
            _log.error("Exiting diagnostic, check configuration point mapping!")
            self.core.stop()

    def create_thresholds(self):
        """Create all the threshold dictionaries needed"""
        self.stcpr_stpt_deviation_thr_dict = {
            "low": self.stcpr_stpt_deviation_thr * 1.5,
            "normal": self.stcpr_stpt_deviation_thr,
            "high": self.stcpr_stpt_deviation_thr * 0.5
        }
        self.sat_stpt_deviation_thr_dict = {
            "low": self.sat_stpt_deviation_thr * 1.5,
            "normal": self.sat_stpt_deviation_thr,
            "high": self.sat_stpt_deviation_thr * 0.5
        }
        self.percent_reheat_thr_dict = {
            "low": self.percent_reheat_thr,
            "normal": self.percent_reheat_thr,
            "high": self.percent_reheat_thr
        }
        self.percent_damper_thr_dict = {
            "low": self.percent_damper_thr + 15.0,
            "normal": self.percent_damper_thr,
            "high": self.percent_damper_thr - 15.0
        }
        self.reheat_valve_thr_dict = {
            "low": self.reheat_valve_thr * 1.5,
            "normal": self.reheat_valve_thr,
            "high": self.reheat_valve_thr * 0.5
        }
        self.sat_high_damper_thr_dict = {
            "low": self.sat_high_damper_thr + 15.0,
            "normal": self.sat_high_damper_thr,
            "high": self.sat_high_damper_thr - 15.0
        }
        self.zn_high_damper_thr_dict = {
            "low": self.zn_high_damper_thr + 5.0,
            "normal": self.zn_high_damper_thr,
            "high": self.zn_high_damper_thr - 5.0
        }
        self.zn_low_damper_thr_dict = {
            "low": self.zn_low_damper_thr,
            "normal": self.zn_low_damper_thr,
            "high": self.zn_low_damper_thr
        }
        self.hdzn_damper_thr_dict = {
            "low": self.hdzn_damper_thr - 5.0,
            "normal": self.hdzn_damper_thr,
            "high": self.hdzn_damper_thr + 5.0
        }
        self.unocc_stp_thr_dict = {
            "low": self.unocc_stp_thr * 1.5,
            "normal": self.unocc_stp_thr,
            "high": self.unocc_stp_thr * 0.625
        }
        self.unocc_time_thr_dict = {
            "low": self.unocc_time_thr * 1.5,
            "normal": self.unocc_time_thr,
            "high": self.unocc_time_thr * 0.5
        }
        self.sat_reset_threshold_dict = {
            "low": max(self.sat_reset_thr - 1.0, 0.5),
            "normal": self.sat_reset_thr,
            "high": self.sat_reset_thr + 1.0
        }
        self.stcpr_reset_threshold_dict = {
            "low": self.stcpr_reset_thr * 0.5,
            "normal": self.stcpr_reset_thr,
            "high": self.stcpr_reset_thr * 1.5
        }

    def create_diagnostics(self):
        """creates the diagnostic classes
        No return
        """
        self.stcpr_aircx = DuctStaticAIRCx()
        self.stcpr_aircx.set_class_values(self.command_tuple, self.no_required_data, self.data_window, self.auto_correct_flag,
                                          self.stcpr_stpt_deviation_thr_dict, self.max_stcpr_stpt, self.stcpr_retuning, self.zn_high_damper_thr_dict,
                                          self.zn_low_damper_thr_dict, self.hdzn_damper_thr_dict, self.min_stcpr_stpt, self.duct_stcpr_stpt_name)
        self.stcpr_aircx.setup_platform_interfaces(self.publish_results, self.send_autocorrect_command)

        self.sat_aircx = SupplyTempAIRCx()
        self.sat_aircx.set_class_values(self.command_tuple, self.no_required_data, self.data_window, self.auto_correct_flag,
                                        self.sat_stpt_deviation_thr_dict, self.rht_on_thr,
                                        self.sat_high_damper_thr_dict, self.percent_damper_thr_dict,
                                        self.percent_reheat_thr_dict, self.min_sat_stpt, self.sat_retuning,
                                        self.reheat_valve_thr_dict, self.max_sat_stpt, self.sat_stpt_name)
        self.sat_aircx.setup_platform_interfaces(self.publish_results, self.send_autocorrect_command)

        self.sched_reset_aircx = SchedResetAIRCx()
        self.sched_reset_aircx.set_class_values(self.unocc_time_thr_dict, self.unocc_stp_thr_dict, self.monday_sch, self.tuesday_sch, self.wednesday_sch,
                                                self.thursday_sch, self.friday_sch, self.saturday_sch, self.sunday_sch, self.no_required_data,
                                                self.stcpr_reset_threshold_dict, self.sat_reset_threshold_dict)
        self.sched_reset_aircx.setup_platform_interfaces(self.publish_results, self.send_autocorrect_command)

    def parse_data_dict(self, data):
        """Breaks down the passed VOLTTRON message
        data: dictionary
        no return
        """
        # reset the data arrays on new message
        self.fan_status_data = []
        self.stcpr_stpt_data = []
        self.stcpr_data = []
        self.sat_stpt_data = []
        self.sat_data = []
        self.zn_rht_data = []
        self.zn_dmpr_data = []
        self.fan_sp_data = []

        for key, value in data.items():
            if value is None:
                continue
            if key == self.fan_status_name:
                self.fan_status_data = value
            elif key == self.duct_stcpr_stpt_name:
                self.stcpr_stpt_data = value
            elif key == self.duct_stcpr_name:
                self.stcpr_data = value
            elif key == self.sat_stpt_name:
                self.sat_stpt_data = value
            elif key == self.sa_temp_name:
                self.sat_data = value
            elif key == self.zn_reheat_name:
                self.zn_rht_data = value
            elif key == self.zn_damper_name:
                self.zn_dmpr_data = value
            elif key == self.fan_sp_name:
                self.fan_sp_data = value

    def check_for_missing_data(self):
        """Method that checks the parsed message results for any missing data
        return bool
        """
        self.missing_data = []
        if not self.fan_status_data and not self.fan_sp_data:
            self.missing_data.append(self.fan_status_name)
        if not self.sat_data:
            self.missing_data.append(self.sa_temp_name)
        if not self.zn_rht_data:
            _log.info("Zone reheat data is missing.")
        if not self.sat_stpt_data:
            _log.info("SAT set point data is missing.")
        if not self.stcpr_data:
            self.missing_data.append(self.duct_stcpr_name)
        if not self.stcpr_stpt_data:
            _log.info("Duct static pressure set point data is missing.")
        if not self.zn_dmpr_data:
            self.missing_data.append(self.zn_damper_name)

        if self.missing_data:
            return True
        return False

    def check_fan_status(self, current_time):
        """Check the status and speed of the fan
        current_time: datetime time delta
        return int
        """
        if self.fan_status_data:
            supply_fan_status = int(max(self.fan_status_data))
        else:
            supply_fan_status = None

        if self.fan_sp_data:
            self.fan_speed = mean(self.fan_sp_data)
        else:
            self.fan_speed = None
        if supply_fan_status is None:
            if self.fan_speed > self.low_sf_thr:
                supply_fan_status = 1
            else:
                supply_fan_status = 0

        if not supply_fan_status:
            if self.unit_status is None:
                self.unit_status = current_time
        else:
            self.unit_status = None
        return supply_fan_status

    def check_elapsed_time(self, current_time):
        """Check on time since last message to see if it is in data window
        current_time: datetime time delta
        condition: datetime time delta
        message: string
        """
        condition = self.unit_status
        message = common.FAN_OFF
        if condition is not None:
            elapsed_time = current_time - condition
        else:
            elapsed_time = td(minutes=0)
        if self.data_window is not None:
            if elapsed_time >= self.data_window:
                common.pre_conditions(self.publish_results, message, common.dx_list, current_time)
                self.clear_all()
        elif condition is not None and condition.hour != current_time.hour:
            message_time = condition.replace(minute=0)
            common.pre_conditions(self.publish_results, message, common.dx_list, message_time)
            self.clear_all()

    def clear_all(self):
        """Reinitialize all data arrays for diagnostics.
        no return
        """
        self.sat_aircx.reinitialize()
        self.stcpr_aircx.reinitialize()
        self.warm_up_start = None
        self.warm_up_flag = True
        self.unit_status = None

    @Core.receiver("onstart")
    def onstart_subscriptions(self, sender, **kwargs):
        """Method used to setup data subscription on startup of the agent"""
        for device in self.device_list:
            _log.info("Subscribing to " + device)
            self.vip.pubsub.subscribe(peer="pubsub", prefix=device, callback=self.new_data_message)

    def new_data_message(self, peer, sender, bus, topic, headers, message):
        """
        Call back method for curtailable device data subscription.
        peer: string
        sender: string
        bus: string
        topic: string
        headers: dict
        message: dict
        no return
        """
        current_time = parser.parse(headers["Date"])
        missing_but_running = False
        if self.initialize_time is None and len(self.master_devices) > 1:
            self.initialize_time = self.find_reinitialize_time(current_time)

        if self.initialize_time is not None and current_time < self.initialize_time:
            if len(self.master_devices) > 1:
                return

        to_zone = dateutil.tz.gettz(self.timezone)
        current_time = current_time.astimezone(to_zone)
        device_data = message[0]
        if isinstance(device_data, list):
            device_data = device_data[0]

        device_needed = self.aggregate_subdevice(device_data, topic)
        if not device_needed:
            fraction_missing = float(len(self.needed_devices)) / len(self.master_devices)
            if fraction_missing > self.missing_data_threshold:
                _log.error("Device values already present, reinitializing at publish: {}".format(current_time))
                self.initialize_devices()
                device_needed = self.aggregate_subdevice(device_data, topic)
                return
            missing_but_running = True
            _log.warning("Device already present. Using available data for diagnostic.: {}".format(current_time))
            _log.warning("Device  already present - topic: {}".format(topic))
            _log.warning("All devices: {}".format(self.master_devices))
            _log.warning("Needed devices: {}".format(self.needed_devices))

        if self.should_run_now() or missing_but_running:
            field_names = {}
            for point, data in self.device_values.items():
                field_names[point] = data
            self.run_diagnostics(current_time, field_names)
            self.initialize_devices()
            if missing_but_running:
                device_needed = self.aggregate_subdevice(field_names, topic)
        else:
            _log.info("Still need {} before running.".format(self.needed_devices))

    def aggregate_subdevice(self, device_data, topic):
        """Get device data organized and remove the device from the needed list of data elements"""
        tagged_device_data = {}
        device_tag = self.device_topic_dict[topic]
        _log.debug("Current device to aggregate: {}".format(device_tag))
        if device_tag not in self.needed_devices:
            return False
        for key, value in device_data.items():
            device_data_tag = "&".join([key, device_tag])
            tagged_device_data[device_data_tag] = value
        self.device_values.update(tagged_device_data)
        self.needed_devices.remove(device_tag)
        return True

    def should_run_now(self):
        """
        Checks if messages from all the devices are received
            before running application
        :returns: True or False based on received messages.
        :rtype: boolean
        """
        # Assumes the unit/all values will have values.
        if not self.device_values.keys():
            return False
        return not self.needed_devices

    def run_diagnostics(self, current_time, device_data):
        """Run diagnostics on the data that is available."""
        _log.info("Processing Results!")
        self.diagnostic_done_flag = False
        device_dict = {}
        for key, value in device_data.items():
            point_device = [_name for _name in key.split("&")]
            if point_device[0] not in device_dict:
                device_dict[point_device[0]] = [value]
            else:
                device_dict[point_device[0]].append(value)
        self.parse_data_dict(device_dict)
        missing_data = self.check_for_missing_data()
        if missing_data:
            _log.info("Missing data from publish: {}".format(self.missing_data))
            return self.run_diagnostics_done()

        current_fan_status = self.check_fan_status(current_time)
        self.sched_reset_aircx.schedule_reset_aircx(current_time, self.stcpr_data, self.stcpr_stpt_data,
                                                    self.sat_stpt_data, current_fan_status)
        self.check_elapsed_time(current_time)
        if not current_fan_status:
            _log.info("Supply fan is off: {}".format(current_time))
            self.warm_up_flag = True
            return self.run_diagnostics_done()
        _log.info("Supply fan is on: {}".format(current_time))

        if self.fan_speed is not None and self.fan_speed > self.high_sf_thr:
            self.low_sf_condition = True
        else:
            self.low_sf_condition = False

        if self.fan_speed is not None and self.fan_speed < self.low_sf_thr:
            self.high_sf_condition = True
        else:
            self.high_sf_condition = False

        if self.warm_up_flag:
            self.warm_up_flag = False
            self.warm_up_start = current_time

        if self.warm_up_start is not None and (current_time - self.warm_up_start) < self.warm_up_time:
            _log.info("Unit is in warm-up. Data will not be analyzed.")
            return self.run_diagnostics_done()

        self.stcpr_aircx.stcpr_aircx(current_time, self.stcpr_stpt_data, self.stcpr_data, self.zn_dmpr_data, self.low_sf_condition, self.high_sf_condition)
        self.sat_aircx.sat_aircx(current_time, self.sat_data, self.sat_stpt_data, self.zn_rht_data, self.zn_dmpr_data)
        return self.run_diagnostics_done()

    def find_reinitialize_time(self, current_time):
        """determine when next data scrape should be"""
        midnight = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_from_midnight = (current_time - midnight).total_seconds()
        offset = seconds_from_midnight % self.interval
        previous_in_seconds = seconds_from_midnight - offset
        next_in_seconds = previous_in_seconds + self.interval
        from_midnight = td(seconds=next_in_seconds)
        _log.debug("Start of next scrape interval: {}".format(midnight + from_midnight))
        return midnight + from_midnight

    def run_diagnostics_done(self):
        """Check the results of the diagnostics for publishing, commands, and loading new config"""
        self.diagnostic_done_flag = True

    def publish_results(self, timestamp, diagnostic_topic, diagnostic_result):
        """Publish the diagnostic results"""
        headers = {
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON,
            headers_mod.DATE: format_timestamp(timestamp)
        }
        for device in self.publish_list:
            publish_topic = "/".join([self.analysis_name, device, diagnostic_topic])
            analysis_topic = topics.RECORD(subtopic=publish_topic)
            json_result = dumps(diagnostic_result)
            self.vip.pubsub.publish("pubsub", analysis_topic, headers, json_result)

    def send_autocorrect_command(self, point, value):
        """Send autocorrect command to the AHU/RTU to improve operational efficiency"""
        base_actuator_path = topics.RPC_DEVICE_PATH(campus=self.campus, building=self.building, unit=None, path="", point=None)
        if not self.actuation_mode:
            _log.debug("Actuation disabled:  autocorrect point: {} -- value: {}".format(point, value))
            return
        for device in self.publish_list:
            point_path = base_actuator_path(unit=device, point=point)
            try:
                _log.info("Set point {} to {}".format(point_path, value))
                self.actuation_vip.call("platform.actuator", "set_point", "rcx", point_path, value).get(timeout=15)
            except RemoteError as ex:
                _log.warning("Failed to set {} to {}: {}".format(point_path, value, str(ex)))
                continue


def main(argv=sys.argv):
    """Main method called by the app."""
    try:
        utils.vip_main(AirsideAgent)
    except Exception as exception:
        _log.exception("unhandled exception")
        _log.error(repr(exception))


if __name__ == "__main__":
    """Entry point for script"""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

