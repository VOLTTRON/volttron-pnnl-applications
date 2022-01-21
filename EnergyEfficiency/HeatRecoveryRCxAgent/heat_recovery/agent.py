import dataclasses
import logging
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta as td
from typing import List, Union, Optional

import dateutil.tz
from dateutil import parser
from numpy import mean

from volttron.platform.agent.utils import (
    vip_main, load_config
)
from volttron.platform.messaging import topics as vtopic
from volttron.platform.vip.agent import (
    Agent,
)
from .analysis_config import AnalysisConfig, UnitProperty
from .diagnostics import (
    table_log_format,
    HRT_LIMIT,
    TemperatureSensor,
    HeatRecoveryCorrectlyOn,
    HeatRecoveryCorrectlyOff, DX_LIST, DX, OAT_LIMIT, EAT_LIMIT, FAN_OFF, OAT_EAT_CLOSE, OAT_SAT_SP_CLOSE, TEMP_SENSOR
)

logging.basicConfig(level=logging.DEBUG)
# setup_logging(logging.DEBUG, True)
_log = logging.getLogger(__name__)

ANALYSIS_NAME = "Heat_Recovery_AIRCx"


@dataclass
class HeatRecoveryConfig(AnalysisConfig):
    # analysis_name: str = dataclasses.field(*, default=ANALYSIS_NAME)
    analysis_name: Optional[str] = ANALYSIS_NAME

    def validate(self):
        super().validate()
        # do validation here.
        for k, v in self.arguments.items():
            print(k, v)


class HeatRecoveryAgent(Agent):
    analysis_name = ANALYSIS_NAME
    hr_off_steady_state = td(minutes=1)

    def __init__(self, config_path, **kwargs):
        super(HeatRecoveryAgent, self).__init__(enable_store=True, **kwargs)

        self.sensitivity = ["normal"]
        self.oatemp_name = "OutdoorAirTemperature"
        self.sf_status_name = "SupplyFanStatus"
        self.ef_status_name = "ExhaustFanStatus"
        self.sf_speed_name = "SupplyFanSpeedPercent"
        self.ef_speed_name = "ExhaustFanSpeedPercent"
        self.eatemp_name = "ReturnAirTemperature"
        self.hrtemp_name = "HrWheelLeavingAirTemperature"
        self.sat_sp_name = "DischargeAirTemperatureSetPoint"
        self.hr_status_name = "HrWheelEnabled"
        self.timezone = "US/Pacific"
        # self.publish_base = ""
        self.sensor_limit_msg = ""

        self.publish_list = []

        self.damper_data = []
        self.oatemp_values = []
        self.sf_status_values = []
        self.ef_status_values = []
        self.sf_speed_values = []
        self.ef_speed_values = []
        self.eatemp_value = []
        self.hrtemp_values = []
        self.sat_sp_values = []
        self.hr_status_values = []
        self.missing_data = []
        self.results_publish = []
        self.timestamp_array = []

        # int attributes
        self.run_interval = 4  # the number of minutes in data_window. not independent.
        self.data_window = td(minutes=self.run_interval)

        self.no_required_data = 4
        self.max_dx_time = 30
        self.hr_cond = None  # condition the HR should be in

        # float attributes
        self.oat_low_threshold = 20.0
        self.oat_high_threshold = 120.0
        self.eat_low_threshold = 50.0
        self.eat_high_threshold = 90.0
        self.hrt_low_threshold = -20.0
        self.hrt_high_threshold = 120.0
        self.oa_ea_low_deadband = 2.0
        self.oa_ea_high_deadband = 5.0
        self.oa_sat_low_deadband = 8.0
        self.oa_sat_high_deadband = 2.0
        self.hre_recovering_threshold = 50.0
        self.rated_cfm = 1000.0
        self.expected_hre = 0.5
        self.eer = 20.0
        self.hr_status_threshold = 0.5
        self.sf_status_threshold = 0.5  # threshold of determining if sf is on (status)
        self.sf_speed_threshold = 30  # threshold for determining if sf is on (speed)
        self.temp_diff_threshold = 4.0
        # bool attributes
        self.constant_volume = False

        self.hr_off_steady_state = td(minutes=1)
        # int data
        self.sf_status = 0
        self.ef_status = 0
        self.sf_speed = 0
        self.ef_speed = 0
        self.hr_status = 0
        # float data
        self.oatemp = 0.0
        self.eatemp = 0.0
        self.hrtemp = 0.0
        self.sat_sp = 0.0

        # precondition flags
        self.oatemp_eatemp_close_condition = []
        self.oatemp_sat_sp_close_condition = []
        self.unit_status = []
        self.sensor_limit = []
        self.temp_sensor_problem = None
        self.diagnostic_done_flag = True

        # diagnostics
        self.temp_sensor = None
        self.hr_correctly_on = None
        self.hr_correctly_off = None

        # our configuration is setup to be a dictionary and is available
        # from the config store or the file passed to the agent itself.
        self.config: Union[dict, HeatRecoveryConfig] = {}

        # Get the data from the passed file.
        config = load_config(config_path)

        # print(self.aconfig)
        # If there is configuration then we need to set it for the default use
        # case, otherwise the agent will use what is currently in the config
        # store.
        if config:
            self.vip.config.set_default("config", config)
            self.config = HeatRecoveryConfig(**config)
            # self.config.update(**config)
            # self.config.validate()
            print(self.config.device.campus)

        # Subscription allows any changes to the config store to propagate
        # to the agent.
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"])

        self._messages_received = 0
        self.create_diagnostics()

    def get_subscription_topics(self) -> List[str]:
        """
        This function uses the device
        :return:
        """
        topics = []
        device = self.config.device

        base_subscription = f"device/{device.campus}/{device.building}"
        # building level all message
        # topics.append(f"{base_subscription}/all")
        topics.append(vtopic.DEVICES_VALUE(campus=device.campus, building=device.building,
                                           unit="", point="all"))
        # unit=u, path="", point="all")

        if isinstance(device.unit, str):
            topics.append(vtopic.DEVICES_VALUE(campus=device.campus, building=device.building, unit=device.unit,
                                               point="all"))
            # topics.append(vtopic.DEVICES_VALUE(campus=device.campus, building=device.building, unit=device.unit))
            # topics.append(f"{base_subscription}/{device.unit}/all")
        elif isinstance(device.unit, UnitProperty):
            # Loops over the name fo the units
            for k in device.unit.units:
                # append the unit i.e rtu
                topics.append(
                    vtopic.DEVICES_VALUE(campus=device.campus, building=device.building, unit=k, point="all")
                )

                # v should be a list of sub devices for the unit i.e ahu
                for subdev in device.unit.unit[k]:
                    topics.append(
                        vtopic.DEVICES_VALUE(campus=device.campus, building=device.building, unit=k,
                                             path=subdev, point="all")
                    )
                    # topics.append(f"{base_subscription}/{k}/{subdev}/all")
        else:
            raise ValueError("Invalid configuration detected ")
        return topics

    def configure(self, config_name, action, contents):
        # Create a copy of the current configuration object.
        if isinstance(self.config, HeatRecoveryConfig):
            # asdict is always available on dataclass objects
            config = dataclasses.asdict(self.config)
        else:
            config = deepcopy(self.config)

        config.update(**contents)

        try:
            # Validate the new values, should raise Key or Value error
            # if invalid data is specified.
            hr_config = HeatRecoveryConfig(**config)

            hr_config.validate()

            # Unsubscribe to all topics.
            self.vip.pubsub.unsubscribe(peer="pubsub", prefix="", callback=self.new_data_message)

            # We now have new state of the configuration
            self.config = hr_config
            self._messages_received = 0

            # TODO: Skip this and just use the config object itself if possible?
            # TODO: Perhaps a shallow copy of these rather than using getattr setattr
            # TODO: Should these be member variables?
            # Set items on the current object from the config object.
            for field in dataclasses.fields(self.config):
                setattr(self, field.name, getattr(self.config, field.name))

            if isinstance(self.config.arguments, dict):
                for k, v in self.config.arguments.items():
                    setattr(self, k, v)
            else:
                for field in dataclasses.fields(self.config.arguments):
                    setattr(self, field.name, getattr(self.config.arguments, field.name))

            for topic in self.get_subscription_topics():
                _log.debug(f"Subscribing to {topic}")
                self.vip.pubsub.subscribe(peer="pubsub", prefix=topic, callback=self.new_data_message)

        except (KeyError, ValueError) as ex:
            _log.error(f"Invalid configuration options specified {ex} ")

            # First time through if we get a validation error then we want to
            # exit with a bad value.
            if config_name == 'config' and action == 'NEW':
                sys.exit(1)

    def create_diagnostics(self):
        self.temp_sensor = TemperatureSensor()
        self.temp_sensor.set_class_values(self.analysis_name, self.results_publish,
                                          self.data_window, self.no_required_data,
                                          self.temp_diff_threshold, self.hr_off_steady_state)
        self.hr_correctly_on = HeatRecoveryCorrectlyOn()
        self.hr_correctly_on.set_class_values(self.results_publish, self.hr_status_threshold,
                                              self.hre_recovering_threshold, self.data_window,
                                              self.analysis_name, self.no_required_data,
                                              self.rated_cfm, self.eer, self.expected_hre)
        self.hr_correctly_off = HeatRecoveryCorrectlyOff()
        self.hr_correctly_off.set_class_values(self.results_publish, self.hr_status_threshold,
                                               self.hre_recovering_threshold, self.data_window,
                                               self.analysis_name, self.no_required_data,
                                               self.rated_cfm, self.eer)

    def parse_data_message(self, message):

        data_message = message[0]

        self.oatemp_values = []
        self.sf_status_values = []
        self.ef_status_values = []
        self.sf_speed_values = []
        self.ef_speed_values = []
        self.eatemp_values = []
        self.hrtemp_values = []
        self.sat_sp_values = []
        self.hr_status_values = []
        self.missing_data = []

        for key in data_message:
            value = data_message[key]
            if value is None:
                continue
            if key in self.oatemp_name:
                self.oatemp_values.append(value)
            if key in self.sf_status_name:
                self.sf_status_values.append(value)
            if key in self.ef_status_name:
                self.ef_status_values.append(value)
            if key in self.sf_speed_name:
                self.sf_speed_values.append(value)
            if key in self.ef_speed_name:
                self.ef_speed_values.append(value)
            if key in self.eatemp_name:
                self.eatemp_values.append(value)
            if key in self.hrtemp_name:
                self.hrtemp_values.append(value)
            if key in self.sat_sp_name:
                self.sat_sp_values.append(value)
            if key in self.hr_status_name:
                self.hr_status_values.append(value)

    def check_for_missing_data(self):
        if not self.oatemp_values:
            self.missing_data.append(self.oatemp_name)
        if not self.sf_status_values and not self.sf_speed_values:  # need either fan status or speed
            self.missing_data.append(self.sf_status_name)
        # if not self.ef_status_values and not self.ef_speed_values:      # don't need exhaust fan status
        #     self.missing_data.append(self.ef_status_name)
        if not self.eatemp_values:
            self.missing_data.append(self.eatemp_name)
        if not self.hrtemp_values:
            self.missing_data.append(self.hrtemp_name)
        if not self.sat_sp_values:
            self.missing_data.append(self.sat_sp_name)
        # if not self.hr_status_values: n                     # don't need heat recovery status
        #     self.missing_data.append(self.hr_status_name)
        if self.missing_data:
            return True
        return False

    def check_sf_status(self, current_time):
        if self.sf_status_values:
            mean_status = mean(self.sf_status_values)
            if mean_status >= self.sf_status_threshold:
                sf_status = 1
            else:
                sf_status = 0
        else:
            sf_status = None
        if self.sf_speed_values:
            self.sf_speed = mean(self.sf_speed_values)
        else:
            self.sf_speed = None
        if sf_status is None:
            if self.sf_speed >= self.sf_speed_threshold:
                sf_status = 1
            else:
                sf_status = 0
        if not sf_status:  # this should not be true. We checked that status and speed are not both missing.
            self.unit_status.append(current_time)
        return sf_status

    def check_oatemp_eatemp_condition(self, current_time):
        # check if OAT is too close to EAT
        if self.oatemp < self.eatemp + self.oa_ea_high_deadband and self.oatemp > self.eatemp - self.oa_ea_low_deadband:
            self.oatemp_eatemp_close_condition.append(current_time)

    def check_oatemp_sat_sp_condition(self, current_time):
        # check if OAT is too close to SAT_SP
        if self.oatemp < self.sat_sp + self.oa_sat_high_deadband and self.oatemp > self.sat_sp - self.oa_sat_low_deadband:
            self.oatemp_sat_sp_close_condition.append(current_time)

    def check_elapsed_time(self, current_time, condition,
                           message):  # condition is a list of timestamps when the condition was true
        if condition:
            elapsed_time = current_time - condition[-1]  # time since the last time this condition was true
        else:
            elapsed_time = td(minutes=0)
        # if ((current_time.minute % self.run_interval and len(condition)>=self.no_required_data) or elapsed_time >= self.data_window):
        if (len(condition) >= self.no_required_data) and (elapsed_time >= self.data_window):
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
        self.temp_sensor.clear_data()
        self.hr_correctly_on.clear_data()
        self.hr_correctly_off.clear_data()

    def pre_conditions(self, message, cur_time):
        dx_msg = {}
        for sensitivity in self.sensitivity:
            dx_msg[sensitivity] = message
        for diagnostic in DX_LIST:  # log the message for each diagnostic
            print("info:" + table_log_format(self.analysis_name, cur_time,
                                             (diagnostic + DX + ":" + str(dx_msg))))
            # self.results_publish.append(...)

    def determine_hr_condition(self):
        if self.oatemp > self.sat_sp + self.oa_sat_high_deadband and self.oatemp < self.eatemp - self.oa_ea_low_deadband:
            self.hr_cond = False
        else:
            self.hr_cond = True

    def sensor_limit_check(self, current_time):
        if self.oatemp < self.oat_low_threshold or self.oatemp > self.oat_high_threshold:
            self.sensor_limit.append(current_time)
            self.sensor_limit_msg = OAT_LIMIT
            print("info: OAT sensor is outside of bounds: {}".format(current_time))
        elif self.eatemp < self.eat_low_threshold or self.eatemp > self.eat_high_threshold:
            self.sensor_limit.append(current_time)
            self.sensor_limit_msg = EAT_LIMIT
            print("info: EAT sensor is outside of bounds: {}".format(current_time))
        elif self.hrtemp < self.hrt_low_threshold or self.hrtemp > self.hrt_high_threshold:
            self.sensor_limit.append(current_time)
            self.sensor_limit_msg = HRT_LIMIT
            print("info: HRT sensor is outside of bounts: {}".format(current_time))

    # def new_data_message(self, message):
    def new_data_message(self, peer, sender, bus, topic, headers, message):
        self.diagnostic_done_flag = False
        current_time = parser.parse(headers["Date"])
        # current_time = message[0]['timestamp']  # parser.parse(headers["Date"])
        to_zone = dateutil.tz.gettz(self.timezone)
        current_time = current_time.astimezone(to_zone)
        print("info: Processing Results!")  # _log.info("Processing Results!")
        self.parse_data_message(message)
        missing_data = self.check_for_missing_data()
        if missing_data:
            print("info: Missing data from publish: {}".format(
                self.missing_data))  # _log.info("Missing data from publish: {}".format(self.missing_data))
            # self.publish_analysis_results()
            # self.check_for_config_update_after_diagnostics()
            return
        self.sf_status = self.check_sf_status(current_time)
        precondition_failed = self.check_elapsed_time(current_time, self.unit_status, FAN_OFF)
        if not self.sf_status or precondition_failed:
            print("info: Supply fan is off: {}".format(
                current_time))  # _lof.info("Supply fan is off: {}".format(current_time))
            # self.publish_analysis_results()
            # self.check_for_config_update_after_diagnostics()
            return
        else:
            print("info: Supply fan is on: {}".format(current_time))

        if self.sf_speed is None and self.constant_volume:
            self.sf_speed = 100
        self.oatemp = mean(self.oatemp_values)
        self.eatemp = mean(self.eatemp_values)
        self.hrtemp = mean(self.hrtemp_values)
        self.sat_sp = mean(self.sat_sp_values)
        avg_hr_status = mean(self.hr_status_values)
        if avg_hr_status >= self.hr_status_threshold:
            self.hr_status = 1
        else:
            self.hr_status = 0

        self.check_oatemp_eatemp_condition(current_time)
        precondition_failed = self.check_elapsed_time(current_time, self.oatemp_eatemp_close_condition,
                                                      OAT_EAT_CLOSE)
        if current_time in self.oatemp_eatemp_close_condition or precondition_failed:
            print("info: OAT and EAT readings are too close: {}".format(current_time))
            # self.publish_analysis_results()
            # self.check_for_config_update_after_diagnostics()
            return
        self.check_oatemp_sat_sp_condition(current_time)
        precondition_failed = self.check_elapsed_time(current_time, self.oatemp_sat_sp_close_condition,
                                                      OAT_SAT_SP_CLOSE)
        if current_time in self.oatemp_sat_sp_close_condition or precondition_failed:
            print("info: OAT and SAT SP readings are too close: {}".format(current_time))
            # self.publish_analysis_results()
            # self.check_for_config_update_after_diagnostics()
            return

        self.sensor_limit_check(current_time)
        precondition_failed = self.check_elapsed_time(current_time, self.sensor_limit, self.sensor_limit_msg)
        if current_time in self.sensor_limit or precondition_failed:
            # self.publish_analysis_results()
            # self.check_for_config_update_after_diagnostics()
            return
        self.timestamp_array.append(current_time)
        # self.temp_sensor_problem = self.temp_sensor.temperature_algorithm(self.oatemp, self.eatemp, self.hrtemp, self.hr_status, current_time)
        self.temp_sensor.temperature_algorithm(self.oatemp, self.eatemp, self.hrtemp, self.hr_status, current_time)
        self.determine_hr_condition()
        print("info: Correct Heat Recovery Status: {}".format(self.hr_cond))
        # if self.temp_sensor_problem is not None and not self.temp_sensor_problem: # if not a temp sensor problem, then append data
        self.hr_correctly_on.heat_recovery_on_algorithm(self.oatemp, self.eatemp, self.hrtemp, self.sf_speed,
                                                        self.hr_status, current_time, self.hr_cond)
        self.hr_correctly_off.heat_recovery_off_algorithm(self.oatemp, self.eatemp, self.hrtemp, self.sf_speed,
                                                          self.hr_status, current_time, self.hr_cond)
        if self.timestamp_array:
            elapsed_time = self.timestamp_array[-1] - self.timestamp_array[0]
        else:
            elapsed_time = td(minutes=0)
        # if not current_time.minute % self.run_interval or elapsed_time >= self.data_window: # for this to work, run_interval should be a factor of 60
        if (elapsed_time >= self.data_window):  # if enough time has elapsed
            self.temp_sensor_problem = self.temp_sensor.run_diagnostic(current_time)  # check for temp sensor problem
            if self.temp_sensor_problem is not None and not self.temp_sensor_problem:  # if no sensor problem is detected, run the other diagnostics
                self.hr_correctly_on.run_diagnostic(current_time)
                self.hr_correctly_off.run_diagnostic(current_time)
                pass
            elif self.temp_sensor_problem:  # if temp sensor problem is present
                self.pre_conditions(TEMP_SENSOR, current_time)
            self.clear_all()
        # self.publish_analysis_results()
        # self.check_for_config_update_after_diagnostics()


if __name__ == '__main__':
    vip_main(HeatRecoveryAgent, identity="heat_recovery",
             publickey="REpJn2gAaKKX7qDzN5M-NW8ZGmdJyPb-ggRDUd_K52Q",
             secretkey="Lj8nDCqwkAb-dul7IhmeBQsE0jKv2fM2YaPgcmf0CBo",
             serverkey="33Jiil4A_kNutFhwKmZ3H4OwuQ0al-kZSe-fsdLsfGI")
