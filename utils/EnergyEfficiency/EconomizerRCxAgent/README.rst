.. _Economizer_Agent:

================
Economizer Agent
================

Economizer Agent helps in the re-tuning process and addresses some of the issues
associated with RCx. RCx is known to save energy consumption , but the process
used is not cost-effective.  Economizer Agent and it's diagnostics allow continuous
re-tuning and problem identification which can lower the costs of RCx


Featured Diagnostics
--------------------

1. **Economizer Control AIRCx Main Diagnostic**

    Main Diagnostic handles all configuration management, reporting,
    and passing thresholds to the AHU diagnostics

2. **Air Temperature Sensor Fault AIRCx**

    Checks for consistency between outdoor-air temperature and
    mixed-air temperature when the outdoor air damper is fully open

3. **AHU is not Fully Economizing When It Should AIRCx**

    Determines whether the economizer is ON and working properly
    when conditions are favorable for economizing.

4. **Economizing When It Should Not AIRCx**

    Determines whether the AHU is economizing when the outdoor
    conditions are not favorable for economizing.  The AHU is
    considered to be in the economizer mode when the outdoor-air
    damper position and OAF exceed their minimum threshold values.

5. **Excess Outdoor-air Intake AIRCx**

    Determines whether the AHU is introducing excess outdoor air
    beyond the minimum ventilation requirements when the outdoor-air
    damper should be at the minimum position.  Conditions are not
    favorable for economizing, and there is no call for cooling the
    zones served by the unit.

6. **Insufficient Outdoor-air Ventilation Intake AIRCx**

    Determines whether the AHU is providing sufficient outdoor air,
    and therefore the minimum ventilation requirements are met


Running Agent
-------------

The agent is an installed Volttron agent. Sample command line for creating the agent

.. code-block:: python

   python scripts/install-agent.py -s /path/to/economizer/agent
   -i economizer -c /path/to/economizer/confi --start --force


Sample Data
-----------
Sample data for running the Economizer is included in the economizer/sampledata directory


Python Testing
--------------
1. **Start Volttron Platform** - ./start-volttron from inside Volttron home
2. **Enable the Volttron Environment** - source env/bin/activate
3. **Run Pytest From inside the economizer agent directory** - pytest ./test.py


Configuration Options
---------------------

The following JSON configuration file shows all the options currently supported
by this agent. A sample configuration is included with the agent

.. code-block:: python

    {
        "application": "economizer.economizer_rcx.Application",
        "device": {
            "campus": "campus",
            "building": "building",
            "unit": {
                "rtu4": {
                    "subdevices": []
                }
            }
        },
        "analysis_name": "Economizer_AIRCx",
        "actuation_mode": "PASSIVE",
        "arguments": {
            "point_mapping": {
                "supply_fan_status": "FanStatus",
                "outdoor_air_temperature": "outsideairtemp",
                "return_air_temperature": "ReturnAirTemp",
                "mixed_air_temperature": "MixedAirTemp",
                "outdoor_damper_signal": "Damper",
                "cool_call": "CompressorStatus",
                "supply_fan_speed": "SupplyFanSpeed"
            },
            "device_type": "rtu",
            "data_window": 1,
            "no_required_data": 1,
            "open_damper_time": 0,
            "low_supply_fan_threshold": 20.0,
            "mat_low_threshold": 50.0,
            "mat_high_threshold": 90.0,
            "oat_low_threshold": 30.0,
            "oat_high_threshold": 100.0,
            "rat_low_threshold": 50.0,
            "rat_high_threshold": 90.0,
            "temp_difference_threshold": 4.0,
            "open_damper_threshold": 90.0,
            "oaf_temperature_threshold": 4.0,
            "cooling_enabled_threshold": 5.0,
            "minimum_damper_setpoint": 10.0,
            "desired_oaf": 10.0,
            "rated_cfm": 1000.0,
            "eer": 10.0,
            "economizer_type": "DDB",
            "temp_band": 1.0
        },
        "conversion_map": {
            ".*Temperature": "float",
            ".*Command": "float",
            ".*Signal": "float",
            "SupplyFanStatus": "int",
            "Cooling.*": "float",
            "SupplyFanSpeed": "int"
        }
    }

