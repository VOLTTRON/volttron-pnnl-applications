import dataclasses
import logging
import os
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta as td, datetime
from pathlib import Path
from typing import List, Union, Optional, Tuple, Dict

import dateutil.tz
from dateutil import parser
from numpy import mean

from volttron.platform.agent.utils import (
    vip_main, load_config
)
from volttron.platform.messaging import topics, headers as headers_mod
from volttron.platform.vip.agent import (
    Agent,
)
from .analysis_config import AnalysisConfig, UnitProperty
from .diagnostics import (
    table_log_format,
    table_publish_format,
    HRT_LIMIT,
    TemperatureSensor,
    HeatRecoveryCorrectlyOn,
    HeatRecoveryCorrectlyOff, DX_LIST, DX, OAT_LIMIT, EAT_LIMIT, FAN_OFF, OAT_EAT_CLOSE, OAT_SAT_SP_CLOSE, TEMP_SENSOR,
    ResultPublisher
)

logging.basicConfig(level=logging.DEBUG)
# setup_logging(logging.DEBUG, True)
_log = logging.getLogger(__name__)

ANALYSIS_NAME = "Heat_Recovery_AIRCx"

__version__ = "0.1.0"
##########################################################################
# FIELD MAPPINGS
#
# These fields which map onto publishes from the platform driver.
# The keys for these fields are specified via the arguments.point_mappings
# dictionary from the yaml or json configuration file.
##########################################################################
F_OA_TEMP = "outdoor_air_temperature"
F_SF_STATUS = "supply_fan_status"
F_SF_SPEED = "supply_fan_speed"
# Exhaust temperature
F_EA_TEMP = "return_air_temperature"
F_MA_TEMP = "mixed_air_temperature"
F_OD_SIGNAL = "outdoor_damper_signal"
F_CC = "cool_call"

F_HR_TEMP = "heat_return_temperature"
F_HR_STATUS = "heat_return_status"

F_DT_SET_POINT = "discharge_temperature_set_point"


@dataclass
class HeatRecoveryConfig(AnalysisConfig):
    analysis_name: str
    actuation_mode: str

    # Each of the following are configuration items that can be
    # overridden from the arguments dictionary in the configuration
    # file.  Reasonable defaults are specified here.
    oat_low_threshold: Optional[float] = 20.0
    oat_high_threshold: Optional[float] = 120.0
    eat_low_threshold: Optional[float] = 50.0
    eat_high_threshold: Optional[float] = 90.0
    hrt_low_threshold: Optional[float] = -20.0
    hrt_high_threshold: Optional[float] = 120.0
    oa_ea_low_deadband: Optional[float] = 2.0
    oa_ea_high_deadband: Optional[float] = 5.0
    oa_sat_low_deadband: Optional[float] = 8.0
    oa_sat_high_deadband: Optional[float] = 2.0
    hre_recovering_threshold: Optional[float] = 50.0
    rated_cfm: Optional[float] = 1000.0
    expected_hre: Optional[float] = 0.5
    eer: Optional[float] = 20.0
    hr_status_threshold: Optional[float] = 0.5
    sf_status_threshold: Optional[float] = 0.5  # threshold of determining if sf is on (status)
    sf_speed_threshold: Optional[float] = 30  # threshold for determining if sf is on (speed)
    temp_diff_threshold: Optional[float] = 4.0
    timezone: Optional[str] = "US/Pacific"
    # Number of minutes in a data window.
    run_interval: Optional[int] = 4
    number_required_data_points: Optional[int] = 4
    max_dx_time: Optional[int] = 30
    hr_cond: Optional[bool] = None
    no_required_data: Optional[int] = 4

    def validate(self):
        super().validate()
        # do validation here.

    def __post_init__(self):
        self.analysis_name = ANALYSIS_NAME
        self.actuation_mode = "PASSIVE"

        # we need to deal with the arguments here that are
        for k, v in self.arguments.items():
            if k == 'point_mapping':
                continue

            # if we don't have an argument that was passed
            # then this is an error.
            if not hasattr(self, k):
                raise ValueError(f"Parameter {k} not found on class {self.__class__.__name__}")

            setattr(self, k, v)


class HeatRecoveryAgent(Agent):
    analysis_name = ANALYSIS_NAME
    hr_off_steady_state = td(minutes=1)

    def __init__(self, config_path, **kwargs):
        super(HeatRecoveryAgent, self).__init__(enable_store=True, **kwargs)

        # Require that we have a configuration file passed to the agent.
        pth = Path(config_path).resolve(strict=True)
        if not pth.is_file():
            raise ValueError(f"Invalid config_path specified {config_path}")

        # our configuration is setup to be a dictionary and is available
        # from the config store or the file passed to the agent itself.
        self.cfg: Union[dict, HeatRecoveryConfig] = {}

        # Get the data from the passed file.
        config = load_config(config_path)

        # If there is configuration then we need to set it for the default use
        # case, otherwise the agent will use what is currently in the config
        # store.
        if config:
            self.vip.config.set_default("config", config)
            self.cfg = HeatRecoveryConfig(**config)

        # Subscription allows any changes to the config store to propagate
        # to the agent.
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"])

        self.sensitivity = ["low", "normal", "high"]

        # A dictionary with keys the arguments.point_map keys and the value the last n values
        # for that point on the bus.
        #
        self.value_map = {}

        # self.oatemp_name = "OutdoorAirTemperature"
        # self.sf_status_name = "SupplyFanStatus"
        # self.ef_status_name = "ExhaustFanStatus"
        # self.sf_speed_name = "SupplyFanSpeedPercent"
        # self.ef_speed_name = "ExhaustFanSpeedPercent"
        #
        # self.eatemp_name = "ReturnAirTemperature"
        # self.hrtemp_name = "HrWheelLeavingAirTemperature"
        # self.sat_sp_name = "DischargeAirTemperatureSetPoint"
        # self.hr_status_name = "HrWheelEnabled"

        # self.publish_base = ""
        self.sensor_limit_msg = ""

        self.publish_list = []

        self.damper_data = []
        # self.oatemp_values = []
        # self.sf_status_values = []
        # self.ef_status_values = []
        # self.sf_speed_values = []
        # self.ef_speed_values = []
        # self.eatemp_value = []
        # self.hrtemp_values = []
        # self.sat_sp_values = []
        # self.hr_status_values = []
        # self.missing_data = []
        self.results_publish = []
        self.timestamp_array = []
        print(id(self.results_publish))

        # int attributes
        # self.run_interval = 4  # the number of minutes in data_window. not independent.
        self.data_window = td(minutes=self.cfg.run_interval)

        # self.no_required_data = 4
        # self.max_dx_time = 30
        # self.hr_cond = None  # condition the HR should be in

        # float attributes
        # self.oat_low_threshold = 20.0
        # self.oat_high_threshold = 120.0
        # self.eat_low_threshold = 50.0
        # self.eat_high_threshold = 90.0
        # self.hrt_low_threshold = -20.0
        # self.hrt_high_threshold = 120.0
        # self.oa_ea_low_deadband = 2.0
        # self.oa_ea_high_deadband = 5.0
        # self.oa_sat_low_deadband = 8.0
        # self.oa_sat_high_deadband = 2.0
        # self.hre_recovering_threshold = 50.0
        # self.rated_cfm = 1000.0
        # self.expected_hre = 0.5
        # self.eer = 20.0
        # self.hr_status_threshold = 0.5
        # self.sf_status_threshold = 0.5  # threshold of determining if sf is on (status)
        # self.sf_speed_threshold = 30  # threshold for determining if sf is on (speed)
        # self.temp_diff_threshold = 4.0
        # bool attributes
        self.constant_volume = False

        self.hr_off_steady_state = td(minutes=1)
        # int data`
        self.sf_status = 0
        self.ef_status = 0
        self.sf_speed = 0
        self.ef_speed = 0
        self.hr_status = 0

        # float data
        self.mean_oatemp = 0.0
        self.mean_eatemp = 0.0
        self.mean_hrtemp = 0.0
        self.mean_sat_sp = 0.0

        # precondition flags
        self.oatemp_eatemp_close_condition = []
        self.oatemp_sat_sp_close_condition = []
        self.unit_status = []
        self.sensor_limit = []
        self.temp_sensor_problem = None
        self.diagnostic_done_flag = True

        # diagnostics
        self.temp_sensor_dx = None
        self.hr_correctly_on_dx = None
        self.hr_correctly_off_dx = None

        self._device_topics = []
        self._publish_topics = []
        self.create_diagnostics()

    def get_subscription_publish_topics(self) -> Tuple[List[str], List[str]]:
        """
        This function uses the device
        :return: subscription and analysis publish topics
        """
        sub_topics = []
        pub_topics = []
        device = self.cfg.device

        base_subscription = f"device/{device.campus}/{device.building}"
        # building level all message
        # sub_topics.append(f"{base_subscription}/all")
        # sub_topics.append(topics.DEVICES_VALUE(campus=device.campus, building=device.building,
        #                                   unit="", point="all"))
        # unit=u, path="", point="all")

        if isinstance(device.unit, str):
            sub_topics.append(topics.DEVICES_VALUE(campus=device.campus, building=device.building, unit=device.unit,
                                                   point="all"))
            pub_topics.append("/".join([device.campus, device.building, device.unit]))
            # sub_topics.append(vtopic.DEVICES_VALUE(campus=device.campus, building=device.building, unit=device.unit))
            # sub_topics.append(f"{base_subscription}/{device.unit}/all")
        elif isinstance(device.unit, UnitProperty):
            # Loops over the name fo the units
            for k in device.unit.units:
                # append the unit i.e rtu
                sub_topics.append(
                    topics.DEVICES_VALUE(campus=device.campus, building=device.building, unit=k, point="all")
                )
                pub_topics.append("/".join([device.campus, device.building, k]))

                # v should be a list of sub devices for the unit i.e ahu
                for subdev in device.unit.unit[k]:
                    sub_topics.append(
                        topics.DEVICES_VALUE(campus=device.campus, building=device.building, unit=k,
                                             path=subdev, point="all")
                    )
                    pub_topics.append("/".join([device.campus, device.building, k, subdev]))
        else:
            raise ValueError("Invalid configuration detected ")
        return sub_topics, pub_topics

    def configure(self, config_name, action, contents):
        # Create a copy of the current configuration object.
        if isinstance(self.cfg, HeatRecoveryConfig):
            # asdict is always available on dataclass objects
            config = dataclasses.asdict(self.cfg)
        else:
            config = deepcopy(self.cfg)

        config.update(**contents)

        try:
            # Validate the new values, should raise Key or Value error
            # if invalid data is specified.
            hr_config = HeatRecoveryConfig(**config)

            hr_config.validate()

            # Unsubscribe to all topics.
            self.vip.pubsub.unsubscribe(peer="pubsub", prefix="", callback=self.new_data_message)

            # We now have new state of the configuration
            self.cfg = hr_config

            # TODO: Skip this and just use the config object itself if possible?
            # TODO: Perhaps a shallow copy of these rather than using getattr setattr
            # TODO: Should these be member variables?
            # Set items on the current object from the config object.
            # for field in dataclasses.fields(self.cfg):
            #     setattr(self, field.name, getattr(self.cfg, field.name))
            #
            # if isinstance(self.cfg.arguments, dict):
            #     for k, v in self.cfg.arguments.items():
            #         setattr(self, k, v)
            # else:
            #     for field in dataclasses.fields(self.cfg.arguments):
            #         setattr(self, field.name, getattr(self.cfg.arguments, field.name))
            self._device_topics, self.publish_list = self.get_subscription_publish_topics()
            for topic in self._device_topics:
                _log.debug(f"Subscribing to {topic}")
                self.vip.pubsub.subscribe(peer="pubsub", prefix=topic, callback=self.new_data_message)
            print(self.publish_list)
        except (KeyError, ValueError) as ex:
            _log.error(f"Invalid configuration options specified {ex} ")

            # First time through if we get a validation error then we want to
            # exit with a bad value.
            if config_name == 'config' and action == 'NEW':
                sys.exit(1)

    def create_diagnostics(self):
        c = self.cfg
        self.temp_sensor_dx = TemperatureSensor(self.analysis_name, self.results_publish)
        self.temp_sensor_dx.set_class_values(data_window=self.data_window,
                                             no_required_data=c.no_required_data,
                                             temp_diff_threshold=c.temp_diff_threshold,
                                             hr_off_steady_state=self.hr_off_steady_state)
        self.hr_correctly_on_dx = HeatRecoveryCorrectlyOn(self.analysis_name, self.results_publish)
        self.hr_correctly_on_dx.set_class_values(c.hr_status_threshold,
                                                 c.hre_recovering_threshold, self.data_window,
                                                 c.no_required_data,
                                                 c.rated_cfm, c.eer, c.expected_hre)
        self.hr_correctly_off_dx = HeatRecoveryCorrectlyOff(self.analysis_name, self.results_publish)
        self.hr_correctly_off_dx.set_class_values(c.hr_status_threshold,
                                                  c.hre_recovering_threshold, self.data_window,
                                                  c.no_required_data,
                                                  c.rated_cfm, c.eer)

    def update_point_values(self, message: List) -> None:
        """
        Given the passed message from the volttron platform driver load the value_map with
        data from it.  This method will reinitialize the value_map each time this
        method is called.

        :param message:
        :return: None
        """
        data_message = message[0]

        # Re-initialize the value mappings
        for k in self.cfg.arguments.point_mapping.get_keys():
            self.value_map[k] = []

        # k in this case is both the key of the message and
        # the value of the arguments.point_mapping.key
        for k, v in data_message.items():
            # if not v:
                # continue
            try:
                point_key = self.cfg.arguments.point_mapping.get_key(k)
                self.value_map[point_key] = v
            except (KeyError, ValueError) as ex:
                _log.warning(f"The value: {k} is not found in point_mapping values.")

        # self.oatemp_values = []
        # self.sf_status_values = []
        # self.ef_status_values = []
        # self.sf_speed_values = []
        # self.ef_speed_values = []
        # self.eatemp_values = []
        # self.hrtemp_values = []
        # self.sat_sp_values = []
        # self.hr_status_values = []
        # self.missing_data = []
        #
        # for key in data_message:
        #     value = data_message[key]
        #     if value is None:
        #         continue
        #     if key in self.oatemp_name:
        #         self.oatemp_values.append(value)
        #     if key in self.sf_status_name:
        #         self.sf_status_values.append(value)
        #     if key in self.ef_status_name:
        #         self.ef_status_values.append(value)
        #     if key in self.sf_speed_name:
        #         self.sf_speed_values.append(value)
        #     if key in self.ef_speed_name:
        #         self.ef_speed_values.append(value)
        #     if key in self.eatemp_name:
        #         self.eatemp_values.append(value)
        #     if key in self.hrtemp_name:
        #         self.hrtemp_values.append(value)
        #     if key in self.sat_sp_name:
        #         self.sat_sp_values.append(value)
        #     if key in self.hr_status_name:
        #         self.hr_status_values.append(value)

    def check_for_missing_data(self) -> List[str]:
        """
        Determines whether or not there are missing values in the message from the
        volttron platform driver.  This function will return a list of missing
        fields if they are not available in the message.

        :return: [] or List of missing fields.
        """

        missing_values: List[str] = []

        def add_missing(field: str, orfield: Optional[str] = None):
            if orfield:
                if not self.value_map.get(field) and not self.value_map.get(orfield):
                    missing_values.append(field)
            elif not self.value_map.get(field):
                missing_values.append(field)

            _log.debug(f"field: {field} orfield: {orfield}")

        add_missing(F_OA_TEMP)
        add_missing(F_SF_SPEED, F_SF_STATUS)
        add_missing(F_EA_TEMP)
        add_missing(F_HR_TEMP)
        add_missing(F_HR_STATUS)
        add_missing(F_DT_SET_POINT)

        return missing_values

        # if not self.oatemp_values:
        #     self.missing_data.append(self.oatemp_name)
        # if not self.sf_status_values and not self.sf_speed_values:  # need either fan status or speed
        #     self.missing_data.append(self.sf_status_name)
        #
        # if not self.eatemp_values:
        #     self.missing_data.append(self.eatemp_name)
        # if not self.hrtemp_values:
        #     self.missing_data.append(self.hrtemp_name)
        # if not self.sat_sp_values:
        #     self.missing_data.append(self.sat_sp_name)
        # if not self.hr_status_values: n                     # don't need heat recovery status
        #     self.missing_data.append(self.hr_status_name)
        # if self.missing_data:
        #     return True
        # return False

    def get_sf_status(self, current_time) -> int:
        """
        Based upon the supply_fan_status and supply_fan_speed determine
        if the supply fan is running.  Returns a 0 or 1 based upone
        whether the supply fan is running or not.

        The sf_status_threshold configuration to determine a threshold of status
        The sf_speed_threshold configuration is used to determine a threshold of the speed.

        :param current_time:
        :return: int - 0 or 1 based upon whether supply fan is running.
        """

        vm = self.value_map

        if vm.get(F_SF_STATUS):
            mean_status = mean(vm.get(F_SF_STATUS))
            if mean_status >= self.cfg.sf_status_threshold:
                sf_status = 1
            else:
                sf_status = 0
        else:
            sf_status = None
        #
        # if self.sf_status_values:
        #     mean_status = mean(self.sf_status_values)
        #     if mean_status >= self.sf_status_threshold:
        #         sf_status = 1
        #     else:
        #         sf_status = 0
        # else:
        #     sf_status = None

        if vm.get(F_SF_SPEED):
            self.sf_speed = mean(vm.get(F_SF_SPEED))
        else:
            self.sf_speed = None

        # if self.sf_speed_values:
        #     self.sf_speed = mean(self.sf_speed_values)
        # else:
        #     self.sf_speed = None
        if sf_status is None:
            if self.sf_speed >= self.cfg.sf_speed_threshold:
                sf_status = 1
            else:
                sf_status = 0

        if not sf_status:  # this should not be true. We checked that status and speed are not both missing.
            self.unit_status.append(current_time)
        return sf_status

    def check_oatemp_eatemp_condition(self, current_time):
        # check if OAT is too close to EAT
        if self.mean_eatemp + self.cfg.oa_ea_high_deadband > self.mean_oatemp > self.mean_eatemp - self.cfg.oa_ea_low_deadband:
            self.oatemp_eatemp_close_condition.append(current_time)

    def check_oatemp_sat_sp_condition(self, current_time):
        # check if OAT is too close to SAT_SP
        if self.mean_sat_sp + self.cfg.oa_sat_high_deadband > self.mean_oatemp > self.mean_sat_sp - self.cfg.oa_sat_low_deadband:
            self.oatemp_sat_sp_close_condition.append(current_time)

    def check_elapsed_time(self, current_time: datetime, condition: List[datetime], message):
        if condition:
            elapsed_time = current_time - condition[-1]  # time since the last time this condition was true
        else:
            elapsed_time = td(minutes=0)

        # if ((current_time.minute % self.run_interval and len(condition)>=self.no_required_data) or elapsed_time >= self.data_window):
        if (len(condition) >= self.cfg.no_required_data) and (elapsed_time >= self.data_window):
            self.pre_conditions(message, current_time)
            # self.publish_analysis_results()
            self.clear_all()
            return True
        return False

    def clear_all(self):
        self.clear_diagnostics()
        self.temp_sensor_problem = None
        self.unit_status = []
        self.sensor_limit = []
        self.sensor_limit_msg = ""
        self.timestamp_array = []

    def clear_diagnostics(self):
        self.temp_sensor_dx.clear_data()
        self.hr_correctly_on_dx.clear_data()
        self.hr_correctly_off_dx.clear_data()

    def pre_conditions(self, message, cur_time: datetime):
        dx_msg = {}
        for sensitivity in self.sensitivity:
            dx_msg[sensitivity] = message

        for diagnostic in DX_LIST:  # log the message for each diagnostic
            txt = table_publish_format(self.analysis_name, cur_time, (diagnostic + DX), str(dx_msg))
            ResultPublisher.push_result(self, txt, cur_time)
            # self.results_publish.append(txt)

    def determine_hr_condition(self) -> bool:
        if self.mean_sat_sp + self.cfg.oa_sat_high_deadband < self.mean_oatemp < self.mean_eatemp - self.cfg.oa_ea_low_deadband:
            self.hr_cond = False
        else:
            self.hr_cond = True

    def sensor_limit_check(self, current_time: datetime) -> None:
        """
        The `sensor_limit_check` method logs whether the OAT, EAT or HRT sensor is out of bounds.  This
        is a mutually exclusive log entry.

        :param current_time:

        """
        if self.mean_oatemp < self.cfg.oat_low_threshold or self.mean_oatemp > self.cfg.oat_high_threshold:
            self.sensor_limit.append(current_time)
            self.sensor_limit_msg = OAT_LIMIT
            _log.info(f"OAT sensor is outside of bounds: {current_time}")
        elif self.mean_eatemp < self.cfg.eat_low_threshold or self.mean_eatemp > self.cfg.eat_high_threshold:
            self.sensor_limit.append(current_time)
            self.sensor_limit_msg = EAT_LIMIT
            _log.info(f"EAT sensor is outside of bounds: {current_time}")
        elif self.mean_hrtemp < self.cfg.hrt_low_threshold or self.mean_hrtemp > self.cfg.hrt_high_threshold:
            self.sensor_limit.append(current_time)
            self.sensor_limit_msg = HRT_LIMIT
            _log.info(f"HRT sensor is outside of bounds: {current_time}")

    def new_data_message(self, peer: str, sender: str, bus: str, topic: str, headers: Dict,
                         message: [Dict, str]) -> None:
        """
        The `new_data_message` is called when a message is published to the volttron message bus.

        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:

        """
        self.diagnostic_done_flag = False
        current_time = parser.parse(headers["Date"])
        # current_time = message[0]['timestamp']  # parser.parse(headers["Date"])
        to_zone = dateutil.tz.gettz(self.cfg.timezone)
        current_time = current_time.astimezone(to_zone)
        _log.info(f"Processing Results: {current_time}")
        # repopulates the self.value_map with new values
        self.update_point_values(message)
        missing_data = self.check_for_missing_data()
        if missing_data:
            _log.info(f"\tMissing data from publish: {missing_data}")
            self.publish_analysis_results()
            # self.check_for_config_update_after_diagnostics()
            return
        self.sf_status = self.get_sf_status(current_time)
        precondition_failed = self.check_elapsed_time(current_time, self.unit_status, FAN_OFF)
        if not self.sf_status or precondition_failed:
            _log.info(f"\tSupply fan is off")
            self.publish_analysis_results()
            # self.check_for_config_update_after_diagnostics()
            return
        else:
            _log.info(f"\tSupply fan is on")

        if self.sf_speed is None and self.constant_volume:
            self.sf_speed = 100

        self.mean_oatemp = mean(self.value_map.get(F_OA_TEMP))
        self.mean_eatemp = mean(self.value_map.get(F_EA_TEMP))
        self.mean_hrtemp = mean(self.value_map.get(F_HR_TEMP))
        self.mean_sat_sp = mean(self.value_map.get(F_DT_SET_POINT))
        avg_hr_status = mean(self.value_map.get(F_HR_STATUS))
        if avg_hr_status >= self.cfg.hr_status_threshold:
            self.hr_status = 1
        else:
            self.hr_status = 0

        # self.oatemp = mean(self.oatemp_values)
        # self.eatemp = mean(self.eatemp_values)
        # self.hrtemp = mean(self.hrtemp_values)
        # self.sat_sp = mean(self.sat_sp_values)
        # avg_hr_status = mean(self.hr_status_values)
        # if avg_hr_status >= self.hr_status_threshold:
        #     self.hr_status = 1
        # else:
        #     self.hr_status = 0

        self.check_oatemp_eatemp_condition(current_time)
        precondition_failed = self.check_elapsed_time(current_time, self.oatemp_eatemp_close_condition,
                                                      OAT_EAT_CLOSE)
        if current_time in self.oatemp_eatemp_close_condition or precondition_failed:
            _log.info(f"\tOAT and EAT readings are too close")
            self.publish_analysis_results()
            # self.check_for_config_update_after_diagnostics()
            return
        self.check_oatemp_sat_sp_condition(current_time)
        precondition_failed = self.check_elapsed_time(current_time, self.oatemp_sat_sp_close_condition,
                                                      OAT_SAT_SP_CLOSE)
        if current_time in self.oatemp_sat_sp_close_condition or precondition_failed:
            _log.info("\tOAT and SAT SP readings are too close")
            self.publish_analysis_results()
            # self.check_for_config_update_after_diagnostics()
            return

        self.sensor_limit_check(current_time)
        precondition_failed = self.check_elapsed_time(current_time, self.sensor_limit, self.sensor_limit_msg)
        if current_time in self.sensor_limit or precondition_failed:
            self.publish_analysis_results()
            # self.check_for_config_update_after_diagnostics()
            return
        self.timestamp_array.append(current_time)
        # self.temp_sensor_problem = self.temp_sensor.temperature_algorithm(self.oatemp, self.eatemp, self.hrtemp, self.hr_status, current_time)
        self.temp_sensor_dx.temperature_algorithm(self.mean_oatemp, self.mean_eatemp, self.mean_hrtemp, self.hr_status,
                                                  current_time)
        self.determine_hr_condition()
        _log.info(f"\tCorrect Heat Recovery Status {self.hr_status}")
        # if self.temp_sensor_problem is not None and not self.temp_sensor_problem: # if not a temp sensor problem, then append data
        self.hr_correctly_on_dx.heat_recovery_on_algorithm(self.mean_oatemp, self.mean_eatemp, self.mean_hrtemp,
                                                           self.sf_speed,
                                                           self.hr_status, current_time, self.hr_cond)
        self.hr_correctly_off_dx.heat_recovery_off_algorithm(self.mean_oatemp, self.mean_eatemp, self.mean_hrtemp,
                                                             self.sf_speed,
                                                             self.hr_status, current_time, self.hr_cond)
        if self.timestamp_array:
            elapsed_time = self.timestamp_array[-1] - self.timestamp_array[0]
        else:
            elapsed_time = td(minutes=0)
        # if not current_time.minute % self.run_interval or elapsed_time >= self.data_window: # for this to work, run_interval should be a factor of 60
        if elapsed_time >= self.data_window:  # if enough time has elapsed
            self.temp_sensor_problem = self.temp_sensor_dx.run_diagnostic(current_time)  # check for temp sensor problem
            if self.temp_sensor_problem is not None and not self.temp_sensor_problem:  # if no sensor problem is detected, run the other diagnostics
                self.hr_correctly_on_dx.run_diagnostic(current_time)
                self.hr_correctly_off_dx.run_diagnostic(current_time)
            elif self.temp_sensor_problem:  # if temp sensor problem is present
                self.pre_conditions(TEMP_SENSOR, current_time)
            self.clear_all()
        self.publish_analysis_results()
        # self.check_for_config_update_after_diagnostics()
    
    # def publish_analysis_results(self):
    #     """Publish the diagnostic results"""
    #     if(len(self.results_publish)) <= 0:
    #         return
    #     publish_base = "/".join([self.analysis_name])
    #     for app, analysis_table in self.results_publish:
    #         to_publish = {}
    #         name_timestamp = app.split("&")
    #         timestamp = name_timestamp[1]
    #         point = analysis_table[0]
    #         result = analysis_table[1]
    #         headers = {headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON, headers_mod.DATE: timestamp, }
    #         for device in self.publish_list:
    #             publish_topic = "/".join([publish_base, device, point])
    #             analysis_topic = topics.RECORD(subtopic=publish_topic)
    #             to_publish[analysis_topic] = result
    #
    #         for result_topic, result in to_publish.items():
    #             self.vip.pubsub.publish("pubsub", result_topic, headers, result)
    #         to_publish.clear()
    #     self.results_publish.clear()

    def publish_analysis_results(self):
        """Publish the diagnostic results"""
        _log.debug(f"Publishing analysis result with len {len(self.results_publish)}")
        _log.debug(f"Results object being published is {id(self.results_publish)}")
        if len(self.results_publish) <= 0:
            return
        publish_base = "/".join([self.analysis_name])
        _log.debug(self.results_publish)
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


if __name__ == '__main__':
    try:
        publickey = os.environ.get("AGENT_PUBLICKEY")
        secretkey = os.environ.get("AGENT_SECRETKEY")
        serverkey = os.environ.get("AGENT_SERVERKEY")
        vip_main(HeatRecoveryAgent, version=__version__, publickey=publickey, secretkey=secretkey, serverkey=serverkey)
    except KeyboardInterrupt:
        pass
