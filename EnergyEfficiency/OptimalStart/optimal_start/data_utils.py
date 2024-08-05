"""
Copyright (c) 2024, Battelle Memorial Institute
All rights reserved.
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.
This material was prepared as an account of work sponsored by an agency of the
United States Government. Neither the United States Government nor the United
States Department of Energy, nor Battelle, nor any of their employees, nor any
jurisdiction or organization that has cooperated in th.e development of these
materials, makes any warranty, express or implied, or assumes any legal
liability or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed, or
represents that its use would not infringe privately owned rights.
Reference herein to any specific commercial product, process, or service by
trade name, trademark, manufacturer, or otherwise does not necessarily
constitute or imply its endorsement, recommendation, or favoring by the
United States Government or any agency thereof, or Battelle Memorial Institute.
The views and opinions of authors expressed herein do not necessarily state or
reflect those of the United States Government or any agency thereof.
PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
"""
from __future__ import annotations
import logging
import warnings
from datetime import datetime as dt
from pathlib import Path
from typing import Optional

import pandas as pd
from dateutil import parser, tz
from volttron.platform.agent.utils import format_timestamp
from volttron.platform.messaging import headers as headers_mod

from .points import Points

warnings.filterwarnings('ignore', category=DeprecationWarning)

_log = logging.getLogger(__name__)


class DataFileAccess:

    def __init__(self, datafile: str | Path) -> None:
        if isinstance(datafile, str):
            self.datafile = Path(datafile)
        else:
            self.datafile = datafile
        _log.debug(f'Data file: {self.datafile} -- {self.datafile.as_posix()}')

    def read(self) -> Optional[pd.DataFrame]:
        return pd.read_csv(self.datafile, index_col='ts', parse_dates=True)

    def write(self, df: pd.DataFrame) -> None:
        df.to_csv(self.datafile.as_posix())

    def write_date_file(self, data: pd.DataFrame) -> None:
        _date = format_timestamp(dt.now())
        new_datafile: Path = self.datafile.parent / f'{self.datafile.stem}_{_date}.csv'
        data.to_csv(new_datafile.as_posix())
        self.datafile.unlink()

    def reset_date_file(self) -> None:
        self.datafile.unlink(missing_ok=True)


class Data:
    # TODO default config already created data_dir
    def __init__(self, *, timezone: tz.tz.tzfile, data_accessor: DataFileAccess, setpoint_offset: float | None = None):
        self.current_dt = dt.now()
        self.df = None
        self.timezone = timezone

        self._file_accessor = data_accessor
        if self._file_accessor.datafile.is_file():
            self.df = data_accessor.read()

        self.setpoint_offset = setpoint_offset

    def assign_local_tz(self, _dt: dt) -> dt:
        """
        Convert UTC time from driver to local time.
        :param _dt: datetime object
        :type _dt: datetime.datetime
        :return: localized datetime object
        :rtype: datetime.datetime
        """
        if _dt.tzinfo is None or _dt.tzinfo.utcoffset(_dt) is None:
            _log.debug(f'TZ: {_dt}')
            return _dt
        else:
            _dt = _dt.astimezone(self.timezone)
            _log.debug(f'TZ: {_dt}')
            return _dt

    def process_data(self):
        """
        Save data to disk, save 15 days of data.
        :return:
        :rtype:
        """
        try:
            self._file_accessor.write_date_file(self.df.ffill())
            self.df = None
        except Exception as ex:
            _log.debug(f'Error saving df csv!: {ex}')
            self.df = None

    def update_data(self, data: dict, header: dict):
        """
        Store current data measurements in daily data df.
        :param payload: data payload from device driver
        :type payload: dict
        :param header: header payload from device driver, contains timestamp
        :type header: dict
        :return: None
        :rtype:
        """
        _now = parser.parse(header[headers_mod.TIMESTAMP])
        stored_data = {}
        current_dt = self.assign_local_tz(_now)
        self.current_dt = current_dt
        for point in Points.values():
            if point.value in data:
                value = data[point.value]
                stored_data[point.name] = [value]

        if self.setpoint_offset is not None:
            stored_data['coolingsetpoint'][0] += self.setpoint_offset
            stored_data['heatingsetpoint'][0] -= self.setpoint_offset

        if 'warmcooladjust' in stored_data:
            stored_data['coolingsetpoint'][0] += stored_data['warmcooladjust'][0]
            stored_data['heatingsetpoint'][0] += stored_data['warmcooladjust'][0]

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
            self.append_df(stored_data, current_dt)

    def append_df(self, data: dict, current_dt: dt):
        """
        Appends a dictionary of data to a pandas DataFrame.

        :param data: dict, The dictionary of data to append to the DataFrame.
        :param current_dt: dt, The current datetime.
        :return: None
        :rtype: None
        """
        data['ts'] = [current_dt]
        df = pd.DataFrame.from_dict(data)
        df.set_index(df['ts'], inplace=True)
        if self.df is not None:
            self.df = pd.concat([self.df, df], axis=0, ignore_index=False)
            self.df = self.df.drop(columns=['ts'])
        else:
            self.df = df

        self._file_accessor.write(self.df)

    def get_current_oat(self):
        if not self.df.empty:
            if Points.outdoorairtemperature.name in self.df.columns:
                df = self.df[self.df[Points.outdoorairtemperature.name].notna()]
                return df.index[-1], df[Points.outdoorairtemperature.name].iloc[-1]
        return None, None
