from dateutil.parser import parse
import datetime as dt
from collections import OrderedDict


def calculate_epoch(_dt):
    if isinstance(_dt, str):
        _dt = parse(_dt)
    _dt = _dt.replace(tzinfo=None)
    _dt = int((_dt-dt.datetime(1970, 1, 1)).total_seconds())
    return _dt


def lists_to_dict(lst1, lst2):
    dct = {}
    for item1, item2 in zip(lst1, lst2):
        dct[item1] = item2
    return dct


def sort_dict(_dict):
    list1, list2 = (list(t) for t in zip(*sorted(zip(_dict.keys(), _dict.values()))))
    d = OrderedDict()
    for key, value in zip(list1, list2):
        d[key] = value
    return d

