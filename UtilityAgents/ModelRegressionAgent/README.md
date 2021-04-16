# ModelRegression Agent

Periodically performs regression for TCC agents to update the coefficients for 
the device models used to predict thermal/power characteristics for the device. 
This agent can be used to train the VAVAgent, RTUAgent, and AHUAgent TCC agents 
that were developed by PNNL.  The configuration is generic so additional 
distributed energy resources that require models to perform predictions could be 
trained using this agent.  

## ModelRegressionAgent Configuration

The json format of the config files are specified below. 

*  Agent config file:

````
{
    "campus": "",
    "building": "",
    "device": "",
    "subdevices": [],

    "subdevice_points": {
        "temp_stpt": "ZoneCoolingTemperatureSetPoint",
        "temp": "ZoneTemperature",
        "m": "ZoneAirFlow"
    },
    "device_points": {
        "oat": "OutdoorAirTemperature"
    },

    "historian_vip": "crate.prod",
    "run_schedule":  "/10080 * * * *",
    "run_onstart": True,

    # For each regregression (device/subdevice) data
    # With different timestamps will be merged and averaged
    # to the following timescale.
    # Options:  "1Min", "5Min", "15Min", "h"
    # for hourly_regression set data_aggregation_frequency='h'
    "data_aggregation_frequency": "h",

    "exclude_weekends_holidays": true,

    # Option to create hourly regression result.
    "regress_hourly": true,

    # When making predictions for zone temperature (ZT)
    # ZT(t+dt) = f(ZT(t), . . . )
    # For this case it is necessary to shift the dependent variable.
    # The shift is equal to the data_aggregation_frequency.
    # To enable this, set shift_dependent_data to true (default is false).
    "shift_dependent_data": false,

    # Number of days of data to use for training
    # Option is only valid if one_shot is set to false
    # For cron scheduled regression the end of the training data
    # will be midnight of the current day
    "training_interval": 5,

    # if one_shot is true specify start and end time for regression
    "one_shot": false,
    "start": "07/01/2019 00:00:00",
    "end": "07/15/2019 00:00:00",
    "local_tz": "US/Pacific",

    "model_structure": "M = (oat - temp) + (temp - temp_stpt)",

    # key should be left side of model_structure.  Value is evaluated based on
    # keys in subdevice_points and device_points.
    # a more complicated example could be {"ZT": "temp-temp_stpt"}
    "model_dependent": {
        "M": "m"
    },
    "model_independent": {
        "(oat - temp)": {
            "coefficient_name": "a1",
            "lower_bound": 0,
            "upper_bound": "infinity"
        },
        "(temp - temp_stpt)": {
            "coefficient_name": "a2",
            "lower_bound": 0,
            "upper_bound": "infinity"
        },
        "intercept": {
            "coefficient_name": "a3",
            "lower_bound": 0,
            "upper_bound": "infinity"
        }
    },
    "post_processing": {
          "a1": "-a2",
          "a2": "a2 - a1",
          "a3": "a1",
          "a4": "a3"
    }
}

````

## Install and activate VOLTTRON environment
For installing, starting, and activating the VOLTTRON environment, refer to the following VOLTTRON readthedocs: 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

## Installing and Running ModelRegression Agent
Install and start the ModelRegression Agent using the script install-agent.py as describe below:

```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> 
                                -c <Agent config file> \
                                -i agent.ModelRegression \
                                -t ModelRegression \
                                --start \
                                --force
```
, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : path of top most folder of the ILC agent

-c : path of the agent config file

-i : agent VIP identity

-t : agent tag
 
--start (optional): start after installation

--force (optional): overwrites existing ilc agent with identity "agent.ModelRegression"  
