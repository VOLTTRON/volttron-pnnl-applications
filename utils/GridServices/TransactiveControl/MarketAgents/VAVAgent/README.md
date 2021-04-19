# VAV Agent

Transactive controls and coordination (TCC) agent that interacts with the volttron market service
as a consumer of cooling/heating air that regulates cooling/heating to building zones. The AHU agent 
is the supplier of the cooling/heating air in this transactive market.

Under this approach, the VAV loads respond to a price-temperature curve that essentially
relates the current energy price to the predetermined comfort expectations of building occupants.
The curve influences AHUs to either reduce power load to balance cost and comfort objectives,
or in cases of abundant, economical electricity, perhaps increase consumption to perform tasks in advance,
such as pre-cooling a building.

## VAV Agent Configuration

You can specify the configuration in either json or yaml format. The json format is specified below:

* Agent config file:

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
User can create a config file using the tcc-config-web-tool: https://tcc-configuration-tool.web.app/
and follow instructions from the tcc-userguide https://tcc-userguide.readthedocs.io/en/latest/

## Install and activate VOLTTRON environment
For installing, starting, and activating the VOLTTRON environment, refer to the following VOLTTRON readthedocs: 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

## Installing and Running VAV Agent
Install and start the VAV Agent using the script install-agent.py as describe below:

```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> 
                                -c <Agent config file> \
                                -i agent.VAV \
                                -t VAV \
                                --start \
                                --force
```
, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : path of top most folder of the ILC agent

-c : path of the agent config file

-i : agent VIP identity

-t : agent tag
 
--start (optional): start after installation

--force (optional): overwrites existing ilc agent with identity "agent.VAV" 


