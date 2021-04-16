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


This material was prepared as an account of work sponsored by an
agency of the United States Government.  Neither the United States
Government nor the United States Department of Energy, nor Battelle,
nor any of their employees, nor any jurisdiction or organization
that has cooperated in the development of these materials, makes
any warranty, express or implied, or assumes any legal liability
or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed,
or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or
service by trade name, trademark, manufacturer, or otherwise does
not necessarily constitute or imply its endorsement, recommendation,
r favoring by the United States Government or any agency thereof,
or Battelle Memorial Institute. The views and opinions of authors
expressed herein do not necessarily state or reflect those of the
United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
"""
import datetime
import logging
from datetime import datetime
from dateutil.parser import parse
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import setup_logging
from . import common

DUCT_STC_RCX3 = "No Static Pressure Reset Dx"
SA_TEMP_RCX3 = "No Supply-air Temperature Reset Dx"
SCHED_RCX = "Operational Schedule Dx"
DX = "/diagnostic message"

INCONSISTENT_DATE = -89.2
INSUFFICIENT_DATA = -79.2

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.debug, format="%(asctime)s   %(levelname)-8s %(message)s",
                    datefmt="%m-%d-%y %H:%M:%S")


class SchedResetAIRCx(object):
    """
    Operational schedule, supply-air temperature set point reset, and duct static pressure reset
    AIRCx for AHUs or RTUs.
    """
    def __init__(self):
        self.fan_status_array = []
        self.schedule = {}
        self.stcpr_array = []
        self.schedule_time_array = []
        self.publish_results = None
        self.send_autocorrect_command = None

        self.stcpr_stpt_array = []
        self.sat_stpt_array = []
        self.reset_table_key = None
        self.timestamp_array = []
        self.dx_table = {}

        self.monday_sch = []
        self.tuesday_sch = []
        self.wednesday_sch = []
        self.thursday_sch = []
        self.friday_sch = []
        self.saturday_sch = []
        self.sunday_sch = []

        self.schedule = {}
        self.pre_msg = ""

        # Application thresholds (Configurable)
        self.no_req_data = 0
        self.unocc_time_thr = {}
        self.unocc_stcpr_thr = {}
        self.stcpr_reset_thr = {}
        self.sat_reset_thr = {}

    def set_class_values(self, unocc_time_thr, unocc_stcpr_thr, monday_sch, tuesday_sch, wednesday_sch, thursday_sch,
                         friday_sch, saturday_sch, sunday_sch, no_req_data, stcpr_reset_thr, sat_reset_thr):
        """Set the values needed for doing the diagnostics"""

        def date_parse(dates):
            return [parse(timestamp_array).time() for timestamp_array in dates]

        self.monday_sch = date_parse(monday_sch)
        self.tuesday_sch = date_parse(tuesday_sch)
        self.wednesday_sch = date_parse(wednesday_sch)
        self.thursday_sch = date_parse(thursday_sch)
        self.friday_sch = date_parse(friday_sch)
        self.saturday_sch = date_parse(saturday_sch)
        self.sunday_sch = date_parse(sunday_sch)

        self.schedule = {0: self.monday_sch, 1: self.tuesday_sch,
                         2: self.wednesday_sch, 3: self.thursday_sch,
                         4: self.friday_sch, 5: self.saturday_sch,
                         6: self.sunday_sch}
        self.pre_msg = ("Current time is in the scheduled hours "
                        "unit is operating correctly.")

        # Application thresholds (Configurable)
        self.no_req_data = no_req_data
        self.unocc_time_thr = unocc_time_thr
        self.unocc_stcpr_thr = unocc_stcpr_thr
        self.stcpr_reset_thr = stcpr_reset_thr
        self.sat_reset_thr = sat_reset_thr

    def setup_platform_interfaces(self, publish_method, autocorrect_method):
        self.publish_results = publish_method
        self.send_autocorrect_command = autocorrect_method

    def reinitialize_sched(self):
        """
        Reinitialize schedule data arrays
        :return:
        """
        self.stcpr_array = []
        self.fan_status_array = []
        self.schedule_time_array = []

    def schedule_reset_aircx(self, current_time, stcpr_data, stcpr_stpt_data,
                             sat_stpt_data, current_fan_status):
        """
        Calls Schedule AIRCx and Set Point Reset AIRCx.
        :param current_time:
        :param stcpr_data:
        :param stcpr_stpt_data:
        :param sat_stpt_data:
        :param current_fan_status:
        :param dx_result:
        :return:
        """
        self.sched_aircx(current_time, stcpr_data, current_fan_status)
        self.setpoint_reset_aircx(current_time, current_fan_status, stcpr_stpt_data, sat_stpt_data)
        self.timestamp_array.append(current_time)

    def sched_aircx(self, current_time, stcpr_data, current_fan_status):
        """
        Main function for operation schedule AIRCx - manages data arrays checks AIRCx run status.
        :param current_time:
        :param stcpr_data:
        :param current_fan_status:
        :return:
        """
        schedule = self.schedule[current_time.weekday()]
        run_status = common.check_run_status(self.timestamp_array, current_time, self.no_req_data, run_schedule="daily")

        if run_status is None:
            _log.info("{} - Insufficient data to produce a valid diagnostic result.".format(current_time))
            common.pre_conditions(self.publish_results, INSUFFICIENT_DATA, [SCHED_RCX], current_time)
            self.reinitialize_sched()

        if run_status:
            self.unocc_fan_operation()
            self.reinitialize_sched()

        if current_time.time() < schedule[0] or current_time.time() > schedule[1]:
            self.stcpr_array.extend(stcpr_data)
            self.fan_status_array.append((current_time, current_fan_status))
            self.schedule_time_array.append(current_time)

    def setpoint_reset_aircx(self, current_time, current_fan_status, stcpr_stpt_data, sat_stpt_data):
        """
        Main function for set point reset AIRCx - manages data arrays checks AIRCx run status.
        :param current_time:
        :param current_fan_status:
        :param stcpr_stpt_data:
        :param sat_stpt_data:
        :return:
        """
        stcpr_run_status = common.check_run_status(self.timestamp_array, current_time, self.no_req_data,
                                                   run_schedule="daily", minimum_point_array=self.stcpr_stpt_array)

        if not self.timestamp_array:
            return

        if stcpr_run_status is None:
            _log.info("{} - Insufficient data to produce - {}".format(current_time, DUCT_STC_RCX3))
            common.pre_conditions(self.publish_results, INSUFFICIENT_DATA, [DUCT_STC_RCX3], current_time)
            self.stcpr_stpt_array = []
        elif stcpr_run_status:
            self.no_static_pr_reset()
            self.stcpr_stpt_array = []

        sat_run_status = common.check_run_status(self.timestamp_array, current_time, self.no_req_data,
                                                 run_schedule="daily", minimum_point_array=self.sat_stpt_array)

        if sat_run_status is None:
            _log.info("{} - Insufficient data to produce - {}".format(current_time, SA_TEMP_RCX3))
            common.pre_conditions(self.publish_results, INSUFFICIENT_DATA, [SA_TEMP_RCX3], current_time)
            self.sat_stpt_array = []
            self.timestamp_array = []
        elif sat_run_status:
            self.no_sat_stpt_reset()
            self.sat_stpt_array = []
            self.timestamp_array = []

        if current_fan_status:
            if stcpr_stpt_data:
                self.stcpr_stpt_array.append(mean(stcpr_stpt_data))
            if sat_stpt_data:
                self.sat_stpt_array.append(mean(sat_stpt_data))

    def unocc_fan_operation(self):
        """
        AIRCx to determine if AHU is operating excessively in unoccupied mode.
        :return:
        """
        avg_duct_stcpr = 0
        percent_on = 0
        fan_status_on = [(fan[0].hour, fan[1]) for fan in self.fan_status_array if int(fan[1]) == 1]
        fanstat = [(fan[0].hour, fan[1]) for fan in self.fan_status_array]
        hourly_counter = []
        thresholds = zip(self.unocc_time_thr.items(), self.unocc_stcpr_thr.items())
        diagnostic_msg = {}

        for counter in range(24):
            fan_on_count = [fan_status_time[1] for fan_status_time in fan_status_on if fan_status_time[0] == counter]
            fan_count = [fan_status_time[1] for fan_status_time in fanstat if fan_status_time[0] == counter]
            if len(fan_count):
                hourly_counter.append(fan_on_count.count(1)/len(fan_count)*100)
            else:
                hourly_counter.append(0)

        if self.schedule_time_array:
            if self.fan_status_array:
                percent_on = (len(fan_status_on)/len(self.fan_status_array)) * 100.0
            if self.stcpr_array:
                avg_duct_stcpr = mean(self.stcpr_array)

            for (key, unocc_time_thr), (key2, unocc_stcpr_thr) in thresholds:
                if percent_on > unocc_time_thr:
                    msg = "{} - Supply fan is on during unoccupied times".format(key)
                    result = 63.1
                else:
                    if avg_duct_stcpr < unocc_stcpr_thr:
                        msg = "{} - No problems detected for schedule diagnostic.".format(key)
                        result = 60.0
                    else:
                        msg = ("{} - Fan status show the fan is off but the duct static "
                               "pressure is high, check the functionality of the "
                               "pressure sensor.".format(key))
                        result = 64.2
                diagnostic_msg.update({key: result})
                _log.info(msg)
        else:
            msg = "ALL - No problems detected for schedule diagnostic."
            _log.info(msg)
            diagnostic_msg = {"low": 60.0, "normal": 60.0, "high": 60.0}
        # Error code 64.2 indicates a high static pressure reading when the unit
        # status shows the supply fan is off.  Will not produce hourly result for this
        # case.
        if 64.2 not in list(diagnostic_msg.values()):
            for _hour in range(24):
                diagnostic_msg = {}
                utc_offset = self.timestamp_array[0].isoformat()[-6:]
                push_time = self.timestamp_array[0].date()
                push_time = datetime.combine(push_time, datetime.min.time())
                push_time = push_time.replace(hour=_hour)
                for key, unocc_time_thr in self.unocc_time_thr.items():
                    diagnostic_msg.update({key: 60.0})
                    if hourly_counter[_hour] > unocc_time_thr:
                        diagnostic_msg.update({key: 63.1})
                _log.info(common.table_log_format(push_time, (SCHED_RCX + DX + ':' + str(diagnostic_msg))))
                self.publish_results(push_time, SCHED_RCX + DX, diagnostic_msg)
        else:
            push_time = self.timestamp_array[0]
            _log.info(common.table_log_format(push_time, (SCHED_RCX + DX + ':' + str(diagnostic_msg))))
            self.publish_results(push_time, SCHED_RCX + DX, diagnostic_msg)

    def no_static_pr_reset(self):
        """
        AIRCx  to detect whether a static pressure set point reset is implemented.
        :return:
        """
        diagnostic_msg = {}
        stcpr_daily_range = max(self.stcpr_stpt_array) - min(self.stcpr_stpt_array)
        for sensitivity, stcpr_reset_thr in self.stcpr_reset_thr.items():
            if stcpr_daily_range < stcpr_reset_thr:
                msg = ("{} - No duct static pressure reset detected.".format(sensitivity))
                result = 71.1
            else:
                msg = ("{} - No problems detected for duct static pressure set point "
                       "reset diagnostic.".format(sensitivity))
                result = 70.0
            _log.info(msg)
            diagnostic_msg.update({sensitivity: result})

        _log.info(common.table_log_format(self.timestamp_array[0], (DUCT_STC_RCX3 + DX + ':' + str(diagnostic_msg))))
        self.publish_results(self.timestamp_array[0], DUCT_STC_RCX3 + DX, diagnostic_msg)

    def no_sat_stpt_reset(self):
        """
        AIRCx to detect whether a supply-air temperature set point reset is implemented.
        :return:
        """
        diagnostic_msg = {}
        sat_daily_range = max(self.sat_stpt_array) - min(self.sat_stpt_array)
        for sensitivity, reset_thr in self.sat_reset_thr.items():
            if sat_daily_range < reset_thr:
                msg = "{} - SAT reset was not detected.".format(sensitivity)
                result = 81.1
            else:
                msg = "{} - No problems detected for SAT set point reset diagnostic.".format(sensitivity)
                result = 80.0
            _log.info(msg)
            diagnostic_msg.update({sensitivity: result})

        _log.info(common.table_log_format(self.timestamp_array[0], (SA_TEMP_RCX3 + DX + ':' + str(diagnostic_msg))))
        self.publish_results(self.timestamp_array[0], SA_TEMP_RCX3 + DX, diagnostic_msg)
