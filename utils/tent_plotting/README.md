Scripts produce building power profile plots and distributed energy resource control plots to 
allow one to evaluate the power and control performance of building assets using TENT with direct 
actuation and ILC integrated with TENT. 

from a terminal install pandas and plotly using pip:

```sh
pip install plotly pandas
 ```

The configuration of the scripts is handled in the tent.json file:


``` {.python}
{{
    "campus": "PNNL",
    "building_db": "small_office.historian.sqlite",
    "baseline_building": "SMALL_OFFICE_VANILLA",
    "building_topic_list":  ["SMALL_OFFICE_VANILLA", "SMALL_OFFICE_ILC", "SMALL_OFFICE_DR"],
    "power_point": "WholeBuildingPower",
    "devices":{
        "heatpumps": {
            "device_list": [
                "HP1",
                "HP2",
                "HP3",
                "HP4",
                "HP5",
                "HP6",
                "HP7",
                "HP8",
                "HP9",
                "HP10"
            ],
            "device_data": {
                "ZoneCoolingTemperatureSetPoint": {
                    "secondary_axis": false,
                    "units": "Temperature (\u00B0F)",
                    "combine": true
                },
                "ZoneTemperature": {
                    "secondary_axis": false,
                    "units": "Temperature (\u00B0F)",
                    "combine": false
                },
                "FirstStageCooling": {
                    "secondary_axis": true,
                    "units": "Status",
                    "combine": false
                }
            }
        },
        "lights": {
            "device_list": [
                "LIGHTING/GS1",
                "LIGHTING/GE2",
                "LIGHTING/GN3",
                "LIGHTING/GW4",
                "LIGHTING/GC5",
                "LIGHTING/TS11",
                "LIGHTING/TE12",
                "LIGHTING/TN13",
                "LIGHTING/TW14",
                "LIGHTING/TC15"
            ],
           "device_data": {
               "DimmingLevelOutput": {
                   "secondary_axis": false,
                   "units":  "Command",
                   "combine":  true
               },
               "Power": {
                   "secondary_axis":  true,
                   "units":  "watts",
                   "combine":  false
               }
           }
        }
    }
}

```

For simulation testing there will often be a baseline for comparison to control experiment.  In this example, the baseline
is "SMALL_OFFICE_VANILLA".  If there is no baseline, remove this field from the file and omit from the "building_topic_list".
For this example, we have two different control cases, TENT integrated with ILC ("SMALL_OFFICE_ILC") and TENT with direct
actuation ("SMALL_OFFICE_DR").  The "building_topic_list" should contain a list of buildings where the name in this list
is the same as contained in the sqlite file.

The plot_transactive_record.py is intended to view the price information related to the TENT with direction actuation.  
