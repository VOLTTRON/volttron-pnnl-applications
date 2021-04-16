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

from device_classes.base_battery import BaseBattery
from device_classes.inverter import Inverter
from device_classes.meter import Meter
import importlib
import re
import logging
import sys
import pytz
from gevent import sleep
from gevent.queue import Queue
from datetime import datetime, timedelta
from collections import namedtuple
from aenum import Enum
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, RPC, Core
from volttron.platform.messaging.health import Status, STATUS_BAD

# TODO: Unit tests
utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.7'


class State(Enum):
    STOPPED = 0
    STARTING = 1
    CONNECTING = 2
    CONNECTED = 3
    HOLD_TRANSITION = 4
    HOLDING = 5
    CHARGE_TRANSITION = 6
    CHARGING = 7
    DISCHARGE_TRANSITION = 8
    DISCHARGING = 9
    STOPPING = 10
    LOW_SOC_RECOVERY = 11


class UserCommandMode(Enum):
    POWER = 1
    CURRENT = 2


StateRequest = namedtuple('StateRequest', ['state', 'command', 'pf'])
StateAttained = namedtuple('StateAttained', ['state', 'command_accepted', 'pf_accepted'])


class BESSAgent(Agent):
    """BESS Controller Agent.

    This agent acts as the top level system controller for a Battery Energy Storage System.
    It is based on the Mesa Device standard, and it is intended to be compatible with any Mesa or Sunspec
    compliant devices.  It should also, however, be readily generalizable to other devices."""
    def __init__(self, config_path, **kwargs):
        super(BESSAgent, self).__init__(**kwargs)

        # Default configuration.  # TODO: Use default config from file if available.
        self.tz = pytz.utc
        self.actuator_vip = 'platform.actuator'  # Used by DataPoint class.

        self.soc_monitor_max_time = timedelta(seconds=30)  # Max time since last received SoC reading in seconds.
        self.soc_high_limit = 90
        self.soc_low_limit = 10
        self.soc_recovered_level = 20  # SoC to attain before exiting LOW_SOC_RECOVERY state.
        self.soc_monitor_interval = 1
        self.soc_recovery_check_interval = 30  # Time in seconds to wait between rechecks while recovering low SoC.
        self.soc_low_recovery_charge_command = 10  # kW rate to charge while in SoC Recovery mode.

        self.system_fault_check_interval = 1
        self.wait_connecting_interval = 1
        self.default_rpc_wait = 0.9

        self.strict_power_sign = True
        self.user_command_mode = 'POWER'  # May be "Power" or "Current"
        self.system_state_publish_topic = 'record/BESS/SystemState'

        # Components:
        self.inverter = Inverter()
        self.battery = BaseBattery()
        self.meter = Meter()

        # Transitions and States:
        self.allowed_transitions = {
            State.STOPPING: [],  # An empty list means the state will always be allowed
            State.LOW_SOC_RECOVERY: [],
            State.STARTING: [State.STOPPED],
            State.CONNECTING: [State.STARTING],
            State.CONNECTED: [State.CONNECTING],
            State.HOLD_TRANSITION: [State.CONNECTED, State.HOLDING, State.CHARGING, State.DISCHARGING,
                                    State.CHARGE_TRANSITION, State.DISCHARGE_TRANSITION],
            State.CHARGE_TRANSITION: [State.HOLDING, State.CHARGING, State.DISCHARGING, State.HOLD_TRANSITION,
                                      State.CHARGE_TRANSITION, State.DISCHARGE_TRANSITION],
            State.DISCHARGE_TRANSITION: [State.HOLDING, State.CHARGING, State.DISCHARGING, State.HOLD_TRANSITION,
                                         State.CHARGE_TRANSITION, State.DISCHARGE_TRANSITION],
        }
        self.transition_method = {
            State.STOPPING: self.stop_transition,
            State.STARTING: self.start_transition,
            State.CONNECTING: self.connecting_transition,
            State.CONNECTED: self.connected_transition,
            State.HOLD_TRANSITION: self.hold_transition,
            State.CHARGE_TRANSITION: self.charge_transition,
            State.DISCHARGE_TRANSITION: self.discharge_transition,
            State.LOW_SOC_RECOVERY: self.low_soc_recovery  # Will not return until reaching self.soc_recovered_level.
        }
        self.state_method = {
            State.STOPPED: self.stopped_state,
            State.HOLDING: self.holding_state,
            State.CHARGING: self.charging_state,
            State.DISCHARGING: self.discharging_state
        }
        self.state_monitor_period = 10

        # Set up config store.
        self.default_config = {"tz": self.tz.zone,
                               "actuator_vip": self.actuator_vip,
                               "soc_monitor_max_time": self.soc_monitor_max_time.total_seconds(),
                               "soc_high_limit": self.soc_high_limit,
                               "soc_low_limit": self.soc_low_limit,
                               "soc_recovered_level": self.soc_recovered_level,
                               "soc_monitor_interval": self.soc_monitor_interval,
                               "soc_recovery_check_interval": self.soc_recovery_check_interval,
                               "soc_low_recovery_charge_command": self.soc_low_recovery_charge_command,
                               "system_fault_check_interval": self.system_fault_check_interval,
                               "wait_connecting_interval": self.wait_connecting_interval,
                               "default_rpc_wait": self.default_rpc_wait,
                               "strict_power_sign": self.strict_power_sign,
                               "user_command_mode": self.user_command_mode,
                               "system_state_publish_topic": self.system_state_publish_topic
                               }

        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

        # Set up state variables.
        self.system_state = State.STOPPED
        self.soc_monitor_timer = None

        # Periodic greenlet handles:
        self.monitors = {}

        # State Manager:
        self.state_manager_greenlet = None
        self.state_queue = Queue()

    def configure(self, config_name, action, contents):
        _log.info('Received configuration {} signal: {}'.format(action, config_name))
        config = self.default_config.copy()
        config.update(contents)

        # make sure config values are valid:
        try:
            # TODO: Currently only one top level component of each type (battery, inverter, meter) is supported.
            self.battery = self.configure_dependency(config.get('battery_config'), self.battery)
            self.inverter = self.configure_dependency(config.get('inverter_config'), self.inverter)
            self.meter = self.configure_dependency(config.get('meter_config'), self.meter)

            self.tz = pytz.timezone(config.get('tz', self.tz))
            self.actuator_vip = config.get('actuator_vip', self.actuator_vip)

            soc_monitor_max_time = float(config.get('soc_monitor_max_time'))
            if soc_monitor_max_time <= 0:
                raise ValueError('SOC MONITOR MAX TIME MUST BE POSITIVE')
            self.soc_monitor_max_time = timedelta(seconds=soc_monitor_max_time)
            self.soc_high_limit = int(config.get('soc_high_limit'))
            if not 0 <= self.soc_high_limit <= 100:
                raise ValueError('SOC HIGH LIMIT OUT OF RANGE (0-100)')
            self.soc_low_limit = int(config.get('soc_low_limit'))
            if not 0 <= self.soc_low_limit <= 100:
                raise ValueError('SOC LOW LIMIT OUT OF RANGE (0-100)')
            if not self.soc_low_limit <= self.soc_high_limit:
                raise ValueError('LOW SOC LIMIT MUST BE LESS THAN OR EQUAL TO HIGH SOC LIMIT')
            self.soc_recovered_level = int(config.get('soc_recovered_level'))
            if not self.soc_recovered_level > self.soc_low_limit:
                raise ValueError('SOC RECOVERED LEVEL MUST BE GREATER THAN SOC LOW LIMIT')
            self.soc_monitor_interval = int(config.get('soc_monitor_interval'))
            if self.soc_monitor_interval <= 0:
                raise ValueError('SOC MONITOR INTERVAL MUST BE POSITIVE')
            self.soc_recovery_check_interval = float(config.get('soc_recovery_check_interval'))
            if self.soc_recovery_check_interval <= 0:
                raise ValueError('SOC RECOVERY CHECK INTERVAL MUST BE POSITIVE')
            self.soc_low_recovery_charge_command = int(config.get('soc_low_recovery_charge_command'))
            if not 0 <= self.soc_low_recovery_charge_command <= 100:
                raise ValueError('SOC LOW RECOVERY CHARGE COMMAND  OUT OF RANGE (0-100)')

            self.system_fault_check_interval = float(config.get('system_fault_check_interval'))
            if self.system_fault_check_interval <= 0:
                raise ValueError('SYSTEM FAULT CHECK INTERVAL MUST BE POSITIVE')
            self.wait_connecting_interval = float(config.get('wait_connecting_interval'))
            if self.wait_connecting_interval <= 0:
                raise ValueError('WAIT CONNECTING INTERVAL MUST BE POSITIVE')
            self.default_rpc_wait = float(config.get('default_rpc_wait'))
            if self.default_rpc_wait <= 0:
                raise ValueError('DEFAULT RPC WAIT MUST BE POSITIVE')

            self.strict_power_sign = config.get('strict_power_sign', self.strict_power_sign)
            if not isinstance(self.strict_power_sign, bool):
                raise ValueError('STRICT POWER SIGN MUST BE A BOOLEAN')
            try:
                self.user_command_mode = UserCommandMode[config.get('user_command_mode')]
            except KeyError:
                raise ValueError('USER COMMAND MODE MUST BE "POWER" OR "CURRENT"')
            self.system_state_publish_topic = config.get('system_state_publish_topic')
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))

        # Start the state manager:
        self.state_manager_greenlet = self.core.spawn(self.manage_state)

    def configure_dependency(self, config, default_dependency=None):
        """Configures each dependency in passed list of configurations.

        Instantiates each dependency.
        Requires each dependency have a configure() method which is passed a dictionary of configurations and
        a reference to this agent.
        It is up to the individual dependency to manage its own configuration.

        Returns list of instantiated and configured dependencies"""
        first_cap_re = re.compile('(.)([A-Z][a-z]+)')
        all_cap_re = re.compile('([a-z0-9])([A-Z])')

        def camel_to_snake(name):
            s1 = first_cap_re.sub(r'\1_\2', name)
            return all_cap_re.sub(r'\1_\2', s1).lower()

        if not config:
            return default_dependency

        cls = config.get('class_name')
        default_module_name = 'bess.device_classes.' + camel_to_snake(cls)
        module = config.get('module_name', default_module_name)
        module = importlib.import_module(module)
        dependency = getattr(module, cls)()
        dependency.configure(self, config)
        return dependency

    #
    # User Interface:
    #
    # TODO: Implement pubsub actuation.
    @RPC.export('start')
    def user_start_rpc(self):
        _log.info('Received USER_START request.')
        self.state_queue.put(StateRequest(State.STARTING, None, None))

    @RPC.export('stop')
    def user_stop_rpc(self):
        _log.info('Received USER_STOP request.')
        self.state_queue.put(StateRequest(State.STOPPING, None, None))

    @RPC.export('charge')
    def user_charge_rpc(self, desired_command, pf=0):
        _log.info('Received USER_CHARGE request.')
        self.state_queue.put(StateRequest(State.CHARGE_TRANSITION, desired_command, pf))

    @RPC.export('discharge')
    def user_discharge_rpc(self, desired_command, pf=0):
        _log.info('Received USER_DISCHARGE request.')
        self.state_queue.put(StateRequest(State.DISCHARGE_TRANSITION, desired_command, pf))

    @RPC.export('hold')
    def user_hold_rpc(self):
        _log.info('Received USER_HOLD request.')
        self.state_queue.put(StateRequest(State.HOLD_TRANSITION, None, None))

    @RPC.export('recover_soc')
    def user_soc_recovery(self, command=None):
        _log.info('Received USER_RECOVER_SOC request')
        self.state_queue.put(StateRequest(State.LOW_SOC_RECOVERY, command, 0))

    @RPC.export('get_state')
    def user_get_state_rpc(self):
        _log.info('Received USER_GET_STATE request.')
        # TODO: Should this verify state (once implemented) instead?
        return self.system_state.name

    #
    # Agent Lifecycle callbacks:
    #

    @Core.receiver('onstop')
    def on_stop(self, sender, **kwargs):
        _log.info('Received onstop from {}: {} Shutting down.'.format(sender, kwargs))
        self.state_manager_greenlet.kill()
        self.stop_transition(StateRequest(State.STOPPING, None, None))

    #
    # State Manager
    #

    def manage_state(self):
        """State Machine. Control transition between states."""
        def set_state(state):
            self.system_state = state
            _log.info('System state is : {}.'.format(state.name))
            self.vip.pubsub.publish('pubsub', self.system_state_publish_topic, message=state.name)

        def transition_waiter(source):
            if source.successful():
                new_token = source.value
                self.state_queue.put(new_token)
            else:
                _log.error("Exception was raised from {} transition: {}".format(source.name, repr(source.exception)),
                           exc_info=getattr(source, 'exc_info', None))
                self.state_queue.put(StateRequest(State.STOPPING, None, None))

        state_monitor = None
        active_transition = None
        while True:
            token = self.state_queue.get()
            if isinstance(token, StateRequest):
                # Check if transition is allowed:
                if token.state in self.allowed_transitions:
                    if self.allowed_transitions[token.state] \
                            and self.system_state not in self.allowed_transitions[token.state]:
                            _log.info('STATE TRANSITION DISALLOWED: {} received while in state: {}'.format(
                                token.state.name, self.system_state.name))
                    else:
                        if state_monitor:
                            state_monitor.kill()
                        if active_transition:
                            active_transition.kill()
                        set_state(token.state)
                        active_transition = self.core.spawn(self.transition_method[token.state], token)
                        active_transition.name = token.state.name
                        active_transition.link(transition_waiter)
                else:
                    _log.warning('Ignoring Unknown StateRequest: "{}".'.format(token.state.name))
            elif isinstance(token, StateAttained):
                set_state(token.state)
                state_monitor = self.core.periodic(self.state_monitor_period, self.state_method[token.state], token)

    #
    #   System State Transitions
    #

    def start_transition(self, request):
        """Start the BESS.  Transition from STOPPED to HOLDING State.
            Intermediate state "STARTING" while starting monitors and initializing equipment.
            """
        try:
            self.reset_faults()
            self.inverter.initialize()
            self.start_monitor('system_faults', self.system_faults, self.system_fault_check_interval)
            self.battery.connect()
        except Exception as e:
            _log.error('Exception while STARTING: {}'.format(e))
            return StateRequest(State.STOPPING, None, None)
        return StateRequest(State.CONNECTING, None, None)

    def connecting_transition(self, request):
        """Intermediate starting state "CONNECTING" while waiting for bank controller to close contactors."""
        waiting_for_connection = True
        while waiting_for_connection:
            state = self.battery.state.get()
            _log.info('Waiting for CONNECT. Battery State is: {}'.format(self.battery.State(state.value).name))
            if not state or state.value != self.battery.State.CONNECTED.value:
                sleep(self.wait_connecting_interval)
            else:
                waiting_for_connection = False
        return StateRequest(State.CONNECTED, None, None)

    def connected_transition(self, request):
        """Intermediate state "CONNECTED while setting up inverter once contactors are closed."""
        try:
            self.system_faults()
            self.inverter.start()
            self.start_monitor('soc', self.soc_monitor, self.soc_monitor_interval)
        except Exception as e:
            _log.error('Exception in connected transition: {} STOPPING now.'.format(e))
            self.state_queue.put(StateRequest(State.STOPPING, None, None))
        return StateRequest(State.HOLD_TRANSITION, None, None)

    def stop_transition(self, request):
        """Shutdown the BESS. Transition to the STOPPED State."""
        # Stop monitors:
        self.stop_monitor('soc')
        self.stop_monitor('system_faults')
        self.stop_monitor('system_heartbeat')
        self.inverter.stop_heartbeat()

        # Set Inverter MaxPowerCommand to zero.
        try:
            self.inverter.command_power(0)
            self.inverter.stop()
            self.battery.disconnect()
            self.reset_faults()
        except Exception as e:
            self.send_alarm('Exception while stopping BESS: {}'.format(e))
            _log.error('Exception while stopping: {}'.format(e))

        return StateAttained(State.STOPPED, None, None)

    def hold_transition(self, request):
        """Transition to the HOLDING State"""
        _log.info('Setting Inverter Power to 0.')
        try:
            self.inverter.command_power(0)
        except Exception as e:
            _log.error('Exception in HOLD_TRANSITION: {}.  STOPPING now.'.format(e))
            return StateRequest(State.STOPPING, None, None)
        return StateAttained(State.HOLDING, None, None)

    def charge_transition(self, request):
        """Transition to the CHARGING State."""
        if self.battery.soc >= self.soc_high_limit:
            _log.warning('Unable to charge, SoC: {} has reached or exceeds high limit: {}.'.format(
                self.battery.soc, self.soc_high_limit))
            return StateRequest(State.HOLD_TRANSITION, None, None)
        try:
            calculated_command = self.calculate_command(request.command, 'CHARGE')
            pf_accepted = self.inverter.set_pf_command(request.pf)
            command_accepted = self.inverter.command_power(calculated_command)
        except Exception as e:
            _log.warning('Exception in CHARGE_TRANSITION: {} HOLDING now.'.format(e))
            return StateRequest(State.HOLD_TRANSITION, None, None)

        return StateAttained(State.CHARGING, command_accepted, pf_accepted)

    def discharge_transition(self, request):
        """Transition to the DISCHARGING State."""
        if self.battery.soc <= self.soc_low_limit:
            _log.warning('Unable to discharge, SoC: {} has reached or exceeds low limit: {}.'.format(
                self.battery.soc, self.soc_high_limit))
            return StateRequest(State.HOLD_TRANSITION, None, None)
        try:
            calculated_command = self.calculate_command(request.command, 'DISCHARGE')
            pf_accepted = self.inverter.set_pf_command(request.pf)
            command_accepted = self.inverter.command_power(calculated_command)
        except Exception as e:
            _log.warning('Exception in DISCHARGE_TRANSITION: {} HOLDING now.'.format(e))
            return StateRequest(State.HOLD_TRANSITION, None, None)
        return StateAttained(State.DISCHARGING, command_accepted, pf_accepted)

    def holding_state(self, *args):
        # TODO: Monitor/Verify HOLDING State
        pass

    def charging_state(self, *args, **kwargs):
        # TODO: Monitor/Verify CHARGING State
        pass

    def discharging_state(self, *args, **kwargs):
        # TODO: Monitor/Verify DISCHARGING State
        pass

    def stopped_state(self, *args, **kwargs):
        # TODO: Monitor/Verify STOPPED State if possible.
        pass

    def low_soc_recovery(self, *args, **kwargs):
        if self.battery.soc > self.soc_recovered_level:
            _log.info('Entered LOW_SOC_RECOVERY, but SoC ({}) is above low_soc_recovered_level ({}), returning to HOLDING state'.format(
                self.battery.soc.last.value, self.soc_recovered_level))
            return StateRequest(State.HOLD_TRANSITION, None, None)
        _log.info('Attempting to charge by {} kW'.format(self.soc_low_recovery_charge_command))
        try:
            if not self.inverter.is_started():
                self.inverter.start()
            charge_command = kwargs.get('command', self.soc_low_recovery_charge_command)
            charge_request = StateRequest(State.CHARGE_TRANSITION, charge_command, 0)
            attained = self.charge_transition(charge_request)
            if attained.state == State.CHARGING:
                self.send_alarm('Successfully entered LOW_SOC_RECOVERY state at {}: SoC reading is {}.'
                                'Charging at {} until the system reaches {}% SoC'.format(
                                    datetime.now(pytz.utc).astimezone(self.tz), self.battery.soc.get(),
                                    attained.command_accepted, self.soc_recovered_level))
            else:
                raise Exception('Charge request resulted in state: {}'.format(attained.state))
        except Exception as e:
            self.send_alarm('FAILED to enter LOW_SOC_RECOVERY state at {}: SoC reading is {}.'
                            ' Manual intervention is required. Exception is: {}'.format(
                                datetime.now(pytz.utc).astimezone(self.tz), self.battery.soc.get(), e))
            return StateRequest(State.STOPPING, None, None)
        else:
            while self.battery.soc < self.soc_recovered_level:
                sleep(self.soc_recovery_check_interval)
            self.send_alarm('Reached {} % SoC at {}. Returning system to HOLDING mode.'.format(
                self.battery.soc.last, datetime.now(pytz.utc).astimezone(self.tz)))
            return self.hold_transition(StateRequest(State.HOLD_TRANSITION, None, None))

    #
    # Helper Functions
    #
    def calculate_command(self, desired_command, charge_mode):
        """Determines allowable command based on current system state.
            charge mode should be CHARGE or DISCHARGE.
            command mode should be POWER or CURRENT"""
        # Ignore sign or fail if desired_power is negative. # TODO: Is this still relevant in current version?
        if self.strict_power_sign and desired_command < 0:
            raise Exception('Received negative power command while "strict_power_sign" is enabled')
        else:
            desired_command = abs(desired_command)

        # Get device command limits:
        try:
            battery_cmd_limit = self.battery.get_allowed_command(charge_mode, 'POWER')
            inverter_cmd_limit = self.inverter.get_allowed_command(charge_mode, 'POWER')
        except Exception as e:
            raise e
        approved_command = min(desired_command, battery_cmd_limit, inverter_cmd_limit)
        charge_sign = self.inverter.charge_sign if charge_mode is 'CHARGE' else self.inverter.charge_sign * -1
        return approved_command * charge_sign

    def reset_faults(self):
        """Reset faults on Inverter and on Bank Controller"""
        _log.info('Resetting Fault Alarm Registers')
        try:
            self.battery.reset_faults()
            self.inverter.reset_faults()
        except Exception as e:
            raise e

    def start_monitor(self, name, method, interval):
        """Start State of Charge Monitor."""
        if name in self.monitors:
            monitor = self.monitors.pop(name)
            monitor.kill()
        # TODO: How to monitor the health of the monitor greenlet?
        _log.info('Starting {} monitor greenlet'.format(name))
        self.monitors[name] = self.core.periodic(interval, method)

    def stop_monitor(self, name):
        if name in self.monitors:
            _log.info('Stopping {} monitor greenlet'.format(name))
            monitor = self.monitors.pop(name)
            monitor.kill()

    def send_alarm(self, error_text):
        """Send an alarm.  This will send an alert which may be picked up by the emailer agent.

        :param error_text: Text of the message to be sent.
        :type error_text: str
        """
        alert_key = "BESSAgent Alarm {}"
        context = "ERROR in BESS Agent: {}".format(error_text)

        status = Status.build(STATUS_BAD, context=context)
        self.vip.health.send_alert(alert_key, status)

    #
    # Periodic Functions
    #

    def soc_monitor(self):
        """Check if State of Charge is within limits. Return Boolean and send Hold signal if False."""
        if self.system_state is State.LOW_SOC_RECOVERY:
            return  # Abort check if already in recovery mode.                
        # Read State of Charge from Bank Controller
        now = datetime.now(pytz.utc).astimezone(self.tz)
        if self.battery.soc:
            self.soc_monitor_timer = None
            soc, last_read = self.battery.soc.get()
            # Stop if too long has passed since last reading.
            if now - last_read > self.soc_monitor_max_time:
                _log.error('Time since last SoC reading exceeds soc_monitor_max_time ({} seconds). STOPPING NOW'.format(
                    self.soc_monitor_max_time.total_seconds()))
                self.state_queue.put(StateRequest(State.STOPPING, None, None))

            # If SoC is out of range, handle according to handle_high/low_soc_condition.
            elif (self.system_state is State.CHARGING) & (soc >= self.soc_high_limit):
                _log.warning('HIGH SOC LIMIT EXCEEDED: SOC is {}. System_State is {}.'.format(soc, self.system_state))
                self.state_queue.put(StateRequest(State.HOLD_TRANSITION, None, None))

            elif (self.system_state is not State.CHARGING) & (soc <= self.soc_low_limit):
                _log.warning('LOW SOC LIMIT EXCEEDED: SOC is {}. System_State is {}.'.format(soc, self.system_state))
                self.state_queue.put(StateRequest(State.LOW_SOC_RECOVERY, None, None))

        else:
            if not self.soc_monitor_timer:
                self.soc_monitor_timer = now
            elif now - self.soc_monitor_timer > self.soc_monitor_max_time:
                _log.error('No SoC readings have been received within soc_monitor_max_time ({} seconds).'
                           ' STOPPING now.'.format(self.soc_monitor_max_time.total_seconds()))

    # TODO: Need to check for LowSoC Alarm, othewise this may stop Low SoC Recovery from happening.
    def system_faults(self):
        """Check for System Faults.  If found, shutdown BESS."""
        faults = []
        # Read fault registers
        faults.extend(self.battery.check_faults())
        faults.extend(self.inverter.check_faults())
        if faults:
            err = '{} System Faults detected. STOPPING now. Faults are:\n{}'.format(len(faults), '\n'.join(faults))
            self.send_alarm(err)
            _log.error(err)
            self.state_queue.put(StateRequest(State.STOPPING, None, None))


def main():
    """Main method called by the platform."""
    utils.vip_main(BESSAgent)


if __name__ == '__main__':
    # Entry point for script.
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
