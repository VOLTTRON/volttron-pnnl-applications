# METER Agent
It is the transactive controls and coordination (TCC) agent that interacts with volttron market service as a electric seller.
The meter agent provides either a fixed price or fixed demand supply curve to the volttron market service. 
 
## METER Agent Configuration
You can specify the configuration in either json or yaml format. The json format is specified below:

* Agent config file:

```` 
{
    "campus": "PNNL", # if omitted defaults to ""
    "building": "BRSW", # if omitted defaults to ""
    "input_data_timezone": "UTC", # if omitted defaults to "UTC"
    "supplier_market_name": "electric",
    "tns": false,

    "agent_name": "meter",
    "inputs": [],
    "outputs": [],
    "schedule":{},

    "model_parameters": {
        "model_type": "simple"
	}
}
````
User can create a config file using the tcc-config-web-tool: https://tcc-configuration-tool.web.app/
and follow instructions from the tcc-userguide https://tcc-userguide.readthedocs.io/en/latest/

## Install and activate VOLTTRON environment
For installing, starting, and activating the VOLTTRON environment, refer to the following VOLTTRON readthedocs: 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

## Installing and Running Meter Agent
Install and start the Meter Agent using the script install-agent.py as describe below:

```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> 
                                -c <Agent config file> \
                                -i agent.Meter \
                                -t Meter \
                                --start \
                                --force
```
, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : path of top most folder of the ILC agent

-c : path of the agent config file

-i : agent VIP identity

-t : agent tag
 
--start (optional): start after installation

--force (optional): overwrites existing ilc agent with identity "agent.Meter"  


