from datetime import timedelta as td, datetime
import logging
from typing import Optional, List, Tuple

from numpy import mean

# import constants
from ..diagnostics import table_log_format, HR1, DX, DiagnosticBase, ResultPublisher

_log = logging.getLogger(__name__)


class TemperatureSensor(DiagnosticBase):
    def __init__(self, analysis_name: str,  results_publish: List[Tuple]):
        super().__init__(analysis_name, results_publish)
        self.oatemp_values = []
        self.eatemp_values = []
        self.hrtemp_values = []

        self.temp_sensor_problem = None
        self.max_dx_time = None
        self.analysis_name = ""

        self.data_window = None
        self.no_required_data = None
        self.temp_diff_threshold = None
        self.inconsistent_date = None
        self.insufficient_data = None

        # self.temp_consistency_dx = TempConsistency()

    def set_class_values(self, data_window, no_required_data, temp_diff_threshold,
                         hr_off_steady_state):

        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window
        self.data_window = data_window
        self.no_required_data = no_required_data
        # why use different thresholds in the consistency and temperature algorithms?
        # oat_hrt_check = { 
        #     "low": max(temp_diff_threshold*1.5, 6.0),
        #     "normal": max(temp_diff_threshold *1.25, 5.0),
        #     "high": max(temp_diff_threshold, 4.0) }
        self.temp_diff_threshold = {
            "low": temp_diff_threshold + 2.0,
            "normal": temp_diff_threshold,
            "high": max(1.0, temp_diff_threshold - 2.0)}
        self.inconsistent_date = {key: 3.2 for key in self.temp_diff_threshold}
        self.insufficient_data = {key: 2.2 for key in self.temp_diff_threshold}

    def run_diagnostic(self, current_time: datetime) -> Optional[bool]:
        if self.timestamp:
            elapsed_time = self.timestamp[-1] - self.timestamp[0]
        else:
            elapsed_time = td(minutes=0)
        _log.info(f"Elapsed time {elapsed_time} -- required time: {self.data_window}")

        if len(self.timestamp) >= self.no_required_data:
            if elapsed_time >= self.max_dx_time:  # if too much time has elapsed without receiving enough data
                _log.info(table_log_format(self.analysis_name,
                                           self.timestamp[-1],
                                           HR1 + DX + ":" + str(self.inconsistent_date)))
                ResultPublisher.push_result(self, HR1 + DX + ":" + str(self.inconsistent_date), current_time)
                self.clear_data()
                return None
            temp_sensor_problem = self.temperature_sensor_dx()
        elif len(self.timestamp) < self.no_required_data:
            # self.push_result(...)
            _log.info("Not enough data to determine temperature range faults")
            temp_sensor_problem = None
        else:
            _log.error(f"{__name__} else for run_diagnostic")
            temp_sensor_problem = None
        self.clear_data()
        return temp_sensor_problem

    def temperature_algorithm(self, oatemp, eatemp, hrtemp, hr_status, cur_time):
        self.oatemp_values.append(oatemp)
        self.eatemp_values.append(eatemp)
        self.hrtemp_values.append(hrtemp)
        self.timestamp.append(cur_time)

    def temperature_sensor_dx(self):
        avg_oa_hr, avg_hr_oa, avg_ea_hr, avg_hr_ea = self.aggregate_data()
        diagnostic_msg = {}

        for sensitivity, threshold in self.temp_diff_threshold.items():
            if avg_oa_hr > threshold and avg_ea_hr > threshold:
                msg = "{}: HRT is less than OAT and EAT - Sensitivity: {}".format(HR1, sensitivity)
                result = 1.1
            elif avg_hr_oa > threshold and avg_hr_ea > threshold:
                msg = "{}: HRT is greater than OAT and RAT - Sensitivity: {}".format(HR1, sensitivity)
                result = 2.1
            else:
                msg = "{}: No problems were detected - Sensitivity: {}".format(HR1, sensitivity)
                result = 0.0
                self.temp_sensor_problem = False
            _log.info(msg)
            diagnostic_msg.update({sensitivity: result})
        if diagnostic_msg["normal"] > 0.0:
            self.temp_sensor_problem = True

        _log.info(table_log_format(self.analysis_name, self.timestamp[-1], (HR1 + DX + ":" + str(diagnostic_msg))))
        ResultPublisher.push_result(self, HR1 + DX + ":" + str(diagnostic_msg))

        temp_sensor_problem = self.temp_sensor_problem
        self.clear_data()  # this clears temp_sensor_problem which we need to return
        return temp_sensor_problem

    def aggregate_data(self):
        oa_hr = [(x - y) for x, y in zip(self.oatemp_values, self.hrtemp_values)]
        avg_oa_hr = mean(oa_hr)
        hr_oa = [(y - x) for x, y in zip(self.oatemp_values, self.hrtemp_values)]
        avg_hr_oa = mean(hr_oa)
        ea_hr = [(x - y) for x, y in zip(self.eatemp_values, self.hrtemp_values)]
        avg_ea_hr = mean(ea_hr)
        hr_ea = [(y - x) for x, y in zip(self.eatemp_values, self.hrtemp_values)]
        avg_hr_ea = mean(hr_ea)
        return avg_oa_hr, avg_hr_oa, avg_ea_hr, avg_hr_ea

    def clear_data(self):
        self.oatemp_values = []
        self.eatemp_values = []
        self.hrtemp_values = []
        self.timestamp.clear()
        if self.temp_sensor_problem:
            self.temp_sensor_problem = None
