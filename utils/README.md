The **Clean Energy Transactive Campus (CETC)** project was led by Pacific Northwest 
National Laboratory (PNNL) and included collaboration with Washington State 
University and the University of Washington to form a multi-campus network for 
conducting research that advances transactive control of DERs. Key goals of the 
project include demonstrating that significant energy savings are possible in 
commercial buildings, and that the reliability of the power grid can be maintained 
even under large-scale integration of renewables at a regional scale by using the 
transactive control technology to coordinate a large number of distributed energy 
assets. These DERs include controllable building loads, energy storage systems 
(electric and thermal), smart inverters for photovoltaic (PV) solar systems, and 
electric vehicles. The ultimate goal of the CETC project is to address coordination 
at four physical scales: single building, single campus, multi-campus, and community 
micro-grid.

The overall objective of the CETC project was to demonstrate that transaction-based 
building controls can lead to clean energy transformation and a reliable and stable 
electric grid. To accomplish this objective, the tasks were further broken down to 
the following:

1. Establish a simulation testbed in which to test transactive control agents within a transactive network system (TNS). This testbed will be used throughout the project to test enhancements and updates to the transactive control agents.

2. Establish a multi-building testbed using buildings on the PNNL campus that can be used to test transactive control agents within a TNS. This real-building testbed will be used throughout the project to test enhancements and updates of the transactive control agents.

3. Demonstrate that Intelligent Load Control (ILC) and transactive control and coordination (TCC) agents can be successfully deployed using VOLTTRON™ to manage DERs across multiple buildings.

4. Demonstrate that a Transactive Network Template (market-clearing system) can be successfully deployed to coordinate the decentralized control decisions of devices that generate or consume electricity and also demonstrate a way to discover the “optimal” price.

5. Identify the enhancements necessary to scale ILC and TCC deployment in buildings with or without building automation systems (BASs) and in buildings configured with variable-air-volume (VAV) systems and rooftop units (RTUs).

6. Identify issues that could prevent the transactive network template and the TNS from scaling.


The repository contains applications that revolve around (and not limited to) following use cases:

- **Energy Efficiency** - The applications that help control building energy system performance. These applications perform RCx diagnostics on 
air-handling units (AHUs) and economizer systems to detect operational problems that when corrected lead to energy 
savings and improved occupant comfort

- **Grid Services** - Building-Grid Integration to support “beyond demand response” approach and integration of distributed energy resources” to grid. 
The applications include Intelligent Load Control (ILC) and Transactive ILC applications and set of market agents to 
demonstrate Transactive Network Template (TNT) framework that allows DERs to participate in utility price market and decide on "optimal" price.

- **Simulations** - Simulation support for VOLTTRON applications. The simulation agents include EnergyPlus and Modelica agents

- **UtilityAgents** - Agents that are designed to peform specific auxilliary tasks to support deployment of TCC

**_NOTE:_**  The new TENT implementation is being tested.

