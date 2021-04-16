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
BATTELLE
for the
UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
"""
import logging
from datetime import timedelta as td
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import setup_logging
from .. import constants

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.debug, format="%(asctime)s   %(levelname)-8s %(message)s",
                    datefmt="%m-%d-%y %H:%M:%S")


class ExcessOutsideAir(object):
    """
    Air-side HVAC ventilation diagnostic.
    ExcessOutside Air uses metered data from a controller or
    BAS to diagnose when an AHU/RTU is providing excess outdoor air.
    """

    def __init__(self):
        # Initialize data arrays
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.oad_values = []
        self.timestamp = []
        self.fan_spd_values = []
        self.economizing = []
        self.analysis_name = ""
        self.results_publish = None

        # Application thresholds (Configurable)
        self.cfm = None
        self.eer = None
        self.max_dx_time = None
        self.data_window = None
        self.no_required_data = None
        self.excess_oaf_threshold = None
        self.min_damper_sp = None
        self.desired_oaf = None
        self.excess_damper_threshold = None
        self.economizing_dict = None
        self.invalid_oaf_dict = None
        self.inconsistent_date = None
        self.nsufficient_data = None

    def set_class_values(self, analysis_name, results_publish, data_window, no_required_data, min_damper_sp, desired_oaf, cfm, eer):
        """Set the values needed for doing the diagnostics
        analysis_name: string
        data_window: datetime time delta
        no_required_data: integer
        min_damper_sp: float
        desired_oaf: float
        cfm: float
        eer: float

        No return
        """
        self.results_publish = results_publish
        self.cfm = cfm
        self.eer = eer
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2
        self.data_window = data_window
        self.analysis_name = analysis_name
        self.no_required_data = no_required_data
        self.excess_oaf_threshold = {
            "low": min_damper_sp*2.0 + 10.0,
            "normal": min_damper_sp + 10.0,
            "high": min_damper_sp*0.5 + 10.0
        }
        self.min_damper_sp = min_damper_sp
        self.desired_oaf = desired_oaf
        self.excess_damper_threshold = {
            "low": min_damper_sp*2.0,
            "normal": min_damper_sp,
            "high":  min_damper_sp*0.5
        }
        self.economizing_dict = {key: 36.0 for key in self.excess_damper_threshold}
        self.invalid_oaf_dict = {key: 31.2 for key in self.excess_damper_threshold}
        self.insufficient_data = {key: 32.2 for key in self.excess_damper_threshold}
        self.inconsistent_date = {key: 35.2 for key in self.excess_damper_threshold}

    def run_diagnostic(self, current_time):
        if self.timestamp:
            elapsed_time = self.timestamp[-1] - self.timestamp[0]
        else:
            elapsed_time = td(minutes=0)
        if self.economizer_conditions(current_time):
            return
        if len(self.timestamp) >= self.no_required_data:
            if elapsed_time > self.max_dx_time:
                _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                          constants.ECON3 + constants.DX + ":" + str(self.inconsistent_date))))
                self.results_publish.append(constants.table_publish_format(self.analysis_name, self.timestamp[-1],
                                                                           (constants.ECON4 + constants.DX),
                                                                           self.inconsistent_date))
                self.clear_data()
                return
            self.excess_oa()
        else:
            self.results_publish.append(constants.table_publish_format(self.analysis_name, current_time,
                                                                       (constants.ECON4 + constants.DX),
                                                                       self.insufficient_data))
            self.clear_data()

    def excess_ouside_air_algorithm(self, oat, rat, mat, oad, econ_condition, cur_time, fan_sp):
        """Perform the excess outside air class algorithm
        oat: float
        rat: float
        mat: float
        oad: float
        econ_condition: float
        cur_time: datetime time delta
        fan_sp: float

        No return
        """
        economizing = self.economizing_check(econ_condition, cur_time)
        if economizing:
            return

        self.oad_values.append(oad)
        self.oat_values.append(oat)
        self.rat_values.append(rat)
        self.mat_values.append(mat)
        self.timestamp.append(cur_time)

        fan_sp = fan_sp / 100.0 if fan_sp is not None else 1.0
        self.fan_spd_values.append(fan_sp)

    def economizer_conditions(self, current_time):
        if len(self.economizing) >= len(self.economizing) * 0.5:
            _log.info(constants.table_log_format(self.analysis_name, current_time,
                                                 (constants.ECON4 + constants.DX + ":" + str(self.economizing_dict))))
            self.results_publish.append(
                constants.table_publish_format(self.analysis_name,
                                               current_time,
                                               (constants.ECON4 + constants.DX),
                                               self.economizing_dict))
            self.clear_data()
            return True
        return False

    def economizing_check(self, econ_condition, cur_time):
        """ Check conditions to see if should be economizing
        econ_conditions: float
        cur_time: datetime time delta
        returns boolean
        """
        if econ_condition:
            _log.info("{}: economizing, for data {} --{}.".format(constants.ECON3, econ_condition, cur_time))
            self.economizing.append(cur_time)
            return True
        return False

    def excess_oa(self):
        """If the detected problems(s) are consistent then generate a fault message(s).
        No return
        """
        energy = 0.0
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_values, self.rat_values, self.mat_values)]
        avg_oaf = mean(oaf) * 100.0
        avg_damper = mean(self.oad_values)
        desired_oaf = self.desired_oaf / 100.0
        diagnostic_msg = {}
        energy_impact = {}

        if avg_oaf < 0 or avg_oaf > 125.0:
            msg = ("{}: Inconclusive result, unexpected OAF value: {}".format(constants.ECON4, avg_oaf))
            _log.info(msg)
            _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (constants.ECON4 + constants.DX + ":" + str(self.invalid_oaf_dict))))
            self.results_publish.append(constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON4 + constants.DX),  self.invalid_oaf_dict))
            self.clear_data()
            return

        avg_oaf = max(0.0, min(100.0, avg_oaf))
        thresholds = zip(self.excess_damper_threshold.items(), self.excess_oaf_threshold.items())
        for (key, damper_thr), (key2, oaf_thr) in thresholds:
            if avg_damper > damper_thr:
                msg = "{}: The OAD should be at the minimum but is significantly higher.".format(constants.ECON4)
                # color_code = "RED"
                result = 32.1
                if avg_oaf - self.desired_oaf > oaf_thr:
                    msg = ("{}: The OAD should be at the minimum for ventilation "
                           "but is significantly above that value. Excess outdoor air is "
                           "being provided; This could significantly increase "
                           "heating and cooling costs".format(constants.ECON4))
                    energy = self.energy_impact_calculation(desired_oaf)
                    result = 34.1
            elif avg_oaf - self.desired_oaf > oaf_thr:
                msg = ("{}: Excess outdoor air is being provided, this could "
                       "increase heating and cooling energy consumption.".format(constants.ECON4))
                # color_code = "RED"
                energy = self.energy_impact_calculation(desired_oaf)
                result = 33.1
            else:
                # color_code = "GREEN"
                msg = ("{}: The calculated OAF is within configured limits.".format(constants.ECON4))
                result = 30.0
                energy = 0.0

            _log.info(msg)
            energy_impact.update({key: energy})
            diagnostic_msg.update({key: result})
        _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (constants.ECON4 + constants.DX + ":" + str(diagnostic_msg))))
        _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (constants.ECON4 + constants.EI + ":" + str(energy_impact))))
        self.results_publish.append(constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON4 + constants.DX),  diagnostic_msg))
        self.results_publish.append(constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON4 + constants.EI), energy_impact))
        self.clear_data()

    def energy_impact_calculation(self, desired_oaf):
        """ Calculate the impact the temperature values have
        desired_oaf: float

        returns float
        """
        ei = 0.0
        energy_calc = [
            (1.08 * spd * self.cfm * (mat - (oat * desired_oaf + (rat * (1.0 - desired_oaf))))) / (1000.0 * self.eer)
            for mat, oat, rat, spd in zip(self.mat_values, self.oat_values, self.rat_values, self.fan_spd_values)
            if (mat - (oat * desired_oaf + (rat * (1.0 - desired_oaf)))) > 0
        ]
        if energy_calc:
            avg_step = (self.timestamp[-1] - self.timestamp[0]).total_seconds() / 60 if len(self.timestamp) > 1 else 1
            dx_time = (len(energy_calc) - 1) * avg_step if len(energy_calc) > 1 else 1.0
            ei = (sum(energy_calc) * 60.0) / (len(energy_calc) * dx_time)
            ei = round(ei, 2)
        return ei

    def clear_data(self):
        """
        Reinitialize data arrays.

        No return
        """
        self.oad_values = []
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.fan_spd_values = []
        self.timestamp = []
        self.economizing = []
