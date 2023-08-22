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
import numpy as np
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


def clean_array(array):
    array = [item for item in array if np.isfinite(item)]
    return array


def parse_df(df, condition):
    if condition == "cooling":
        data_sort = df[df['zonetemperature'] <= df["coolingsetpoint"]]
    else:
        data_sort = df[df['zonetemperature'] >= df["heatingsetpoint"]]
    data_sort_mode = df[df[condition].diff() < 0]
    if not data_sort.empty:
        idx = data_sort.index[0]
        df = df.loc[:idx]
    if not data_sort_mode.empty:
        idx = data_sort_mode.index[0]
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
    lst = [item for item in lst if item != 0]
    lst = [item for item in lst if not np.isnan(item)]
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
        self.training_interval = config.get('training_interval', 10)
        self.prestart_time = self.earliest_start_time
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
            end = offset_time(end, 60)
            _log.debug("Train Start: {} -- End: {}".format(start, end))
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
                data = parse_df(data, 'cooling')
                data.to_csv('sort1.csv')
                data['temp_diff'] = data['zonetemperature'] - data['coolingsetpoint']
                self.train_cooling(data)
            elif data['heating'].sum() > 0:
                data = parse_df(data, 'heating')
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

    def _start(self, config, schedule):
        self.c1 = clean_array(self.c1)
        self.h1 = clean_array(self.h1)
        self.latest_start_time = config.get('latest_start_time', 0)
        self.earliest_start_time = config.get('earliest_start_time', 120)
        self.t_error = config.get("allowable_setpoint_deviation", 1.0)
        self.training_interval = config.get('training_interval', 10)
        self.schedule = schedule

    def train_cooling(self, data):
        data = data[data['cooling'] != 0]
        self.c1 = clean_array(self.c1)
        htr = self.heat_transfer_rate(data)
        if htr.empty:
            _log.debug("Carrier debug cooling htr returned empty!")
            return
        time_diff, temp_diff = get_time_temp_diff(htr)
        if not time_diff:
            _log.debug("Carrier debug cooling time_diff == 0!")
            return
        c1 = temp_diff/time_diff
        if not np.isfinite(c1):
            _log.debug("C - cooling model returned non-numeric coefficients!")
            return
        self.c1 = trim(self.c1, c1, 10)
        self.record = {"date": format_timestamp(dt.now()), "c1": c1, "c1_array": self.c1}

    def train_heating(self, data):
        data = data[data['heating'] != 0]
        self.h1 = clean_array(self.h1)
        htr = self.heat_transfer_rate(data)
        if htr.empty:
            _log.debug("Carrier debug heating htr returned empty!")
            return
        time_diff, temp_diff = get_time_temp_diff(htr)
        if not time_diff:
            _log.debug("Carrier debug heating temp_diff == 0!")
            return
        h1 = temp_diff / time_diff
        if not np.isfinite(h1):
            _log.debug("C - heating model returned non-numeric coefficients!")
            return
        self.h1 = trim(self.h1, h1, 10)
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

    def _start(self, config, schedule):
        self.c1 = clean_array(self.c1)
        self.c2 = clean_array(self.c2)
        self.h1 = clean_array(self.h1)
        self.h2 = clean_array(self.h2)
        self.latest_start_time = config.get('latest_start_time', 0)
        self.earliest_start_time = config.get('earliest_start_time', 120)
        self.t_error = config.get("allowable_setpoint_deviation", 1.0)
        self.training_interval = config.get('training_interval', 10)
        self.schedule = schedule

    def train_cooling(self, data):
        data = data[data['cooling'] != 0]
        self.c1 = clean_array(self.c1)
        self.c2 = clean_array(self.c2)
        htr = self.heat_transfer_rate(data)
        if htr.empty:
            _log.debug("Siemens debug cooling htr returned empty!")
            return
        zcsp = htr['zonetemperature'][0] - htr['coolingsetpoint'][0]
        osp = htr['outdoortemperature'][0] - htr['coolingsetpoint'][0]
        # zcspf = htr['zonetemperature'][-1] - htr['coolingsetpoint'][-1]
        htr['timediff'] = htr['ts'].diff().dt.total_seconds() / 60
        time_avg = htr['timediff'].mean()
        if np.isnan(time_avg):
            _log.debug("Siemens cooling debug time_avg is nan")
            return
        precooling = htr['timediff'].sum()
        # Calculate average value of time to change degree
        c1 = time_avg / 60
        c2 = (precooling / 60 - c1 * zcsp) / (osp * zcsp / 10)
        _log.debug("S - precooling: {} - c1: {} - zcsp: {} -- osp: {}".format(precooling, self.c1, zcsp, osp))
        if not np.isfinite(c1) or not np.isfinite(c2):
            _log.debug("S: cooling model returned non-numeric coefficients!")
            return
        self.c1 = trim(self.c1, c1, 10)
        self.c2 = trim(self.c2, c2, 10)
        self.record = {"date": format_timestamp(dt.now()), "c1": c1, "c1_array": self.c1, "c2": c2, "c2_array": self.c2}

    def train_heating(self, data):
        data = data[data['heating'] != 0]
        self.h1 = clean_array(self.h1)
        self.h2 = clean_array(self.h2)
        htr = self.heat_transfer_rate(data)
        if htr.empty:
            _log.debug("Siemens debug cooling htr returned empty!")
            return
        #change htr to data?
        zhsp = htr['zonetemperature'][0] - htr['heatingsetpoint'][0]
        osp = htr['outdoortemperature'][0] - htr['heatingsetpoint'][0]
        htr['timediff'] = htr['ts'].diff().dt.total_seconds() / 60
        time_avg = htr['timediff'].mean()
        if np.isnan(time_avg):
            _log.debug("Siemens heating debug time_avg is nan")
            return
        h1 = time_avg/60.0
        preheating = htr['timediff'].sum()
        _log.debug("S - preheating: {} - h1: {} - zhsp: {} -- osp: {}".format(preheating, self.h1, zhsp, osp))
        h2 = (preheating / 60 - h1 * zhsp) / (osp * zhsp / 10)
        if not np.isfinite(h1) or not np.isfinite(h1):
            _log.debug("S - heating model returned non-numeric coefficients!")
            return
        self.h1 = trim(self.h1, h1, 10)
        self.h2 = trim(self.h2, h2, 10)
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
                zsp = zonetemp - hsp
                osp = oat - hsp
                coefficient1 = ema(self.h1)
                coefficient2 = ema(self.h2)
                start_time = (coefficient1 * zsp + coefficient2 * zsp * osp / 10.0) * 60.0 + self.adjust_time
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

    def _start(self, config, schedule):
        self.c1_list = clean_array(self.c1_list)
        self.c2_list = clean_array(self.c2_list)
        self.h1_list = clean_array(self.h1_list)
        self.h2_list = clean_array(self.h2_list)
        self.c1 = ema(self.c1_list) if self.c1_list else 0
        self.c2 = ema(self.c2_list) if self.c2_list else 0
        self.h1 = ema(self.h1_list) if self.h1_list else 0
        self.h2 = ema(self.h2_list) if self.h2_list else 0
        _log.debug("J: {} -- {} -- {} -- {} --{} -- {} --{} -- {}".format(self.c1_list, self.c1, self.c2_list, self.c2, self.h1_list, self.h1, self.h2_list, self.h2))
        self.latest_start_time = config.get('latest_start_time', 0)
        self.earliest_start_time = config.get('earliest_start_time', 120)
        self.t_error = config.get("allowable_setpoint_deviation", 1.0)
        self.training_interval = config.get('training_interval', 10)
        self.schedule = schedule

    def train_cooling(self, data):
        # cooling trained flag checked
        self.c1_list = clean_array(self.c1_list)
        self.c2_list = clean_array(self.c2_list)
        data = data[data['cooling'] != 0]
        temp_diff_begin = data['zonetemperature'][0] - data['coolingsetpoint'][0]
        # check if there is cooling data for the training data
        if not data.empty:
            htr = self.heat_transfer_rate(data)
            htr['timediff'] = htr['ts'].diff().dt.total_seconds() / 60
            precooling = htr['timediff'].sum()
            if htr.empty:
                _log.debug("Johnson debug cooling htr returned empty!")
                return
            c2 = htr['timediff'].mean()
            c1 = (precooling - c2)/(temp_diff_begin*temp_diff_begin)
            _log.debug("J - precooling: {} - c1: {} - c2: {} -- zcsp: {}".format(precooling, c1, c2, temp_diff_begin))
            if not np.isfinite(c1) or not np.isfinite(c2):
                _log.debug("J - cooling model returned non-numeric coefficients!")
                return
            if c1 != 0:
                self.c1_list = trim(self.c1_list, c1, self.training_interval)
                self.c1 = ema(self.c1_list)
            else:
                self.c1 = 0
            self.c2_list = trim(self.c2_list, c2, self.training_interval)
            self.c2 = ema(self.c2_list)
            self.record = {
                "date": format_timestamp(dt.now()), "c1": c1,
                "c1_array": self.c1_list, "c2": c2,
                "c2_array": self.c2_list
            }

    def train_heating(self, data):
        # cooling trained flag checked
        self.h1_list = clean_array(self.h1_list)
        self.h2_list = clean_array(self.h2_list)
        data = data[data['heating'] != 0]
        temp_diff_begin = data['heatingsetpoint'][0] - data['zonetemperature'][0]
        data['temp_diff'] = data['heatingsetpoint'] - data['zonetemperature']
        # check if there is cooling data for the training data
        if not data.empty:
            htr = self.heat_transfer_rate(data)
            htr['timediff'] = htr['ts'].diff().dt.total_seconds() / 60
            preheating = htr['timediff'].sum()
            if htr.empty:
                _log.debug("Johnson debug heating htr returned empty!")
                return
            h2 = htr['timediff'].mean()
            h1 = (preheating - h2)/(temp_diff_begin*temp_diff_begin)
            _log.debug("J - preheating: {} - h1: {} - h2: {} -- zhsp: {}".format(preheating, h1, h2, temp_diff_begin))
            if not np.isfinite(h1) or not np.isfinite(h2):
                _log.debug("J - heating model returned non-numeric coefficients!")
                return
            if h1 != 0:
                self.h1_list = trim(self.h1_list, h1, self.training_interval)
                self.h1 = ema(self.h1_list)
            else:
                self.h1 = 0
            self.h2_list = trim(self.h2_list, h2, self.training_interval)
            self.h2 = ema(self.h2_list)
            self.record = {
                "date": format_timestamp(dt.now()), "h1": h1,
                "h1_array": self.h1_list, "h2": h2,
                "h2_array": self.h2_list
            }

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


class Sbs(Model):
    def __init__(self, config, schedule):
        super(Sbs, self).__init__(config, schedule)
        self.e_last = 0
        self.sXY = 0
        self.sX2 = 0
        self.ctime = 0
        self.sp_error_occ = 0
        default_start = (self.earliest_start_time + self.latest_start_time)
        self.alpha = np.exp(-1/default_start)
        self.day_count = 0
        self.train_heating = self.train_cooling

    def _start(self, config, schedule):
        self.schedule = schedule

    def reset_estimation(self):
        # initialize estimation parameters
        self.sXY = 0
        self.sX2 = 0
        # resset timer
        self.ctime = 0

    def deadband(self, row):
        # apply deadband
        e_b = row['e_b']
        db = row['db']
        if np.abs(e_b) <= db/2:
            e_a = 0
        elif e_b > db / 2:
            e_a = e_b - db / 2
        else:
            e_a = e_b + db / 2
        return e_a

    def train_cooling(self, data):
        self.reset_estimation()
        data['sp'] = (data['coolingsetpoint'] + data['heatingsetpoint'])/2
        data['db'] = data['coolingsetpoint'] - data['heatingsetpoint']
        data['e_b'] = data['sp'] - data['zonetemperature']
        data['e_a'] = data.apply(self.deadband, axis=1)
        data['timediff'] = data['ts'].diff().dt.total_seconds() / 60
        time_avg = data['timediff'].mean()
        for index, row in data.iterrows():
            _log.debug("row - %s", row)
            self.ctime = self.ctime + time_avg
            # need this to start only after error has jumped due to mode change
            x = self.e_last  # + (self.sp - self.sp_last)
            y = row['e_a']
            self.sX2 = self.sX2 + x ** 2
            self.sXY = self.sXY + x * y
            _log.debug("SBS: x: %s -- e_a: %s  --sXy: %s -- sX2: %s -- alpha: %s", self.e_last, row['e_a'], self.sXY, self.sX2, self.alpha)
            # update previous values
            self.e_last = row['e_a']
        self.day_count += 1
        self.day_count = min(self.day_count, 10)
        new_alpha = None
        if self.sX2 * self.sXY > 0:
            new_alpha = self.sXY / self.sX2
            _log.debug("CALCULATE SAMPLE: {} -- {}".format(new_alpha, self.alpha))
            # put upper and lower bounds on alpha based on min/max start times
            new_alpha = max(0.001, min(0.999, new_alpha))
            # EWMA of alpha estimate
            self.alpha = self.alpha + (new_alpha - self.alpha) / self.day_count
        self.record = {"date": format_timestamp(dt.now()), "new_alpha": new_alpha, "alpha": self.alpha}

    def calculate_prestart(self, data):
        # set target setpoint and deadband
        rt = (data['coolingsetpoint'][-1] + data['heatingsetpoint'][-1])/2.0
        db = data['coolingsetpoint'][-1] - data['heatingsetpoint'][-1]
        # current room temperature
        yp = data['zonetemperature'][-1]
        # start error (adjusted by deadband)
        e0 = (rt - yp)
        db_dict = {'e_b': e0, 'db': db}
        e0 = np.abs(self.deadband(db_dict))
        # calculate time required to get error within tolerance (in units of dt)
        if e0 > 0:
            # zone_logger.info("Calculating start time with temperature error")
            prestart_time = np.log(self.t_error / e0) / np.log(self.alpha)
        else:
            prestart_time = self.latest_start_time
        # zone_logger.info("Calculating final start time")
        prestart_time = max(prestart_time, self.latest_start_time)
        prestart_time = min(prestart_time, self.earliest_start_time)
        # zone_logger.info("Calculated final start time")
        # calculate error at start time (time to occupancy in units of dt)
        self.sp_error_occ = e0 * np.power(self.alpha, self.earliest_start_time)
        _log.debug("OPTIMIZE_I: -- %s -- %s", e0, self.sp_error_occ)
        return prestart_time