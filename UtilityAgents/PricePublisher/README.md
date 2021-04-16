# PricePublisher

Reads a csv file with time based electric price information and publishes data 
an array of the last 24-hour prices.  Current implementation assumes that price 
csv contains hourly price data.  Although the agent would work on sub-hourly 
price information it does not include a timestamp in the message payload that 
contains the array of prices, therefore the agent would need to be designed 
to utilize price information as given or this agent would need to be extended 
to include timestamp information as well as the price array.
