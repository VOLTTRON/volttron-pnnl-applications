import os
import logging
import pandas as pd
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
from datetime import datetime as dt, timedelta as td
from dateutil import parser, tz
from volttron.platform.agent.utils import setup_logging, format_timestamp
from volttron.platform.messaging import topics, headers as headers_mod

setup_logging()
_log = logging.getLogger(__name__)


class Data:
    def __init__(self, points, timezone, tag, data_dir=""):
        self.points = points
        self.current_time = dt.now()
        self.df = None
        try:
            self.local_tz = tz.gettz(timezone)
        except:
            self.local_tz = tz.gettz("UTC")
        if data_dir:
            data_file = data_dir + "/data_{}.csv".format(tag)
        else:
            data_dir = os.path.expanduser("~/optimal_start")
            data_file = data_dir + "/data_{}.csv".format(tag)
        self.data_path = data_dir
        self.tag = tag
        _log.debug("Data file: {}".format(data_file))
        if os.path.isfile(data_file):
            try:
                self.df = pd.read_csv(data_file)

            except Exception as ex:
                _log.debug("No previous dataframe object: %s", ex)

    def assign_local_tz(self, _dt):
        """
        Convert UTC time from driver to local time.
        """
        if _dt.tzinfo is None or _dt.tzinfo.utcoffset(_dt) is None:
            _log.debug("TZ: %s", _dt)
            return _dt
        else:
            _dt = _dt.astimezone(self.local_tz)
            _log.debug("TZ: %s", _dt)
            return _dt

    def process_data(self):
        """
        Save data to disk, save 15 days of data.
        """
        _date = format_timestamp(dt.now())
        data_file = self.data_path + + "/data_{}_{}.csv".format(self.tag, _date)
        try:
            self.df.to_csv(data_file)
            self.df = None
        except Exception as ex:
            _log.debug("Error saving df csv!: %s", ex)
            self.df = None

    def update_data(self, payload, header):
        """
        Store current data measurements in daily data df.
        """
        data, meta = payload
        _now = parser.parse(header[headers_mod.TIMESTAMP])
        stored_data = {}
        current_time = self.assign_local_tz(_now)
        self.current_time = current_time
        for point, value in data.items():
            if point in self.points.values():
                _key = list(filter(lambda x: self.points[x] == point, self.points))[0]
                stored_data[_key] = [value]
        if 'reversingvalve' in stored_data and 'compressorcommand' in stored_data:
            vlv = stored_data['reversingvalve'][0]
            comp = stored_data['compressorcommand'][0]
            if not comp:
                stored_data['heating'] = [0]
                stored_data['cooling'] = [0]
            else:
                if not vlv:
                    stored_data['heating'] = [1]
                    stored_data['cooling'] = [0]
                else:
                    stored_data['heating'] = [0]
                    stored_data['cooling'] = [1]

        if stored_data:
            stored_data['ts'] = [current_time]
            df = pd.DataFrame.from_dict(stored_data)
            df['timeindex'] = df['ts']
            df = df.set_index(df['timeindex'])
            if self.df is not None:
                self.df = pd.concat([self.df, df], axis=0, ignore_index=False)
            else:
                self.df = df
            data_path = self.data_path + "/data_{}.csv".format(self.tag)
            self.df.to_csv(data_path)
