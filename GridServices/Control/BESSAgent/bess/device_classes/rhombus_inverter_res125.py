# Copyright 2019 The University of Toledo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from bess.base.data_point import DataPoint
from inverter import Inverter
from datetime import timedelta
from volttron.platform.agent import utils
from datetime import datetime
from aenum import Enum, Flag
import pytz
import logging

utils.setup_logging()
_log = logging.getLogger(__name__)


class RhombusInverterRes125(Inverter):
    class OpMode(Enum):
        CONSTANT_POWER = 1
        CONSTANT_CURRENT = 2
        STOP_INVERTER = 0
        SWITCH_OFF = 111  # TODO: Should this be HEX?
        SWITCH_ON = 222  # TODO: Should this be HEX?
        RESET_UNIT = 61440

    class InverterCommandMode(Enum):
        POWER = 1
        CURRENT = 2

    # TODO: Is this correct? The documentation is very lacking.  Could be bits, is labelled unit16 but values on/off
    class UnitStatus(Enum):
        POWER_ON_CONTROLLERS = 1
        DISCONNECTED = 2
        CONNECTING = 3
        CONSTANT_CURRENT_MODE = 4
        CONSTANT_POWER_MODE = 5
        CONSTANT_VOLTAGE_MODE = 6
        POWER_OFF_CONTROLLERS = 7
        FAULT_SHUTDOWN = 8
        SERVICE_REQUIRED = 9
        MAINTENANCE = 10
        MAINTENANCE_SHUTDOWN = 11


    class CIUFaultSummary(Flag):
        CRITICAL_MOD_COMMUNICATION_ERROR = 2**0
        KEY_FAULT = 2**1
        CONTROL_VALUE_NOT_RECEIVED = 2**2
        MODBUS_COMM_FAILURE = 2**3
        CONTROLLER_MODE_ERROR = 2**4
        OVERTEMP_SHUTDOWN = 2**5
        CIU_FAULTED = 2**6
        PROTECTION_SHUTDOWN = 2**7
        EPO_SHUTDOWN = 2**8
        LVPS_LOW_FAULT = 2**13
        LOW_BATTERY_FAULT = 2**14
        AMBIENT_TEMP_OUT_OF_RANGE = 2**15
        
    class MIU1FaultSummary(Flag):
        PHASE_OUT_U_VOLTAGE = 2**0
        PHASE_OUT_O_VOLTAGE = 2**1
        CPLATE_OVERTEMP_SD = 2**2
        DC_LINK_OVERVOLTAGE_SD = 2**3
        DC_LINK_O_VOLTAGE_SD = 2**4
        DC_BUS_HW_FAULT_SD = 2**5
        M2_UNIT_PHASE_C_SD = 2**6
        EPC_M_SOFTWARE_OVERFLOW = 2**7
        UNIT_RESPONSE_T_O = 2**8
        CURRENT_LIMIT_TIME = 2**9
        CRIT_MOD_COMMUNICATION_ERROR = 2**10
        OFFSET_IR_SHUTDOWN = 2**11
        OFFSET_IS_SHUTDOWN = 2**12
        K1_FAILURE_TO_CLOSE = 2**13
        K1_WELDED = 2**14
        EPO_SHUTDOWN = 2**15

    class MIU2FaultSummary(Flag):
        CP_TEMPERATURE_SENSOR_FAULT = 2**0
        UNEXPECTED_DC_BUS = 2**1
        M2_UNIT_PH_A_SHUTDOWN = 2**2
        DC_LINK_OVERVOLTAGE_SD = 2**3
        THERMAL_OVERLOAD_SD = 2**4
        HSTEMP_SENSE_DISCLOSE_SD = 2**5
        NO_COOLANT_SUSPECT_SD = 2**6
        DC_POLARITY_REVERSE_SD = 2**8
        DC_BUS_REVERSE_POWER_SD = 2**9
        PRECHARGE_FAIL_SD = 2**13
        DC_CONTACT_WELDED_SD = 2**14
        DC_CONTACT_OPEN_SD = 2**15

    class MIU3FaultSummary(Flag):
        FLASH_CHECKSUM = 2**0
        WRONG_VOLTAGE_AT_START = 2**1
        SINGLE_PHASE_OPEN = 2**2
        SYNC_ERROR_TIME_OUT_SHUT = 2**3
        GRID_PHASE_SEQ_REVERSED = 2**4
        INVERTER_UNDERFREQUENCY = 2**5
        INVERTER_OVERFREQUENCY = 2**6
        LCA_GDRIVE_HW_FAULT = 2**7
        SW_OVER_CURRENT = 2**8
        ENCLOSURE_DOOR_OPEN_FAULT = 2**9
        COOLANT_FLOW_LOSS_SHUTDOWN = 2**10
        PROGRAM_CONFIG_INVALID = 2**11
        POWER_SUPPLY_RANGE_FAULT = 2**13
        EXTERNAL_AD_A = 2**14
        EXTERNAL_AD_B = 2**15

    class MIU4FaultSummary(Flag):
        LCAO_CURRENT_SHUTDOWN = 2**0
        DEADTIME_SD = 2**1
        LCA_DCLINK_OVERVOLTAGE_SD = 2**2
        O_CURRENT_SHORT_SD = 2**3
        LCA_CNEG_FAULTED_SD = 2**4
        LCA_CPOS_FAULTED_SD = 2**5
        LCA_BNEG_FAULTED_SD = 2**6
        LCA_BPOS_FAULTED_SD = 2**7
        LCA_ANEG_FAULTED_SD = 2**8
        LCA_APOS_FAULTED_SD = 2**9
        LCAO_CUR_EARLY_SD = 2**10
        LCA_GROUND_FAULT_SD = 2**11
        LCA_CPLT_O_TEMP_SD = 2**12
        LCA_CPLT_U_TEMP_SD = 2**13
        M2_UNIT_FAILURE_SD = 2**14
        DC_BUS_V_OOR_SD = 2**15
        
    class Warnings(Flag):
        DC_AUX_CONTACT_WELD = 2**0
        PHASE_OUT_UV = 2**1
        POWER_LIMIT_HIT = 2**3
        GRID_OVERVOLTAGE = 2**4
        GRID_UNDERVOLTAGE = 2**5
        GRID_OVERFREQUENCY = 2**6
        GRID_UNDERFREQUENCY = 2**7
        OVER_CURRENT_SHORT = 2**8
        OVER_CURRENT = 2**9
        PHASE_OUT_OV = 2**10
        INVERTER_OVER_FREQUENCY = 2**11
        INVERTER_UNDER_FREQUENCY = 2**12
        TOO_COLD = 2**13
        COLD_PLATE_OVERTEMP = 2**14
        EEPROM_BAD = 2**15


    def __init__(self):
        super(RhombusInverterRes125, self).__init__()
        # Configuration settings.
        self.inverter_heartbeat_warning_time = timedelta(seconds=60)
        self.initial_inverter_heartbeat_count = 931
        self.inverter_heartbeat_count_limit = 750
        self.security_code_value = 125
        self.max_inverter_command = 125
        self.inverter_command_mode = self.InverterCommandMode.POWER

        # Data Points:
        self.ambient_temperature = DataPoint()
        self.auto_transition = DataPoint()
        self.ciu_fault_summary = DataPoint()
        self.connect_type = DataPoint()
        self.dc_input_voltage = DataPoint()
        self.dc_link_voltage = DataPoint()
        self.dc_link_voltage_current_power = DataPoint()
        self.grid_frequency = DataPoint()
        self.grid_off_standalone_on = DataPoint()
        self.heartbeat = DataPoint()
        self.heatsink_temperature = DataPoint()
        self.kdcac1 = DataPoint()
        self.miu_f1_summary = DataPoint()
        self.miu_f2_summary = DataPoint()
        self.miu_f3_summary = DataPoint()
        self.miu_f4_summary = DataPoint()
        self.max_power_command = DataPoint()
        self.modbus_heartbeat = DataPoint()
        self.op_mode = DataPoint() # TODO: Is this same as PCSSetOperation, operating_state, vendor operating state?
        self.over_frequency_limit_1 = DataPoint()
        self.over_frequency_standalone = DataPoint()
        self.over_frequency_trip_time_condition_1 = DataPoint()
        self.over_voltage_limit_1 = DataPoint()
        self.over_voltage_limit_2 = DataPoint()
        self.over_voltage_stand_alone = DataPoint()
        self.over_voltage_trip_time_condition_1 = DataPoint()
        self.over_voltage_trip_time_condition_2 = DataPoint()
        self.phase_a_grid_voltage_rms = DataPoint()
        self.phase_b_grid_voltage_rms = DataPoint()
        self.phase_c_grid_voltage_rms = DataPoint()
        self.power_factor_offset = DataPoint()
        self.random_number = DataPoint()
        self.raw_dc_current = DataPoint()
        self.raw_dc_link_power = DataPoint()
        self.raw_grid_ac_power = DataPoint()
        self.raw_phase_a_grid_current_rms = DataPoint()
        self.raw_phase_b_grid_current_rms = DataPoint()
        self.raw_phase_c_grid_current_rms = DataPoint()
        self.reconnect_delay = DataPoint()
        self.security_code = DataPoint()
        self.shutdowns = DataPoint()
        self.system_controller_status = DataPoint()
        self.total_hours_of_operation_1 = DataPoint()
        self.total_hours_of_operation_2 = DataPoint()
        self.under_frequency_limit_1 = DataPoint()
        self.under_frequency_standalone = DataPoint()
        self.under_frequency_trip_time_condition_1 = DataPoint()
        self.under_frequency_trip_time_condition_2 = DataPoint()
        self.under_voltage_limit_1 = DataPoint()
        self.under_voltage_limit_2 = DataPoint()
        self.under_voltage_stand_alone = DataPoint()
        self.under_voltage_trip_time_condition_1 = DataPoint()
        self.under_voltage_trip_time_condition_2 = DataPoint()
        self.unit_status = DataPoint()
        self.warnings = DataPoint()

        self.point_mapping = {
            'AmbientTemperature': 'ambient_temperature',
            'AutoTransition': 'auto_transition',
            'CIUFaultSummary': 'ciu_fault_summary',
            'ConnectType': 'connect_type',
            'DCInputVoltage': 'dc_input_voltage',
            'DCLinkVoltage': 'dc_link_voltage',
            'DCLinkVoltageCurrentPower': 'dc_link_voltage_current_power',
            'GridFrequency': 'grid_frequency',
            'GridOffStandaloneOn': 'grid_off_standalone_on',
            'Heartbeat': 'heartbeat',
            'HeatSinkTemperature': 'heatsink_temperature',
            'KDCAC1': 'kdcac1',
            'MIUF1Summary': 'miu_f1_summary',
            'MIUF2Summary': 'miu_f2_summary',
            'MIUF3Summary': 'miu_f3_summary',
            'MIUF4Summary': 'miu_f4_summary',
            'MaxPowerCommand': 'max_power_command',
            'ModbusHeartbeat': 'modbus_heartbeat',
            'OpMode': 'op_mode',
            'OverFrequencyLimit1': 'over_frequency_limit_1',
            'OverFrequencyStandalone': 'over_frequency_standalone',
            'OverFrequencyTripTimeCondition1': 'over_frequency_trip_time_condition_1',
            'OverVoltageLimit1': 'over_voltage_limit_1',
            'OverVoltageLimit2': 'over_voltage_limit_2',
            'OverVoltageStandalone': 'over_voltage_stand_alone',
            'OverVoltageTripTimeCondition1': 'over_voltage_trip_time_condition_1',
            'OverVoltageTripTimeCondition2': 'over_voltage_trip_time_condition_2',
            'PhaseAGridVoltageRMS': 'phase_a_grid_voltage_rms',
            'PhaseBGridVoltageRMS': 'phase_b_grid_voltage_rms',
            'PhaseCGridVoltageRMS': 'phase_c_grid_voltage_rms',
            'PowerFactorOffset': 'power_factor_offset',
            'RandomNumber': 'random_number',
            'RawDCCurrent': 'raw_dc_current',
            'RawDCLinkPower': 'raw_dc_link_power',
            'RawGridACPower': 'raw_grid_ac_power',
            'RawPhaseAGridCurrentRMS': 'raw_phase_a_grid_current_rms',
            'RawPhaseBGridCurrentRMS': 'raw_phase_b_grid_current_rms',
            'RawPhaseCGridCurrentRMS': 'raw_phase_c_grid_current_rms',
            'ReconnectDelay': 'reconnect_delay',
            'SecurityCode': 'security_code',
            'Shutdowns': 'shutdowns',
            'SystemControllerStatus': 'system_controller_status',
            'TotalHoursOfOperation1': 'total_hours_of_operation_1',
            'TotalHoursOfOperation2': 'total_hours_of_operation_2',
            'UnderFrequencyLimit1': 'under_frequency_limit_1',
            'UnderFrequencyStandalone': 'under_frequency_standalone',
            'UnderFrequencyTripTimeCondition1': 'under_frequency_trip_time_condition_1',
            'UnderFrequencyTripTimeCondition2': 'under_frequency_trip_time_condition_2',
            'UnderVoltageLimit1': 'under_voltage_limit_1',
            'UnderVoltageLimit2': 'under_voltage_limit_2',
            'UnderVoltageStandalone': 'under_voltage_stand_alone',
            'UnderVoltageTripTimeCondition1': 'under_voltage_trip_time_condition_1',
            'UnderVoltageTripTimeCondition2': 'under_voltage_trip_time_condition_2',
            'UnitStatus': 'unit_status',
            'Warnings': 'warnings'
        }

        # Monitor:
        self.inverter_heartbeat_greenlet = None
        self.inverter_heartbeat_monitor_timer = None

    def configure(self, agent, config):
        super(RhombusInverterRes125, self).configure(agent, config)

        try:
            self.inverter_heartbeat_warning_time = float(config.get('inverter_heartbeat_warning_time',
                                                                    self.inverter_heartbeat_warning_time))
            if not self.inverter_heartbeat_warning_time > 0:
                raise ValueError('INVERTER HEARTBEAT WARNING TIME MUST BE POSITIVE')
            self.initial_inverter_heartbeat_count = int(config.get('initial_inverter_heartbeat_count',
                                                        self.initial_inverter_heartbeat_count))
            self.inverter_heartbeat_count_limit = int(config.get('inverter_heartbeat_count_limit',
                                                                 self.inverter_heartbeat_count_limit))
            if not all(count > 0 for count in [self.initial_inverter_heartbeat_count,
                                               self.inverter_heartbeat_count_limit]):
                raise ValueError('INVERTER HEARTBEAT COUNTS MUST BE POSITIVE')

            self.security_code_value = int(config.get('inverter_security_code', self.security_code_value))
            self.max_inverter_command = float(config.get('max_inverter_command', self.max_inverter_command))
            if not self.max_inverter_command > 0:
                raise ValueError('MAX INVERTER COMMAND MUST BE POSITIVE')
            self.inverter_heartbeat_check_interval = int(config.get('inverter_heartbeat_check_interval',
                                                                    self.inverter_heartbeat_check_interval))
            if not self.inverter_heartbeat_check_interval > 0:
                raise ValueError('INTERVALS MUST BE POSITIVE')
            try:
                self.inverter_command_mode = self.InverterCommandMode[config.get('inverter_command_mode',
                                                                                 self.inverter_command_mode.name)]
            except KeyError:
                raise ValueError('INVERTER COMMAND MODE MUST BE "POWER" OR "CURRENT"')
        except ValueError as e:
            _log.error("ERROR PROCESSING RHOMBUS INVERTER CONFIGURATION: {}".format(e))

    def initialize(self):
        # Unlock write on inverter.
        if not self.security_code.set(self.security_code_value):
            raise Exception('Failed to set security code to initialize inverter.')

    def start(self):
        if not self.op_mode.set(self.OpMode.CONSTANT_POWER.value):
            raise Exception('Failed to set Inverter to CONSTANT_POWER mode.')

    def stop(self):
        _log.info('Setting Inverter OpMode to STOP_INVERTER')
        if self.op_mode.set(self.OpMode.STOP_INVERTER.value) != 0:
            _log.error('Failed to stop Inverter while STOPPING.')

    def is_started(self):
        op_mode = self.op_mode.get()
        if op_mode in [self.OpMode.CONSTANT_POWER, self.OpMode.CONSTANT_CURRENT]:
            return True
        else:
            return False

    def manage_inverter_heartbeat(self):
        """Track inverter heartbeat value and adjust as needed.

        Inverter will count down heartbeat from a set value, with a reduction of one per beat, where each beat is 100ms.
        This will track the heartbeat. When it is below self.inverter_heartbeat_count_limit,
        this function will set it to self.initial_inverter_heartbeat_count."""

        inverter_heartbeat_reading = self.inverter_heartbeat.get()
        if inverter_heartbeat_reading and inverter_heartbeat_reading <= self.inverter_heartbeat_count_limit:
                if not self.inverter_heartbeat.set(self.initial_inverter_heartbeat_count):
                    _log.warning('Failed to reset Inverter Heartbeat.')
        else:
            now = datetime.now(pytz.utc).astimezone(self.agent.tz)
            if not self.inverter_heartbeat_monitor_timer:
                self.inverter_heartbeat_monitor_timer = now
            elif now - self.inverter_heartbeat_monitor_timer > self.inverter_heartbeat_warning_time:
                _log.warning('Unable to read inverter heartbeat in inverter_heartbeat_max_time: ({} seconds)'.format(
                    self.inverter_heartbeat_warning_time.total_seconds))
                self.inverter_heartbeat_monitor_timer = now

    def command_power(self, power):
        _log.info('Setting Inverter MaxPowerCommand to {}'.format(power))
        max_power_command_success = self.max_power_command.set(power)
        # TODO: Should we accept certain types of different response, say if it accepts a lesser value?
        if max_power_command_success != power:
            raise Exception('Failed to set Inverter MaxPowerCommand to {}. Received {}'.format(
                power, max_power_command_success))
        return max_power_command_success

    def command_current(self, current):
        raise NotImplementedError('RhombusInverter.command_current() is not implemented.')
        # TODO: Implement: Return accepted current.

    def reset_faults(self):
        if not self.op_mode.set(self.OpMode.RESET_UNIT.value):
            raise Exception('Failed to reset alarms on inverter.')

    def get_allowed_command(self, charge_mode, user_command_mode):
        if user_command_mode == 'POWER':
            return self.max_inverter_command
        else:
            raise NotImplementedError('RhombusInverter.get_allowed_command does not implement command_mode: {}.'.format(
                charge_mode))

    # TODO: JCI indicates that PF control is open loop.  How should this be managed using meter reading?
    # TODO: JCI uses scale factor of 100 and -0.5 to 0.5 limits, but the Rhombus manual shows same limits with +or- 25
    # TODO: as the command which would be scale factor of 50.
    def set_pf_command(self, pf):
        """Set power factor in inverter after restricting to limit of 60 degrees. Returns approved power factor."""
        # Curtail Power Factor to Natural Limits
        if -0.5 > pf:
            approved_pf = -0.5
        elif 0.5 < pf:
            approved_pf = 0.5
        else:
            approved_pf = pf
        _log.info('Requested power factor offset: {}. Setting to: {}'.format(pf, approved_pf))

        # Write Power Factor Command.
        accepted_pf = self.power_factor_offset.set(approved_pf)
        # TODO: Look into whether volttron modbus tk driver actually returns a value from modbus set or value passed.
        if accepted_pf is False:
            raise Exception('Failed to set PowerFactorOffset.')
        return accepted_pf

    def check_faults(self):
        # Collect fault conditions:
        faults = []
        try:
            ciu = self.ciu_fault_summary.get().value
            if ciu:
                faults.extend([fault.name for fault in self.CIUFaultSummary(ciu)])
            miu1 = self.miu_f1_summary.get().value
            if miu1:
                faults.extend([fault.name for fault in self.MIU1FaultSummary(miu1)])
            miu2 = self.miu_f2_summary.get().value
            if miu2:
                faults.extend([fault.name for fault in self.MIU2FaultSummary(miu2)])
            miu3 = self.miu_f3_summary.get().value
            if miu3:
                faults.extend([fault.name for fault in self.MIU3FaultSummary(miu3)])
            miu4 = self.miu_f4_summary.get().value
            if miu4:
                faults.extend([fault.name for fault in self.MIU4FaultSummary(miu4)])
            standalone_on = self.grid_off_standalone_on.get().value
            if standalone_on:
                faults.append('GRID_STANDALONE_ON')
            auto_transition_on = self.auto_transition.get().value
            if auto_transition_on:
                faults.append('AUTO_TRANSITION_ON')
        except Exception as e:
            faults.append('UNKNOWN_INVERTER_FAULT')
        return faults
