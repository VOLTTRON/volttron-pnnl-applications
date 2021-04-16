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
from aenum import Enum
from volttron.platform.agent import utils
import logging

utils.setup_logging()
_log = logging.getLogger(__name__)


class Inverter(BessComponent):
    class LocRemCtl(Enum):
        REMOTE = 0
        LOCAL = 1

    class PCSSetOperation(Enum):
        START = 1
        STOP = 2
        ENTER_STANDBY = 3
        EXIT_STANDBY = 4

    class St(Enum):
        OFF = 1
        SLEEPING = 2
        STARTING = 3
        MPPT = 4
        THROTTLED = 5
        SHUTTING_DOWN = 6
        FAULT = 7
        STANDBY = 8
        STARTED = 9

    class Evt1(Enum):
        GROUND_FAULT = 0
        DC_OVER_VOLT = 1
        AC_DISCONNECT = 2
        DC_DISCONNECT = 3
        GRID_DISCONNECT = 4
        CABINET_OPEN = 5
        MANUAL_SHUTDOWN = 6
        OVER_TEMP = 7
        OVER_FREQUENCY = 8
        UNDER_FREQUENCY = 9
        AC_OVER_VOLT = 10
        AC_UNDER_VOLT = 11
        BLOWN_STRING_FUSE = 12
        UNDER_TEMP = 13
        MEMORY_LOSS = 14
        HW_TEST_FAILURE = 15
        OTHER_ALARM = 16
        OTHER_WARNING = 17

    def __init__(self):
        super(Inverter, self).__init__()

        # Inverter data points:
        self.ac_current = DataPoint()
        self.phase_a_current = DataPoint()
        self.phase_b_current = DataPoint()
        self.phase_c_current = DataPoint()
        self.phase_voltage_ab = DataPoint()
        self.phase_voltage_bc = DataPoint()
        self.phase_voltage_ca = DataPoint()
        self.phase_voltage_an = DataPoint()
        self.phase_voltage_bn = DataPoint()
        self.phase_voltage_cn = DataPoint()
        self.ac_power = DataPoint()
        self.line_frequency = DataPoint()
        self.ac_apparent_power = DataPoint()
        self.ac_reactive_power = DataPoint()
        self.ac_power_factor = DataPoint()
        self.ac_energy = DataPoint()
        self.dc_current = DataPoint()
        self.dc_voltage = DataPoint()
        self.dc_power = DataPoint()
        self.cabinet_temperature = DataPoint()
        self.heat_sink_temperature = DataPoint()
        self.transformer_temperature = DataPoint()
        self.other_temperature = DataPoint()
        self.operating_state = DataPoint()
        self.vendor_operating_state = DataPoint()
        self.event_1 = DataPoint()                   # Bitfield Evt1
        self.event_2 = DataPoint()                   # Future Use.
        self.vendor_event_1 = DataPoint()
        self.vendor_event_2 = DataPoint()
        self.vendor_event_3 = DataPoint()
        self.vendor_event_4 = DataPoint()

        self.local_remote_control = DataPoint()      # Inverter control mode. LocRemCtl Enumeration.
        self.inverter_heartbeat = DataPoint()        # Value is incremented every second with periodic resets to zero.
        self.controller_heartbeat = DataPoint()      # Value is incremented every second with periodic resets to zero.
        self.alarm_reset = DataPoint()               # Used to reset any latched alarms.  1 = Reset.
        self.PCSSetOperation = DataPoint()           # Commands the PCS. PCSSetOperation Enumeration.
        self.max_dc_charge_current = DataPoint()     # Instantaneous maximum DC charge current.
        self.max_dc_discharge_current = DataPoint()  # Instantaneous maximum DC discharge current.
        self.max_current_rating = DataPoint()        # Nameplate maximum AC charge/discharge current.
        self.max_current = DataPoint()               # Instantaneous maximum AC charge/discharge current, as % MaxA.

        # Inverter object settings:
        self.inverter_heartbeat_check_interval = 50  # TODO: What is PCS standard check interval?
        self.charge_sign = -1

        # Monitor:
        self.inverter_heartbeat_greenlet = None

    def configure(self, agent, config):
        super(Inverter, self).configure(agent, config)
        try:
            self.inverter_heartbeat_check_interval = config.get('inverter_heartbeat_check_interval',
                                                                self.inverter_heartbeat_check_interval)
            if self.inverter_heartbeat_check_interval <= 0:
                raise ValueError('INVERTER HEARTBEAT CHECK INTERVAL MUST BE POSITIVE')
            self.charge_sign = config.get('charge_sign', self.charge_sign)
            if abs(self.charge_sign) != 1:
                raise ValueError("CHARGE SIGN MUST BE 1 or -1")
        except ValueError as e:
            _log.error("ERROR PROCESSING INVERTER CONFIGURATION: {}".format(e))

    def initialize(self):
        pass

    def start(self):
        raise NotImplemented('Inverter.start() is not implemented.')

    def stop(self):
        raise NotImplementedError('Inverter.stop() is not implemented.')

    def is_started(self):
        raise NotImplementedError('Inverter.is_started() is not implemented.')

    # TODO: What is supposed to call this?  The heartbeat does not appear to get started.
    def start_heartbeat(self):
        if self.inverter_heartbeat_greenlet is None:
            _log.info('Starting Inverter Heartbeat Manager.')
            self.inverter_heartbeat_greenlet = self.agent.core.periodic(self.inverter_heartbeat_check_interval,
                                                                        self.manage_inverter_heartbeat)

    def stop_heartbeat(self):
        if self.inverter_heartbeat_greenlet:
            _log.info('Stopping Inverter Heartbeat Greenlet')
            self.inverter_heartbeat_greenlet.kill()
            self.inverter_heartbeat_greenlet = None

    def manage_inverter_heartbeat(self):
        pass  # TODO: Implement MESA PCS Standard heartbeat management.

    def command_power(self, power):
        raise NotImplementedError('Inverter.command_power() is not implemented.')
        # TODO: Implement: Return accepted_power.

    def command_current(self, current):
        raise NotImplementedError('Inverter.command_current() is not implemented.')
        # TODO: Implement: Return accepted current.

    def reset_faults(self):
        pass

    def get_allowed_command(self, charge_mode, user_command_mode):
        raise NotImplementedError('Inverter.get_allowed_command() is not implemented.')

    def set_pf_command(self, pf):
        raise NotImplementedError('Inverter.set_pf_command() is not implemented.')
        # TODO: Implement: Return accepted pf.

    def check_faults(self):
        # Should return list of string fault names.
        raise NotImplementedError('Inverter.check_faults() is not implemented.')
