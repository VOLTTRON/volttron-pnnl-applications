# Monitor Agent

Monitors data coming of the message bus and evaluates rules declared in the 
configuration file.  If the rule(s) is evaluated as True, for for the 
configured duration, then a pubsub message is sent out on the alert topic 
captured by the EmailerAgent.  Intended for use in conjunction with an 
EmailerAgent. 
