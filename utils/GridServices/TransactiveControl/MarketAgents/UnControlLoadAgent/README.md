# UnControlLoad Agent

The UncontrolLoad Transactive control and coordination (TCC) agent interacts with the volttron market service
 as a consumer electricity. This agent bids in a fixed demand curve to the volttron market service that represents
 the non-transactive (non-controllable) building load.
  

## UnControlLoad Agent Configuration

You can specify the configuration in either json or yaml format. The json format is specified below:

* Agent config file:

````
{
    "market_name": "electric",
    "campus": "CAMPUS",
    "building": "BUILDING1",
    "agent_name": "uncontrol",
    "sim_flag": true, 
    "market_type": "rtp",
    "single_market_interval": 
	"devices": {
        "LIGHTING/Basement": {
            "points": ["Power"],
            "conversion": "-Power"
        },
        "AHU1": {
            "points": ["SupplyFanPower"],
            "conversion": "-SupplyFanPower"
        },
        "Chiller1": {
            "points": ["Power"],
            "conversion": "-Power"
        },
        "METERS": {
            "points": ["WholeBuildingPower"],
            "conversion": "WholeBuildingPower"
        }
    },
    "power_20": 910.92720999999995, 
    "power_21": 620.0424549999999, 
    "power_22": 463.91088619999999, 
    "power_23": 354.8858176, 
    "power_5": 383.05938989999999, 
    "power_4": 341.89288340000002, 
    "power_7": 1046.510896, 
    "power_6": 793.5936805, 
    "power_1": 407.73100620000002, 
    "power_0": 285.74411989999999, 
    "power_3": 297.9663372, 
    "power_2": 285.74414289999999, 
    "power_9": 1002.4691770000001, 
    "power_8": 1040.259965, 
    "power_11": 973.61131440000008, 
    "power_10": 1023.4367090000001, 
    "power_13": 1054.2777890000002, 
    "power_12": 1045.760123, 
    "power_15": 1121.4733550000001, 
    "power_14": 1057.4063470000001, 
    "power_17": 1004.74153, 
    "power_16": 1112.1835679999999, 
    "power_19": 900.16603769999995, 
    "power_18": 967.11965269999996
}
````

The agent builds subscriptions to device data using  the campus, building, and devices information.  In this example
the agent subscribes to devices published on:
   ````
   devices/CAMPUS/BUILDING1/LIGHTING/Basement/all
   devices/CAMPUS/BUILDING1/AHU1/all
   devices/CAMPUS/BUILDING1/CHILLER1/all
   devices/CAMPUS/BUILDING1/METERS/all
   ````
Each of the entries in "devices" represents either a controllable load or the building level power meter.
For example, for the entry that follows the conversion field is an equation that is evaluated using the point "Power"
from the Lighting/Basement device (published by the MasterDriverAgent).

````
"LIGHTING/Basement": {
    "points": ["Power"],
    "conversion": "-Power"
}
````

All the conversion equations for each controllable load is summed as well as the building level power meter.  Since all of the controllable
loads have negative signs we get the following evaluation:

    Uncontrollable load = (Total Building Power Measurement) - (Sum of controllable loads)

When the configuration parameter "market_type" is set to "rtp" (real time price), the agent uses a exponential
forecasting to predict the uncontrollable load during the next market cycle.  If the "market_type" configuration parameter
is set to "tns", then the uncontrollable load averages and stores each hours uncontrollable load.  Since the TNS market is an 
hourly day-ahead market.  The average stored value for the previous day for the same market hour is used to produce the demand curve.
The values in the configuration file labled "power_0" - "power_23" are the initialized uncontrollable loads for the TNS market 
during the first day of predictions.

## Install and activate VOLTTRON environment
For installing, starting, and activating the VOLTTRON environment, refer to the following VOLTTRON readthedocs: 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

## Installing and Running UnControlLoadAgent Agent
Install and start the UnControlLoadAgent Agent using the script install-agent.py as describe below:

```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> 
                                -c <Agent config file> \
                                -i agent.UnControlLoadAgent \
                                -t UnControlLoadAgent \
                                --start \
                                --force
```
, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : path of top most folder of the ILC agent

-c : path of the agent config file

-i : agent VIP identity

-t : agent tag
 
--start (optional): start after installation

--force (optional): overwrites existing ilc agent with identity "agent.UnControlLoadAgent"  
