# Transactive Applications


## Transactive Control and Coordination (TCC) Application

TCC creates markets at different levels to make control decisions. Market-based
control, an example of transactive control, is a distributed control strategy.
In this document, these terms are used interchangeably. In a market-based
control system, a virtual market enables transactions between heating,
ventilation, and air-conditioning (HVAC) components for the exchange of
“commodities,” such as electric power or cooling/heating energy. Each component
is represented by an “agent” that is self-interested and tends to maximize its
own benefit. Agents submit bids for commodities based on the benefit they
receive, also referred to as the price-capacity curve in this report. The bids
from each system/component are aggregated at the building level and submitted
for clearing using the transactive network template. The market receives bids
from all agents that consume energy and from agents that supply power and
determines the clearing price of the commodity. The cleared prices are
propagated to each agent, which then adjusts its consumption based on the
cleared price. Hierarchical market-based control is distributed and scalable,
making it suitable for large-scale application.

Markets may be defined within a building by commodity (e.g., chilled water, hot
water, electricity, gas, etc.), physical relationship (e.g., all VAV boxes
connected to an air-handling unit), or some combination thereof. In this work,
we used this concept to create a market in a commercial building HVAC system
that allows zones to bid for cooling energy with the air handler and chiller,
which then bids for electricity from the electric market to generate the
necessary amount of cooling. The purpose of this system is to expose the
building’s inherent electric demand flexibility, and thus allow integration of
building operation with power system operation. The structure of our market is
bi-level—both cooled air and electricity are commodities. TCC VAV agents,
representing the thermal zones needing cool air for conditioning, purchase the
cool air from the Air Market. This market has a single supplier, the Chiller
agent, which in turn purchases the electricity it requires to generate the cool
air from the Electricity Market.

The control system is composed of a set of models, each representing separate
conditioned areas, equipment, and markets. Models are control-oriented models—all
of which are inverse empirical models—and are therefore relatively simple
compared to those used in detailed energy simulation. The developed models include

1. A zone model to predict the HVAC energy demand primarily as a function of the
outdoor dry-bulb temperature and other certain zone parameters,

2. An air handler model used to estimate fan power and cooling load given
real-time measurements from the BAS,

3. A simple chiller model that estimates the electric demand of the
district chilled water plant required to serve the cooling load calculated by
the air-handling unit, and (4) a set of RTU models for commercial buildings
that have one or more zones conditioned by packaged rooftop air conditioners or
heat pumps.
   
### Example of running Transactive control agents all together in simulation mode:

To run TCC agents all together in the simulation mode, We need to run following agents in a
volttron environment:
1. MarketService agent, 
2. EnergyPlus agent,
3. PricePublisher agent,
4. TCC agents (AHU, RTU, Lighting, Meter, VAV, etc)

* Install and activate VOLTTRON environment

For installing, starting, and activating the VOLTTRON environment, refer to the following VOLTTRON readthedocs: 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

* Market-Service agent:

The following JSON configuration file shows all the options currently supported by this agent.
````
{
    "market_period"    : 300,
    "reservation_delay": 0,
    "offer_delay"      : 120,
    "verbose_logging"  : 0
}
````
Install and start MarketService agent

````
python VOLTTRON_ROOT/scripts/install-agent.py \
    -s VOLTTRON_ROOT/services/core/MarketServiceAgent \
    -i platform.market \
    --config transactivecontrol/MarketAgents/config/BRSW/market-service-config \
    --tag market-service \
    --start \
    --force
````
, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

* Install and start Energy Plus:

Refer the readme of Energy plus agent for installing and
running EnergyPlus simulation in the VOLTTRON environment
https://github.com/VOLTTRON/volttron/tree/develop/examples/EnergyPlusAgent.

This will explain how to run building model simulations with EnergyPlus,send/receive messages backand forth between VOLTTRON
and EnergyPlus simulation.

Install and start the energy plus agent using the following command: 
````
python VOLTTRON_ROOT/scripts/install-agent.py \
    -s VOLTTRON_APPLICATION_ROOT/Simulations/EnergyplusAgent \
    -i platform.actuator \
    --tag eplus \
    --config <Agent config file> \
    --start \
    --force
````
, where VOLTTRON_ROOT, and VOLTTRON_APPLICATION_ROOT are the roots of the source directories of 
VOLTTRON and VOLTTRON_PNNL_APPLICATION respectively.

Example config file for energyplus agent can be found here: 
VOLTTRON_APPLICATION_ROOT/Simulations/EnergyplusAgent/eplus_config

For more information about EnergyPlus, please refer to https://www.energyplus.net/sites/default/files/docs/site_v8.3.0/GettingStarted/GettingStarted/index.html.
Technical documentation about the simulation framework can be found at 
https://volttron.readthedocs.io/en/develop/developing-volttron/integrating-simulations/index.html

* Install and start PricePublisher agent:

The Price publisher agent reads a csv file with time based electric price information
and publishes data an array of the last 24-hour prices.  Current implementation assumes that price 
csv contains hourly price data.  Although the agent would work on sub-hourly 
price information it does not include a timestamp in the message payload that 
contains the array of prices, therefore the agent would need to be designed 
to utilize price information as given or this agent would need to be extended 
to include timestamp information as well as the price array.
The yaml format of the config files are specified below. 

Agent config file:

```` yaml
cron_schedule: '*/5 * * * *'
price_file: /home/vuzer/transactivecontrol/MarketAgents/config/RTP/RTP-sept.csv
````
Install and start the energy plus agent using the following command:
````
python VOLTTRON_ROOT/scripts/install-agent.py \
    -s VOLTTRON_APPLICATION_ROOT/UtilityAgents/PricePublisher \
    -c  <Agent config file> \
    -t price_pub \
    -i agent.price_pub \
    --force \
    --start

````

, where VOLTTRON_ROOT and VOLTTRON_APPLICATION_ROOT are the roots of the source directories of 
VOLTTRON and VOLTTRON_PNNL_APPLICATION, respectively.

* Install and start TCC agents:

Install and start the TCC Agent using the script install-agent.py as describe below:

```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> 
                                -c <Agent config file>
                                -i agent.AHU
                                -t AHU
                                --start --force
```
, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : followed by path of top most folder of the AHU agent

-c : followed by path of the agent config file

-i : followed by agent identity

-t : followed by name tag
 
--start (optional): start after installation

--force (optional): overwrites the existing agent


## Transactive ILC Coordinator Application

This application allows ILC to participate in either real-time pricing (RTP)
markets or single-step market-based control. Further enhancements of the
TC ILC are needed to allow for its full integration with the Transactive
Network Template framework by adding the ability for the TC ILC to forecast
the building flexibility over a 24-hour horizon.

This work is under way and consists of the following:

1. Forecasting the hourly average building demand for the next 24 hours based on historical building data and current weather conditions.

2. Forecasting the hourly average flexibility of each controllable load for the next 24-hour period (i.e., an hourly average value for maximum and minimum consumptions for each controllable load) based on historical data and current weather conditions.

3. The methodology for accomplishing this is in progress and this feature should be incorporated in software tested for the June milestone.


## Transactive Network Template (TNT)

The complexity of launching a new transactive energy network is overwhelming. Successful recent examples might include Independent System Operators. These have probably been successful because 1) the rules of these markets were codified and accepted by market participants, and 2) the market networks are notably shallow in that they have but one centralized price discovery mechanism. 

How might still deeper, more distributed networks of transactive agents might be facilitated? Price discovery mechanisms and computations in these networks should become fully decentralized.  The many transactive agents that make up the distributed transactive energy networks might reside not only with load serving entities and wholesale providers who participate today, but also at many additional levels of the electricity distribution circuit—in appliances, devices, residences, businesses, industries, substations, transformers, generators, and distributed energy resources of any type. 
To facilitate the creation of distributed transactive energy networks having fully decentralized price discovery, a transactive network template was formulated. The transactive network template is a metamodel of the object classes that are needed to configure and instantiate the perspective of one transactive agent within a network of such transactive agents. The principal objects, besides the agent object itself, include models of assets that are owned by the agent, modeled representations of other neighboring transactive agents, and a market module. The principal behaviors of the system are divided among responsibilities to schedule price-responsive power, balance supply and demand, and coordinate with neighboring transactive agents using transactive signals. Reference implementations of the transactive network template may be coded in various languages and implemented on various platforms. The transactive network template may be improved to include new assets, objectives, and even price discovery mechanisms through class inheritance and extension. A key to extensibility in a network is found to be the requirement of certain basic behavioral responsibilities and information interfaces, while allowing substantial flexibility concerning just how those responsibilities are performed and how required information is calculated. 

So far, a single reference code implementation has been created using Python, and a reference field implementation has been completed on the Pacific Northwest National Laboratory (PNNL) campus. The campus network agents model the local electric municipality, the PNNL campus, and campus buildings. Prices become differentiated by hour at these locations due to time-of-use wholesale electricity prices, wholesale demand charges, distribution energy losses, municipal demand charges, dynamic demand, and the price responses of the building control systems. The primary price-responsive elements are a set of commercial building control systems. Prices and flexible demand participate in a rolling series of 24 forward hourly intervals.
Work continues to improve the transactive network template on several fronts: First, the market module is to be improved to accommodate commodities other than electricity and to demonstrate value exchange between the various commodities. Second, it must be demonstrated that the transactive network template can accommodate different alternative price discovery mechanisms and protocols.

The TNT framework has been integrated with VOLTTRON. There are three agents - CityAgent, CampusAgent and BuildingAgent representing the city, campus and building nodes. The responsibilitites of the city, campus and building nodes are encapsulated within these agents. 

The TNT framework can be made to run along with the TCC application described in the above sections. The below section provide instructions on how to run the two market frameworks together to demonstrate communication between buildings, their smart devices, the grid, and power markets to automatically and quickly negotiate power use and costs.

### Example of running Transactive control agents all together in simulation mode:
To run TNS agents all together in the simulation mode, We need to run following agents in a
volttron environment:
1. MarketService agent,
2. EnergyPlus agent,
3. TCC agents (AHU, RTU, Lighting, Meter, VAV, etc)
4. TNS agents (BuildingAgent, CampusAgent, CityAgent)

From 1 to 3 follow the example form TCC application:

* TNS agents:

Install and start the BuildingAgent using the following command: 
````
python VOLTTRON_ROOT/scripts/install-agent.py \
    -s VOLTTRON_APPLICATION_ROOT/GridServices/TransactiveControl/BuildingAgent \
    -i platform.building \
    --tag building \
    --config <Agent config file> \
    --start \
    --force
````
, where VOLTTRON_ROOT, and VOLTTRON_APPLICATION_ROOT are the roots of the source directories of 
VOLTTRON and VOLTTRON_PNNL_APPLICATION respectively.

Similarly, Campus and City agents can be installed.

Example config file for Building or City or Campus agent can be found here: 
VOLTTRON_APPLICATION_ROOT/GridServices/TransactiveControl/(BuildingAgent or CampusAgent or CityAgent)
