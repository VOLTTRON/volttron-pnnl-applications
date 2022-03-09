import logging
from datetime import timedelta as td
from typing import Tuple, List

from numpy import mean

from . import table_log_format, HR3, DX, EI, DiagnosticBase, ResultPublisher

_log = logging.getLogger(__name__)

# import constants


class HeatRecoveryCorrectlyOff(DiagnosticBase):
    def __init__(self, analysis_name: str, results_publish: List[Tuple]):
        super().__init__(analysis_name, results_publish)
        # initialize data arrays
        self.oatemp_values = []
        self.eatemp_values = []
        self.hrtemp_values = []
        self.sf_speed_values = []
        self.hr_status_values = []
        self.timestamp = []
        self.recovering_timestamp = []
        self.analysis_name = ""

        # Initialize not_recovering flag
        self.recovering = []

        self.hre_recovering_threshold = None
        self.hr_status_threshold = None
        self.data_window = None
        self.no_required_data = None
        self.cfm = None
        self.eer = None
        self.max_dx_time = None

        self.recovering_dict = None
        self.inconsistent_date = None
        self.insufficient_data = None

        self.alg_result_messages = [
            "Inconsistent or missing data; therefore, potential operational improvements cannot be detected at this time",
            "The heat recovery system is commanded off, but heat is still being recovered",
            "The conditions are not favorable for heat recovery, but the heat recovery system is operating",
            "The heat recovery is functioning as expected"]

    def set_class_values(self, hr_status_threshold,
                         hre_recovering_threshold, data_window, no_required_data, rated_cfm, eer):
        self.hr_status_threshold = hr_status_threshold
        self.hre_recovering_threshold = {"low": hre_recovering_threshold + 20,
                                         "normal": hre_recovering_threshold,
                                         "high": hre_recovering_threshold - 20}
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.rated_cfm = rated_cfm
        self.eer = eer
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2
        self.recovering_dict = {key: 25.0 for key in self.hre_recovering_threshold}
        self.insufficient_data = {key: 23.2 for key in self.hre_recovering_threshold}
        self.inconsistent_date = {key: 22.2 for key in self.hre_recovering_threshold}

    def run_diagnostic(self, current_time):
        if self.timestamp:
            elapsed_time = self.timestamp[-1] - self.timestamp[0]
        else:
            elapsed_time = td(minutes=0)

        if self.heat_recovery_conditions(current_time):
            return

        if len(self.timestamp) >= self.no_required_data:
            if elapsed_time > self.max_dx_time:
                _log.info(table_log_format(self.analysis_name, self.timestamp[-1],
                                                 HR3 + DX + ":" + str(self.inconsistent_date)))
                ResultPublisher.push_result(obj=self, table=(HR3 + DX), data=self.inconsistent_date,
                                            timestamp=self.timestamp[-1])
                self.clear_data()
                return
            self.recovering_when_not_needed()
        else:
            # TODO What to publish here?
            # self.push_result(...)
            self.clear_data()

    def heat_recovery_off_algorithm(self, oatemp, eatemp, hrtemp, sf_speed, hr_status, cur_time, hr_cond):
        recovering = self.recovering_check(hr_cond, cur_time)
        self.recovering_timestamp.append(cur_time)
        if recovering:
            return
        self.timestamp.append(cur_time)
        self.oatemp_values.append(oatemp)
        self.eatemp_values.append(eatemp)
        self.hrtemp_values.append(hrtemp)
        self.hr_status_values.append(hr_status)
        sf_speed = sf_speed / 100.0 if sf_speed is not None else 1.0
        self.sf_speed_values.append(sf_speed)

    def recovering_check(self, hr_cond, cur_time):
        if hr_cond:
            _log.info(f"{HR3}: recovering heat at {cur_time}")
            self.recovering.append(cur_time)
            return True
        return False

    def heat_recovery_conditions(self, current_time):
        # More than half the time we are recovering.
        if len(self.recovering) >= len(self.recovering_timestamp) * 0.5:
            txt = table_log_format(self.analysis_name, current_time, HR3 + DX + str(self.recovering_dict))
            _log.info(txt)
            ResultPublisher.push_result(obj=self, table=(HR3 + DX), data=self.recovering_dict, timestamp=current_time)
            self.clear_data()
            return True
        return False

        # if len(self.not_cooling) >= len(self.not_cooling)*0.5:
        #     _log.info(constants.table_log_format(self.analysis_name, current_time,
        #                                          (constants.ECON2 + constants.DX + ":" + str(self.not_cooling_dict))))
        #     self.results_publish.append(
        #         constants.table_publish_format(self.analysis_name,
        #                                        current_time,
        #                                        (constants.ECON2 + constants.DX),
        #                                        self.not_cooling_dict))
        #     self.clear_data()
        #     return True
        # if len(self.not_cooling) >= len(self.not_cooling)*0.5:
        #     _log.info(constants.table_log_format(self.analysis_name, current_time,
        #                                          (constants.ECON2 + constants.DX + ":" + str(self.not_cooling_dict))))
        #     self.results_publish.append(
        #         constants.table_publish_format(self.analysis_name,
        #                                        current_time,
        #                                        (constants.ECON2 + constants.DX),
        #                                        self.not_cooling_dict))
        #     self.clear_data()
        #     return True
        # return False

    def recovering_when_not_needed(self):
        hre = [(oat - hrt) / (oat - eat) for oat, hrt, eat in
               zip(self.oatemp_values, self.hrtemp_values, self.eatemp_values)]
        avg_hre = mean(hre)
        avg_hr_status = mean(self.hr_status_values)
        diagnostic_msg = {}
        energy_impact = {}
        for key, hre_threshold in self.hre_recovering_threshold.items():
            if avg_hr_status >= self.hr_status_threshold:  # recovery not on
                msg = "{} - {}: {}".format(HR3, key, self.alg_result_messages[2])
                result = 21.1
                energy = self.energy_impact_calculation()
            elif avg_hre >= hre_threshold / 100:  # recovery on but not effective
                msg = "{} - {}: {} - HRE={}%".format(HR3, key, self.alg_result_messages[1], round(avg_hre * 100, 1))
                result = 22.1
                energy = self.energy_impact_calculation()
            else:  # no problem
                msg = "{} - {}: {}".format(HR3, key, self.alg_result_messages[3])
                result = 20.0
                energy = 0.0

            _log.info(msg)
            diagnostic_msg.update({key: result})
            energy_impact.update({key: energy})

        _log.info(table_log_format(self.analysis_name, self.timestamp[-1], HR3 + DX + ":" + str(diagnostic_msg)))
        ResultPublisher.push_result(obj=self, table=(HR3 + DX), data=diagnostic_msg, timestamp=self.timestamp[-1])

        _log.info(table_log_format(self.analysis_name, self.timestamp[-1], HR3 + EI + ":" + str(energy_impact)))
        ResultPublisher.push_result(obj=self, table=(HR3 + DX), data=energy_impact, timestamp=self.timestamp[-1])

        self.clear_data()

    def energy_impact_calculation(self):
        ei = 0.0
        energy_calc = [1.08 * self.rated_cfm * sf_speed * abs(hrt - oat) / (1000 * self.eer) for oat, hrt, sf_speed in
                       zip(self.oatemp_values, self.hrtemp_values, self.sf_speed_values)]
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
        self.timestamp = []
        self.recovering = []
        self.recovering_timestamp = []
