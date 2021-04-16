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


class InsufficientOutsideAir(object):
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
        self.timestamp = []
        self.max_dx_time = None
        self.analysis_name = ""
        self.results_publish = None

        # Application thresholds (Configurable)
        self.data_window = None
        self.no_required_data = None
        self.ventilation_oaf_threshold = None
        self.desired_oaf = None
        self.invalid_oaf_dict = None
        self.inconsistent_date = None
        self.insufficient_data = None

    def set_class_values(self, analysis_name, results_publish, data_window, no_required_data, desired_oaf):
        """Set the values needed for doing the diagnostics
        analysis_name: string
        data_window: datetime time delta
        no_required_data: integer
        desired_oaf: float

        No return
        """
        self.results_publish = results_publish
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2

        # Application thresholds (Configurable)
        self.data_window = data_window
        self.analysis_name = analysis_name
        self.no_required_data = no_required_data
        self.ventilation_oaf_threshold = {
            "low": desired_oaf*0.75,
            "normal": desired_oaf*0.5,
            "high": desired_oaf*0.25
        }
        self.desired_oaf = desired_oaf
        self.invalid_oaf_dict = {key: 41.2 for key in self.ventilation_oaf_threshold}
        self.inconsistent_date = {key: 44.2 for key in self.ventilation_oaf_threshold}
        self.insufficient_data = {key: 42.2 for key in self.ventilation_oaf_threshold}

    def run_diagnostic(self, current_time):
        if self.timestamp:
            elapsed_time = self.timestamp[-1] - self.timestamp[0]
        else:
            elapsed_time = td(minutes=0)

        if len(self.timestamp) >= self.no_required_data:
            if elapsed_time > self.max_dx_time:
                _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (
                            constants.ECON5 + constants.DX + ":" + str(self.inconsistent_date))))
                self.results_publish.append(constants.table_publish_format(self.analysis_name, self.timestamp[-1],
                                                                           (constants.ECON5 + constants.DX),
                                                                           self.inconsistent_date))
                self.clear_data()
                return
            self.insufficient_oa()
        else:
            self.results_publish.append(constants.table_publish_format(self.analysis_name, current_time,
                                                                       (constants.ECON5 + constants.DX),
                                                                       self.insufficient_data))
            self.clear_data()

    def insufficient_outside_air_algorithm(self, oatemp, ratemp, matemp, cur_time):
        """Perform the insufficient outside air class algorithm
        oatemp: float
        ratemp: float
        matemp: float
        cur_time: datetime time delta

        No return
        """
        self.oat_values.append(oatemp)
        self.rat_values.append(ratemp)
        self.mat_values.append(matemp)
        self.timestamp.append(cur_time)

    def insufficient_oa(self):
        """If the detected problems(s) are consistent then generate a fault message(s).
        No return
        """
        oaf = [(mat - rat) / (oat - rat) for oat, rat, mat in zip(self.oat_values, self.rat_values, self.mat_values)]
        avg_oaf = mean(oaf) * 100.0
        diagnostic_msg = {}

        if avg_oaf < 0 or avg_oaf > 125.0:
            msg = ("{}: Inconclusive result, the OAF calculation led to an "
                   "unexpected value: {}".format(constants.ECON5, avg_oaf))
            _log.info(msg)
            _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (constants.ECON5 + constants.DX + ":" + str(self.invalid_oaf_dict))))
            self.results_publish.append(constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON5 + constants.DX), self.invalid_oaf_dict))
            self.clear_data()
            return

        avg_oaf = max(0.0, min(100.0, avg_oaf))
        for sensitivity, threshold in self.ventilation_oaf_threshold.items():
            if self.desired_oaf - avg_oaf > threshold:
                msg = "{}: Insufficient OA is being provided for ventilation - sensitivity: {}".format(constants.ECON5, sensitivity)
                result = 43.1
            else:
                msg = "{}: The calculated OAF was within acceptable limits - sensitivity: {}".format(constants.ECON5, sensitivity)
                result = 40.0
            _log.info(msg)
            diagnostic_msg.update({sensitivity: result})
        _log.info(constants.table_log_format(self.analysis_name, self.timestamp[-1], (constants.ECON5 + constants.DX + ":" + str(diagnostic_msg))))
        self.results_publish.append(constants.table_publish_format(self.analysis_name, self.timestamp[-1], (constants.ECON5 + constants.DX), diagnostic_msg))

        self.clear_data()

    def clear_data(self):
        """
        Reinitialize data arrays.

        No return
        """
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []
        return
