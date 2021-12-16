import pandas as pd
from numpy import mean
import dateutil.tz
from datetime import timedelta as td
from .diagnostics import (
    table_log_format,
    HRT_LIMIT,
    TemperatureSensor,
    HeatRecoveryCorrectlyOn,
    HeatRecoveryCorrectlyOff, DX_LIST, DX, OAT_LIMIT, EAT_LIMIT, FAN_OFF, OAT_EAT_CLOSE, OAT_SAT_SP_CLOSE, TEMP_SENSOR
)

from volttron.platform.vip.agent import (
    Agent,
    Core,
)

from volttron.platform.agent.utils import (
    setup_logging,
    vip_main
)


class HeatRecoveryAgent: #(Agent):
    def __init__(self):
        # list of class attributes.  Default values will be filled in from reading config file
        # string attributes
        self.config = None
        self.campus = "PNNL"
        self.building = "SEB"
        # self.agent_id = ""
        self.device_type = "ahu hr"
        self.analysis_name = "Heat_Recovery_AIRCx"
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

        # list attributes
        self.device_list = ["AHU1"]
        self.publish_list = []
        self.units = []
        self.arguments = []
        self.point_mapping = []
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
        self.hr_off_steady_state = td(minutes=1)
        self.temp_diff_threshold = 4.0
        # bool attributes
        self.constant_volume = False

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
        self.create_diagnostics()

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

    def new_data_message(self, message):
        self.diagnostic_done_flag = False
        current_time = message[0]['timestamp']  # parser.parse(headers["Date"])
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




