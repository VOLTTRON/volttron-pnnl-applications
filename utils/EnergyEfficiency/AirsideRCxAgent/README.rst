.. _Airside_Agent:

=============
Airside Agent
=============

The air-side AIRCx Agent (automated identification of retro-commissioning measures)
processes use a decision-tree structure to detect, diagnose, and automatically
provide corrective actions for the problems associated with an AHU’s operation.


Featured Processes
------------------

1. **Air-Side AIRCx Main Diagnostic**

    Main Diagnostic handles all configuration management, reporting,
    and passing thresholds to the AHU diagnostics

2. **Low Supply-Air Temperature AIRCx**

    Identify the re-tuning opportunities within the SAT control strategy.

3. **High Supply-Air Temperature AIRCx**

    Identify re-tuning opportunities with the SAT control strategy.

4. **No Supply-Air Temperature Set Point Reset AIRCx**

    Identify opportunities with the SAT control strategy associated with SAT set point

5. **Unoccupied Supply-Fan Operation AIRCx**

    Identify unscheduled operation of AHUs.

6. **Low Duct Static Pressure AIRCx**

    Identify conditions when the AHU duct static pressure is too low

7. **High Duct Static Pressure AIRCx**

    Identify conditions when the AHU duct static pressure is too high

8. **No Duct Static Pressure Set Point Reset AIRCx**

    Identify conditions under which the static pressure remains constant or does not reset (change)


Running Agent
-------------

The agent is an installed Volttron agent. Sample command line for creating the agent

.. code-block:: python

   python scripts/install-agent.py -s /path/to/airside/agent
   -i airside -c /path/to/airside/config --start --force


Sample Data
-----------
Sample data for running the Economizer is included in the airside/sampledata directory


Python Testing
--------------
1. **Start Volttron Platform** - ./start-volttron from inside Volttron home
2. **Enable the Volttron Environment** - source env/bin/activate
3. **Run Pytest From inside the airside agent directory** - pytest ./test.py


Configuration Options
---------------------

The following JSON configuration file shows all the options currently supported
by this agent. A sample configuration is included with the agent

.. code-block:: python

    {
        "analysis_name": "AirsideAIRCx",
        "device": {
            "campus": "campus",
            "building": "building",
            "unit": {

                "AHU3": {
                    "subdevices": [

                        "VAV107", "VAV104",
                        "VAV116", "VAV105"

                    ]
                }
            }
        },
        "actuation_mode": "passive",
        "arguments": {
            "point_mapping": {
                "fan_status": "supplyfanstatus",
                "zone_reheat": "heatingsignal",
                "zone_damper": "damperposition",
                "duct_stcpr": "ductstaticpressure",
                "duct_stcpr_stpt": "ductstaticpressuresetpoint",
                "sa_temp": "dischargeairtemperature",
                "fan_speedcmd": "supplyfanspeed",
                "sat_stpt": "dischargeairtemperaturesetpoint"

        }
        #### Uncomment to customize thresholds (thresholds have single #)

        # "no_required_data": 10,
        # "sensitivity": custom

        ### auto_correct_flag can be set to false, "low", "normal", or "high" ###
        # "auto_correct_flag": false,
        # "warm_up_time": 5,

        ### data_window - time duration for data collection prior to analysis_name
        ### if data_window is ommitted from configuration defaults to run on the hour.

        ### Static Pressure AIRCx Thresholds ###
        # "stcpr_stpt_deviation_thr": 20
        # "warm_up_time": 5,
        # "duct_stcpr_retuning": 0.1,
        # "max_duct_stcpr_stpt": 2.5,
        # "high_sf_thr": 95.0,
        # "low_sf_thr": 20.0,
        # "zn_high_damper_thr": 90.0,
        # "zn_low_damper_thr": 10.0,
        # "min_duct_stcpr_stpt": 0.5,
        # "hdzn_damper_thr": 30.0,

        ### SAT AIRCx Thresholds ###
        # "sat_stpt_deviation_thr": 5,
        # "percent_reheat_thr": 25.0,
        # "rht_on_thr": 10.0,
        # "sat_high_damper_thr": 80.0,
        # "percent_damper_thr": 60.0,
        # "min_sat_stpt": 50.0,
        # "sat_retuning": 1.0,
        # "reheat_valve_thr": 50.0,
        # "max_sat_stpt": 75.0,

        #### Schedule/Reset AIRCx Thresholds ###
        # "unocc_time_thr": 40.0,
        # "unocc_stcpr_thr": 0.2,
        # "monday_sch": ["5:30","18:30"],
        # "tuesday_sch": ["5:30","18:30"],
        # "wednesday_sch": ["5:30","18:30"],
        # "thursday_sch": ["5:30","18:30"],
        # "friday_sch": ["5:30","18:30"],
        # "saturday_sch": ["0:00","0:00"],
        # "sunday_sch": ["0:00","0:00"],

        # "sat_reset_thr": 5.0,
        # "stcpr_reset_thr": 0.25


        }
    }
