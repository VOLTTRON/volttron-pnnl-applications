# Monitor Agent

Monitors data coming of the message bus and evaluates rules declared in the 
configuration file.  If the rule(s) is evaluated as True, for for the 
configured duration, then a pubsub message is sent out on the alert topic 
captured by the EmailerAgent.  Intended for use in conjunction with an 
EmailerAgent. 

## MonitorAgent Configuration

The json format of the config files are specified below. 

Agent config file:

````
{   "email_list": ["user.name@gmail.com"],
    "rules": 
    [
        {
            "condition": "(ZoneTemperatureRm127>75.5) & (OccupancyMode)",
            "inputs": {
                "devices/CAMPUS/BUILDING1/HP1A/all": ["ZoneTemperatureRm127", "OutdoorAirTemperature", "OccupancyMode"]
            },
            "duration": 20,
            "alert_message": "BUILDING1 - High zone temperature HP1A Room 127",
             # This is the alert message will be send to the candidates from email list 
             # when the condition is false

            "disable_actuation": true,
            "disable_actuation_payload": {"topic": "tnc/CAMPUS/BUILDING1/HP1A", "message": 0, "header": {}}
        },
        {
            "condition": "(ZoneTemperatureRm123>75.0) & (OccupancyMode)",
            "inputs": {
                "devices/CAMPUS/BUILDING1/HP1A/all": ["ZoneTemperatureRm123", "OutdoorAirTemperature", "OccupancyMode"]
            },
            "duration": 20,
            "disable_actuation": true,
            "disable_actuation_payload": {"topic": "tnc/CAMPUS/BUILDING1/HP1A", "message": 0, "header": {}},
            "alert_message": "BUILDING1 - High zone temperature HP1A Room 123"
        },
    ]
}
````

## Install and activate VOLTTRON environment
For installing, starting, and activating the VOLTTRON environment, refer to the following VOLTTRON readthedocs: 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

## Install emailer agent
Monitor agent is intend to use with emailer agent. The emailer agent is responsible for sending emails 
with the alert message to the email list candidates.
For installing emailer agent follow the documentation and readme file of the emailer agent describe below:
https://volttron.readthedocs.io/en/develop/agent-framework/operations-agents/emailer/emailer-agent.html?highlight=emailer
https://github.com/VOLTTRON/volttron/blob/main/services/ops/EmailerAgent/README.rst

## Installing and Running Monitor Agent
Install and start the Monitor Agent using the script install-agent.py as describe below:

```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> 
                                -c <Agent config file> \
                                -i agent.Monitor \
                                -t Monitor \
                                --start \
                                --force
```
, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : path of top most folder of the ILC agent

-c : path of the agent config file

-i : agent VIP identity

-t : agent tag
 
--start (optional): start after installation

--force (optional): overwrites existing ilc agent with identity "agent.Monitor"  

