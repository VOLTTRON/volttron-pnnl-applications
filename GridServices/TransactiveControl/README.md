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