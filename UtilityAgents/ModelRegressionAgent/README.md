# ModelRegression Agent

Periodically performs regression for TCC agents to update the coefficients for 
the device models used to predict thermal/power characteristics for the device. 
This agent can be used to train the VAVAgent, RTUAgent, and AHUAgent TCC agents 
that were developed by PNNL.  The configuration is generic so additional 
distributed energy resources that require models to perform predictions could be 
trained using this agent.  