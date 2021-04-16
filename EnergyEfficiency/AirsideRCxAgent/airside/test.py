"""
Copyright (c) 20120, Battelle Memorial Institute
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
jurisdiction or organization that has cooperated in th.e development of these
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

"""
File used to unit test Airside
"""
import unittest

from datetime import timedelta as td
from .diagnostics.sat_aircx import SupplyTempAIRCx
from .diagnostics.stcpr_aircx import DuctStaticAIRCx
from .diagnostics.schedule_reset_aircx import SchedResetAIRCx
from .diagnostics import common
from datetime import datetime


class TestDiagnosticsSupplyTempAIRCx(unittest.TestCase):
    """
    Contains all the tests for SupplyTempAIRCx Diagnostic
    """

    def test_temp_sensor_dx_creation(self):
        """test the creation of temp sensor diagnostic class"""
        diagnostic = SupplyTempAIRCx()
        if isinstance(diagnostic, SupplyTempAIRCx):
            assert True
        else:
            assert False

    def test_temp_sensor_dx_set_class_values(self):
        """test the creation of temp sensor diagnostic class"""
        diagnostic = SupplyTempAIRCx()
        data_window = td(minutes=1)
        diagnostic.set_class_values({}, 1, data_window, False, {}, 4.0, 4.0, {}, {}, 2, 3, {}, 5, "test", "test_c", [])
        assert diagnostic.data_window == td(minutes=1)
        assert diagnostic.no_req_data == 1
        assert diagnostic.analysis == "test"
        assert diagnostic.sat_stpt_cname == "test_c"
        assert diagnostic.max_sat_stpt == 5
        assert diagnostic.min_sat_stpt == 2
        assert diagnostic.sat_retuning == 3

    def test_temp_sensor_dx_reinitialize(self):
        """test the creation of temp sensor diagnostic class"""
        diagnostic = SupplyTempAIRCx()
        diagnostic.table_key = "test"
        diagnostic.timestamp_array = "test"
        diagnostic.sat_stpt_array = "test"
        diagnostic.sat_array = "test"
        diagnostic.rht_array = "test"
        diagnostic.percent_rht = "test"
        diagnostic.percent_dmpr ="test"
        diagnostic.reinitialize()
        assert diagnostic.table_key is None
        assert diagnostic.timestamp_array == []
        assert diagnostic.sat_stpt_array == []
        assert diagnostic.sat_array == []
        assert diagnostic.rht_array == []
        assert diagnostic.percent_rht == []
        assert diagnostic.percent_dmpr == []

    def test_temp_sensor_dx_sat_aircx(self):
        """test the sat_aircx method"""
        diagnostic = SupplyTempAIRCx()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(1036)
        diagnostic.set_class_values({}, 1, data_window, False, {}, 4.0, 4.0, {}, {}, 2, 3, {}, 5, "test", "test_c", [])
        diagnostic.sat_aircx(cur_time, [4.0], [4.0], [4.0], [4.0])
        assert diagnostic.results_publish == []
        assert diagnostic.sat_array[0] == 4.0
        assert diagnostic.rht_array[0] == 4.0
        assert diagnostic.timestamp_array[0] == cur_time

    def test_temp_sensor_dx_low_sat(self):
        """test the clow_sat method"""
        diagnostic = SupplyTempAIRCx()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(1036)
        diagnostic.set_class_values({}, 1, data_window, False, {}, 4.0, 4.0, {}, {}, 2, 3, {}, 5, "test", "test_c", [])
        diagnostic.sat_aircx(cur_time, [4.0], [4.0], [4.0], [4.0])
        diagnostic.low_sat(4.0)
        assert diagnostic.results_publish == [['test&1969-12-31 19:17:16', ['Low Supply-air Temperature Dx/diagnostic message: ', '{}']]]
        assert diagnostic.sat_array[0] == 4.0
        assert diagnostic.rht_array[0] == 4.0
        assert diagnostic.timestamp_array[0] == cur_time

    def test_temp_sensor_dx_high_sat(self):
        """test the high sat method"""
        diagnostic = SupplyTempAIRCx()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(1036)
        diagnostic.set_class_values({}, 1, data_window, False, {}, 4.0, 4.0, {}, {}, 2, 3, {}, 5, "test", "test_c", [])
        diagnostic.sat_aircx(cur_time, [4.0], [4.0], [4.0], [4.0])
        diagnostic.high_sat(4.0)
        assert diagnostic.results_publish == [['test&1969-12-31 19:17:16', ['High Supply-air Temperature Dx/diagnostic message: ', '{}']]]
        assert diagnostic.sat_array[0] == 4.0
        assert diagnostic.rht_array[0] == 4.0
        assert diagnostic.timestamp_array[0] == cur_time

class TestDiagnosticsDuctStaticAIRCx(unittest.TestCase):
    """
    Contains all the tests for DuctStaticAIRCx Diagnostic
    """

    def test_duct_static_dx_creation(self):
        """test the creation of duct static diagnostic class"""
        diagnostic = DuctStaticAIRCx()
        if isinstance(diagnostic, DuctStaticAIRCx):
            assert True
        else:
            assert False

    def test_duct_static_dx_set_class_values(self):
        """test the creation of duct static diagnostic class"""
        diagnostic = DuctStaticAIRCx()
        data_window = td(minutes=1)
        diagnostic.set_class_values({}, 1, data_window, False, {}, 4.0, 4.0, {}, {}, {}, 3, "test", "test_c", [])
        assert diagnostic.data_window == td(minutes=1)
        assert diagnostic.no_req_data == 1
        assert diagnostic.analysis == "test"
        assert diagnostic.stcpr_stpt_cname == "test_c"
        assert diagnostic.max_stcpr_stpt == 4.0
        assert diagnostic.min_stcpr_stpt == 3.0
        assert diagnostic.stcpr_retuning == 4.0

    def test_duct_static_dx_reinitialize(self):
        """test the creation of duct static diagnostic class"""
        diagnostic = DuctStaticAIRCx()
        diagnostic.table_key = "test"
        diagnostic.timestamp_array = "test"
        diagnostic.stcpr_stpt_array = "test"
        diagnostic.stcpr_array = "test"
        diagnostic.ls_dmpr_low_avg = "test"
        diagnostic.ls_dmpr_high_avg = "test"
        diagnostic.hs_dmpr_high_avg ="test"
        diagnostic.low_sf_condition = "test"
        diagnostic.high_sf_condition = "test"
        diagnostic.reinitialize()
        assert diagnostic.table_key is None
        assert diagnostic.timestamp_array == []
        assert diagnostic.stcpr_stpt_array == []
        assert diagnostic.stcpr_array == []
        assert diagnostic.ls_dmpr_low_avg == []
        assert diagnostic.ls_dmpr_high_avg == []
        assert diagnostic.hs_dmpr_high_avg == []
        assert diagnostic.low_sf_condition == []
        assert diagnostic.high_sf_condition == []

    def test_duct_static_dx_stcpr_aircx(self):
        """test the sat_aircx method"""
        diagnostic = DuctStaticAIRCx()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(1036)
        diagnostic.set_class_values({}, 1, data_window, False, {}, 4.0, 4.0, {}, {}, {}, 3, "test", "test_c", [])
        diagnostic.stcpr_aircx(cur_time, [4.0], [4.0], [4.0], 1, 1)
        assert diagnostic.results_publish == []
        assert diagnostic.low_sf_condition[0] == 1
        assert diagnostic.high_sf_condition[0] == 1
        assert diagnostic.timestamp_array[0] == cur_time

    def test_duct_static_dx_low_sat(self):
        """test the clow_sat method"""
        diagnostic = DuctStaticAIRCx()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(1036)
        diagnostic.set_class_values({}, 1, data_window, False, {}, 4.0, 4.0, {}, {}, {}, 3, "test", "test_c", [])
        diagnostic.stcpr_aircx(cur_time, [4.0], [4.0], [4.0], 1, 1)
        diagnostic.low_stcpr_aircx(4.0)
        assert diagnostic.results_publish == [['test&1969-12-31 19:17:16', ['Low Duct Static Pressure Dx/diagnostic message: ', '{}']]]
        assert diagnostic.timestamp_array[0] == cur_time
        assert diagnostic.command_tuple == {}

    def test_duct_static_dx_high_sat(self):
        """test the high sat method"""
        diagnostic = DuctStaticAIRCx()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(1036)
        diagnostic.set_class_values({}, 1, data_window, False, {}, 4.0, 4.0, {}, {}, {}, 3, "test", "test_c", [])
        diagnostic.stcpr_aircx(cur_time, [4.0], [4.0], [4.0], 1, 1)
        diagnostic.high_stcpr_aircx(4.0)
        assert diagnostic.results_publish == [['test&1969-12-31 19:17:16', ['High Duct Static Pressure Dx/diagnostic message: ', '{}']]]
        assert diagnostic.timestamp_array[0] == cur_time
        assert diagnostic.command_tuple == {}

class TestDiagnosticsScheduleResetAIRCx(unittest.TestCase):
    """
    Contains all the tests for SchedResetAIRCx Diagnostic
    """

    def test_schedule_reset_dx_creation(self):
        """test the creation of schedule reset diagnostic class"""
        diagnostic = SchedResetAIRCx()
        if isinstance(diagnostic, SchedResetAIRCx):
            assert True
        else:
            assert False

    def test_duct_static_dx_set_class_values(self):
        """test the creation of schedule reset diagnostic class"""
        diagnostic = SchedResetAIRCx()
        diagnostic.set_class_values({1.0}, {2.0}, {}, {}, {}, {}, {}, {}, {}, 1, {3.0}, {4.0}, "test", [])
        assert diagnostic.no_req_data == 1
        assert diagnostic.analysis == "test"
        assert diagnostic.unocc_time_thr == {1.0}
        assert diagnostic.unocc_stcpr_thr == {2.0}
        assert diagnostic.stcpr_reset_thr == {3.0}
        assert diagnostic.sat_reset_thr == {4.0}
        assert diagnostic.monday_sch == []

    def test_temp_sensor_dx_reinitialize(self):
        """test the creation of schedule reset reinitialize"""
        diagnostic = SchedResetAIRCx()
        diagnostic.stcpr_array = "test"
        diagnostic.fan_status_array = "test"
        diagnostic.schedule_time_array = "test"
        diagnostic.reinitialize_sched()
        assert diagnostic.stcpr_array == []
        assert diagnostic.fan_status_array == []
        assert diagnostic.schedule_time_array == []

    def test_temp_sensor_dx_schedule_reset(self):
        """test the creation of schedule reset """
        diagnostic = SchedResetAIRCx()
        diagnostic.set_class_values({1.0}, {2.0}, ["0:00", "23:59"], ["0:00", "23:59"], ["0:00", "23:59"], ["0:00", "23:59"], ["0:00", "23:59"], ["0:00", "23:59"], ["0:00", "23:59"], 1, {3.0}, {4.0}, "test", [])
        cur_time = datetime.fromtimestamp(1036)
        diagnostic.schedule_reset_aircx(cur_time, [4.0], [5.0], [6.0], 1)
        assert diagnostic.results_publish == []
        assert diagnostic.timestamp_array[0] == cur_time
        assert diagnostic.fan_status_array == []
        assert diagnostic.schedule_time_array == []


class TestDiagnosticsCommon(unittest.TestCase):
    """
    Contains all the tests for common Diagnostic
    """

    def test_common_check_date(self):
        """test the common check date"""
        cur_time = datetime.fromtimestamp(1036)
        timestamp_array = []
        response = common.check_date(cur_time, timestamp_array)
        assert response is False

    def test_common_check_run_status(self):
        """test the common check run status"""
        cur_time = datetime.fromtimestamp(1036)
        timestamp_array = []
        response = common.check_run_status(timestamp_array, cur_time, 1, None, "hourly", None)
        assert response is False

    def test_common_setpoint_control_check(self):
        """test the common check setpoint control"""
        thr_dict = {
            "low": 1 * 1.5,
            "normal": 1,
            "high": 1 * 0.5
        }
        avg, dx_string, dx_msg = common.setpoint_control_check([1, 2, 3], [1, 2, 3], thr_dict, "test dx", 0)
        assert avg == 2.0
        assert dx_string == "test dx/diagnostic message: "
        assert dx_msg == "{'low': 0.0, 'normal': 0.0, 'high': 0.0}"

    def test_common_pre_conditions(self):
        """test the common pre conditions"""
        results_publish = []
        message = "test"
        dx_li = ["d1", "d2"]
        analysis = "test_analysis"
        cur_time = datetime.fromtimestamp(1036)
        common.pre_conditions(results_publish, message, dx_li, analysis, cur_time)
        assert len(results_publish) == 2
        assert results_publish[0][0] == "test_analysis&1969-12-31 19:17:16"
        assert results_publish[0][1] == ['d1/diagnostic message:', "{'low': 'test', 'normal': 'test', 'high': 'test'}"]
        assert results_publish[1][0] == "test_analysis&1969-12-31 19:17:16"
        assert results_publish[1][1] == ['d2/diagnostic message:', "{'low': 'test', 'normal': 'test', 'high': 'test'}"]

