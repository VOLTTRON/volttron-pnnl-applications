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
import math
import logging
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import setup_logging
from . import common

INCONSISTENT_DATE = -89.2
INSUFFICIENT_DATA = -79.2
DUCT_STC_RCX = "Duct Static Pressure Set Point Control Loop Dx"
DUCT_STC_RCX1 = "Low Duct Static Pressure Dx"
DUCT_STC_RCX2 = "High Duct Static Pressure Dx"
DX = "/diagnostic message"
DX_LIST = [DUCT_STC_RCX, DUCT_STC_RCX1, DUCT_STC_RCX2]

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.debug, format="%(asctime)s   %(levelname)-8s %(message)s",
                    datefmt="%m-%d-%y %H:%M:%S")


class DuctStaticAIRCx(object):
    """Air-side HVAC Self-Correcting Diagnostic: Detect and correct
    duct static pressure problems.
    """
    def __init__(self):
        # Initialize data arrays
        self.table_key = None
        self.stcpr_stpt_array = []
        self.stcpr_array = []
        self.timestamp_array = []
        self.publish_results = None
        self.send_autocorrect_command = None

        # Initialize configurable thresholds
        self.stcpr_stpt_cname = ""
        self.no_req_data = 0
        self.stpt_deviation_thr = {}
        self.max_stcpr_stpt = 0
        self.stcpr_retuning = 0
        self.zn_high_dmpr_thr = {}
        self.zn_low_dmpr_thr = {}
        self.data_window = 0

        self.auto_correct_flag = False
        self.min_stcpr_stpt = 0
        self.hdzn_dmpr_thr = {}
        self.ls_dmpr_low_avg = []
        self.ls_dmpr_high_avg = []
        self.hs_dmpr_high_avg = []
        self.low_sf_condition = []
        self.high_sf_condition = []
        self.command_tuple = []

    def set_class_values(self, command_tuple, no_req_data,
                         data_window, auto_correct_flag, stpt_deviation_thr,
                         max_stcpr_stpt, stcpr_retuning, zn_high_dmpr_thr,
                         zn_low_dmpr_thr, hdzn_dmpr_thr, min_stcpr_stpt,
                         stcpr_stpt_cname):
        """Set the values needed for doing the diagnostic"""

        # Initialize configurable thresholds
        self.command_tuple = command_tuple
        self.stcpr_stpt_cname = stcpr_stpt_cname
        self.no_req_data = no_req_data
        self.stpt_deviation_thr = stpt_deviation_thr
        self.max_stcpr_stpt = max_stcpr_stpt
        self.stcpr_retuning = stcpr_retuning
        self.zn_high_dmpr_thr = zn_high_dmpr_thr
        self.zn_low_dmpr_thr = zn_low_dmpr_thr
        self.data_window = data_window

        self.auto_correct_flag = False
        if isinstance(auto_correct_flag, str) and auto_correct_flag in ["low", "normal", "high"]:
            self.auto_correct_flag = auto_correct_flag
        self.min_stcpr_stpt = float(min_stcpr_stpt)
        self.hdzn_dmpr_thr = hdzn_dmpr_thr

    def setup_platform_interfaces(self, publish_method, autocorrect_method):
        self.publish_results = publish_method
        self.send_autocorrect_command = autocorrect_method

    def reinitialize(self):
        """
        Reinitialize data arrays.
        :return:
        """
        self.table_key = None
        self.stcpr_stpt_array = []
        self.stcpr_array = []
        self.timestamp_array = []
        self.ls_dmpr_low_avg = []
        self.ls_dmpr_high_avg = []
        self.hs_dmpr_high_avg = []
        self.low_sf_condition = []
        self.high_sf_condition = []

    def stcpr_aircx(self, current_time, stcpr_stpt_data, stcpr_data,
                    zn_dmpr_data, low_sf_cond, high_sf_cond):
        """
        Check duct static pressure AIRCx pre-requisites and manage analysis data set.
        :param current_time:
        :param stcpr_stpt_data:
        :param stcpr_data:
        :param zn_dmpr_data:
        :param low_sf_cond:
        :param high_sf_cond:
        :return:
        """
        if common.check_date(current_time, self.timestamp_array):
            common.pre_conditions(self.publish_results, INCONSISTENT_DATE, DX_LIST, current_time)
            self.reinitialize()

        run_status = common.check_run_status(self.timestamp_array, current_time, self.no_req_data, self.data_window)

        if run_status is None:
            _log.info("{} - Insufficient data to produce a valid diagnostic result.".format(current_time))
            common.pre_conditions(self.publish_results, INSUFFICIENT_DATA, DX_LIST, current_time)
            self.reinitialize()

        if run_status:
            avg_stcpr_stpt, dx_string, dx_msg = common.setpoint_control_check(self.stcpr_stpt_array, self.stcpr_array, self.stpt_deviation_thr, DUCT_STC_RCX)
            self.publish_results(current_time, dx_string, dx_msg)
            self.low_stcpr_aircx(avg_stcpr_stpt)
            self.high_stcpr_aircx(avg_stcpr_stpt)
            self.reinitialize()

        self.stcpr_array.append(mean(stcpr_data))
        if stcpr_stpt_data:
            self.stcpr_stpt_array.append(mean(stcpr_stpt_data))

        zn_dmpr_data.sort(reverse=False)
        self.ls_dmpr_low_avg.extend(zn_dmpr_data[:int(math.ceil(len(zn_dmpr_data) * 0.5)) if len(zn_dmpr_data) != 1 else 1])
        self.ls_dmpr_high_avg.extend(zn_dmpr_data[int(math.ceil(len(zn_dmpr_data) * 0.5)) - 1 if len(zn_dmpr_data) != 1 else 0:])

        zn_dmpr_data.sort(reverse=True)
        self.hs_dmpr_high_avg.extend(zn_dmpr_data[:int(math.ceil(len(zn_dmpr_data) * 0.5)) if len(zn_dmpr_data) != 1 else 1])

        self.low_sf_condition.append(low_sf_cond if low_sf_cond is not None else 0)
        self.high_sf_condition.append(high_sf_cond if high_sf_cond is not None else 0)
        self.timestamp_array.append(current_time)

    def low_stcpr_aircx(self, avg_stcpr_stpt):
        """
        AIRCx to identify and correct low duct static pressure.
        :param avg_stcpr_stpt:
        :return:
        """
        dmpr_low_avg = mean(self.ls_dmpr_low_avg)
        dmpr_high_avg = mean(self.ls_dmpr_high_avg)
        low_sf_condition = True if sum(self.low_sf_condition)/len(self.low_sf_condition) > 0.5 else False
        thresholds = zip(self.zn_high_dmpr_thr.items(), self.zn_low_dmpr_thr.items())
        diagnostic_msg = {}

        for (key, zn_high_dmpr_thr), (key2, zn_low_dmpr_thr) in thresholds:
            if dmpr_high_avg > zn_high_dmpr_thr and dmpr_low_avg > zn_low_dmpr_thr:
                if low_sf_condition is not None and low_sf_condition:
                    msg = "{} - duct static pressure too low. Supply fan at maximum.".format(key)
                    result = 15.1
                elif avg_stcpr_stpt is None:
                    # Create diagnostic message for fault
                    # when duct static pressure set point
                    # is not available.
                    msg = "{} - duct static pressure is too low but set point data is not available.".format(key)
                    result = 14.1
                elif self.auto_correct_flag and self.auto_correct_flag == key:
                    aircx_stcpr_stpt = avg_stcpr_stpt + self.stcpr_retuning
                    if aircx_stcpr_stpt <= self.max_stcpr_stpt:
                        self.send_autocorrect_command(self.stcpr_stpt_cname, aircx_stcpr_stpt)
                        stcpr_stpt = "%s" % float("%.2g" % aircx_stcpr_stpt)
                        stcpr_stpt = stcpr_stpt + " in. w.g."
                        msg = "{} - duct static pressure too low. Set point increased to: {}".format(key,
                                                                                                     stcpr_stpt)
                        result = 11.1
                    else:
                        self.send_autocorrect_command(self.stcpr_stpt_cname, self.max_stcpr_stpt)
                        stcpr_stpt = "%s" % float("%.2g" % self.max_stcpr_stpt)
                        stcpr_stpt = stcpr_stpt + " in. w.g."
                        msg = "{} - duct static pressure too low. Set point increased to max {}.".format(key,
                                                                                                         stcpr_stpt)
                        result = 12.1
                else:
                    msg = "{} - duct static pressure is too low but auto-correction is not enabled.".format(key)
                    result = 13.1
            else:
                msg = "{} - no retuning opportunities detected for Low duct static pressure diagnostic.".format(key)
                result = 10.0
            diagnostic_msg.update({key: result})
            _log.info(msg)

        _log.info(common.table_log_format(self.timestamp_array[-1], (DUCT_STC_RCX1 + DX + ": " + str(diagnostic_msg))))
        self.publish_results(self.timestamp_array[-1], DUCT_STC_RCX1 + DX, diagnostic_msg)

    def high_stcpr_aircx(self, avg_stcpr_stpt):
        """
        AIRCx to identify and correct high duct static pressure.
        :param avg_stcpr_stpt::
        :return:
        """
        high_sf_condition = True if sum(self.high_sf_condition) / len(self.high_sf_condition) > 0.5 else False
        dmpr_high_avg = mean(self.hs_dmpr_high_avg)
        diagnostic_msg = {}

        for key, hdzn_dmpr_thr in self.hdzn_dmpr_thr.items():
            if dmpr_high_avg <= hdzn_dmpr_thr:
                if high_sf_condition is not None and high_sf_condition:
                    msg = "{} - duct static pressure too high. Supply fan at minimum.".format(key)
                    result = 25.1
                elif avg_stcpr_stpt is None:
                    # Create diagnostic message for fault
                    # when duct static pressure set point
                    # is not available.
                    msg = "{} - duct static pressure is too high but set point data is not available.".format(key)
                    result = 24.1
                elif self.auto_correct_flag and self.auto_correct_flag == key:
                    aircx_stcpr_stpt = avg_stcpr_stpt - self.stcpr_retuning
                    if aircx_stcpr_stpt >= self.min_stcpr_stpt:
                        self.send_autocorrect_command(self.stcpr_stpt_cname, aircx_stcpr_stpt)
                        stcpr_stpt = "%s" % float("%.2g" % aircx_stcpr_stpt)
                        stcpr_stpt = stcpr_stpt + " in. w.g."
                        msg = "{} - duct static pressure too high. Set point decreased to: {}".format(key,
                                                                                                      stcpr_stpt)
                        result = 21.1
                    else:
                        self.send_autocorrect_command(self.stcpr_stpt_cname, self.min_stcpr_stpt)
                        stcpr_stpt = "%s" % float("%.2g" % self.min_stcpr_stpt)
                        stcpr_stpt = stcpr_stpt + " in. w.g."
                        msg = "{} - duct static pressure too high. Set point decreased to min {}.".format(key,
                                                                                                          stcpr_stpt)
                        result = 22.1
                else:
                    msg = "{} - duct static pressure is too high but auto-correction is not enabled.".format(key)
                    result = 23.1
            else:
                msg = "{} - No retuning opportunities detected for high duct static pressure diagnostic.".format(key)
                result = 20.0
            diagnostic_msg.update({key: result})
            _log.info(msg)

        _log.info(common.table_log_format(self.timestamp_array[-1], (DUCT_STC_RCX2 + DX + ": " + str(diagnostic_msg))))
        self.publish_results(self.timestamp_array[-1], DUCT_STC_RCX2 + DX, diagnostic_msg)
