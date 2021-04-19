# ModelicaAgent
The Modelica agent allows co-simulation between VOLTTRON and Modelica. Unlike the EnergyPlus agent 
the Modelica agent does not start the modelica simulation, but facilitates communication between a running modelica
simulation and VOLTTRON.

The Modelica model that co-simulates with VOLTTRON must have the appropriate output and input blocks created within the
Modelica model to facilitate this co-simulation.  The documentation for this process has not yet been created but for further 
assistance one can email sen.huang@pnnl.gov for support.

## Modelica Installation
For installing setup in Linux based systems, follow the steps described in
https://sparxsystems.com/enterprise_architect_user_guide/14.0/model_simulation/installing_openmodelica_on_linux_.html

## ModelicaAgent Configuration

User can specify the configuration in either json or yaml format. The json format is specified below: 

* Agent config file:

```` 
{
    "model": "IBPSA.Utilities.IO.RESTClient.Examples.PIDTest",
    "model_runtime": 361,
    "result_file": "PIDTest",
    "mos_file_path": "/home/volttron/dymola/run_PID.mos",
    "advance_simulation_topic": "modelica/advance",
    "inputs" : {
        "control_setpoint" : {
            "name" : "control_setpoint",
            "topic" : "building/device",
            "field" : "control_setpoint"

        },
        "control_output" : {
            "name" : "control_output",
            "topic" : "building/device",
            "field" : "control_output"

        }
    },
    "outputs" : {
        "measurement" : {
            "name" : "measurement",
            "topic" : "building/device",
            "field" : "measurement",
            "meta" : {"type": "Double", "unit": "none"}
        },
        "setpoint" : {
            "name" : "setpoint",
            "topic" : "building/device",
            "field" : "control_setpoint",
            "meta" : {"type": "Double", "unit": "none"}
        }
}          
````

The "outputs" section of the agent's configuration define topics and data received from modelica where outputs with the same topic will be
combined into a single data payload of key-value pairs. The "name" in the "outputs" section  is the key and the value is the 
data from modelica for the modelica parameter "field". The "topic" in the "outputs" section represent the topic name in which data 
is going to publish on VOLTTRON message bus in the same format as the VOLTTRON MasterDriverAgent.
In "inputs" section, The "name", "field" and "topic" define as the point name, Modelica name identifier, topic name of the actuating device
respectively.

## Install and activate VOLTTRON environment
For installing, starting, and activating the VOLTTRON environment,
refer to the following VOLTTRON readthedocs:
 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

## Installing and Running Modelica Agent
Install and start the Modelica Agent using the script install-agent.py as describe below:

```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> 
                                -c <Agent config file> \
                                -i agent.Modelica \
                                -t Modelica \
                                --start \
                                --force
```

, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : path of top most folder of the ILC agent

-c : path of the agent config file

-i : agent VIP identity

-t : agent tag
 
--start (optional): start after installation

--force (optional): overwrites existing ilc agent with identity "agent.Modelica"  
