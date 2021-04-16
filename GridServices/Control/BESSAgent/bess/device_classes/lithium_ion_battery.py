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
from base_battery import BaseBattery
from aenum import Enum, Flag


class LithiumIonCell(BessComponent):
    class St(Flag):
        CELL_IS_BALANCING = 2 ** 0

    def __init__(self):
        super(LithiumIonCell, self).__init__()
        self.voltage = None
        self.temperature = None
        self.status = None
    
    def configure(self, agent, config):
        super(LithiumIonCell, self).configure(agent, config)


class LithiumIonModule(BessComponent):
    def __init__(self):
        super(LithiumIonModule, self).__init__()
        self.module_cell_count = None
        self.module_soc = None
        self.module_soh = None
        self.max_cell_voltage = None
        self.max_cell_voltage_cell = None
        self.min_cell_voltage = None
        self.min_cell_voltage_cell = None
        self.average_cell_voltage = None
        self.max_cell_temperature = None
        self.max_cell_temperature_cell = None
        self.min_cell_temperature = None
        self.min_cell_temperature_cell = None
        self.average_cell_temperature = None
        
    def configure(self, agent, config):
        super(LithiumIonModule, self).configure(agent, config)


class LithiumIonModuleDetail(LithiumIonModule):
    def __init__(self):
        super(LithiumIonModuleDetail, self).__init__()
        self.module_index = None
        self.depth_of_discharge = None
        self.cycle_count = None
        self.module_voltage = None
        self.serial_number = None
        self.balanced_cell_count = None
        self.cells = []
    
    def configure(self, agent, config):
        super(LithiumIonModuleDetail, self).configure(agent, config)

class LithiumIonString(BessComponent):
    class St(Flag):
        STRING_ENABLED = 2 ** 0
        CONTACTOR_STATUS = 2 ** 1

    class ConFail(Enum):
        NO_FAILURE = 0
        BUTTON_PUSHED = 1
        STR_GROUND_FAULT = 2
        OUTSIDE_VOLTAGE_RANGE = 3
        STRING_NOT_ENABLED = 4
        FUSE_OPEN = 5
        CONTACTOR_FAILURE = 6

    class ConSt(Flag):
        CONTACTOR_0 = 2 ** 0
        CONTACTOR_1 = 2 ** 1
        CONTACTOR_2 = 2 ** 2
        CONTACTOR_3 = 2 ** 3
        CONTACTOR_4 = 2 ** 4
        CONTACTOR_5 = 2 ** 5
        CONTACTOR_6 = 2 ** 6
        CONTACTOR_7 = 2 ** 7
        CONTACTOR_8 = 2 ** 8
        CONTACTOR_9 = 2 ** 9
        CONTACTOR_10 = 2 ** 10
        CONTACTOR_11 = 2 ** 11
        CONTACTOR_12 = 2 ** 12
        CONTACTOR_13 = 2 ** 13
        CONTACTOR_14 = 2 ** 14
        CONTACTOR_15 = 2 ** 15
        CONTACTOR_16 = 2 ** 16
        CONTACTOR_17 = 2 ** 17
        CONTACTOR_18 = 2 ** 18
        CONTACTOR_19 = 2 ** 19
        CONTACTOR_20 = 2 ** 20
        CONTACTOR_21 = 2 ** 21
        CONTACTOR_22 = 2 ** 22
        CONTACTOR_23 = 2 ** 23
        CONTACTOR_24 = 2 ** 24
        CONTACTOR_25 = 2 ** 25
        CONTACTOR_26 = 2 ** 26
        CONTACTOR_27 = 2 ** 27
        CONTACTOR_28 = 2 ** 28
        CONTACTOR_29 = 2 ** 29
        CONTACTOR_30 = 2 ** 30

    class Evt1(Flag):
        COMMUNICATION_ERROR = 2 ** 0
        OVER_TEMPERATURE_ALARM = 2 ** 1
        OVER_TEMPERATURE_WARNING = 2 ** 2
        UNDER_TEMPERATURE_ALARM = 2 ** 3
        UNDER_TEMPERATURE_WARNING = 2 ** 4
        OVER_CHARGE_CURRENT_ALARM = 2 ** 5
        OVER_CHARGE_CURRENT_WARNING = 2 ** 6
        OVER_DISCHARGE_CURRENT_ALARM = 2 ** 7
        OVER_DISCHARGE_CURRENT_WARNING = 2 ** 8
        OVER_VOLTAGE_ALARM = 2 ** 9
        OVER_VOLTAGE_WARNING = 2 ** 10
        UNDER_VOLTAGE_ALARM = 2 ** 11
        UNDER_VOLTAGE_WARNING = 2 ** 12
        UNDER_STATE_OF_CHARGE_MIN_ALARM = 2 ** 13
        UNDER_STATE_OF_CHARGE_MIN_WARNING = 2 ** 14
        OVER_STATE_OF_CHARGE_MAX_ALARM = 2 ** 15
        OVER_STATE_OF_CHARGE_MAX_WARNING = 2 ** 16
        VOLTAGE_IMBALANCE_WARNING = 2 ** 17
        TEMPERATURE_IMBALANCE_ALARM = 2 ** 18
        TEMPERATURE_IMBALANCE_WARNING = 2 ** 19
        CONTACTOR_ERROR = 2 ** 20
        FAN_ERROR = 2 ** 21
        GROUND_FAULT_ERROR = 2 ** 22
        OPEN_DOOR_ERROR = 2 ** 23
        RESERVED = 2 ** 24
        OTHER_STRING_ALARM = 2 ** 25
        OTHER_STRING_WARNING = 2 ** 26

    class SetEna(Enum):
        ENABLE_STRING = 1
        DISABLE_STRING = 2

    class SetCon(Enum):
        CONNECT_STRING = 1
        DISCONNECT_STRING = 2

    def __init__(self):
        super(LithiumIonString, self).__init__()
        self.module_count = None                    # Count of modules in the string.
        self.string_status = None                   # Current status of the string.
        self.connection_failure_reason = None
        self.string_state_of_charge = None          # Battery string state of charge, expressed as a percentage.
        self.string_state_of_health = None          # Battery string state of health, expressed as a percentage.
        self.string_current = None                  # String current measurement.
        self.max_cell_voltage = None                # Maximum voltage for all cells in the string.
        self.max_cell_voltage_module = None         # Module containing the maximum cell voltage.
        self.min_cell_voltage = None                # Minimum voltage for all cells in the string.
        self.min_cell_voltage_module = None         # Module containing the minimum cell voltage.
        self.average_cell_voltage = None            # Average voltage for all cells in the string.
        self.max_module_temperature = None          # Maximum temperature for all modules in the bank.
        self.max_module_temperature_module = None   # Module with the maximum temperature.
        self.min_module_temperature = None          # Minimum temperature for all modules in the bank.
        self.min_module_temperature_module = None   # Module with the miniumum temperature.
        self.average_module_temperature = None      # Average temperature for all modules in the bank.
        self.contactor_status = None
        self.string_event_1 = None                  # Alarms, warnings and status values.  Bit flags.
        self.string_event_2 = None                  # Alarms, warnings and status values.  Bit flags.
        self.vendor_string_event_bitfield_1 = None  # Vendor defined events.
        self.vendor_string_event_bitfield_2 = None  # Vendor defined events.
        self.enable_disable_string = None           # Enables and disables the string.
        self.connect_disconnect_string = None       # Connects and disconnects the string.
        self.modules = []

    def configure(self, agent, config):
        super(LithiumIonString, self).configure(agent, config)


class LithiumIonStringDetail(LithiumIonString):
    def __init__(self):
        super(LithiumIonStringDetail, self).__init__()
        self.string_index = None                    # Index of the string within the bank.
        self.string_cell_balancing_count = None     # Number of cells currently being balanced in the string.
        self.string_depth_of_discharge = None       # Depth of discharge for the string, expressed as a percentage.
        self.string_cycle_count = None              # Number of discharge cycles executed upon the string.
        self.string_voltage = None                  # String voltage measurement.

    def configure(self, agent, config):
        super(LithiumIonStringDetail, self).configure(agent, config)


class LithiumIonBattery(BaseBattery):
    def __init__(self):
        super(LithiumIonBattery, self).__init__()
        self.string_count = None                    # Number of strings in the bank.
        self.connected_string_count = None          # Number of strings with contactor closed.
        self.max_module_temperature = None          # Maximum temperature for all modules in the bank.
        self.max_module_temperature_string = None   # String containing the module with maximum temperature.
        self.max_module_temperature_module = None   # Module with maximum temperature.
        self.min_module_temperature = None          # Minimum temperature for all modules in the bank.
        self.min_module_temperature_string = None   # String containing the module with minimum temperature.
        self.min_module_temperature_module = None   # Module with minimum temperature.
        self.average_module_temperature = None      # Average temperature for all modules in the bank.
        self.max_string_voltage = None              # Maximum string voltage for all strings in the bank.
        self.max_string_voltage_string = None       # String with maximum voltage.
        self.min_string_voltage = None              # Minimum string voltage for all strings in the bank.
        self.min_string_voltage_string = None       # String with minimum voltage.
        self.average_string_voltage = None          # Average string voltage for all strings in the bank.
        self.max_string_current = None              # Maximum current of any string in the bank.
        self.max_string_current_string = None       # String with the maximum current.
        self.min_string_current = None              # Minimum current of any string in the bank.
        self.min_string_current_string = None       # String with the minimum current.
        self.average_string_current = None          # Average string current for all strings in the bank.
        self.battery_cell_balancing_count = None    # Total number of cells that are currently being balanced.

        self.cell_voltage_scale_factor = 1          # Scale factor for cell voltage.
        self.module_temperature_scale_factor = 1    # Scale factor for module temperatures.
        self.current_scale_factor = 1               # Scale factor for Max String Current and Min String Current.
        self.state_of_health_scale_factor = 1       # Scale factor for String State of Health.
        self.strings = []

    def configure(self, agent, config):
        super(LithiumIonBattery, self).configure(agent, config)
