import logging
import re
from dateutil.parser import parse
from sympy.parsing.sympy_parser import parse_expr
from sympy import symbols
from volttron.platform.agent.utils import setup_logging

__version__ = "0.2"

setup_logging()
_log = logging.getLogger(__name__)


def parse_sympy(data, condition=False):
    """
    :param condition:
    :param data:
    :return:
    """

    def clean_text(text, rep={" ": ""}):
        rep = dict((re.escape(k), v) for k, v in rep.items())
        pattern = re.compile("|".join(rep.keys()))
        new_key = pattern.sub(lambda m: rep[re.escape(m.group(0))], text)
        return new_key

    if isinstance(data, dict):
        return_data = {}
        for key, value in data.items():
            new_key = clean_text(key)
            return_data[new_key] = value

    elif isinstance(data, list):
        if condition:
            return_data = ""
            for item in data:
                parsed_string = clean_text(item)
                parsed_string = "(" + clean_text(item) + ")" if parsed_string not in ("&", "|") else parsed_string
                return_data += parsed_string
        else:
            return_data = []
            for item in data:
                return_data.append(clean_text(item))
    else:
        return_data = clean_text(data)
    return return_data

def init_schedule(schedule):
    _schedule = {}
    if schedule:
        for day_str, schedule_info in schedule.items():
            _day = parse(day_str).weekday()
            if schedule_info not in ["always_on", "always_off"]:
                start = parse(schedule_info["start"]).time()
                end = parse(schedule_info["end"]).time()
                _schedule[_day] = {"start": start, "end": end}
            else:
                _schedule[_day] = schedule_info
    return _schedule


def check_schedule(dt, schedule):
    if not schedule:
        occupied = True
        return occupied
    current_schedule = schedule[dt.weekday()]
    if "always_on" in current_schedule:
        occupied = True
        return occupied

    if "always_off" in current_schedule:
        occupied = False
        return occupied

    _start = current_schedule["start"]
    _end = current_schedule["end"]
    if _start < dt.time() < _end:
        occupied = True
    elif dt.time() > _end:
        occupied = False
    else:
        occupied = False
    return occupied


class ClusterContainer(object):
    def __init__(self):
        self.clusters = []
        self.devices = {}

    def add_curtailment_cluster(self, cluster):
        self.clusters.append(cluster)
        self.devices.update(cluster.devices)

    def get_device_name_list(self):
        return self.devices.keys()

    def get_device(self, device_name):
        return self.devices[device_name]

    def get_power_bounds(self):
        positive_power = []
        negative_power = []
        for cluster in self.clusters:
            pos_power, neg_power = cluster.get_power_values()
            positive_power.extend(pos_power)
            negative_power.extend(neg_power)
        _log.debug("power_adders: pos {} - neg {}".format(positive_power, negative_power))
        return positive_power, negative_power

class DeviceClusters(object):
    def __init__(self, cluster_config, load_type):
        self.devices = {}
        for device_name, device_config in cluster_config.items():
            if load_type == "discreet":
                self.devices[device_name] = DiscreetLoadManager(device_config)
            elif load_type == "continuous":
                self.devices[device_name] = ContinuousLoadManager(device_config)

    def get_power_values(self):
        positive_power = []
        negative_power = []
        for device_id, device in self.devices.items():
            pos_power, neg_power = device.get_power_values()
            positive_power.extend(pos_power)
            negative_power.extend(neg_power)
        return positive_power, negative_power

class DiscreetLoadManager(object):
    def __init__(self, device_config):
        self.command_status = {}
        self.device_power = {}
        self.device_status_args = {}
        self.sop_args = {}
        self.sop_expr = {}
        self.expr = {}

        self.condition = {}
        self.sop_condition = {}

        self.points = {}
        self.sop_points = {}
        self.rated_power = {}
        self.positive_power = {}
        self.negative_power = {}
        for device_id, config in device_config.items():
            rated_power = config['rated_power']
            device_dict = config.pop('parameters')

            device_status_args = parse_sympy(device_dict['discreet_on_condition_args'])
            condition = device_dict['discreet_on_condition']

            self.device_status_args[device_id] = device_status_args
            self.condition[device_id] = parse_sympy(condition, condition=True)
            self.points[device_id] = symbols(device_status_args)
            self.expr[device_id] = parse_expr(self.condition[device_id])
            pos_sop_condition = device_dict.get("pos_sop", "")
            neg_sop_condition = device_dict.get("neg_sop", "")
            sop_args = parse_sympy(device_dict['sop_args'])
            self.sop_args[device_id] = sop_args
            self.sop_condition[device_id] = [parse_sympy(pos_sop_condition), parse_sympy(neg_sop_condition)]
            self.sop_points[device_id] = symbols(sop_args)

            self.sop_expr[device_id] = [parse_expr(sop_cond) if sop_cond else False for sop_cond in self.sop_condition[device_id]]

            self.command_status[device_id] = False
            self.device_power[device_id] = 0.
            self.rated_power[device_id] = rated_power
            self.negative_power[device_id] = 0.
            self.positive_power[device_id] = 0.

    def ingest_data(self, data):
        for device_id in self.rated_power:
            conditional_points = []
            sop_points = []

            for item in self.device_status_args[device_id]:
                conditional_points.append((item, data[item]))

            for item in self.sop_args[device_id]:
                sop_points.append((item, data[item]))

            conditional_value = False
            sop_values = []
            if conditional_points:
                conditional_value = self.expr[device_id].subs(conditional_points)
            for expr in self.sop_expr[device_id]:
                if sop_points and expr or not self.sop_args[device_id]:
                    sop_values.append(expr.subs(sop_points))
                elif not expr:
                    sop_values.append(0.)

            _log.debug('{} - {} (device status) evaluated to {}'.format(device_id, self.condition[device_id], conditional_value))
            _log.debug('{} - {} (device power) evaluated to {}'.format(device_id, self.sop_condition[device_id], sop_values))
            try:
                self.command_status[device_id] = bool(conditional_value)
            except TypeError:
                self.command_status[device_id] = False
            self.determine_power_adders(device_id, sop_values)

    def get_power_values(self):
        return self.positive_power.values(), self.negative_power.values()

    def determine_power_adders(self, device_id, sop):
        sop = [min(max(0.0, value), 1.0) for value in sop]
        status = self.command_status[device_id]

        if status:
            self.positive_power[device_id] = 0
            self.negative_power[device_id] = float(sop[1]) * self.rated_power[device_id]
        else:
            self.positive_power[device_id] = float(sop[0]) * self.rated_power[device_id]
            self.negative_power[device_id] = 0

        _log.debug("{} - Negative Power: {} - sop: {}".format(device_id, self.negative_power, sop))
        _log.debug("{} - Positive Power: {} - sop: {}".format(device_id, self.positive_power, sop))


class ContinuousLoadManager(object):
    def __init__(self, device_config):

        self.device_power = {}
        self.sop_args = {}
        self.condition = {}
        self.sop_condition = {}
        self.points = {}
        self.sop_points = {}
        self.rated_power = {}
        self.positive_power = {}
        self.negative_power = {}
        self.sop_expr = {}
        for device_id, config in device_config.items():
            rated_power = config['rated_power']
            device_dict = config.pop('parameters')

            pos_sop_condition = device_dict.get("pos_sop", "")
            neg_sop_condition = device_dict.get("neg_sop", "")
            sop_args = parse_sympy(device_dict['sop_args'])
            self.sop_args[device_id] = sop_args
            self.sop_condition[device_id] = [parse_sympy(pos_sop_condition), parse_sympy(neg_sop_condition)]
            self.sop_points[device_id] = symbols(sop_args)
            self.sop_expr[device_id] = [parse_expr(sop_cond) if sop_cond else False for sop_cond in self.sop_condition[device_id]]

            self.device_power[device_id] = 0.
            self.rated_power[device_id] = rated_power
            self.negative_power[device_id] = 0.
            self.positive_power[device_id] = 0.

    def ingest_data(self, data):
        for device_id in self.rated_power:
            sop_points = []
            for item in self.sop_args[device_id]:
                sop_points.append((item, data[item]))
            sop_values = []
            for expr in self.sop_expr[device_id]:
                if sop_points and expr or not self.sop_args[device_id]:
                    sop_values.append(expr.subs(sop_points))
                elif not expr:
                    sop_values.append(0)
            _log.debug('{} (device power) evaluated to {}'.format(self.sop_condition[device_id], sop_values))
            self.determine_power_adders(device_id, sop_values)

    def get_power_values(self):
        return self.positive_power.values(), self.negative_power.values()

    def determine_power_adders(self, device_id, sop):
        sop = [min(max(0.0, value), 1.0) for value in sop]

        self.negative_power[device_id] = float(sop[1]) * self.rated_power[device_id]
        self.positive_power[device_id] = float(sop[0]) * self.rated_power[device_id]

        _log.debug("{} - Negative Power: {} - sop: {}".format(device_id, self.negative_power, sop))
        _log.debug("{} - Positive Power: {} - sop: {}".format(device_id, self.positive_power, sop))
