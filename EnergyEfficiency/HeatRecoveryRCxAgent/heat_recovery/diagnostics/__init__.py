# from importlib.util import find_spec

# if not find_spec("heat_recovery.diagnostics"):
from __future__ import annotations

import json
from typing import Any

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


def table_publish_format(name, timestamp, table, data):
    """ Return a dictionary for use in the results publish"""
    table_key = str(str(name) + "&" + str(timestamp))
    data = json.dumps(data)
    return [table_key, [table, data]]


class DiagnosticBase:
    def __init__(self, analysis_name: str, results_publish: List[Tuple]):
        self.analysis_name = analysis_name
        self.timestamp: List[datetime] = []

        # [table_key, [table, data]]
        self.results_publish = results_publish
        print(id(self.results_publish))


class ResultPublisher:
    @staticmethod
    def push_result(obj: DiagnosticBase | Any, data: Any, timestamp: Optional[datetime] = None):
        if timestamp is None:
            timestamp = obj.timestamp[-1]
        data = json.dumps(data)
        type(obj).mro()
        table = type(obj).__name__
        table_key = f"{table}&{str(timestamp)}"
        obj.results_publish.append((table_key, (table, data)))


from .heat_recovery_correctly_off import *
from .heat_recovery_correctly_on import *
from .temperature_sensor import *
