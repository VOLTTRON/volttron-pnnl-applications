# Intelligent Load Control (ILC) Agent

ILC supports traditional demand response as well as transactive energy
services. ILC manages controllable loads while also mitigating
service-level excursions (e.g., occupant comfort, minimizing equipment
ON/OFF cycling) by dynamically prioritizing available loads for curtailment
using both quantitative (deviation of zone conditions from set point) and
qualitative rules (type of zone).

## ILC Agent Configuration

The  ILC agent, requires four configuration files per device cluster (i.e., homogenous set of devices).  These
files should be loaded into the agent's config store via vctl config command line interface.  The files are as follows:
 1. config - ILC (main) configuration.  This file is loaded into the agent's config store with 
    cannonical name "config"
 2. device_control_config - Contains information related to the control of device cluster.  File reference, as shown
    in the example ILC "config" below is with respect to the config store with configuration name "control_config". 
 3. device_criteria_config - Contains information related to the use of real time data to prioritize devices within cluster for
    load management.  File reference, as shown in the example ILC "config" below is with respect to the config store 
    with configuration name "criteria_config". 
 4. pairwise_criteria_config - Contains information related to the relative importance of each criteria for a device cluster.
    File reference, as shown in the example ILC "config" below is with respect to the config store 
    with configuration name "pairwise_criteria.json".
 
A web-based configuration tool has been developed to simplify creation of the configuration files for ILC.
The web tool can be accessed at: 

https://ilc-configuration-tool.web.app/

Instructions for the configuration web-tool can be found here: 

https://userguide-ilc.readthedocs.io/en/latest/

Examples of each configuration file are as follows - 

*  ILC "config":

````
{
    "campus": "CAMPUS",
    "building": "BUILDING",
    "power_meter": {
        "device_topic": "CAMPUS/BUILDING/METERS",
        "point": "WholeBuildingPower",
         "demand_forumla": {
            "operation": "Abs(WholeBuildingPower)",
            "operation_args": ["WholeBuildingPower"]
         }
    },
    "agent_id": "ILC",
    "demand_limit": 30.0,
    "control_time": 20.0,
    "curtailment_confirm": 5.0,
    "curtailment_break": 20.0,
    "average_building_power_window": 15.0,
    "stagger_release": true,
    "stagger_off_time": true,
    "clusters": [ 
        {
            "device_control_config": "config://control_config",
            "device_criteria_config": "config://criteria_config",
            "pairwise_criteria_config": "config://pairwise_criteria.json",
            "cluster_priority": 1.0
        }
    ]
 }

````

* device_control_config:  

````
{
    "HP1": {
        "FirstStageCooling": {
            "device_topic": "CAMPUS/BUILDING/HP1",
            "device_status": {
                "curtail": {
                    "condition": "FirstStageCooling", 
                    "device_status_args": ["FirstStageCooling"]
                },
                "augment": {
                    "condition": "FirstStageCooling < 1",
                    "device_status_args": ["FirstStageCooling"]
                }
            },
            "curtail_settings": {
                "point": "ZoneTemperatureSetPoint",
                "curtailment_method": "offset",
                "offset": 2.0,
                "load": 6.0
            },
            "augment_settings": {
                "point": "ZoneTemperatureSetPoint",
                "curtailment_method": "offset",
                "offset": -2.0,
                "load": 6.0
            }
        }
    },
    "HP2": {
        "FirstStageCooling": {
            "device_topic": "CAMPUS/BUILDING/HP2",
            "device_status": {
                "curtail": {
                    "condition": "FirstStageCooling",
                    "device_status_args": ["FirstStageCooling"]
                },
                "augment": {
                    "condition": "FirstStageCooling < 1",
                    "device_status_args": ["FirstStageCooling"]
                }
            },
            "curtail_settings": {
                "point": "ZoneTemperatureSetPoint",
                "curtailment_method": "equation",
                "equation": {
                    "operation": "ZoneTemperature+0.5",
                    "equation_args": ["ZoneTemperature"],
                    "minimum": 69.0,
                    "maximum": 77.0
                },
                "load": 6.5
            },
            "augment_settings": {
                "point": "ZoneTemperatureSetPoint",
                "curtailment_method": "value",
                "value": 69.0,
                "load": 6.5
            }
        }
    }
}

````
* device_criteria_config:

In this configuration, any number of relevant criteria can be defined to prioritize loads for curtailment (reducing) 
or augmentation (increasing) a building's electricity consumption. In the following example, five criteria are used;
 1. zonetemperature-setpoint,
 2. rated-power,
 3. room-type,
 4. stage,
 5. history-zonetemperature.
 
These criteria are differentiated  by their operation type.  The five different types of criteria are formula, status, 
mapper, constant, and history.  In the configuration that follows, an example for each type of criteria is given:
   
````
{
    "HP1": {
        "FirstStageCooling": {
            "curtail": {
                "device_topic": "CAMPUS/BUILDING/HP1",
                "zonetemperature-setpoint":{
                    "operation": "1/(AverageZoneTemperature-CoolingTemperatureSetPoint)",
                    "operation_type": "formula",
                    "operation_args": {
                                        "always": ["CoolingTemperatureSetPoint", "AverageZoneTemperature"]
                                      },
                    "minimum": 0,
                    "maximum": 10
                },
                "rated-power": {
                    "on_value": 6.0,
                    "off_value": 0.0,
                    "operation_type": "status",
                    "point_name": "FirstStageCooling"
                },
                "room-type": {
                    "map_key": "Office",
                    "operation_type": "mapper",
                    "dict_name": "zone_type"
                },
                "stage": {
                    "value": 1.0,
                    "operation_type": "constant"
                },
                "history-zonetemperature": {
                    "comparison_type": "direct",
                    "operation_type": "history",
                    "point_name": "AverageZoneTemperature",
                    "previous_time": 15,
                    "minimum": 0,
                    "maximum": 10
                }
            },
            "augment": {
                "device_topic": "CAMPUS/BUILDING/HP1",
                "zonetemperature-setpoint":{
                    "operation": "1/(CoolingTemperatureSetPoint-AverageZoneTemperature)",
                    "operation_type": "formula",
                    "operation_args": {
                        "always": ["CoolingTemperatureSetPoint", "AverageZoneTemperature"],
                        "nc": ["
                    },
                    "minimum": 0,
                    "maximum": 10
                },
                "rated-power": {
                    "on_value": 0.0,
                    "off_value": 6.0,
                    "operation_type": "status",
                    "point_name": "FirstStageCooling"
                },
                "room-type": {
                    "map_key": "Office",
                    "operation_type": "mapper",
                    "dict_name": "zone_type"
                },
                "stage": {
                    "value": 1.0,
                    "operation_type": "constant"
                },
                "history-zonetemperature": {
                    "comparison_type": "direct",
                    "operation_type": "history",
                    "point_name": "AverageZoneTemperature",
                    "previous_time": 15,
                    "minimum": 0,
                    "maximum": 10
                }
            }
        }
    },
    "HP2": {
        "FirstStageCooling": {
            "curtail": {
                "device_topic": "CAMPUS/BUILDING/HP2",
                "zonetemperature-setpoint":{
                    "operation": "1/(AverageZoneTemperature-CoolingTemperatureSetPoint)",
                    "operation_type": "formula",
                    "operation_args": ["CoolingTemperatureSetPoint", "AverageZoneTemperature"],
                    "minimum": 0,
                    "maximum": 10
                },
                "rated-power": {
                    "on_value": 4.4,
                    "off_value": 0.0,
                    "operation_type": "status",
                    "point_name": "FirstStageCooling"
                },
                "room-type": {
                    "map_key": "Office",
                    "operation_type": "mapper",
                    "dict_name": "zone_type"
                },
                "stage": {
                    "value": 1.0,
                    "operation_type": "constant"
                },
                "history-zonetemperature": {
                    "comparison_type": "direct",
                    "operation_type": "history",
                    "point_name": "AverageZoneTemperature",
                    "previous_time": 15,
                    "minimum": 0,
                    "maximum": 10
                }
            },
            "augment": {
                "device_topic": "CAMPUS/BUILDING/HP2",
                "zonetemperature-setpoint":{
                    "operation": "1/(CoolingTemperatureSetPoint-AverageZoneTemperature)",
                    "operation_type": "formula",
                    "operation_args": ["CoolingTemperatureSetPoint", "AverageZoneTemperature"],
                    "minimum": 0,
                    "maximum": 10
                },
                "rated-power": {
                    "on_value": 0.0,
                    "off_value": 4.4,
                    "operation_type": "status",
                    "point_name": "FirstStageCooling"
                },
                "room-type": {
                    "map_key": "Office",
                    "operation_type": "mapper",
                    "dict_name": "zone_type"
                },
                "stage": {
                    "value": 1.0,
                    "operation_type": "constant"
                },
                "history-zonetemperature": {
                    "comparison_type": "direct",
                    "operation_type": "history",
                    "point_name": "AverageZoneTemperature",
                    "previous_time": 15,
                    "minimum": 0,
                    "maximum": 10
                }
            }
        }
    },
    "mappers": {
        "zone_type": {
            "Private Office": 1,
            "Office": 3,
            "Conference Room": 5,
            "Lobby": 9,
            "Restroom": 9
        }
    }
}
````
* pariwise_criteria_config:

The relative importance of the two criteria is measured and evaluated
according to a numerical scale from 1 to 9. The higher the value, the more important the corresponding criterion is. Pair-wise
comparison is conducted to determine qualitatively which criteria are more important and assign to each
criterion a qualitative weight.

For more detail about pair-wise criteria, please refer section 2.0 of the following documentation:
https://www.pnnl.gov/main/publications/external/technical_reports/PNNL-26034.pdf

```
{
    "curtail": {
        "history-zonetemperature": {
            "room-type": 5,
            "rated-power": 3
        },
        "room-type": {},
        "rated-power": {
            "room-type": 3
        },
        "zonetemperature-setpoint": {
            "history-zonetemperature": 5,
            "room-type": 8,
            "rated-power": 6,
            "stage": 2
        },
        "stage": {
            "history-zonetemperature": 3,
            "room-type": 6,
            "rated-power": 4
        }
    },
    "augment": {
        "history-zonetemperature": {
            "room-type": 5,
            "rated-power": 3
        },
        "room-type": {},
        "rated-power": {
            "room-type": 3
        },
        "zonetemperature-setpoint": {
            "history-zonetemperature": 5,
            "room-type": 8,
            "rated-power": 6,
            "stage": 2
        },
        "stage": {
            "history-zonetemperature": 3,
            "room-type": 6,
            "rated-power": 4
        }
    }
}
```

## Install and activate VOLTTRON environment
For installing, starting, and activating the VOLTTRON environment, refer to the following VOLTTRON readthedocs: 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

## Install ILC config file using VOLTTRON config store:

To store ILC configuration files in the Configuration Store use the following store sub-command: 

```
vctl cofig store <ILC agent VIP> <config name> <path of config file>
```

Using the previous example configurations, the commands would be as follows
 (assuming the ILC agents VIP identity is ilc.agent):

```
vctl config store ilc.agent config <path of config file>
vctl config store ilc.agent control_config <path to device_control_config>
vctl config store ilc.agent criteria_config <path to device_criteria_config>
vctl config store ilc.agent pairwise_criteria.json <path to pairwise_criteria_config>
```

Other sub-commands of "config store command-line" tool can be found here: 
https://volttron.readthedocs.io/en/develop/platform-features/config-store/commandline-interface.html

## Installing and Running ILC Agent
Install and start the ILC Agent using the script install-agent.py as describe below:
```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> \
                                -i ilc.agent \
                                -t ilc \
                                --start \
                                --force
```
where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : path of top most folder of the ILC agent

-i : agent VIP identity

-t : agent tag
 
--start (optional): start after installation

--force (optional): overwrites existing ilc agent with identity <ILC agent VIP> 
