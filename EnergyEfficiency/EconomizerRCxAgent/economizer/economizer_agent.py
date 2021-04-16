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
from datetime import timedelta as td
from dateutil import parser
import dateutil.tz
from volttron.platform.agent import utils
from volttron.platform.messaging import (headers as headers_mod, topics)
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import setup_logging
from volttron.platform.vip.agent import Agent, Core

from . import constants
from . diagnostics.TemperatureSensor import TemperatureSensor
from . diagnostics.EconCorrectlyOn import EconCorrectlyOn
from . diagnostics.EconCorrectlyOff import EconCorrectlyOff
from . diagnostics.ExcessOutsideAir import ExcessOutsideAir
from . diagnostics.InsufficientOutsideAir import InsufficientOutsideAir

__version__ = "2.0.0"

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.debug, format='%(asctime)s   %(levelname)-8s %(message)s',
                    datefmt='%m-%d-%y %H:%M:%S')


class EconomizerAgent(Agent):
    """
     Agent that starts all of the economizer diagnostics
    """
    def __init__(self, config_path, **kwargs):
        super(EconomizerAgent, self).__init__(**kwargs)

        #list of class attributes.  Default values will be filled in from reading config file
        #string attributes
        self.config = None
        self.campus = ""
        self.building = ""
        self.agent_id = ""
        self.device_type = ""
        self.economizer_type = ""
        self.sensitivity = ""
        self.analysis_name = ""
        self.fan_status_name = ""
        self.fan_sp_name = ""
        self.oat_name = ""
        self.rat_name = ""
        self.mat_name = ""
        self.oad_sig_name = ""
        self.cool_call_name = ""
        self.timezone = ""
        self.publish_base = ""
        self.sensor_limit_msg = ""

        #list attributes
        self.device_list = []
        self.publish_list = []
        self.units = []
        self.arguments = []
        self.point_mapping = []
        self.damper_data = []
        self.oat_data = []
        self.mat_data = []
        self.rat_data = []
        self.cooling_data = []
        self.fan_sp_data = []
        self.fan_status_data = []
        self.missing_data = []
        self.results_publish = []
        self.timestamp_array = []

        #int attributes
        self.data_window = 0
        self.no_required_data = 0
        self.open_damper_time = 0
        self.fan_speed = 0
        self.run_interval = 0

        #bool attributes
        self.constant_volume = False

        #float attributes
        self.econ_hl_temp = 0.0
        self.temp_band = 0.0
        self.oaf_temperature_threshold = 0.0
        self.oaf_economizing_threshold = 0.0
        self.cooling_enabled_threshold = 0.0
        self.temp_difference_threshold = 0.0
        self.mat_low_threshold = 0.0
        self.mat_high_threshold = 0.0
        self.rat_low_threshold = 0.0
        self.rat_high_threshold = 0.0
        self.oat_low_threshold = 0.0
        self.oat_high_threshold = 0.0
        self.oat_mat_check = 0.0
        self.open_damper_threshold = 0.0
        self.minimum_damper_setpoint = 0.0
        self.desired_oaf = 0.0
        self.low_supply_fan_threshold = 0.0
        self.excess_damper_threshold = 0.0
        self.excess_oaf_threshold = 0.0
        self.ventilation_oaf_threshold = 0.0
        self.insufficient_damper_threshold = 0.0
        self.temp_damper_threshold = 0.0
        self.rated_cfm = 0.0
        self.eer = 0.0
        self.temp_deadband = 0.0
        self.oat = 0.0
        self.rat = 0.0
        self.mat = 0.0
        self.oad = 0.0

        # Precondition flags
        self.oaf_condition = []
        self.unit_status = []
        self.sensor_limit = []
        self.temp_sensor_problem = None
        self.update_config_flag = None
        self.diagnostic_done_flag = True

        # diagnostics
        self.temp_sensor = None
        self.econ_correctly_on = None
        self.econ_correctly_off = None
        self.excess_outside_air = None
        self.insufficient_outside_air = None

        # start reading all the class configs and check them
        self.read_config(config_path)
        self.setup_device_list()
        self.read_argument_config()
        self.read_point_mapping()
        self.configuration_value_check()
        self.create_diagnostics()

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
        # get device, then the units underneath that

        self.analysis_name = self.config.get("analysis_name", "analysis_name")
        self.timezone = self.config.get("local_timezone", "US/Pacific")
        self.device = self.config.get("device", {})

        if "campus" in self.device:
            self.campus = self.device["campus"]
        if "building" in self.device:
            self.building = self.device["building"]
        if "unit" in self.device:
            #units will be a dictionary with subdevices
            self.units = self.device["unit"]
        for u in self.units:
            # building the connection string for each unit
            self.device_list.append(topics.DEVICES_VALUE(campus=self.campus, building=self.building, unit=u, path="", point="all"))
            self.publish_list.append("/".join([self.campus, self.building, u]))
            # loop over subdevices and add them
            if "subdevices" in self.units[u]:
                for sd in self.units[u]["subdevices"]:
                    self.device_list.append(topics.DEVICES_VALUE(campus=self.campus, building=self.building, unit=u, path=sd, point="all"))
                    self.publish_list.append("/".join([self.campus, self.building, u, sd]))

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
            self.update_config_flag = True
            if self.diagnostic_done_flag:
                self.update_configuration()
            elif self.diagnostic_done_flag == False:
                _log.info("Waiting for Diagnostics to finish before updating configuration!")

    def update_configuration(self):
        """Update configurations for agent"""
        self.device_unsubscribe()
        self.device_list = []
        self.publish_list = []
        self.setup_device_list()
        self.read_argument_config()
        self.read_point_mapping()
        self.configuration_value_check()
        self.create_diagnostics()
        self.update_config_flag = False
        self.onstart_subscriptions(None)

    def read_argument_config(self):
        """read all the config arguments section
        no return
        """

        self.arguments = self.config.get("arguments", {})

        self.econ_hl_temp = self.read_argument("econ_hl_temp", 65.0)
        self.constant_volume = self.read_argument("constant_volume", False)
        self.temp_band = self.read_argument("temp_band", 1.0)
        self.oaf_temperature_threshold = self.read_argument("oaf_temperature_threshold", 5.0)
        self.oaf_economizing_threshold = self.read_argument("oaf_economizing_threshold", 25.0)
        self.cooling_enabled_threshold = self.read_argument("cooling_enabled_threshold", 5.0)
        self.temp_difference_threshold = self.read_argument("temp_difference_threshold", 4.0)
        self.mat_low_threshold = self.read_argument("mat_low_threshold", 50.0)
        self.mat_high_threshold = self.read_argument("mat_high_threshold", 90.0)
        self.rat_low_threshold = self.read_argument("rat_low_threshold", 50.0)
        self.rat_high_threshold = self.read_argument("rat_high_threshold", 90.0)
        self.oat_low_threshold = self.read_argument("oat_low_threshold", 30.0)
        self.oat_high_threshold = self.read_argument("oat_high_threshold", 110.0)
        self.oat_mat_check = self.read_argument("oat_mat_check", 5.0)
        self.open_damper_threshold = self.read_argument("open_damper_threshold", 80.0)
        self.minimum_damper_setpoint = self.read_argument("minimum_damper_setpoint", 20.0)
        self.desired_oaf = self.read_argument("desired_oaf", 10.0)
        self.low_supply_fan_threshold = self.read_argument("low_supply_fan_threshold", 15.0)
        self.excess_damper_threshold = self.read_argument("excess_damper_threshold", 20.0)
        self.excess_oaf_threshold = self.read_argument("excess_oaf_threshold", 20.0)
        self.ventilation_oaf_threshold = self.read_argument("ventilation_oaf_threshold", 5.0)
        self.insufficient_damper_threshold = self.read_argument("insufficient_damper_threshold", 15.0)
        self.temp_damper_threshold = self.read_argument("temp_damper_threshold", 90.0)
        self.rated_cfm = self.read_argument("rated_cfm", 6000.0)
        self.eer = self.read_argument("eer", 10.0)
        self.temp_deadband = self.read_argument("temp_band", 1.0)
        self.run_interval = self.read_argument("data_window", 30)
        self.data_window = td(minutes=self.read_argument("data_window", 30))
        self.no_required_data = self.read_argument("no_required_data", 15)
        self.open_damper_time = td(minutes=self.read_argument("open_damper_time", 5))
        self.device_type = self.read_argument("device_type", "ahu").lower()
        self.economizer_type = self.read_argument("economizer_type", "DDB").lower()
        self.sensitivity = self.read_argument("sensitivity", ["low", "normal", "high"])
        self.point_mapping = self.read_argument("point_mapping", {})

    def setup_default_config(self):
        """Setup a default configuration object"""
        default_config = {
            "application": "economizer.economizer_rcx.Application",
            "device": {
                "campus": "campus",
                "building": "building",
                "unit": {
                    "rtu4": {
                        "subdevices": []
                    }
                }
            },
            "analysis_name": "Economizer_AIRCx",
            "actuation_mode": "PASSIVE",
            "arguments": {
                "point_mapping": {
                    "supply_fan_status": "FanStatus",
                    "outdoor_air_temperature": "outsideairtemp",
                    "return_air_temperature": "ReturnAirTemp",
                    "mixed_air_temperature": "MixedAirTemp",
                    "outdoor_damper_signal": "Damper",
                    "cool_call": "CompressorStatus",
                    "supply_fan_speed": "SupplyFanSpeed"
                },
                "device_type": "rtu",
                "economizer_type": "DDB",
                "data_window": 30,
                "no_required_data": 15,
                "open_damper_time": 5,
                "econ_hl_temp": 65.0,
                "sensitivity": ["low", "normal", "high"],
                "constant_volume": False,
                "low_supply_fan_threshold": 15.0,
                "mat_low_threshold": 50.0,
                "mat_high_threshold": 90.0,
                "oat_low_threshold": 30.0,
                "oat_high_threshold": 110.0,
                "oat_mat_check": 5.0,
                "rat_low_threshold": 50.0,
                "rat_high_threshold": 90.0,
                "temp_difference_threshold": 4.0,
                "open_damper_threshold": 80.0,
                "oaf_economizing_threshold": 25.0,
                "oaf_temperature_threshold": 5.0,
                "cooling_enabled_threshold": 5.0,
                "minimum_damper_setpoint": 20.0,
                "excess_damper_threshold": 20.0,
                "insufficient_damper_threshold": 15.0,
                "excess_oaf_threshold": 20.0,
                "ventilation_oaf_threshold": 5.0,
                "temp_damper_threshold": 90,
                "desired_oaf": 10.0,
                "rated_cfm": 6000.0,
                "eer": 10.0,
                "temp_band": 1.0
            },
            "conversion_map": {
                ".*Temperature": "float",
                ".*Command": "float",
                ".*Signal": "float",
                "SupplyFanStatus": "int",
                "Cooling.*": "float",
                "SupplyFanSpeed": "int"
            }
        }
        return default_config

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
        self.fan_status_name = self.get_point_mapping_or_none("supply_fan_status")
        self.fan_sp_name = self.get_point_mapping_or_none("supply_fan_speed")
        self.oat_name = self.get_point_mapping_or_none("outdoor_air_temperature")
        self.rat_name = self.get_point_mapping_or_none("return_air_temperature")
        self.mat_name = self.get_point_mapping_or_none("mixed_air_temperature")
        self.oad_sig_name = self.get_point_mapping_or_none("outdoor_damper_signal")
        self.cool_call_name = self.get_point_mapping_or_none("cool_call")

    def get_point_mapping_or_none(self, name):
        """ Get the item from the point mapping, or return None
        return mixed (string or float or int or dic
        """
        value = self.point_mapping.get(name, None)
        if value is not None and isinstance(value, str):
            value = [value]
        return value

    def configuration_value_check(self):
        """Method goes through the configuration values and checks them for correctness.  Will error if values are not correct. Some may change based on specific settings
        no return
        """
        if self.sensitivity is not None and self.sensitivity == "custom":
            self.oaf_temperature_threshold = max(5.0, min(self.oaf_temperature_threshold, 15.0))
            self.cooling_enabled_threshold = max(5.0, min(self.cooling_enabled_threshold, 50.0))
            self.temp_difference_threshold = max(2.0, min(self.temp_difference_threshold, 6.0))
            self.mat_low_threshold = max(40.0, min(self.mat_low_threshold, 60.0))
            self.mat_high_threshold = max(80.0, min(self.mat_high_threshold, 90.0))
            self.rat_low_threshold = max(40.0, min(self.rat_low_threshold, 60.0))
            self.rat_high_threshold = max(80.0, min(self.rat_high_threshold, 90.0))
            self.oat_low_threshold = max(20.0, min(self.oat_low_threshold, 40.0))
            self.oat_high_threshold = max(90.0, min(self.oat_high_threshold, 125.0))
            self.open_damper_threshold = max(60.0, min(self.open_damper_threshold, 90.0))
            self.minimum_damper_setpoint = max(0.0, min(self.minimum_damper_setpoint, 50.0))
            self.desired_oaf = max(5.0, min(self.desired_oaf, 30.0))
        else:
            self.oaf_temperature_threshold = 5.0
            self.cooling_enabled_threshold = 5.0
            self.temp_difference_threshold = 4.0
            self.mat_low_threshold = 50.0
            self.mat_high_threshold = 90.0
            self.rat_low_threshold = 50.0
            self.rat_high_threshold = 90.0
            self.oat_low_threshold = 30.0
            self.oat_high_threshold = 110.0
            self.open_damper_threshold = 80.0
            self.minimum_damper_setpoint = 20.0
            self.desired_oaf = 10.0
        self.sensitivity = ["low", "normal", "high"]
        if self.economizer_type == "hl":
            self.econ_hl_temp = max(50.0, min(self.econ_hl_temp, 75.0))
        else:
            self.econ_hl_temp = None
        self.temp_band = max(0.5, min(self.temp_band, 10.0))
        if self.device_type not in ("ahu", "rtu"):
            _log.error("device_type must be specified as AHU or RTU in configuration file.")
            sys.exit()

        if self.economizer_type.lower() not in ("ddb", "hl"):
            _log.error("economizer_type must be specified as DDB or HL in configuration file.")
            sys.exit()

        if self.fan_sp_name is None and self.fan_status_name is None:
            _log.error("SupplyFanStatus or SupplyFanSpeed are required to verify AHU status.")
            sys.exit()

    def create_diagnostics(self):
        """creates the diagnostic classes
        No return
        """
        self.temp_sensor = TemperatureSensor()
        self.temp_sensor.set_class_values(self.analysis_name, self.results_publish, self.data_window, self.no_required_data, self.temp_difference_threshold, self.open_damper_time,  self.temp_damper_threshold)
        self.econ_correctly_on = EconCorrectlyOn()
        self.econ_correctly_on.set_class_values(self.analysis_name, self.results_publish, self.data_window, self.no_required_data, self.minimum_damper_setpoint, self.open_damper_threshold, float(self.rated_cfm), self.eer)
        self.econ_correctly_off = EconCorrectlyOff()
        self.econ_correctly_off.set_class_values(self.analysis_name, self.results_publish, self.data_window, self.no_required_data, self.minimum_damper_setpoint, self.desired_oaf, float(self.rated_cfm), self.eer)
        self.excess_outside_air = ExcessOutsideAir()
        self.excess_outside_air.set_class_values(self.analysis_name, self.results_publish, self.data_window, self.no_required_data, self.minimum_damper_setpoint, self.desired_oaf, float(self.rated_cfm), self.eer)
        self.insufficient_outside_air = InsufficientOutsideAir()
        self.insufficient_outside_air.set_class_values(self.analysis_name, self.results_publish, self.data_window, self.no_required_data, self.desired_oaf)

    def parse_data_message(self, message):
        """Breaks down the passed VOLTTRON message
        message: dictionary
        no return
        """
        data_message = message[0]
        # reset the data arrays on new message
        self.fan_status_data = []
        self.damper_data = []
        self.oat_data = []
        self.mat_data = []
        self.rat_data = []
        self.cooling_data = []
        self.fan_sp_data = []
        self.missing_data = []

        for key in data_message:
            value = data_message[key]
            if value is None:
                continue
            if key in self.fan_status_name:
                self.fan_status_data.append(value)
            elif key in self.oad_sig_name:
                self.damper_data.append(value)
            elif key in self.oat_name:
                self.oat_data.append(value)
            elif key in self.mat_name:
                self.mat_data.append(value)
            elif key in self.rat_name:
                self.rat_data.append(value)
            elif key in self.cool_call_name:
                self.cooling_data.append(value)
            elif key in self.fan_sp_name:
                self.fan_sp_data.append(value)

    def check_for_missing_data(self):
        """Method that checks the parsed message results for any missing data
        return bool
        """
        if not self.oat_data:
            self.missing_data.append(self.oat_name)
        if not self.rat_data:
            self.missing_data.append(self.rat_name)
        if not self.mat_data:
            self.missing_data.append(self.mat_name)
        if not self.damper_data:
            self.missing_data.append(self.oad_sig_name)
        if not self.cooling_data:
            self.missing_data.append(self.cool_call_name)
        if not self.fan_status_data and not self.fan_sp_data:
            self.missing_data.append(self.fan_status_name)

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
            if self.fan_speed > self.low_supply_fan_threshold:
                supply_fan_status = 1
            else:
                supply_fan_status = 0

        if not supply_fan_status:
            self.unit_status.append(current_time)
        return supply_fan_status

    def check_temperature_condition(self, current_time):
        """Ensure the OAT and RAT have minimum difference to allow for a conclusive diagnostic.
        current_time: datetime time delta

        no return
        """
        if abs(self.oat - self.rat) < self.oaf_temperature_threshold:
            self.oaf_condition.append(current_time)

    def check_elapsed_time(self, current_time, condition, message):
        """Check on time since last message to see if it is in data window
        current_time: datetime time delta
        condition: datetime time delta
        message: string
        """
        if condition:
            elapsed_time = current_time - condition[-1]
        else:
            elapsed_time = td(minutes=0)
        if ((current_time.minute % self.run_interval and len(condition) > self.no_required_data)
                or elapsed_time > self.data_window):
            self.pre_conditions(message, current_time)
            self.publish_analysis_results()
            self.clear_all()
            return True
        return False

    def clear_all(self):
        """Reinitialize all data arrays for diagnostics.
        no return
        """
        self.clear_diagnostics()
        self.temp_sensor_problem = None
        self.unit_status = []
        self.oaf_condition = []
        self.sensor_limit = []
        self.sensor_limit_msg = ""
        self.timestamp_array = []

    def clear_diagnostics(self):
        """Clear the diagnositcs
        no return
        """
        self.temp_sensor.clear_data()
        self.econ_correctly_on.clear_data()
        self.econ_correctly_off.clear_data()
        self.excess_outside_air.clear_data()
        self.insufficient_outside_air.clear_data()

    def pre_conditions(self, message, cur_time):
        """Publish Pre conditions not met
        message: string
        cur_time: datetime time delta

        no return
        """
        dx_msg = {}
        for sensitivity in self.sensitivity:
            dx_msg[sensitivity] = message

        for diagnostic in constants.DX_LIST:
            _log.info(constants.table_log_format(self.analysis_name, cur_time, (diagnostic + constants.DX + ":" + str(dx_msg))))
            self.results_publish.append(constants.table_publish_format(self.analysis_name, cur_time, (diagnostic + constants.DX), str(dx_msg)))

    def sensor_limit_check(self, current_time):
        """ Check temperature limits on sensors.
        current_time: datetime time delta

        return bool
        """
        if self.oat < self.oat_low_threshold or self.oat > self.oat_high_threshold:
            self.sensor_limit.append(current_time)
            self.sensor_limit_msg = constants.OAT_LIMIT
            _log.info("OAT sensor is outside of bounds: {}".format(current_time))
        elif self.mat < self.mat_low_threshold or self.mat > self.mat_high_threshold:
            self.sensor_limit.append(current_time)
            self.sensor_limit_msg = constants.MAT_LIMIT
            _log.info("MAT sensor is outside of bounds: {}".format(current_time))
        elif self.rat < self.rat_low_threshold or self.rat > self.rat_high_threshold:
            self.sensor_limit.append(current_time)
            self.sensor_limit_msg = constants.RAT_LIMIT
            _log.info("RAT sensor is outside of bounds: {}".format(current_time))

    def determine_cooling_condition(self):
        """Determine if the unit is in a cooling mode and if conditions are favorable for economizing.

        return float
        return Bool/int
        """
        cool_call = None
        if self.device_type == "ahu":
            clg_vlv_pos = mean(self.cooling_data)
            cool_call = True if clg_vlv_pos > self.cooling_enabled_threshold else False
        elif self.device_type == "rtu":
            cool_call = int(max(self.cooling_data))

        if self.economizer_type == "ddb":
            econ_condition = (self.rat - self.oat) > self.temp_band
        else:
            econ_condition = (self.econ_hl_temp - self.oat) > self.temp_band

        return econ_condition, cool_call

    @Core.receiver("onstart")
    def onstart_subscriptions(self, sender, **kwargs):
        """Method used to setup data subscription on startup of the agent"""
        for device in self.device_list:
            self.vip.pubsub.subscribe(peer="pubsub", prefix=device, callback=self.new_data_message)

    def device_unsubscribe(self):
        """Method used to unsubscribe devices"""
        self.vip.pubsub.unsubscribe("pubsub", None, None)

    def check_for_config_update_after_diagnostics(self):
        """Check to see if the configuration needs to be update"""
        self.diagnostic_done_flag = True
        if self.update_config_flag:
            _log.info("finishing config update check")
            self.update_configuration()

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
        self.diagnostic_done_flag = False
        current_time = parser.parse(headers["Date"])
        to_zone = dateutil.tz.gettz(self.timezone)
        current_time = current_time.astimezone(to_zone)
        _log.info("Processing Results!")
        self.parse_data_message(message)
        missing_data = self.check_for_missing_data()
        # want to do no further parsing if data is missing
        if missing_data:
            _log.info("Missing data from publish: {}".format(self.missing_data))
            self.publish_analysis_results()
            self.check_for_config_update_after_diagnostics()
            return

        # check on fan status and speed
        fan_status = self.check_fan_status(current_time)
        precondition_failed = self.check_elapsed_time(current_time, self.unit_status, constants.FAN_OFF)
        if not fan_status or precondition_failed:
            _log.info("Supply fan is off: {}".format(current_time))
            self.publish_analysis_results()
            self.check_for_config_update_after_diagnostics()
            return
        else:
            _log.info("Supply fan is on: {}".format(current_time))

        if self.fan_speed is None and self.constant_volume:
            self.fan_speed = 100.0

        self.oat = mean(self.oat_data)
        self.rat = mean(self.rat_data)
        self.mat = mean(self.mat_data)
        self.oad = mean(self.damper_data)

        # check on temperature condition
        self.check_temperature_condition(current_time)
        precondition_failed = self.check_elapsed_time(current_time, self.oaf_condition, constants.OAF)
        if current_time in self.oaf_condition or precondition_failed:
            _log.info("OAT and RAT readings are too close : {}".format(current_time))
            self.publish_analysis_results()
            self.check_for_config_update_after_diagnostics()
            return

        self.sensor_limit_check(current_time)
        precondition_failed = self.check_elapsed_time(current_time, self.sensor_limit, self.sensor_limit_msg)
        # check to see if there was a temperature sensor out of bounds
        if current_time in self.sensor_limit or precondition_failed:
            self.publish_analysis_results()
            self.check_for_config_update_after_diagnostics()
            return
        self.timestamp_array.append(current_time)
        self.temp_sensor_problem = self.temp_sensor.temperature_algorithm(self.oat, self.rat, self.mat, self.oad, current_time)
        econ_condition, cool_call = self.determine_cooling_condition()
        _log.debug("Cool call: {} - Economizer status: {}".format(cool_call, econ_condition))

        if self.temp_sensor_problem is not None and not self.temp_sensor_problem:
            self.econ_correctly_on.economizer_on_algorithm(cool_call, self.oat, self.rat, self.mat, self.oad, econ_condition, current_time, self.fan_speed)
            self.econ_correctly_off.economizer_off_algorithm(self.oat, self.rat, self.mat, self.oad, econ_condition, current_time, self.fan_speed)
            self.excess_outside_air.excess_ouside_air_algorithm(self.oat, self.rat, self.mat, self.oad, econ_condition, current_time, self.fan_speed)
            self.insufficient_outside_air.insufficient_outside_air_algorithm(self.oat, self.rat, self.mat, current_time)

        if self.timestamp_array:
            elapsed_time = self.timestamp_array[-1] - self.timestamp_array[0]
        else:
            elapsed_time = td(minutes=0)
        if not current_time.minute % self.run_interval or elapsed_time > self.data_window:
            self.temp_sensor.run_diagnostic(current_time)
            if self.temp_sensor_problem is not None and not self.temp_sensor_problem:
                self.econ_correctly_on.run_diagnostic(current_time)
                self.econ_correctly_off.run_diagnostic(current_time)
                self.excess_outside_air.run_diagnostic(current_time)
                self.insufficient_outside_air.run_diagnostic(current_time)
            elif self.temp_sensor_problem:
                self.pre_conditions(constants.TEMP_SENSOR, current_time)
            self.clear_all()

        self.publish_analysis_results()
        self.check_for_config_update_after_diagnostics()

    def publish_analysis_results(self):
        """Publish the diagnostic results"""
        if(len(self.results_publish)) <= 0:
            return
        publish_base = "/".join([self.analysis_name])
        for app, analysis_table in self.results_publish:
            to_publish = {}
            name_timestamp = app.split("&")
            timestamp = name_timestamp[1]
            point = analysis_table[0]
            result = analysis_table[1]
            headers = {headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON, headers_mod.DATE: timestamp, }
            for device in self.publish_list:
                publish_topic = "/".join([publish_base, device, point])
                analysis_topic = topics.RECORD(subtopic=publish_topic)
                to_publish[analysis_topic] = result

            for result_topic, result in to_publish.items():
                self.vip.pubsub.publish("pubsub", result_topic, headers, result)
            to_publish.clear()
        self.results_publish.clear()


def main(argv=sys.argv):
    """Main method called by the app."""
    try:
        utils.vip_main(EconomizerAgent)
    except Exception as exception:
        _log.exception("unhandled exception")
        _log.error(repr(exception))


if __name__ == "__main__":
    """Entry point for script"""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
