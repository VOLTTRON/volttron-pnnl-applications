# ProactiveDiagnostics Agent

Proactive AFDD is a process that involves automatically initiating changes to cause or
 to simulate operating conditions that may not occur for some time,
  thus producing results that might not be available for months otherwise.
Such tests could be automated to cover a more complete range of conditions
 or to deepen Diagnostic beyond what might be possible without this capability
 
The Proactive Diagnostic agent allows one to configure proactive diagnostics
 for nearly any building system. The control action and fault diagnostics rule sets
 are configured in form of diagnostic recipes. These recipes are contained within 
 JSON text file(s). The following example configuration is for the detection of faulty or
 inconsistent mixed-air/discharge-air temperature sensors for AHU/RTU economizer systems. 
 

## ProactiveDiagnostic Agent Configuration

In activated VOLTTRON environment, install all the ProactiveDiagnostic dependent python packages

```
cd EnergyEfficiency/ProactiveDiagnosticAgent
pip install -r requirements.txt
```
For this agent you will require two config files-
 
 1. Agent config file, and
 2. Diagnosis config file

The json format of the config files are specified below. 

*  Agent config file:

````
{
    "campus": "campus",
    "building": "building",
    "device": ["AHU1"],
    "run_schedule": "*/3 * * * *",
    "prerequisites": {
        "conditions": ["Abs(OutdoorAirTemperature - ReturnAirTemperature)>5.0", "OutdoorAirTemperature>35.0"],
        "condition_args": ["OutdoorAirTemperature", "ReturnAirTemperature"]
    },
    "diagnostics": [
        "config://diagnostic1.config"
    ]
}
````

All diagnostics in diagnostics array are run consecutively.
This is initiated based on a cron scheduling string - https://crontab.guru
Example - "0 18 * * *" is every day at 6pm

*  Diagnosis Config File:

There are two types of fault conditions -
1. all: if all conditions are "true" in the rules list, then only proactive agent sends fault code. 
Otherwise, it sends non fault code.
2. any: if atleast one of the conditions is true in the list, then it sends fault code.
Otherwise it sends non fault code. 

steady_state_interval: Time in seconds after control action to wait for steady state prior to performing analysis

data_collection_interval: Time in seconds after proactive diagnostic
            # application will perform get_point 10 times evenly space over collection interval


```json
{
    "name": "MAT_DAT_CONSISTENCY",
    "fault_code": 1,
    "non_fault_code": 0,
    "fault_condition": "all", 
    "control": [
        {
            "points": {
                "OutdoorDamperSignal": 0,
                "ChilledWaterValvePosition": 0,
                "FirstStageHeatingOutput": 0,
                "SupplyFanSpeedCommand": 100,
                "OccupancySchedule": 1,
                "SupplyFanStatusCommand": 1
            },
            "steady_state_interval": 20,
            "data_collection_interval": 20,
            "analysis": {
            
                "rule_list": ["Abs(MixedAirTemperature - DischargeAirTemperature) > 6"],
                "inconclusive_conditions_list": ["Abs(ReturnAirTemperature - OutdoorAirTemperature) > 6"],
                "points": ["MixedAirTemperature", "DischargeAirTemperature", "ReturnAirTemperature", "OutdoorAirTemperature"]
            }
        },
        {
            "points": {
                "OutdoorDamperSignal": 100,
                "ChilledWaterValvePosition": 0,
                "FirstStageHeatingOutput": 0,
                "SupplyFanSpeedCommand": 100,
                "OccupancySchedule": 1,
                "SupplyFanStatusCommand": 1
            },
            "steady_state_interval": 20,
            "data_collection_interval": 20,
            "analysis": {
                "rule_list": ["Abs(MixedAirTemperature - DischargeAirTemperature) > 6"],
                "inconclusive_conditions_list": ["Abs(ReturnAirTemperature - OutdoorAirTemperature) > 6"],
                "points": ["MixedAirTemperature", "DischargeAirTemperature", "ReturnAirTemperature", "OutdoorAirTemperature"]
            }
        }
    ]
}
````
## Install and activate VOLTTRON environment
For installing, starting, and activating the VOLTTRON environment, refer to the following VOLTTRON readthedocs: 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

## Installing and Running ProactiveDiagnostic Agent
Install and start the ProactiveDiagnostic Agent using the script install-agent.py as describe below:

```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> 
                                -c <Agent config file> \
                                -i agent.proactivediagnostic \
                                -t proactivediagnostic \
                                --start \
                                --force
```
, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : path of top most folder of the ILC agent

-c : path of the agent config file

-i : agent VIP identity

-t : agent tag
 
--start (optional): start after installation

--force (optional): overwrites existing proactivediagnostics agent with identity "agent.proactivediagnostic" 


