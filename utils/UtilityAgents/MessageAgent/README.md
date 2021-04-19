# MessageAgent

On start, publishes a message on a configured topic with a configured message payload. 
 Intended to enable/disable actuation of the TCC control agents during a control test

## MessageAgent Configuration

The json format of the config files are specified below. 

1.  Agent config file:

````
"topic": "topic_name"
"value" : 0
````

## Install and activate VOLTTRON environment
For installing, starting, and activating the VOLTTRON environment, refer to the following VOLTTRON readthedocs: 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

## Installing and Running Message Agent
Install and start the Message Agent using the script install-agent.py as describe below:

```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> 
                                -c <Agent config file> \
                                -i agent.Message \
                                -t Message \
                                --start \
                                --force
```

, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : path of top most folder of the ILC agent

-c : path of the agent config file

-i : agent VIP identity

-t : agent tag
 
--start (optional): start after installation

--force (optional): overwrites existing ilc agent with identity "agent.Message"  
