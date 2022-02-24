from datetime import timedelta as td
import logging
from typing import Tuple, List

from numpy import mean

# import constants
from ..diagnostics import table_log_format, HR2, DX, EI, table_publish_format, DiagnosticBase, ResultPublisher

_log = logging.getLogger(__name__)


class HeatRecoveryCorrectlyOn(DiagnosticBase):
    def __init__(self, analysis_name: str, results_publish: List[Tuple]):
        super().__init__(analysis_name, results_publish)
        # initialize data arrays
        self.oatemp_values = []
        self.eatemp_values = []
        self.hrtemp_values = []
        self.sf_speed_values = []
        self.hr_status_values = []

        # Initialize not_recovering flag
        self.not_recovering = []
        self.not_recovering_timestamp = []

        self.hre_recovering_threshold = None
        self.hr_status_threshold = None
        self.data_window = None
        self.no_required_data = None
        self.cfm = None
        self.eer = None
        self.expected_hre = None
        self.max_dx_time = None

        self.not_recovering_dict = None
        self.inconsistent_date = None
        self.insufficient_data = None

        self.alg_result_messages = [
            "The conditions are favorable for heat recovery, but the heat recovery system is not operating",
            "The heat recovery system is operating but is not effectively recovering heat",
            "The heat recovery is functioning as expected"]

    def set_class_values(self, hr_status_threshold, hre_recovering_threshold, data_window,
                         no_required_data, rated_cfm, eer, expected_hre):
        # override base class's results_published with passed agent results publish.
        self.hr_status_threshold = hr_status_threshold
        self.hre_recovering_threshold = {"low": hre_recovering_threshold - 20,
                                         "normal": hre_recovering_threshold,
                                         "high": hre_recovering_threshold + 20}
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.rated_cfm = rated_cfm
        self.eer = eer
        self.expected_hre = expected_hre
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2
        self.not_recovering_dict = {key: 15.0 for key in self.hre_recovering_threshold}
        self.insufficient_data = {key: 13.2 for key in self.hre_recovering_threshold}
        self.inconsistent_date = {key: 13.2 for key in self.hre_recovering_threshold}

    def run_diagnostic(self, current_time):
        if self.timestamp:
            elapsed_time = self.timestamp[-1] - self.timestamp[0]
        else:
            elapsed_time = td(minutes=0)
        # if self.heat_recovery_conditions(current_time): # what is the intent here?
        #     return
        if len(self.timestamp) >= self.no_required_data:
            if elapsed_time > self.max_dx_time:
                _log.info(table_log_format(self.analysis_name, self.timestamp[-1],
                                           HR2 + DX + ":" + str(self.inconsistent_date)))
                # table_publish_format(self.analysis_name, self.timestamp[-1], __name__,
                #                      HR2 + DX + ":" + str(self.inconsistent_date))
                ResultPublisher.push_result(self, HR2 + DX + ":" + str(self.inconsistent_date))

                self.clear_data()
                return
            self.not_recovering_when_needed()
        else:
            # TODO what should be published here?
            # self.push_result(...)
            self.clear_data()

    def heat_recovery_on_algorithm(self, oatemp, eatemp, hrtemp, sf_speed, hr_status, cur_time, hr_cond):
        recovering = self.recovering_check(hr_cond, cur_time)
        self.not_recovering_timestamp.append(cur_time)
        if not recovering:
            return
        self.timestamp.append(cur_time)
        self.oatemp_values.append(oatemp)
        self.eatemp_values.append(eatemp)
        self.hrtemp_values.append(hrtemp)
        self.hr_status_values.append(hr_status)
        sf_speed = sf_speed / 100.0 if sf_speed is not None else 1.0
        self.sf_speed_values.append(sf_speed)

    def recovering_check(self, hr_cond, cur_time):
        if not hr_cond:
            _log.info(f"{HR2} not recovering heat at {cur_time}")
            self.not_recovering.append(cur_time)
            return False
        return True

    def heat_recovery_conditions(self, current_time):
        # More than half the time we are recovering.
        if len(self.not_recovering) >= len(self.not_recovering_timestamp) * 0.5:
            txt = table_log_format(self.analysis_name, current_time, HR2 + DX + str(self.not_recovering_dict))
            _log.info(txt)
            ResultPublisher.push_result(self, txt, current_time)
            self.clear_data()
            return True
        return False

    def not_recovering_when_needed(self):
        hre = [(oat - hrt) / (oat - eat) for oat, hrt, eat in
               zip(self.oatemp_values, self.hrtemp_values, self.eatemp_values)]
        avg_hre = mean(hre)
        avg_hr_status = mean(self.hr_status_values)
        diagnostic_msg = {}
        energy_impact = {}
        for key, hre_threshold in self.hre_recovering_threshold.items():
            if avg_hr_status < self.hr_status_threshold:  # recovery not on
                msg = "{} - {}: {}".format(HR2, key, self.alg_result_messages[0])
                result = 11.1
                energy = self.energy_impact_calculation()
            elif avg_hre < hre_threshold / 100:  # recovery on but not effective
                msg = "{} - {}: {} - HRE={}%".format(HR2, key, self.alg_result_messages[1], round(avg_hre * 100, 1))
                result = 12.1
                energy = self.energy_impact_calculation()
            else:  # no problem
                msg = "{} - {}: {}".format(HR2, key, self.alg_result_messages[2])
                result = 10.0
                energy = 0.0
            _log.info(msg)
            diagnostic_msg.update({key: result})
            energy_impact.update({key: energy})

        _log.info(table_log_format(self.analysis_name, self.timestamp[-1], HR2 + DX + ":" + str(diagnostic_msg)))
        ResultPublisher.push_result(self, HR2 + DX + ":" + str(diagnostic_msg))

        _log.info(table_log_format(self.analysis_name, self.timestamp[-1], HR2 + EI + ":" + str(energy_impact)))
        ResultPublisher.push_result(self, HR2 + EI + ":" + str(energy_impact))

        self.clear_data()

    def energy_impact_calculation(self):
        ei = 0.0
        energy_calc = [
            1.08 * self.rated_cfm * sf_speed * abs(hrt - oat + self.expected_hre * (oat - eat)) / (1000 * self.eer) for
            oat, hrt, eat, sf_speed in
            zip(self.oatemp_values, self.hrtemp_values, self.eatemp_values, self.sf_speed_values)]
        if energy_calc:
            avg_step = (self.timestamp[-1] - self.timestamp[0]).total_seconds() / 60 if len(self.timestamp) > 1 else 1
            dx_time = (len(energy_calc) - 1) * avg_step if len(energy_calc) > 1 else 1.0
            ei = sum(energy_calc) * 60.0 / (len(energy_calc) * dx_time)
            ei = round(ei, 2)
            return ei

    def clear_data(self):
        self.oatemp_values = []
        self.eatemp_values = []
        self.hrtemp_values = []
        self.sf_speed_values = []
        self.hr_status_values = []
        self.timestamp.clear()
        self.not_recovering = []
        self.not_recovering_timestamp = []
