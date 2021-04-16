class Constant:
    ALL_NODES_ID = 0xFFFFFFFF  # Node Identifier to which all nodes listen
    HYSTERESIS = 1  # = deg. C
    MAXIMUM_ALLOWED_TEMPERATURE = (160 - 32) / 1.8  # = 71.1 deg. C
    MINIMUM_ALLOWED_TEMPERATURE = (45 - 32) / 1.8  # = 7.2 deg. C
    MPN_NODE_ID = 0x00000000  # Node Identifier to which market pricing node must listen
    OFF = 0
    ON = 1
    MY_NODE_ID = 0x00000001  # This node's unique identifier
    #                                               # Must be unique within primary pricing region.
    #                                               # Constant, assigned in manufacturing.
    MY_PPR_ID = 0x00000001  # Primary pricing region's unique identifier.
    #                                                 Constant, assigned by configuration.
