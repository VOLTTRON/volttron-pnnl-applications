"""
Copyright (c) 2023, Battelle Memorial Institute
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
import pandas as pd
import sys
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import logging
import datetime
from datetime import timedelta as td, datetime as dt
import math
from volttron.platform.agent.utils import setup_logging, format_timestamp


setup_logging()
_log = logging.getLogger(__name__)


def parse_df(df, condition):
    data_sort = df[df['zonetemperature'] == df[condition]]
    if not data_sort.empty:
        idx = data_sort.index[0]
        df = df.loc[:idx]
    return df


def offset_time(_time, offset):
    _hour = _time.hour
    _minute = _time.minute + offset
    if _minute >= 60:
        _hour += 1
        _minute = _minute - 60
    ret_time = datetime.time(hour=_hour, minute=_minute)
    return ret_time


def trim(lst, new_value, cutoff):
    lst.append(new_value)
    if lst and len(lst) > cutoff:
        lst.pop(0)
    return lst


def get_time_temp_diff(htr):
    htr['timediff'] = htr['ts'].diff().dt.total_seconds() / 60
    time_diff = htr['timediff'].sum(axis=0)
    temp_diff = htr['temp_diff'].iloc[0] - htr['temp_diff'].iloc[-1]
    return time_diff, temp_diff


def ema(lst):
    smoothing_constant = 2.0 / (len(lst) + 1.0) * 2.0 if lst else 1.0
    smoothing_constant = smoothing_constant if smoothing_constant <= 1.0 else 1.0
    _sort = list(lst)
    _sort.sort(reverse=True)
    ema = 0
    for n in range(len(lst)):
        ema += _sort[n] * smoothing_constant * (1.0 - smoothing_constant) ** n

    ema += _sort[-1] * (1.0 - smoothing_constant) ** (len(lst))
    return ema


def calculate_prestart_time(end, prestart):
    _hours, _minutes = divmod(prestart, 60)
    _minutes = end.minute - _minutes
    if _minutes < 0:
        _minutes = 60 + _minutes
        _hours += 1
    _hours = end.hour - _hours
    start = datetime.time(hour=_hours, minute=_minutes)
    return start


class Model:
    def __init__(self, config, schedule):
        self.latest_start_time = config.get('latest_start_time', 0)
        self.earliest_start_time = config.get('earliest_start_time', 120)
        self.t_error = config.get("allowable_setpoint_deviation", 1.0)
        self.prestart_time = self.earliest_start_time
        self.cooling_trained = False
        self.heating_trained = False
        self.schedule = schedule
        self.record = {}

    def train(self, data, prestart):
        self.record = {}
        if prestart is None:
            prestart = self.earliest_start_time
        if data.empty:
            return
        _day = dt.now().weekday()
        schedule = self.schedule[_day]
        if 'start' in schedule and 'earliest' in schedule:
            end = schedule['start']
            start = calculate_prestart_time(end, prestart)
            end = offset_time(end, 30)
            _log.debug("TRAIN DEBUG: {} -- {}".format(start, end))
        else:
            _log.debug("No start in schedule!!")
            return
        data['ts'] = pd.to_datetime(data['ts'])
        data['time'] = data['ts']
        data = data.set_index(data['time'])
        data.index = pd.to_datetime(data.index)
        data = data.between_time(start, end)
        data = data[data['supplyfanstatus'] != 0]
        data.to_csv('sort.csv')
        if not data.empty:
            if data['cooling'].sum() > 0:
                data = parse_df(data, 'coolingsetpoint')
                data.to_csv('sort1.csv')
                data['temp_diff'] = data['zonetemperature'] - data['coolingsetpoint']
                self.train_cooling(data)
            elif data['heating'].sum() > 0:
                data = parse_df(data, 'heatingsetpoint')
                data.to_csv('sort1.csv')
                data['temp_diff'] = data['heatingsetpoint'] - data['zonetemperature']
                self.train_heating(data)
            else:
                print("I don't know what to do!")

    def train_cooling(self, data):
        pass

    def train_heating(self, data):
        pass

    def heat_transfer_rate(self, data):
        df_list = []
        if data.empty:
            int_tot1 = 1
        else:
            int_tot1 = int(math.ceil(data['temp_diff'][0]))

        int_tot2 = int(max(abs(data['temp_diff'] - data['temp_diff'][0])))

        if int_tot1 > int_tot2:
            int_tot = int_tot2 + 1
        else:
            int_tot = int_tot1
        for j in range(0, int_tot):
            try:
                min_slope = data[(data['temp_diff'][0] - data['temp_diff']) >= j].index[0]
                df_list.append(data.loc[min_slope])
            except (IndexError, ValueError) as ex:
                _log.debug("Model error getting heat transfer rate: %s", ex)
        if len(df_list) == 1 and int_tot > self.t_error:
            df_list.append(data.iloc[-1])
        htr = pd.concat(df_list, axis=1).T
        htr.to_csv('htr.csv')
        return htr


class Carrier(Model):
    def __init__(self, config, schedule):
        super(Carrier, self).__init__(config, schedule)
        self.c1 = config.get('c1', [])
        self.h1 = config.get('h1', [])
        self.adjust_time = config.get('adjust_time', 0)

    def train_cooling(self, data):
        htr = self.heat_transfer_rate(data)
        if htr.empty:
            _log.debug("Carrier debug cooling htr returned empty!")
            return
        time_diff, temp_diff = get_time_temp_diff(htr)
        if not time_diff:
            _log.debug("Carrier debug cooling temp_diff == 0!")
            return
        c1 = temp_diff/time_diff
        self.c1 = trim(self.c1, c1, 15)
        self.record = {"date": format_timestamp(dt.now()), "c1": c1, "c1_array": self.c1}

    def train_heating(self, data):
        htr = self.heat_transfer_rate(data)
        if htr.empty:
            _log.debug("Carrier debug heating htr returned empty!")
            return
        time_diff, temp_diff = get_time_temp_diff(htr)
        if not time_diff:
            _log.debug("Carrier debug heating temp_diff == 0!")
            return
        h1 = temp_diff / time_diff
        self.h1 = trim(self.h1, h1, 15)
        self.record = {"date": format_timestamp(dt.now()), "h1": h1, "h1_array": self.h1}

    def calculate_prestart(self, data):
        if not data.empty:
            csp = data['coolingsetpoint'][-1]
            hsp = data['heatingsetpoint'][-1]
            zonetemp = data['zonetemperature'][-1]
            oat = data['outdoortemperature'][-1]
            if zonetemp + self.t_error < hsp:
                if not self.h1:
                    return self.earliest_start_time
                zsp = hsp - zonetemp
                coefficient1 = ema(self.h1)
                start_time = zsp / ((0.0 - oat) / (0 - 32.0) * coefficient1)
            elif zonetemp - self.t_error > csp:
                if not self.c1:
                    return self.earliest_start_time
                zsp = zonetemp - csp
                coefficient1 = ema(self.c1)
                start_time = zsp / ((100 - oat) / (100 - 65) * coefficient1)
            else:
                return self.latest_start_time
        else:
            start_time = self.earliest_start_time
        self.prestart_time = start_time
        return start_time


class Siemens(Model):
    def __init__(self, config, schedule):
        super(Siemens, self).__init__(config, schedule)
        self.c1 = config.get('c1', [])
        self.c2 = config.get('c2', [])
        self.h1 = config.get('h1', [])
        self.h2 = config.get('h2', [])
        self.adjust_time = config.get('adjust_time', 0)

    def train_cooling(self, data):
        htr = self.heat_transfer_rate(data)
        if htr.empty:
            _log.debug("Siemens debug cooling htr returned empty!")
            return
        zcsp = htr['zonetemperature'][0] - htr['coolingsetpoint'][0]
        osp = htr['outdoortemperature'][0] - htr['coolingsetpoint'][0]
        # zcspf = htr['zonetemperature'][-1] - htr['coolingsetpoint'][-1]
        htr['timediff'] = htr['ts'].diff().dt.total_seconds() / 60
        time_avg = htr['timediff'].mean()
        if math.isnan(time_avg):
            _log.debug("Siemens cooling debug time_avg is nan")
            return
        precooling = htr['timediff'].sum()
        # Calculate average value of time to change degree
        c1 = time_avg / 60

        self.c1 = trim(self.c1, c1, 15)
        c2 = (precooling / 60 - c1 * zcsp) / (osp * zcsp / 10)
        self.c2 = trim(self.c2, c2, 15)
        self.record = {"date": format_timestamp(dt.now()), "c1": c1, "c1_array": self.c1, "c2": c2, "c2_array": self.c2}

    def train_heating(self, data):
        htr = self.heat_transfer_rate(data)
        if htr.empty:
            _log.debug("Siemens debug cooling htr returned empty!")
            return
        zhsp = htr['heatingsetpoint'][0] - htr['zonetemperature'][0]
        osp = - htr['heatingsetpoint'][0] - htr['outdoortemperature'][0]
        htr['timediff'] = htr['ts'].diff().dt.total_seconds() / 60
        time_avg = htr['timediff'].mean()
        if math.isnan(time_avg):
            _log.debug("Siemens heating debug time_avg is nan")
            return
        h1 = time_avg/60.0
        preheating = htr['timediff'].sum()

        self.h1 = trim(self.h1, h1, 15)
        _log.debug("preheating: {} - h1: {} - zhsp: {} -- osp: {}".format(preheating, self.h1, zhsp, osp))
        h2 = (preheating / 60 - h1 * zhsp) / (osp * zhsp / 25)
        self.h2 = trim(self.h2, h2, 15)
        self.record = {"date": format_timestamp(dt.now()), "h1": h1, "h1_array": self.h1, "h2": h2, "h2_array": self.h2}

    def calculate_prestart(self, data):
        if not data.empty:
            csp = data['coolingsetpoint'][-1]
            hsp = data['heatingsetpoint'][-1]
            zonetemp = data['zonetemperature'][-1]
            oat = data['outdoortemperature'][-1]
            if zonetemp + self.t_error < hsp:
                if not self.h1 or not self.h2:
                    return self.earliest_start_time
                zsp = hsp - zonetemp
                osp = hsp - oat
                coefficient1 = ema(self.h1)
                coefficient2 = ema(self.h2)
                start_time = (coefficient1 * zsp + coefficient2 * zsp * osp / 25.0) * 60.0 + self.adjust_time
            elif zonetemp - self.t_error > csp:
                if not self.c1 or not self.c2:
                    return self.earliest_start_time
                zsp = zonetemp - csp
                osp = oat - csp
                coefficient1 = ema(self.c1)
                coefficient2 = ema(self.c2)
                start_time = (coefficient1 * zsp + coefficient2 * zsp * osp / 10.0) * 60.0 + self.adjust_time
            else:
                return self.latest_start_time
        else:
            start_time = self.earliest_start_time
        self.prestart_time = start_time
        return start_time


class Johnson(Model):
    def __init__(self, config, schedule):
        super(Johnson, self).__init__(config, schedule)
        self.c1 = config.get('c1', 0)
        self.c2 = config.get('c2', 0)
        self.h1 = config.get('h1', 0)
        self.h2 = config.get('h2', 0)
        self.c1_list = []
        self.c2_list = []
        self.h1_list = []
        self.h2_list = []
        self.cooling_heating_adjust = config.get('cooling_heating_adjust', 0.025)

    def train_cooling(self, data):
        # cooling trained flag checked
        temp_diff_end = data['zonetemperature'][-1] - data['coolingsetpoint'][-1]
        temp_diff_begin = data['zonetemperature'][0] - data['coolingsetpoint'][0]
        if not self.cooling_trained:
            data = data[data['cooling'] != 0]
            # check if there is cooling data for the training data
            if not data.empty:
                htr = self.heat_transfer_rate(data)
                htr['timediff'] = htr['ts'].diff().dt.total_seconds() / 60
                precooling = htr['timediff'].sum()
                if htr.empty:
                    _log.debug("Johnson debug cooling htr returned empty!")
                    return
                c2 = htr['timediff'].mean()
                self.c2_list = trim(self.c2_list, c2, 15)
                c1 = (precooling - c2)/(temp_diff_begin*temp_diff_begin)
                _log.debug("precooling: {} - h1: {} - h2: {} -- zhsp: {}".format(precooling, c1, c2, temp_diff_begin))
                self.c1_list = trim(self.c1_list, c1, 15)
                self.c1 = ema(self.c1_list)
                self.c2 = ema(self.c2_list)
                self.record = {"date": format_timestamp(dt.now()), "c1": c1, "c1_array": self.c1_list, "c2": c2,
                               "c2_array": self.c2_list}
                if len(self.c1_list) >= 15:
                    self.cooling_trained = True
        else:
            if temp_diff_end > self.t_error:
                self.c1 += self.cooling_heating_adjust*2.0
            else:
                self.c1 -= self.cooling_heating_adjust
            self.record = {"date": format_timestamp(dt.now()), "c1": self.c1, "c1_array": self.c1_list, "c2": self.c2,
                           "c2_array": self.c2_list}

    def train_heating(self, data):
        # cooling trained flag checked
        temp_diff_end = data['heatingsetpoint'][-1] - data['zonetemperature'][-1]
        temp_diff_begin = data['heatingsetpoint'][0] - data['zonetemperature'][0]
        data['temp_diff'] = data['heatingsetpoint'] - data['zonetemperature']
        if not self.heating_trained:
            data = data[data['heating'] != 0]
            # check if there is cooling data for the training data
            if not data.empty:
                htr = self.heat_transfer_rate(data)
                htr['timediff'] = htr['ts'].diff().dt.total_seconds() / 60
                preheating = htr['timediff'].sum()
                if htr.empty:
                    _log.debug("Johnson debug heating htr returned empty!")
                    return
                h2 = htr['timediff'].mean()
                self.h2_list = trim(self.h2_list, h2, 15)
                h1 = (preheating - h2)/(temp_diff_begin*temp_diff_begin)
                _log.debug("preheating: {} - h1: {} - h2: {} -- zhsp: {}".format(preheating, h1, h2, temp_diff_begin))
                self.h1_list = trim(self.h1_list, h1, 15)
                self.h1 = ema(self.h1_list)
                self.h2 = ema(self.h2_list)
                self.record = {"date": format_timestamp(dt.now()), "h1": h1, "h1_array": self.h1_list,
                               "h2": h2,
                               "h2_array": self.h2_list}
                if len(self.h1_list) >= 15:
                    self.heating_trained = True
        else:
            if temp_diff_end > self.t_error:
                self.h1 += self.cooling_heating_adjust * 2.0
            else:
                self.h1 -= self.cooling_heating_adjust
            self.record = {"date": format_timestamp(dt.now()), "h1": self.h1, "h1_array": self.h1_list,
                           "h2": self.h2,
                           "h2_array": self.h2_list}

    def calculate_prestart(self, data):
        if not data.empty:
            csp = data['coolingsetpoint'][-1]
            hsp = data['heatingsetpoint'][-1]
            zonetemp = data['zonetemperature'][-1]
            if zonetemp + self.t_error < hsp:
                zsp = zonetemp - hsp
                if not self.h1_list or not self.h2_list:
                    return self.earliest_start_time
                coefficient1 = self.h1
                coefficient2 = self.h2
            elif zonetemp - self.t_error > csp:
                zsp = csp - zonetemp
                if not self.c1_list or not self.c2_list:
                    return self.earliest_start_time
                coefficient1 = self.c1
                coefficient2 = self.c2
            else:
                return self.latest_start_time
            start_time = coefficient1 * zsp * zsp + coefficient2
        else:
            start_time = self.earliest_start_time
        self.prestart_time = start_time
        return start_time

