# RTU Agent

The RTU Transactive control and coordination (TCC) agent interacts with the volttron market service
as a consumer of electricity. The agent represents a RTU/HP hardware device that provides cooling/heating to a 
 building thermal zone. The RTU agent electronically “bid” on the cooling/heating capacity based on price
 and desired occupant comfort level.

Under this approach, the RTU loads respond to a price-temperature curve that essentially
relates the current energy price to the predetermined comfort expectations of building occupants.
The curve influences RTU to either reduce power load to balance cost and comfort objectives,
or in cases of abundant, economical electricity, perhaps increase consumption to perform tasks in advance,
such as pre-cooling a building.

## RTU Agent Configuration

You can specify the configuration in either json or yaml format. The json format is specified below: 

* Agent config file:

````
{
    "campus": "PNNL", 
    "building": "350_BUILDING",
    "device": "HP1A",
    "input_data_timezone": "US/Pacific",
    "control_interval": 300, 
    "agent_name": "hp1a",
    "actuation_method": "periodic",
    "market_type": "rtp",
    "actuation_enable_topic": "PNNL/350_BUILDING/Actuate",
    "actuation_enabled_onstart": true,
    "market_name": "electric",
    "static_price_flag": true,
    "static_minimum_price": 6.0,
    "static_maximum_price": 155.0,
    "inputs": [
        {
            "mapped": "sfs", 
            "point": "SupplyFanStatus", 
            "topic": "devices/PNNL/350_BUILDING/HP1A/all",
            "inital_value": 0
        }, 
        {
            "mapped": "oat", 
            "point": "OutdoorAirTemperature", 
            "topic": "devices/PNNL/350_BUILDING/HP1A/all",
            "inital_value": 75.0
        }, 
        {
            "mapped": "zt", 
            "point": "ZoneTemperature", 
            "topic": "devices/PNNL/350_BUILDING/HP1A/all",
            "inital_value": 73.0
        }, 
        {
            "mapped": "mclg", 
            "point": "FirstStageCooling", 
            "topic": "devices/PNNL/350_BUILDING/HP1A/all",
            "inital_value": 0
        }
    ], 
    "outputs": [
        {
            "mapped": "csp", 
            "point": "CoolingTemperatureSetPoint",
            "topic": "PNNL/350_BUILDING/HP1A/CoolingTemperatureSetPoint",
            "flexibility_range": [
                71.0,
                73.0
            ], 
            "off_setpoint": 80,
            "actuator": "platform.actuator", 
            "release": "None"
        }
    ], 
    "schedule": {
        "Monday": {
            "start": "6:00",
            "end": "20:00"
        }, 
        "Tuesday": {
            "start": "6:00",
            "end": "20:00"
        }, 
        "Wednesday": {
            "start": "6:00",
            "end": "20:00"
        }, 
        "Thursday": {
            "start": "6:00",
            "end": "20:00"
        }, 
        "Friday": {
            "start": "6:00",
            "end": "20:00"
        }, 
        "Saturday": "always_off", 
        "Sunday": "always_off"
    }, 
    "model_parameters": {
    }
}
````

User can create a config file using the tcc-config-web-tool: https://tcc-configuration-tool.web.app/
and follow instructions from the tcc-userguide https://tcc-userguide.readthedocs.io/en/latest/

## Install and activate VOLTTRON environment
For installing, starting, and activating the VOLTTRON environment, refer to the following VOLTTRON readthedocs: 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

## Installing and Running RTU Agent
Install and start the RTU Agent using the script install-agent.py as describe below:

```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> 
                                -c <Agent config file> \
                                -i agent.RTU \
                                -t RTU \
                                --start \
                                --force
```
, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : path of top most folder of the ILC agent

-c : path of the agent config file

-i : agent VIP identity

-t : agent tag
 
--start (optional): start after installation

--force (optional): overwrites existing ilc agent with identity "agent.RTU"  


