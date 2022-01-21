# from importlib.util import find_spec

# if not find_spec("heat_recovery.diagnostics"):


HR1 = "Temperature Sensor Dx"
HR2 = "Not Recovering Heat When Unit Should Dx"
HR3 = "Recovering Heat When Unit Should Not Dx"
DX = "/diagnostic message"
EI = "/energy impact"

DX_LIST = [HR1, HR2, HR3]

FAN_OFF = -99.3
OAT_EAT_CLOSE = -89.21
OAT_SAT_SP_CLOSE = -89.22
OAT_LIMIT = -79.2
EAT_LIMIT = -69.2
HRT_LIMIT = -59.2
TEMP_SENSOR = -49.2


def table_log_format(name, timestamp, data):
    """ Return a formatted string for use in the log"""
    return str(str(name) + "&" + str(timestamp) + "->[" + str(data) + "]")


from .heat_recovery_correctly_off import *
from .heat_recovery_correctly_on import *
from .temperature_sensor import *
