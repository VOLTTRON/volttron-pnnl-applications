# BESS Agent

The BESS Agent is a controller for Battery Energy Storage Systems originally 
 developed at the University of Toledo The BESS Agent is intended to be compatible
 with devices implementing the [MESA-Device/SunSpec Energy Storage Specification](
 http://mesastandards.org/mesa-device/). The controller is organized around three
 basic components: a battery, an inverter, and a meter. The base classes for these
 components are organized as specified in the Storage, PCS, and Meter component 
 specifications of MESA-Device. The code is modular, and additional, 
 non-MESA-compliant devices may also be supported via subclasses of base 
 components. At least one subclass for Rhombus RES-125kW Inverter is currently 
 included, and contribution of additional subclasses for distribution with this code
 are [welcome](mailto://david.raker@utoledo.edu).
 
 Interaction with the BESS agent may be carried out by the use of [RPC
 commands](#rpc-interface) as detailed in [Features](#features). The agent
 currently supports only a manual mode of interaction, whereby commands to charge,
 discharge, or hold are issued directly via RPC from another agent or user. 
 Additional modes, such as those specified in 
 [MESA-ESS](http://mesastandards.org/mesa-ess-2016/) are [planned](#roadmap). 
 
 While current code does not fully implement MESA-Device, as detailed in 
 [Mesa Compatibility](#mesa-compatibility), it is intended that compatibility will
 improve in future versions, as additional features, modes, and devices are added.
 Any incompatibility between this implementation and MESA compliant devices is
 considered a bug and should be reported to the 
 [original developer](mailto://david.raker@utoledo.edu).
 
## Features
The BESS Agent provides data classes organized in compliance with the MESA-Device
specification. Attributes of these classes are mapped to VOLTTRON device driver
topics in configuration files. It is therefore unnecessary for point names to match
exactly with those specified by MESA. Where functional differences exist between
the MESA models and the device being configured, subclasses may be implemented which
extend the functionality of the BESS agent. The agent is organized in a modular
design to facilitate easy of subclassing. The agent additionally provides the 
following features:

* [Non-blocking state machine](#state-machine)
* [RPC Interface](#rpc-interface) 
* [Fault Monitoring](#fault-monitoring)
* [Automatic State of Charge (SoC) Recovery](#soc-recovery)

#### State Machine:
   The controller is implemented as a non-blocking state machine which specifies
   a set of states and transitions. As the BESS Agent is intended to interact with
   real-world hardware, which may experience lag in actuation, the state-machine
   will continue to accept new commands while transitions are in progress. While
   the BESS is in charging, discharging, or holding modes, new commands will be
   acted on even if the previous command has not returned from the device.  This
   is necessary to support high-speed operation, and should not cause deleterious
   effects, but should other behavior be desired, the set of allowed transitions
   is specified in the definition of self.allowed_transitions in the \__init\__()
   method of agent.py.  Stop commands are always honored from any state or 
   transition.
   
#### RPC Interface:
The following RPC calls are exposed:
   - **start**: Initializes the BESS. The inverter will be started and contactors
     on the battery will be closed. The BESS must be started before other commands
     will be honored.

   - **stop**: Shut down the BESS.  This command stops the inverter and opens
     contactors on the battery.

   - **charge**: Set the BESS to a charging state.  This command will be honored
     only while the BESS is currently charging, discharging, or holding.

   - **discharge**: Set the BESS to a discharging state.  This command will be
     honored only while the BESS is currently charging, discharging, or holding.

   - **hold**: Set the BESS to an idle state. The BESS remains ready for operation
     but is neither charging nor discharing while holding. This command will be
     honored only while the BESS is currently charging, discharging, or holding.

   - **get_state**: Returns the current state of the BESS to the calling agent.

   - **recover_soc**: Sets the BESS to an [State of Charge recovery state](
    #soc-recovery).

#### Fault Monitoring:
   Fault detection runs in a separate greenlet while the once the BESS has been
   initialized.  The core state machine is designed to be non-blocking to allow
   an immediate response when faults are detected, even where there is an ongoing
   transition.  Faults are not currently configurable, but additional conditions
   may be specified by overriding the check_faults() method in any component.
   Subclasses should call super unless they separately implement the faults
   specified by the corresponding MESA model.
    
#### SoC Recovery:
   SoC Recovery Mode is intended to avoid the risk of damage from a deep discharge
   of the batteries should SoC fall below low SoC limits. While in Soc Recovery, 
   the BESS attempts to charge at a pre-configured rate until it has reached a safe 
   state of charge.
   
   Commands to discharge are not available in this mode, though commands to stop
   will be honored. The SoC Recovery state is entered automatically if the BESS
   reaches a low SoC threshold, but may also be manually invoked, including during
   initialization, as this may be necessary to recover a battery which has
   fallen below the low SoC limit while disconnected.

## Configuration
#### Agent Configuration
This agent is intended to be used with the VOLTTRON configuration store.  Loading
the configuration from a default file is not currently supported, though defaults
are provided in the agent \__init\__() method.  The agent configuration file should
be stored in the config store (assuming a vip identity of ```bess.agent``` and
the provided configuration file from the top level directory of the agent as:

```$ vctl config store bess.agent config bess/bessagent.config```

###### Agent Configuration File
An example configuration file is provided as bess/bessagent.config. The BESS Agent
  main configuration file suports the following options: 

  - **tz**: The timezone of data being polled by the driver. Default: "UTC"
  - **actuator_vip**: The VIP idenentity of the actuator agent. Default:
   "platform.actuator"
  - **soc_monitor_max_time**:  Maximum number of seconds allowed before the SoC
   monitor triggers a shutdown of the BESS. Default: 30
  - **soc_high_limit**: Highest allowed SoC. The BESS will not charge past this
   level. Default: 90
  - **soc_low_limit**: Lowest allowed SoC. Reaching this level will trigger SoC
   Recovery Mode. Default: 10
  - **soc_recovered_level**: The level to which SoC Recovery Mode will attempt to
   charge the BESS before releasing it to normal operation. Default: 20
  - **soc_monitor_interval**: The interval in seconds on which the SoC Monitor is
   called: Default: 1
  - **soc_recovery_check_interval**: The interval in seconds on which SoC is
   checked during SoC Recovery Mode. Default: 1
  - **soc_low_recovery_charge_command**: The commanded rate at which the battery
   will charge in SoC Recovery Mode. The units depend on the user_command_mode
   setting. Default: 10
  - **system_fault_check_interval**: The interval in seconds on which the Fault
  Check Monitor is called. Default: 1
  - **wait_connecting_interval**: The interval in seconds on which the controller
   waits before checking for a response from the battery during initialization.
   Default: 1
  - **strict_power_sign**: If true, the agent will log a warning and hold rather
  than accept a negative charge or discharge command.  If false, the sign of the
  command will be ignored and the abolute value will be used. Default: true
  - **user_command_mode**:  The units used by the user to command the BESS.
    Currently only "POWER" is supported, but "CURRENT" is intended to be an option
    in future versions. Note that this is a separate issue from the units delivered
    to the inverter or battery, which may be configurable in the configuration for
    that device. In the instance that the inverter is configured for "CURRENT" 
    commands but this setting is "POWER", automatic conversion between units should 
    be made by the inverter device class before commanding the inverter. 
    Default: "POWER"
  - **system_state_publish_topic**: The topic on which publishes will be made by
   the BESS Agent to the VOLTTRON message bus when the state of the system is
   changed. Default: "record/BESS/SystemState"

  - **battery_config**: The config store path of the battery configuration file.
   Default: "config://battery.config"
  - **inverter_config**: The config store path of the inverter configuration file.
   Default: "config://inverter.config"
  - **meter_config**: The config store path of the meter configuration file.
   Default: "config://meter.config"

#### Device Configuration
Device classes are each configured with two files in a manner analogous to VOLTTRON
driver configuration: a json file with settings for the overall device, and a csv
file with one row for each point mapped for the device. The name of the json file
should be included in the top level agent configuration file (see previous section)
if it differs from the default file names. These files must be loaded into the
VOLTTRON configuration store to be read:

```
$ vctl config store bess.agent battery.config bess/battery.config
$ vctl config store bess.agent battery_points.csv bess/battery_points.csv --csv
$ vctl config store bess.agent inverter.config bess/inverter.config
$ vctl config store bess.agent inverter_points.csv bess/inverter_points.csv --csv
```
The meter configuration is currently unnecessary, as all control in manual-mode
is currently open-loop, but this is likely to change in future versions once modes
are implemented which require feedback for closed loop control (i.e. following
Volt-VAR or Frequency-Watt curves). 

All devices support several device-level configurations:

  - **class_name:** The name of the class or subclass which implements the device.
    The default battery class is: "BaseBattery" and should be sufficent for basic
    control and monitoring of any battery as discussed in the
    [battery.config](#battery.config) subsection. The default inverter class is
    "Inverter", however this class is currently a stub as discussed in the
    [inverter.config](#inverter.config) subsection.
  - **module_name:** The name of the python module containing the class listed in
   the ```class_name``` configuration. The default module name is:
   ```bess.device_classes.[CLASS_NAME]``` where [CLASS_NAME] is the name returned
   by the snake case representation of the ```class_name``` setting (e.g. the
   BaseBattery class will be assumed by default to reside in a file located in the
   path ```bess/device_classes/base_battery.py```.
  - **points:** The VOLTTRON configuration store path of the csv file for point
   configuration.  The structure of these files is specified in the
   [Point Configuration](#point_configuration) section below.
  - **repeatable_blocks:** [UNTESTED: FUTURE USE] Repeating blocks may be specified
   in line with the MESA-Device models.  Example classes of this type are provided
   in the device_classes/lithium_ion_battery.py file. Each will be treated and
   configured as with the top-level devices by providing a dictionary with 
   ```"name": "config_store_path"``` key-pairs.

Additional configurations may also be required or supported for individual devices,
especially where those devices are not fully MESA-compliant, as is the case with
the RhombusInverterRes125 class.
    
###### NOTE ON BATTERY CLASSES:
The default battery class is called "BaseBattery". This class implements the
 MESA 802 model, which provides the key monitoring and control points shared by
 all battery classes.  This is expected to be sufficient for basic control of any
 battery device.
   
 A LithiumIonBattery subclass is also provided, along with classes for
 the repeating blocks specified in MESA models for Lithium Ion batteries in the
 lithium_ion_battery.py module, however these classes provide only the model
 data points. Should more sophisticated control or monitoring be desired which 
 makes use of Lithium Ion specific models, this should be added to the the 
 LithiumIonBattery subclass.  If only data is desired for non-control applications,
 the use of this subclass within the BESS Agent is unlikely to be necessary as this
 information should already be collected and available outside the BESS Agent from 
 VOLTTRON drivers. 
 
 The flow battery models specified by MESA-Storage are not currently
 implemented, though it is expected that BaseBattery will be sufficient for any
 simple monitoring and control applications for flow batteries, as it is with
 Lithium Ion batteries. The Lithium Ion battery models are provided primarily as
 a guide for implementation of new architectures, especially should architecture 
 specific functionality be required for operation.

###### NOTE ON INVERTER CLASES
This agent was originally developed for a system at The University of Toledo (UT) 
in which the inverter is not a MESA-PCS compliant inverter. UT uses the a subclass
called RhombusInverterRes125, which has been tested, but functionality for the 
general case of MESA-PCS compliant inverters has not been fully implemented nor 
tested in the base class. The issue of the code for MESA-PCS support is intended to
be addressed before version 1.0, and code and testing
[contributions](#contributions) are welcome.  

The base Inverter class does accept the following additional configurations:

- **inverter_heartbeat_check_interval:** Interval in seconds between checks of the 
 inverter heartbeat.  Default: 50
- **charge_sign:** Sign convention expected by the inverter for the commanded
 quantity (power or current) while charging. Default: -1 (Charge commands to the
 inverter will be negative, and discharge commands will be positive.)
 
 The RhombusInverterRes125 class accepts the following additional configurations.
 Some are expected to move into the base class as it is finished, others are
 specific to this inverter:

- **inverter_heartbeat_warning_time:**  Longest interval in seconds allowed without 
    receiving heartbeat before initiating shutdown. Default: 60
- **initial_inverter_heartbeat_count:** Value to which to set the inverter
    heartbeat when it is initialized or reset. Default: 931
- **inverter_heartbeat_count_limit:** Lowest value allowed for heartbeat before
    reset. Default: 750

- **security_code_value:** Security code sent to unlock the inverter. Default: 125
- **max_inverter_command":** Highest command allowed. This must match the command
    type as defined by ```inverter_command_mode```. Default: 125
- **inverter_command_mode:** Quantity type being used to command the inverter. This
    Inverter accepts either "POWER" or "CURRENT". Default: "POWER"

#### Point Configuration
Device data is collected by subscription to VOLTTRON driver publishes using a
mapping provided for each device in a CSV file. It should be noted that very few
points are actually used for monitoring and control of the BESS compared to those
specified by the MESA-Device models. Only those points strictly used for control
need to be mapped for the BESS Agent to function correctly, though the default
configuration files specify all points within the base devices. The points
required for basic functionality are listed in [Required Points](#required_points)
below.
 
###### CSV Layout
Each mapped point is represented as a row in the CSV file. Individual device
subclasses may also require additional fields, but all devices support at least
the following:
  
- **mesa_name (required):** The name specified by the MESA standard to which the 
 point is being mapped. For devices which are non-MESA compliant, this field should 
 still be used to represent the name used internally by the device subclass for 
 this point.
- **driver_point_name (required):** The point name being published by the VOLTTRON
 driver to the message bus.  (e.g. for the point with the full topic:
 ```Campus/BESS/Battery/SoC```, the point name is "SoC")
- **topic_prefix (required):** The topic name being published by the VOLTTRON 
driver to the message bus. (e.g. for the point with the full topic:
 ```Campus/BESS/Battery/SoC```, the topic_prefix is: "Campus/BESS/Battery")
- **scale_factor:** If the scale factor is not being provided by the VOLTTRON
driver (The ModbusTk driver is prefered, and provides this functionality already)
the scale factor may be provided here. The direction of this transformation is such
that the real-world value of the measurement should comply with
```scale_factor * driver_provided_value```. Default: 1.0
- **offset:** An offset transformation may be applied to the driver provided value
if this has not already been handled by the VOLTTRON driver. The direction of this
transformation is such that the real-world value of the measurement should comply
with ```offset + driver_provided_value```. Default: 0.0
- **unit:** The unit of the measurement as a string.
- **rpc_attempts:** The number of attempts to make when writing the point using
the VOLTTRON actuator. Default: 5
- **rpc_wait:** The time in seconds to wait between write attempts using the
VOLTTRON actuator. Default: 0.9
- **max_data_age:** Age in seconds for which data is still considered valid.
 Default: 0 (any data will be accepted as valid, regardless of age).
- **buffer_length:** Number of data points to retain in buffer. Default: 1
 (Note: No current functionality of the BESS Agent requires keeping a buffer of
 data, though the underlying data structure supports it. This is here for future
 use, but may be removed if the functionality is never required.)
 
###### Required Points
The following points are required to be available for operation of the BESS:

- **Battery:**
    - SetOp: Set Operation.
    - AlmRst: Alarm reset register.
    - V: Bank voltage.
    - AChaMax: Maximum currently alllowed charging current.
    - ADisChaMax: Maximum currently allowed discharge current.
    - State: State of the battery system.

- **Inverter:**
    The base inverter class is not fully developed yet.
    Some required points from the Rhombus inverter will apply 
    to all inverters, while others will not. This readme
    will be updated as the base class is finished.
    
    - **Rhombus RES 125kW Inverter:**
        - SecurityCode: Password to unlock inverter.
        - OpMode: Inverter operation mode.
        - Heartbeat: Heartbeat.
        - MaxPowerCommand: Command register for setting power or current.
        - PowerFactorOffset: Offset from unity power factor.
        - CIUFaultSummary: Fault register
        - MIUF1Summary: Fault register
        - MIUF2Summary: Fault register
        - MIUF3Summary: Fault register
        - MIUF4Summary: Fault register
        - GridOffStandaloneOn: Used to configure whether the inverter will operate
            in island mode.
        - AutoTransition: Used to configure whether the inverter will operate in 
            island mode.
    
## MESA Compatibility
The BESS Agent aims to work without modification for any device complying with MESA
standards for battery systems.  Several issues remain for full compliance with the
standards however. The system is also designed to be modular, such that
non-compliant devices will work as well by subclassing the appropriate device
classes. [Contributions](#contributions) will be welcomed for both improvements in
base class compliance and for subclasses extending functionality to additional
devices.

#### MESA Device
MESA-Device has three component standards for which data models are defined.  It is
expected that compliant devices will organize Modbus registers in a particular
order and implement certain functionality to allow auto-discovery.  Auto-discovery
functionality, however, is not implemented here, as none of the devices available
to the original authors are sufficiently compliant to provide this functionality.
A script allowing automatic configuration of the BESS Agent using this
functionality may be considered for future releases. Meanwhile, those intereseted
in scripting configuration may be interested in the 
[pySunSpec](https://pysunspec.readthedocs.io/en/latest/pysunspec.html) package.
  
###### MESA Storage
The BaseBattery class implements the 802 model shared by all batteries in the
MESA-Storage specification.  An additional LithiumIonBattery class provides the
remaining models for these devices, but currently adds no functionality beyond
that offered by the BaseBattery class for monitoring and control.  The flow battery
models are not implemented at this time, but are not expected to be needed for
basic control.  Users should use the BaseBattery class directly unless additional
model fields are required for user-developed extensions.

###### MESA PCS
As the original developer did not have access to a MESA-PCS compliant inverter,
the base level Inverter class is currently incomplete.  This is intended to be
fleshed out for compliance with the standards in upcoming versions, but code
[contributions](#contributions) are welcome.

###### MESA Meter
Only a manual control mode is currently implemented, which does not require the
models provided by the MESA-Meter specification.  The Meter class is therefore
incomplete. This is expected to be finished in upcoming versions, as feedback from
the meter will be required to implement operation modes involving closed-loop
control.  As always, [contributions](#contributions) are welcome.

#### MESA ESS
 MESA-ESS functionality, for DNP3 outstation communications, is provided by the
 [MesaAgent](https://volttron.readthedocs.io/en/develop/specifications/mesa_agent.html)
 provided in the core/DNP3Agent directory of VOLTTRON.  Various operation modes
 specified in MESA-ESS are intended to be added to this agent in upcoming releases.
 As these are added, an effort will be made to ensure seamless interaction between
 the MesaAgent and BESS Agent. Meanwhile, [contributions](#contributions) are
 welcome.  These modes, as added, will also be exposed locally to allow control
 from VOLTTRON agents without the need for external DNP3 signaling.
 
## Roadmap
#### V. 0.8:
- Allow choice of opearation modes beyond manual control.  Additional modes should
be implemented as modular, pluggable classes.
- Allow command over PubSub interface in addition to RPC. 
#### V. 0.9:
- MESA-PCS control functionality completed in Inverter.py.
#### V. 1.0:
- Remaining models implemented.
- Full MESA-Device compatibility.
- Unit tests.
#### Future Plans:
- Implement additional control modes, including those specified by MESA-ESS
incuding:
    - Volt-VAR
    - Frequency-Watt
    - Solar Smoothing
#### Contributions:
If you are interested in contributing code to improve the BESS Agent, are
are interested in testing features of the agent on new equipment, or you have
uncovered any bugs/defects which need to be addressed, please feel free to contact
the original developer, [David Raker](mailto:david.raker@utoledo.edu). 
## License

&copy;2019 The University of Toledo
   
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.