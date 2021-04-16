# Transactive Control and Coordination Market Agents
The TCC agent behavior is defined by configuration.  As shown in Figure 1, the TCC agents have a
hierarchical inheritance structure: functions are encapsulated into classes at different levels.
This hierarchical structure avoids duplication of function implementation and thus significantly
simplify maintenance and upgrades.

All TCC agents inherit from the control class (transactive base class) and use a standardized
configuration format.  Agents that participate in multiple markets (e.g., the TCC AHU agent which is a
supplier of air and a consumer of electricity) and/or require the aggregate demand curve of one commodity
to determine their respective demand of the same or a different commodity also inherit from the aggregator class.

![img.png](img.png)

Figure 1.  TCC agent structure

The following configuration file is for a VAV TCC agent.


````
{
    "campus": "CAMPUS", 
    "building": "BUILDING", 
    "actuation_enable_topic": "default", 
    "input_data_timezone": "UTC", 
    "actuation_enabled_onstart": true, 
    "agent_name": "vav1", 
    "actuation_method": "periodic", 
    "control_interval": 300, 
    "market_name": "air_AHU1", 
    "inputs": [
        {
            "mapped": "sfs", 
            "point": "SupplyFanStatus", 
            "topic": "devices/CAMPUS/BUILDING/AHU1/all", 
            "inital_value": 0
        }, 
        {
            "mapped": "oat", 
            "point": "OutdoorAirTemperature", 
            "topic": "devices/CAMPUS/BUILDING/AHU1/all", 
            "inital_value": 72.0
        }, 
        {
            "mapped": "zt", 
            "point": "ZoneTemperature", 
            "topic": "devices/CAMPUS/BUILDING/AHU1/VAV1/all", 
            "inital_value": 72
        }, 
        {
            "mapped": "zdat", 
            "point": "ZoneDischargeAirTemperature", 
            "topic": "devices/CAMPUS/BUILDING/AHU1/VAV1/all", 
            "inital_value": 55.0
        }, 
        {
            "mapped": "zaf", 
            "point": "ZoneAirFlow", 
            "topic": "devices/CAMPUS/BUILDING/AHU1/VAV1/all", 
            "inital_value": 0.0
        }
    ], 
    "outputs": [
        {
            "mapped": "csp", 
            "point": "ZoneCoolingTemperatureSetPoint", 
            "topic": "CAMPUS/BUILDING/AHU1/VAV1/ZoneCoolingTemperatureSetPoint", 
            "flexibility_range": [
                550.0, 
                165.0
            ], 
            "control_flexibility": [
                70, 
                74
            ], 
            "off_setpoint": 78, 
            "actuator": "platform.actuator1",
            "release": "None", 
            "offset": 0, 
            "fallback": 72.0
        }
    ], 
    "schedule": {
        "Monday": {
            "start": "6:00",
            "end": "18:00"
        },
        "Tuesday": {
            "start": "6:00",
            "end": "18:00"
        },
        "Wednesday": {
            "start": "6:00",
            "end": "18:00"
        },
        "Thursday": {
            "start": "6:00",
            "end": "18:00"
        },
        "Friday": {
            "start": "6:00",
            "end": "18:00"
        }, 
        "Saturday": "always_off", 
        "Sunday": "always_off"
    }, 
    "model_parameters": {
        "model_type": "firstorderzone", 
        "terminal_box_type": "VAV", 
        "a1": [
            -1.9005604400483092, 
            -1.8035757207933385, 
            -1.5718448462110994, 
            -1.6130404200459123, 
            -1.6219664882233298, 
            -1.446041469455.005, 
            -99.999999999999986, 
            -9.8859312144580294, 
            -35.636563293196701, 
            -52.082799060042085, 
            -59.107921674800004, 
            -69.099847480360566, 
            -69.76018395929222, 
            -65.310615147625512, 
            -71.275421772002687, 
            -80.04159882765498, 
            -99.999999999999986, 
            -53.812948983904519, 
            -2.0183960614064329, 
            -1.5331896373826073, 
            -3.1093884007604027, 
            -2.1578469901640789, 
            -2.0935563324948823, 
            -1.9235185619427082
        ], 
        "a2": [
            1.2464835290632195, 
            1.040560210651035, 
            0.75200121944950782, 
            0.67461477145413329, 
            0.67271153164569464, 
            0.59684087980464107, 
            99.999999999999986, 
            -0.18363660872.03115, 
            28.786328626494164, 
            45.129232737418938, 
            52.466618715235114, 
            62.154560901044441, 
            63.730168042415322, 
            60.117085575095714, 
            66.500810719751513, 
            75.03847342933237, 
            95.027862593499862, 
            47.942898098251298, 
            2.0183960614064329, 
            1.5331896373826073, 
            2.9740612654390044, 
            1.8739489433885441, 
            1.6656801596001993, 
            1.4511393877503538
        ], 
        "a3": [
            0.6540769109850898, 
            0.76301551014230362, 
            0.81984362676159162, 
            0.93842564859177902, 
            0.94925495657763515, 
            0.84920058960873945, 
            6.6516751528235715e-27, 
            10.069567822669161, 
            6.8502346667025362, 
            6.953566322623149, 
            6.6413029595648858, 
            6.9452865793161225, 
            6.0300159168769003, 
            5.1935295725297967, 
            4.774611052251168, 
            5.0031253983226085, 
            4.9721374065001189, 
            5.8700508856532192, 
            2.5209253283394105e-20, 
            1.6433720968734872e-24, 
            0.1353271353255.042, 
            0.28389804677553487, 
            0.42787617289468294, 
            0.47237917419235448
        ], 
        "a4": [
            15.2103448035963, 
            17.616151837607344, 
            18.802122727671168, 
            21.976390492403411, 
            23.246289317928241, 
            20.649830678763387, 
            99.999999999999986, 
            99.999999999999986, 
            99.999999999999986, 
            99.999999999999986, 
            99.999999999999986, 
            99.999999999999986, 
            99.999999999999986, 
            99.999999999999986, 
            99.999999999999986, 
            99.999999999999986, 
            99.999999999999986, 
            99.999999999999986, 
            12.127935343760493, 
            6.9596291215056443, 
            13.147620334420724, 
            10.206736732821282, 
            11.735690109695756, 
            12.369132040424791
        ]
    }
}
````

All TCC agent configuration files have top level configurations, an inputs section, 
outputs section, schedule section, and model_parameters section.

The TCC agent top level configuration parameters contains agent identifiers (e.g., agent_name and market_name).  The TCC agent top level configurations parameters are as follows:

 * campus – string value for the campus name.  This value is used to build record topic for storage of TCC results in a local or remote database.
 * building –string value for the building name.  This value is used to build record topic for storage of TCC results in a local or remote database.


 - agent_name – string value for the agent name.  This value is used to build record topic for storage of TCC results in a local or remote database.


 - market_type – string value.  If tns is set to false the TCC will assume a single timestep market (i.e., the market clears periodically at a fixed interval).  If tns is set to true then the TCC agent will assume that the market is hourly and will project device demand for the next 24 hours at each hourly market interval.


 - market_name – the market name that the agent will participate in.  In the above example the VAV agent is a consumer of air provided by an air handling unit.  The VAV agent will submit a price-capacity curve (demand curve) to the “air2” market.


 - actuation_method – string value used to determine how the TCC agent will control.
   - market_clear – The TCC agent will send a control command to its respective device each time the market clears. 
   - periodic – The TCC agent will send a control command to the device at a fix rate (e.g., once every 10 minutes.
    

 - actuaion_enabled_onstart – boolean value.  true indicates that actuation is enabled when the agent starts.  False indicates that the agent is not enabled to actuate until it receives a message on the message bus on the topic “campus/building/actuate” with a message of true (or 1).

For aggregators (such as the AHU agent) two additional fields are required:

 - consumer_market – list of strings or string.  Name or list of names for the market(s) where the aggregator is a consumer of commodity. For the AHU agent this is the “electric”.


 - supplier_market – list of strings or string.  Name or list of names for the market(s) where the aggregator is a supplier of commodity.  For AHU agent this will is an “air” market (e.g., “air1” for AHU1).


The following describes the input parameters for one input entry:

 - topic – string value.  The topic that the driver will publish the device data.


 - point - string value.  The point name for the data.  The point name is used to identify the data point in the VOLTTRON driver data payload.


 - mapped – this is an internal parameter that is set in the TCC agents model.


 - initial_value – prior to receiving any data from the drivers the TCC agent will initialize the input to this value


The schedule section describes the building occupancy or when the device is considered ON.  
Currently, in the VAV agent during unoccupied periods the agent will assume it has zero demand 
for cooling.  Each day, Monday – Sunday, can be given a start and end time as a string 
(format should be “hh:mm” or “hh:mm:ss”), the string “always_on” for 24 hour operation, 
or the string “always_off” for days where the equipment is intended to remain off (e.g., weekends).

The following describes the outputs parameters:

 - topic – string value.  Topic for device that the TCC agent will control.  Note this topic does not contain the prefix “devices” as the topic is used to make an RPC call to the Actuator agent or building simulation engines set_point method.


 - point – string value.  The point on the device that the TCC agent will control.


 - flexibility_range – list or array.  This value bounds the demand prediction of the TCC agent.  For the VAV agent this list consists of the maximum and minimum airflow rates.  If control_flexibility is omitted from the outputs configuration then the flexibility_range is also the control_flexibility.


 - control_flexibility – list or array.  We impose a linear relationship between the price and the control action. Because the demands of individual TCC are directly determined by their control action, the relationship actually leads to price-responsive demand. Note that such a linear relationship is only selected for easy demonstration of the proposed idea and may not reflect the actual preferences of building occupants.  This behavior can be overwritten in the transactive base class (volttron-GS/pnnl/transactive/transactive.py) in the determine_control method.


 - release – string value.  If release is set to “default” then the TCC agent will store the original value of the control point and restore set point upon agent shutdown or when transitioning to unoccupied periods.  Otherwise the TCC agent will write None to the point.  Writing None will revert the point to its default value for BACnet devices and EnergyPlus simulations.


 - actuator – string value.  The vip identity of the VOLLTRON actuator agent or building simulation engine.  Defaults to “platform.actuator”.


 - mapped – this is an internal parameter that is set in the the TCC agents model.


The agent’s model_parameters section contains information necessary for the TCC agent’s model to create predictions of demand of their respective market commodity.
These parameters are not standardized and are potentially different for each different device type.
