u"""
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
import datetime as dt
import numpy as np


def clean_array(array):
    """
    Returns list of coefficients with nan, -inf, inf, negative
    numbers, and outliers removed.
        :param array: (list) coefficients from models
        :return: array (list)
    """
    array = [item for item in array if np.isfinite(item) and item > 0]
    if len(array) > 3:
        u = np.mean(array)
        s = np.std(array)
        if np.isfinite(u) and np.isfinite(s):
            array = [e for e in array if (u - 1.5 * s < e < u + 1.5 * s)]
    return array


def parse_df(df, condition):
    if condition == "cooling":
        data_sort = df[df['zonetemperature'] <= df["coolingsetpoint"]]
    else:
        data_sort = df[df['zonetemperature'] >= df["heatingsetpoint"]]
    df['conditioning'] = df[condition].rolling(window=10).mean()
    data_sort_mode = df[df['conditioning'] == 0]
    if not data_sort.empty:
        idx = data_sort.index[0]
        df = df.loc[:idx]
    if not data_sort_mode.empty:
        idx = data_sort_mode.index[0]
        df = df.loc[:idx]
    df = df[df[condition] > 0]
    return df


def offset_time(_time, offset):
    _offset_hr, offset_min = divmod(offset, 60)
    _hour = _time.hour + _offset_hr
    _minute = _time.minute + offset_min
    if _minute >= 60:
        _hour += 1
        _minute = _minute - 60
    ret_time = dt.time(hour=_hour, minute=_minute)
    return ret_time


def trim(lst, new_value, cutoff):
    lst.append(new_value)
    if lst and len(lst) > cutoff:
        lst.pop(0)
    # lst = [item for item in lst if item != 0]
    lst = [item for item in lst if not np.isnan(item)]
    return lst


def get_time_temp_diff(htr):
    htr['timediff'] = htr.index.to_series().diff().dt.total_seconds() / 60
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
    if _sort:
        ema += _sort[-1] * (1.0 - smoothing_constant) ** (len(lst))
    return ema


def calculate_prestart_time(end, prestart):
    _hours, _minutes = divmod(prestart, 60)
    _minutes = end.minute - _minutes
    if _minutes < 0:
        _minutes = 60 + _minutes
        _hours += 1
    _hours = end.hour - _hours
    start = dt.time(hour=_hours, minute=_minutes)
    return start