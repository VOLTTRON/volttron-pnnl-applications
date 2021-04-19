
# PricePublisher

Reads a csv file with time based electric price information and publishes data 
an array of the last 24-hour prices.  Current implementation assumes that price 
csv contains hourly price data.  Although the agent would work on sub-hourly 
price information it does not include a timestamp in the message payload that 
contains the array of prices, therefore the agent would need to be designed 
to utilize price information as given or this agent would need to be extended 
to include timestamp information as well as the price array.

## PricePublisher Configuration

The yaml format of the config files are specified below. 

Agent config file:

```` yaml
cron_schedule: '*/5 * * * *'
price_file: /home/vuzer/transactivecontrol/MarketAgents/config/RTP/RTP-sept.csv
````

## Install and activate volttron environment
Refer following volttron readthedocs for Installing, starting and activating volttron environment: 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

## Installing and Running PricePublisher Agent
Install and start the PricePublisher Agent using the script install-agent.py as describe below:

```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> 
                                -c <Agent config file> \
                                -i agent.PricePublisher \
                                -t PricePublisher \
                                --start \
                                --force
```
, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : path of top most folder of the ILC agent

-c : path of the agent config file

-i : agent VIP identity

-t : agent tag
 
--start (optional): start after installation

--force (optional): overwrites existing ilc agent with identity "agent.PricePublisher"  

