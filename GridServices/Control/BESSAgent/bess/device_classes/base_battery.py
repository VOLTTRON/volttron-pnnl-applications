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

from bess.base.bess_component import BessComponent
from bess.base.data_point import DataPoint
from aenum import Enum, Flag
from volttron.platform.agent import utils
import logging

utils.setup_logging()
_log = logging.getLogger(__name__)


class UserCommandMode(Enum):
    POWER = 1
    CURRENT = 2


class BaseBattery(BessComponent):
    class ChaSt(Enum):
        OFF = 1
        EMPTY = 2
        DISCHARGING = 3
        CHARGING = 4
        FULL = 5
        HOLDING = 6
        TESTING = 7

    class LocRemCtl(Enum):
        REMOTE = 0
        LOCAL = 1

    class Typ(Enum):
        NOT_APPLICABLE_UNKNOWN = 0
        LEAD_ACID = 1
        NICKEL_METAL_HYDRATE = 2
        NICKEL_CADMIUM = 3
        LITHIUM_ION = 4
        CARBON_ZINC = 5
        ZINC_CHLORIDE = 6
        ALKALINE = 7
        RECHARGEABLE_ALKALINE = 8
        SODIUM_SULFUR = 9
        FLOW = 10
        OTHER = 99

    class State(Enum):
        DISCONNECTED = 1
        INITIALIZING = 2
        CONNECTED = 3
        STANDBY = 4
        SOC_PROTECTION = 5
        FAULT = 99

    class Evt1(Flag):
        """Two register bit field.  40009-40010"""
        COMM_ERROR = 2**0
        OVER_TEMP_ALARM = 2**1
        OVER_TEMP_WARNING = 2**2
        UNDER_TEMP_ALARM = 2**3
        UNDER_TEMP_WARNING = 2**4
        OVER_CHARGE_CURRENT_ALARM = 2**5
        OVER_CHARGE_CURRENT_WARNING = 2**6
        OVER_DISCHARGE_CURRENT_ALARM = 2**7
        OVER_DISCHARGE_CURRENT_WARNING = 2**8
        OVER_VOLT_ALARM = 2**9
        OVER_VOLT_WARNING = 2**10
        UNDER_VOLT_ALARM = 2**11
        UNDER_VOLT_WARNING = 2**12
        UNDER_SOC_MIN_ALARM = 2**13
        UNDER_SOC_MIN_WARNING = 2**14
        OVER_SOC_MAX_ALARM = 2**15
        OVER_SOC_MAXIMUM_WARNING = 2**16
        VOLTAGE_IMBALANCE_WARNING = 2**17
        TEMPERATURE_IMBALANCE_ALARM = 2**18
        TEMPERATURE_IMBALANCE_WARNING = 2**19
        CONTACTOR_ERROR = 2**20
        FAN_ERROR = 2**21
        GROUND_FAULT = 2**22
        OPEN_DOOR_ERROR = 2**23
        CURRENT_IMBALANCE_WARNING = 2**24
        OTHER_BATTERY_ALARM = 2**25
        OTHER_BATTERY_WARNING = 2**26

    class ReqInvState(Enum):
        NO_REQUEST = 0
        START = 1
        STOP = 2

    class SetOp(Enum):
        CONNECT = 1
        DISCONNECT = 2

    class SetInvState(Enum):
        INVERTER_STOPPED = 1
        INVERTER_STANDBY = 2
        INVERTER_STARTED = 3

    def __init__(self):
        super(BaseBattery, self).__init__()

        self.charge_capacity_rating = DataPoint()  # Nameplate charge capacity in amp-hours.
        self.energy_capacity_rating = DataPoint()  # Nameplate energy capacity in DC watt-hours.
        self.w_charge_rate_max = DataPoint()  # Maximum rate of energy transfer into the storage device in DC watts.
        self.w_discharge_rate_max = DataPoint()  # Maximum rate of energy transfer out of the device in DC watts.
        self.discharge_rate = DataPoint()  # Self discharge rate.  Percentage of capacity (WHRtg) discharged per day.
        self.max_soc = DataPoint()  # Manufacturer maximum state of charge, expressed as a percentage.
        self.min_soc = DataPoint()  # Manufacturer minimum state of charge, expressed as a percentage.
        self.max_reserve_soc = DataPoint()  # Setpoint for max reserve for storage as % of the nominal maximum storage.
        self.min_reserve_soc = DataPoint()  # Setpoint for max reserve for storage as % of the nominal maximum storage.
        self.soc = DataPoint()  # State of charge, expressed as a percentage.
        self.dod = DataPoint()  # Depth of discharge, expressed as a percentage.
        self.soh = DataPoint()  # Percentage of battery life remaining.
        self.n_cycles = DataPoint()  # Number of cycles executed in the battery.
        self.charge_status = DataPoint()  # Charge status of storage device. ChaSt enumeration.
        self.local_remote_control = DataPoint()  # BaseBattery control mode. LocRemCtl enumeration.
        self.battery_heartbeat = DataPoint()  # Value is incremented every second with periodic resets to zero.
        self.control_heartbeat = DataPoint()  # Value is incremented every second with periodic resets to zero.
        self.alarm_reset = DataPoint()  # Used to reset any latched alarms.  1 = Reset.
        self.type = DataPoint()  # Type of battery. Enumeration.
        self.state = DataPoint()  # State of the battery bank.  Enumeration.
        self.warranty_date = DataPoint()  # Date the device warranty expires.
        self.event_1 = DataPoint()  # Alarms and warnings.  Evt1 Bit flags.
        self.event_2 = DataPoint()  # Alarms and warnings.  Evt2 Bit flags. (future use)
        self.vendor_event_1 = DataPoint()  # Vendor defined events.
        self.vendor_event_2 = DataPoint()  # Vendor defined events.
        self.voltage = DataPoint()  # DC Bus Voltage.
        self.max_voltage = DataPoint()  # Instantaneous maximum battery voltage.
        self.min_voltage = DataPoint()  # Instantaneous minimum battery voltage.
        self.max_cell_voltage = DataPoint()  # Maximum voltage for all cells in the bank.
        self.max_cell_voltage_string = DataPoint()  # String containing the cell with maximum voltage.
        self.max_cell_voltage_module = DataPoint()  # Module containing the cell with maximum voltage.
        self.min_cell_voltage = DataPoint()  # Minimum voltage for all cells in the bank.
        self.min_cell_voltage_string = DataPoint()  # String containing the cell with minimum voltage.
        self.min_cell_voltage_module = DataPoint()  # Module containing the cell with minimum voltage.
        self.avg_cell_voltage = DataPoint()  # Average cell voltage for all cells in the bank.
        self.current = DataPoint()  # Total DC current flowing to/from the battery bank.
        self.max_charge_current = DataPoint()  # Instantaneous maximum DC charge current.
        self.max_discharge_current = DataPoint()  # Instantaneous maximum DC discharge current.
        self.power = DataPoint()  # Total power flowing to/from the battery bank.
        self.request_inverter_state = DataPoint()  # Request from battery to start/stop the inverter. ReqInvState Enume.
        self.power_request = DataPoint()  # AC Power requested by battery.

        self.set_op = DataPoint()  # Instruct the battery bank to perform an operation.  SetOp Enum.
        self.set_inverter_state = DataPoint()  # Set the current state of the inverter. SetInvState Enum.

        self.point_mapping = {'AHRtg': 'charge_capacity_rating',
                         'WHRtg': 'energy_capacity_rating',
                         'WChaRteMax': 'w_charge_rate_max',
                         'WDisChaRteMax': 'w_discharge_rate_max',
                         'DisChaRte': 'discharge_rate',
                         'SoCMax': 'max_soc',
                         'SoCMin': 'min_soc',
                         'SoCRsvMax': 'max_reserve_soc',
                         'SoCRsvMin': 'min_reserve_soc',
                         'SoC': 'soc',
                         'DoD': 'dod',
                         'SoH': 'soh',
                         'NCyc': 'n_cycles',
                         'ChaSt': 'charge_status',
                         'LocRemCtl': 'local_remote_control',
                         'Hb': 'battery_heartbeat',
                         'CtrlHb': 'control_heartbeat',
                         'AlmRst': 'alarm_reset',
                         'Typ': 'type',
                         'State': 'state',
                         'WarrDt': 'warranty_date',
                         'Evt1': 'event_1',
                         'Evt2': 'event_2',
                         'EvtVnd1': 'vendor_event_1',
                         'EvtVnd2': 'vendor_event_2',
                         'V': 'voltage',
                         'VMax': 'max_voltage',
                         'VMin': 'min_voltage',
                         'CellVMax': 'max_cell_voltage',
                         'CellVMaxStr': 'max_cell_voltage_string',
                         'CellVMaxMod': 'max_cell_voltage_module',
                         'CellVMin': 'min_cell_voltage',
                         'CellVMinStr': 'min_cell_voltage_string',
                         'CellVMinMod': 'min_cell_voltage_module',
                         'CellVAvg': 'avg_cell_voltage',
                         'A': 'current',
                         'AChaMax': 'max_charge_current',
                         'ADisChaMax': 'max_discharge_current',
                         'W': 'power',
                         'ReqInvState': 'request_inverter_state',
                         'ReqW': 'power_request',
                         'SetOp': 'set_op',
                         'SetInvState': 'set_inverter_state'
                         }

    def configure(self, agent, config):
        super(BaseBattery, self).configure(agent, config)

    def connect(self):
        _log.info('CONNECTING Battery.')
        if not self.set_op.set(self.SetOp.CONNECT.value):
            raise Exception('Failed to SetOp on battery to CONNECT.')

    def disconnect(self):
        _log.info('DISCONNECTING Battery.')
        if not self.set_op.set(self.SetOp.DISCONNECT.value):
            raise Exception('Failed to SetOp on battery to DISCONNECT.')

    def reset_faults(self):
        if not self.alarm_reset.set(1):
            raise Exception('Failed to reset alarms on battery.')

    def get_allowed_command(self, charge_mode, user_command_mode):
        bank_voltage = self.voltage.get()
        if charge_mode == 'CHARGE':
            a_max = self.max_charge_current.get()
        elif charge_mode == 'DISCHARGE':
            a_max = self.max_discharge_current.get()
        else:
            raise Exception('Unknown charge_mode: {}.'.format(charge_mode))
        if not a_max or not bank_voltage:
            raise Exception('Failed to get Max Current Rate or Voltage from BaseBattery.')

        # TODO: Use ENUM
        if user_command_mode is 'POWER':
            battery_command_limit = a_max.value * bank_voltage.value
        elif user_command_mode == 'CURRENT':
            battery_command_limit = a_max.value
        else:
            raise Exception('Unknown user command mode in BaseBattery.get_allowed_command.')
        return battery_command_limit

    def check_faults(self):
        # Returns list of string fault names.
        # Collect fault conditions:
        faults = []
        try:
            if self.State(self.state.get().value) == self.State.FAULT:
                faults.append('BATTERY_FAULT_STATE')
        except:
            faults.append('UNKNOWN_BATTERY_FAULT')
        return faults
