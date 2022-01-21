import json
from pprint import pprint

from heat_recovery.analysis_config import AnalysisConfig


def test_validate_config():
    a = AnalysisConfig()
    a.validate()


def test_load_config():
    d = {
        "application": "economizer.economizer_rcx.Application",
        "device": {
            "campus": "campus",
            "building": "building",
            "unit":
                #'rtu4'
            {
                "rtu4": [
                    "ahu1",
                    "ahu2"
                ]
            }
        },
        "analysis_name": "Economizer_AIRCx",
        "actuation_mode": "PASSIVE",
        "arguments": {
            "point_mapping": {
                "supply_fan_status": "FanStatus",
                "outdoor_air_temperature": "outsideairtemp",
                "return_air_temperature": "ReturnAirTemp",
                "mixed_air_temperature": "MixedAirTemp",
                "outdoor_damper_signal": "Damper",
                "cool_call": "CompressorStatus",
                "supply_fan_speed": "SupplyFanSpeed"
            },
            "device_type": "rtu",
            "data_window": 1,
        },
        "conversion_map": [
            {"match": ".*Temperature", "datatype": "float"},
            {"match": ".*Command", "datatype": "float"},
            {"match": ".*Command", "datatype": "float"},
            {"match": ".Signal", "datatype": "float"},
            {"match": "Cooling.*", "datatype": "int"},
            {"match": "SupplyFanStatus", "datatype": "int"},
            {"match": "SupplyFanSpeed", "datatype": "int"}
        ]
    }

    a = AnalysisConfig(**d)
    a.validate()

    pprint(a)
    assert "ahu1" == a.device.unit.rtu4[0]
    # print(json.dumps(a))
    # print(a)
    # print([x for x in a.device.unit.rtu4])
