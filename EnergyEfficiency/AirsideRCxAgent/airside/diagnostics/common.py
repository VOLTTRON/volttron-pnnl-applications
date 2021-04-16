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

FAN_OFF = -99.3
DUCT_STC_RCX = "Duct Static Pressure Set Point Control Loop Dx"
DUCT_STC_RCX1 = "Low Duct Static Pressure Dx"
DUCT_STC_RCX2 = "High Duct Static Pressure Dx"
DX = "/diagnostic message"
SA_TEMP_RCX = "Supply-air Temperature Set Point Control Loop Dx"
SA_TEMP_RCX1 = "Low Supply-air Temperature Dx"
SA_TEMP_RCX2 = "High Supply-air Temperature Dx"
dx_list = [DUCT_STC_RCX, DUCT_STC_RCX1, DUCT_STC_RCX2, SA_TEMP_RCX, SA_TEMP_RCX1, SA_TEMP_RCX2]
dx_offsets = {SA_TEMP_RCX: 30.0, DUCT_STC_RCX: 0.0}

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.debug, format="%(asctime)s   %(levelname)-8s %(message)s",
                    datefmt="%m-%d-%y %H:%M:%S")


def check_date(current_time, timestamp_array):
    """
    Check current timestamp with previous timestamp to verify that there are no large missing data gaps.
    :param current_time:
    :param timestamp_array:
    :return:
    """
    if not timestamp_array:
        return False
    if current_time.date() != timestamp_array[-1].date():
        if (timestamp_array[-1].date() + td(days=1) != current_time.date() or
                (timestamp_array[-1].hour != 23 and current_time.hour == 0)):
            return True
        return False


def check_run_status(timestamp_array, current_time, no_required_data, minimum_diagnostic_time=None,
                     run_schedule="hourly", minimum_point_array=None):
    """
    The diagnostics run at a regular interval (some minimum elapsed amount of time) and have a
    minimum data count requirement (each time series of data must contain some minimum number of points).
    :param timestamp_array:
    :param current_time:
    :param no_required_data:
    :param minimum_diagnostic_time:
    :param run_schedule:
    :param minimum_point_array:
    :return:
    """
    def minimum_data():
        min_data_array = timestamp_array if minimum_point_array is None else minimum_point_array
        if len(min_data_array) < no_required_data:
            return None
        return True

    if minimum_diagnostic_time is not None and timestamp_array:
        sampling_interval = round(((timestamp_array[-1] - timestamp_array[0]) / len(timestamp_array)).total_seconds() / 60)
        sampling_interval = td(minutes=max(sampling_interval, 1))
        required_time = (timestamp_array[-1] - timestamp_array[0]) + sampling_interval

        if required_time >= minimum_diagnostic_time:
            return minimum_data()
        return False

    if run_schedule == "hourly":
        if timestamp_array and timestamp_array[-1].hour != current_time.hour:
            return minimum_data()
    elif run_schedule == "daily":
        if timestamp_array and timestamp_array[-1].date() != current_time.date():
            return minimum_data()
    return False


def setpoint_control_check(set_point_array, point_array, setpoint_deviation_threshold, dx_name):
    """
    Verify that point if tracking with set point - identify potential control or sensor problems.
    :param set_point_array:
    :param point_array:
    :param allowable_deviation:
    :param dx_name:
    :param dx_offset:
    :param dx_result:
    :return:
    """
    avg_set_point = None
    diagnostic_msg = {}
    for sensitivity, threshold in setpoint_deviation_threshold.items():
        if set_point_array:
            avg_set_point = mean(set_point_array)
            zipper = (set_point_array, point_array)
            set_point_tracking = [abs(x - y) for x, y in zip(*zipper)]
            set_point_error = mean(set_point_tracking)/avg_set_point*100.

            if set_point_error > threshold:
                # color_code = 'red'
                msg = '{} - {}: point deviating significantly from set point.'.format(sensitivity, dx_name)
                result = 1.1 + dx_offsets[dx_name]
            else:
                # color_code = 'green'
                msg = " {} - No problem detected for {} set".format(sensitivity, dx_name)
                result = 0.0 + dx_offsets[dx_name]
        else:
            # color_code = 'grey'
            msg = "{} - {} set point data is not available.".format(sensitivity, dx_name)
            result = 2.2 + dx_offsets[dx_name]
        _log.info(msg)
        diagnostic_msg.update({sensitivity: result})
        diganostic_string = dx_name + DX
    return avg_set_point, diganostic_string, diagnostic_msg


def pre_conditions(results_pub, message, dx_li, cur_time):
    """
    Check for persistence of failure to meet pre-conditions for diagnostics.
    :param message:
    :param dx_list:
    :param analysis:
    :param cur_time:
    :return:
    """
    dx_msg = {"low": message, "normal": message, "high": message}
    for diagnostic in dx_li:
        _log.info(table_log_format(cur_time, (diagnostic + DX + ':' + str(dx_msg))))
        results_pub(cur_time, (diagnostic + DX), dx_msg)


def table_log_format(timestamp, data):
    """ Return a formatted string for use in the log"""
    return str(timestamp) + '->[' + str(data) + ']'


