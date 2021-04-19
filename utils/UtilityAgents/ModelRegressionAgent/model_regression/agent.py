# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2019, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}

import os
import sys
import logging
from collections import defaultdict, OrderedDict
from datetime import datetime as dt, timedelta as td
from dateutil import parser

import json
from scipy.optimize import lsq_linear
from volttron.platform.vip.agent import Agent, Core, PubSub, RPC
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)
from volttron.platform.scheduling import cron
from volttron.platform.messaging import topics

import numpy as np
import pandas as pd
import patsy

from pandas.tseries.offsets import CustomBusinessDay
from pandas.tseries.holiday import USFederalHolidayCalendar as calendar
import scipy
import pytz
import re


utils.setup_logging()
_log = logging.getLogger(__name__)
UTC_TZ = pytz.timezone('UTC')
WORKING_DIR = os.getcwd()
__version__ = 0.1
HOLIDAYS = pd.to_datetime(CustomBusinessDay(calendar=calendar()).holidays)


def is_weekend_holiday(start, end, tz):
    if start.astimezone(tz).date() in HOLIDAYS and \
            end.astimezone(tz).date() in HOLIDAYS:
        return True
    if start.astimezone(tz).weekday() > 4 and \
            end.astimezone(tz).weekday() > 4:
        return True
    return False


def sort_list(lst):
    sorted_list = []
    for item in lst:
        if "+" in item:
            sorted_list.append(item)
            lst.remove(item)
        elif "-" in item:
            sorted_list.append(item)
            lst.remove(item)
        elif "*" in item:
            sorted_list.append(item)
            lst.remove(item)
    for item in lst:
        sorted_list.append(item)
    return sorted_list


class Device:
    """
    Container to store topics for historian query.
    """
    def __init__(self, site, building,
                 device, subdevice,
                 device_points, subdevice_points):
        """
        Device constructor.
        :param site:
        :param building:
        :param device:
        :param subdevice:
        :param device_points:
        :param subdevice_points:
        """
        self.device = device
        if not subdevice_points:
            subdevice = ""
        base_record_list = ["tnc", site, building, device, subdevice, "update_model"]
        base_record_list = list(filter(lambda a: a != "", base_record_list))
        self.record_topic = '/'.join(base_record_list)
        key_map = defaultdict()
        for token, point in subdevice_points.items():
            topic = topics.RPC_DEVICE_PATH(campus=site,
                                           building=building,
                                           unit=device,
                                           path=subdevice,
                                           point=point)
            key_map[token] = topic
        for token, point in device_points.items():
            topic = topics.RPC_DEVICE_PATH(campus=site,
                                           building=building,
                                           unit=device,
                                           path='',
                                           point=point)
            key_map[token] = topic
        self.input_data = key_map


class Regression:
    """
    Regression class contains the functions involved in performing
    least squares regression.
    """
    def __init__(self,
                 model_independent,
                 model_dependent,
                 model_struc,
                 regress_hourly,
                 shift_dependent_data,
                 post_processing,
                 debug):
        """
        Regression constructor.
        :param model_independent: dict; independent regression parameters
        :param model_dependent: list; dependent regression variable
        :param model_struc: str; formula for regression
        :param regress_hourly: bool; If true create hourly regression results
        """
        self.debug = debug
        self.bounds = {}
        self.regression_map = OrderedDict()
        self.model_independent = model_independent
        self.model_dependent = model_dependent
        self.regress_hourly = regress_hourly
        self.intercept = None
        self.create_regression_map()
        self.model_struc = model_struc.replace("=", "~")
        self.shift_dependent_data = shift_dependent_data
        self.post_processing = post_processing
        if not self.validate_regression():
            _log.debug("Regression will fail!")
            sys.exit()
        if post_processing is not None:
            if not self.validate_post_processor():
                _log.warning("Post processing mis-configured! Agent will not attempt post-processing")
                self.post_processing = None

    def create_regression_map(self):
        """
        Create the regression map {device: regression parameters}.  Check the
        bounds on regression coefficients and ensure that they are parsed to
        type float.
        :return: None
        """
        self.bounds = {}
        regression_map = {}
        for token, parameters in self.model_independent.items():
            regression_map.update({token: parameters['coefficient_name']})
            # If the bounds are not present in the configuration file
            # then set the regression to be unbounded (-infinity, infinity).
            if 'lower_bound' not in parameters:
                self.model_independent[token].update({'lower_bound': np.NINF})
                _log.debug('Coefficient: %s setting lower_bound to -infinity.', token)
            if 'upper_bound' not in parameters:
                self.model_independent[token].update({'upper_bound': np.inf})
                _log.debug('Coefficient: %s setting upper_bound to infinity.', token)
            # infinity and -infinity as strings should is set to
            # np.NINF and np.inf (unbounded).  These are type float.
            if self.model_independent[token]['lower_bound'] == '-infinity':
                self.model_independent[token]['lower_bound'] = np.NINF
            if self.model_independent[token]['upper_bound'] == 'infinity':
                self.model_independent[token]['upper_bound'] = np.inf
            # If the bounds in configuration file are strings
            # then convert them to numeric value (float).  If
            # a ValueError exception occurs then the string cannot be
            # converted and the regression will be unbounded.
            try:
                if isinstance(self.model_independent[token]['lower_bound'], str):
                    self.model_independent[token]['lower_bound'] = \
                        float(self.model_independent[token]['lower_bound'])
            except ValueError:
                _log.debug("Could not convert lower_bound from string to float!")
                _log.debug("Device: %s -- bound: %s", token, self.model_independent[token]["lower_bound"])
                self.model_independent[token]['lower_bound'] = np.NINF
            try:
                if isinstance(self.model_independent[token]['upper_bound'], str):
                    self.model_independent[token]['upper_bound'] = \
                        float(self.model_independent[token]['upper_bound'])
            except ValueError:
                _log.debug("Could not convert lower_bound from string to float!")
                _log.debug("Device: %s -- bound: %s", token, self.model_independent[token]["upper_bound"])
                self.model_independent[token]['upper_bound'] = np.inf
            # Final check on bounds if they are not float or ints then again
            # set the regression to be unbounded.
            if not isinstance(self.model_independent[token]["lower_bound"],
                              (float, int)):
                self.model_independent[token]['lower_bound'] = np.NINF
            if not isinstance(self.model_independent[token]["upper_bound"],
                              (float, int)):
                self.model_independent[token]['upper_bound'] = np.inf
            self.bounds[self.model_independent[token]['coefficient_name']] = [
                self.model_independent[token]['lower_bound'],
                self.model_independent[token]['upper_bound']
            ]

        if 'Intercept' in regression_map:
            self.intercept = regression_map.pop('Intercept')
        elif 'intercept' in regression_map:
            self.intercept = regression_map.pop('intercept')
        tokens = list(regression_map)
        tokens = sort_list(tokens)
        for token in tokens:
            self.regression_map[token] = regression_map[token]

    def validate_regression(self):
        """
        Return True if model_independent expressions and model_dependent parameters
        are in the model_structure and return False if they are not.
        :return: bool;
        """
        for regression_expr in self.regression_map:
            if regression_expr not in self.model_struc:
                _log.debug("Key: %s for model_independent is not in the model_structure!", regression_expr)
                _log.debug("model_structure will not resolve for regression!")
                return False
        for regression_parameter in self.model_dependent:
            if regression_parameter not in self.model_struc:
                _log.debug("Value: %s for model_independent is not in the model_structure!", regression_parameter)
                _log.debug("model_structure will not resolve for regression!")
                return False
        return True

    def regression_main(self, df, device):
        """
        Main regression run method called by RegressionAgent.
        :param df: pandas DataFrame; Aggregated but unprocessed data.
        :param device: str; device name.
        :return:
        """
        df, formula = self.process_data(df)
        
        results_df = None
        # If regress_hourly is True then linear least squares
        # will be performed for each hour of the day.  Otherwise,
        # one set of coefficients will be generated.
        num_val = 24 if self.regress_hourly else 1
        for i in range(num_val):
            if self.regress_hourly:
                # Query data frame for data corresponding to each hour i (0-23).
                process_df = df.loc[df['Date'].dt.hour == i]
            else:
                process_df = df

            if self.debug:
                filename = '{}/{}-hourly-{}-{}.csv'.format(WORKING_DIR, device.replace('/', '_'),
                                                           i, format_timestamp(dt.now()))
                with open(filename, 'w') as outfile:
                    process_df.to_csv(outfile, mode='w', index=True)

            coefficient_dict = self.calc_coeffs(process_df, formula, device)
            if not coefficient_dict:
               return None
            current_results = pd.DataFrame.from_dict(coefficient_dict)
            _log.debug('Coefficients for index %s -- %s', i, current_results)
            if results_df is None:
                results_df = current_results
            else:
                results_df = results_df.append(current_results)

        if self.post_processing is not None:
            results_df = self.post_processor(results_df)

        return results_df

    def process_data(self, df):
        """
        Evaluate data in df using formula.  new_df will have columns
        corresponding to the coefficients which will be determined during
        linear least squares regression.
        :param df: pandas DataFrame;
        :return:new_df (pandas DataFrame); formula (str)
        """
        formula = self.model_struc
        df = df.dropna()
        new_df = pd.DataFrame()
        # Evaluate independent regression parameters as configured in
        # model_structure (model formula).
        for independent, coefficient in self.regression_map.items():
            new_df[coefficient] = df.eval(independent)
            formula = formula.replace(independent, coefficient)
        # Evaluate dependent regression parameters as configured in
        # model_structure (model formula).
        for token, evaluate in self.model_dependent.items():
            new_df[token] = df.eval(evaluate)
            if self.shift_dependent_data:
                new_df[token] = new_df[token].shift(periods=1)

        new_df.dropna(inplace=True)
        new_df["Date"] = df["Date"]
        return new_df, formula

    def calc_coeffs(self, df, formula, device):
        """
        Does linear least squares regression based on evaluated formula
        and evaluated input data.
        :param df: pandas DataFrame
        :param formula: str
        :return: fit (pandas Series of regression coefficients)
        """
        # create independent/dependent relationship by
        # applying formula and data df
        coefficient_dict = defaultdict(list)
        dependent, independent = patsy.dmatrices(formula, df, return_type='dataframe')
        y = dependent[list(self.model_dependent)[0]]
        if not any(x in self.model_independent.keys() for x in ['Intercept', 'intercept']):
            x = independent.drop(columns=['Intercept'])
        else:
            x = independent.rename(columns={'Intercept': self.intercept})
            x = x.rename(columns={'intercept': self.intercept})

        bounds = [[], []]
        for coeff in x.columns:
            bounds[0].append(self.bounds[coeff][0])
            bounds[1].append(self.bounds[coeff][1])

        _log.debug('Bounds: %s *** for Coefficients %s', bounds, x.columns)
        _log.debug('value of x = {}'.format(x)) 
        _log.debug('value of y = {}'.format(y))
        try:
            result = scipy.optimize.lsq_linear(x, y, bounds=bounds)
        except:
            e = sys.exc_info()[0]
            _log.debug("Least square error - %s", e)
            return coefficient_dict
        coeffs_map = tuple(zip(x.columns, result.x))
        for coefficient, value in coeffs_map:
            coefficient_dict[coefficient].append(value)
        _log.debug('***Scipy regression: ***')
        _log.debug(result.x.tolist())

        return coefficient_dict

    def post_processor(self, df):
        rdf = pd.DataFrame()
        for key, value in self.post_processing.items():
            try:
                rdf[key] = df.eval(value)
            except:
                _log.warning("Post processing error on %s", key)
                rdf[key] = df[key]
        return rdf

    def validate_post_processor(self):
        independent_coefficients = set(self.regression_map.values())
        validate_coefficients = set()
        for coefficient, processor in self.post_processing.items():
            for key, name in self.regression_map.items():
                if name in processor:
                    validate_coefficients.add(name)
                    break
        return validate_coefficients == independent_coefficients


class RegressionAgent(Agent):
    """
    Automated model regression agent.  Communicates with volttron
    historian to query configurable device data.  Inputs data into a
    configurable model_structure to generate regression coefficients.

    Intended use is for automated updating of PNNL TCC models for
    device flexibility determination.
    """
    def __init__(self, config_path, **kwargs):
        """
        Constructor for
        :param config_path:
        :param kwargs:
        """
        super(RegressionAgent, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        self.debug = config.get("debug", True)
        # Read equipment configuration parameters
        self.regression_inprogress = False
        site = config.get('campus', '')
        building = config.get('building', '')
        device = config.get('device', '')
        subdevices = config.get('subdevices', [])
        device_points = config.get('device_points')
        subdevice_points = config.get('subdevice_points')

        # VIP identity for the VOLTTRON historian
        self.data_source = config.get('historian_vip', 'crate.prod')
        # External platform for remote RPC call.
        self.external_platform = config.get("external_platform", "")

        if device_points is None and subdevice_points is None:
            _log.warning('Missing device or subdevice points in config.')
            _log.warning("Cannot perform regression! Exiting!")
            sys.exit()
        if not device and not subdevices:
            _log.warning('Missing device topic(s)!')

        model_struc = config.get('model_structure')
        model_dependent = config.get('model_dependent')
        model_independent = config.get('model_independent')
        regress_hourly = config.get('regress_hourly', True)
        shift_dependent_data = config.get("shift_dependent_data", False)
        post_processing = config.get('post_processing')
        # All parameters related to running in simulation - for time keeping only
        self.simulation = config.get("simulation", False)
        self.simulation_data_topic = config.get("simulation_data_topic", "devices")
        simulation_interval = config.get("simulation_regression_interval", 15)
        self.simulation_regression_interval = td(days=simulation_interval)
        self.simulation_initial_time = None

        if model_struc is None or model_dependent is None or model_independent is None:
            _log.exception('At least one of the model fields is missing in config')
            sys.exit()

        device_list = subdevices if subdevices else [device]
        self.device_list = {}
        self.regression_list = {}
        for unit in device_list:
            self.device_list[unit] = Device(site, building, device, unit, device_points, subdevice_points)
            self.regression_list[unit] = Regression(model_independent,
                                                    model_dependent,
                                                    model_struc,
                                                    regress_hourly,
                                                    shift_dependent_data,
                                                    post_processing,
                                                    self.debug)

        # Aggregate data to this value of minutes
        self.data_aggregation_frequency = config.get("data_aggregation_frequency", "h")

        # This  sets up the cron schedule to run once every 10080 minutes
        # Once every 7 days
        self.run_schedule = config.get("run_schedule", "*/10080 * * * *")
        self.training_interval = int(config.get('training_interval', 5))
        if self.training_interval < 5 and "h" in self.data_aggregation_frequency:
            _log.debug("There is a limited number of days in regression!!")
            _log.debug("Update aggregation frequency for hourly to 15 minute!")
            self.data_aggregation_frequency = "15min"

        self.exclude_weekends_holidays = config.get("exclude_weekends_holidays", True)
        self.run_onstart = config.get("run_onstart", True)

        self.one_shot = config.get('one_shot', False)

        self.local_tz = pytz.timezone(config.get('local_tz', 'US/Pacific'))
        # If one shot is true then start and end should be specified
        if self.one_shot:
            self.start = config.get('start')
            self.end = config.get('end')

        self.coefficient_results = {}
        self.exec_start = None
        _log.debug("Validate historian running vip: %s - platform %s",
                   self.data_source, self.external_platform)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        """
        onstart method handles scheduling regression execution.
        Either cron schedule for periodic updating of model parameters
        or one_shot to run once.
        :param sender: str;
        :param kwargs: None
        :return: None
        """
        # TODO: note in function.  reschedule do not exit.
        #if not self.validate_historian_reachable():
        #    _log.debug("Cannot verify historian is running!")
        #    sys.exit()

        if not self.one_shot:
            if not self.simulation:
                self.core.schedule(cron(self.run_schedule), self.scheduled_run_process)
            else:
                self.simulation_setup()
            if self.run_onstart:
                self.scheduled_run_process()
        else:
            try:
                self.start = parser.parse(self.start)
                self.start = self.local_tz.localize(self.start)
                self.start = self.start.astimezone(UTC_TZ)
                self.end = parser.parse(self.end)
                self.end = self.local_tz.localize(self.end)
                self.end = self.end.astimezone(UTC_TZ)
            except (NameError, ValueError) as ex:
                _log.debug('One shot regression:  start_time or end_time '
                           'not specified correctly!: *%s*', ex)
                self.end = dt.now(self.local_tz).replace(hour=0,
                                                         minute=0,
                                                         second=0,
                                                         microsecond=0)
                self.start = self.end - td(days=self.training_interval)
            self.main_run_process()

    def simulation_setup(self):
        _log.debug("Running with simulation using topic %s",
                   self.simulation_data_topic)
        self.vip.pubsub.subscribe(peer="pubsub",
                                  prefix=self.simulation_data_topic,
                                  callback=self.simulation_time_handler)

    def simulation_time_handler(self, peer, sender, bus, topic, header, message):
        current_time = parser.parse(header["Date"])
        _log.debug("Simulation time handler current_time: %s", current_time)
        if self.simulation_initial_time is None:
            self.simulation_initial_time = current_time
        retraining_time_delta = current_time - self.simulation_initial_time
        _log.debug("Simulation time handler time delta: %s",
                   retraining_time_delta)
        if retraining_time_delta >= self.simulation_regression_interval:
            self.simulation_run_process(current_time)

    def validate_historian_reachable(self):
        _log.debug("Validate historian running vip: %s - platform %s",
                   self.data_source, self.external_platform)
        historian_reachable = False
        try:
            result = self.vip.rpc.call("control",
                                       'list_agents',
                                       external_platform=self.external_platform).get(timeout=30)
        except:
            _log.debug("Connection to platform failed, cannot validate historian running!")
            # TODO:  Update to schedule a rerun
            sys.exit()
        for agent_dict in result:
            if agent_dict["identity"] == self.data_source:
                historian_reachable = True

        return historian_reachable

    @Core.receiver('onstop')
    def stop(self, sender, **kwargs):
        pass

    def scheduled_run_process(self):
        self.end = get_aware_utc_now().replace(hour=0,
                                               minute=0,
                                               second=0, microsecond=0)
        if self.exclude_weekends_holidays:
            training_interval = self.calculate_start_offset()
        else:
            training_interval = self.training_interval
        self.start = self.end - td(days=training_interval)
        self.main_run_process()
        self.regression_inprogress = False

    def simulation_run_process(self, current_time):
        self.end = current_time.replace(hour=0,
                                        minute=0,
                                        second=0, microsecond=0)
        if self.exclude_weekends_holidays:
            training_interval = self.calculate_start_offset()
        else:
            training_interval = self.training_interval
        self.start = self.end - td(days=training_interval)
        self.main_run_process()
        self.simulation_initial_time = None
        self.regression_inprogress = False

    def calculate_start_offset(self):
        """
        The regression interval is a number of days of data
        to include in regression ending at midnight of the current day.
        If this date interval contains weekends or holidays and
        exclude_weekends_holidays is True then the start date must be
        made earlier to compensate for the weekends and holidays.
        :return:
        """
        increment = 0
        for _day in range(1, self.training_interval + 1):
            training_date = (self.end - td(days=_day)).astimezone(self.local_tz)
            if training_date.date() in HOLIDAYS:
                increment += 1
            elif training_date.weekday() > 4 and \
                    training_date.weekday() > 4:
                increment += 1
        return self.training_interval + increment

    def main_run_process(self):
        """
        Main run process for RegressionAgent.  Calls data query methods
        and regression methods.  Stores each devices result.
        :return:
        """
        if self.regression_inprogress:
            return
        self.regression_inprogress = True
        self.exec_start = utils.get_aware_utc_now()
        _log.debug('Start regression - UTC converted: {}'.format(self.start))
        _log.debug('End regression UTC converted: {}'.format(self.end))

        # iterate for each device or subdevice in the device list
        for name, device in self.device_list.items():
            self.exec_start = utils.get_aware_utc_now()
            df = self.query_historian(device.input_data)
            df = self.localize_df(df, name)
            result = self.regression_list[name].regression_main(df, name)
            if result is None:
                _log.debug("ERROR for regression for %s", name)
                continue
            result.reset_index()
            result = result.to_dict(orient='list')
            self.coefficient_results[device.record_topic] = result
            if self.debug:
                with open('{}/{}_results.json'.format(WORKING_DIR, name.replace('/', '_')), 'w+') as outfile:
                    json.dump(result, outfile, indent=4, separators=(',', ': '))
                _log.debug('*** Finished outputting coefficients ***')
            self.publish_coefficients(device.record_topic, result)
            exec_end = utils.get_aware_utc_now()
            exec_dif = exec_end - self.exec_start
            _log.debug("Regression for %s duration: %s", device, exec_dif)

    def publish_coefficients(self, topic, result):
        """
        Publish coefficients for each device.
        :return:
        """
        self.vip.pubsub.publish("pubsub", topic, {}, result).get(timeout=10)

    def query_historian(self, device_info):
        """
        Query VOLTTRON historian for all points in device_info
        for regression period.  All data will be combined and aggregated
        to a common interval (i.e., 1Min).
        :param device_info: dict; {regression token: query topic}
        :return:
        """
        aggregated_df = None
        rpc_start = self.start
        rpc_end = rpc_start + td(hours=8)
        # get data via query to historian
        # Query loop for device will continue until start > end
        # or all data for regression period is obtained.
        while rpc_start < self.end.astimezone(pytz.UTC):
            df = None
            # If exclude_weekend_holidays is True then do not query for
            # these times.  Reduces rpc calls and message bus traffic.
            if self.exclude_weekends_holidays:
                if is_weekend_holiday(rpc_start, rpc_end, self.local_tz):
                    rpc_start = rpc_start + td(hours=8)
                    rpc_end = rpc_start + td(minutes=479)
                    if rpc_end > self.end.astimezone(UTC_TZ):
                        rpc_end = self.end.astimezone(UTC_TZ)
                    continue

            for token, topic in device_info.items():
                rpc_start_str = format_timestamp(rpc_start)
                rpc_end_str = format_timestamp(rpc_end)
                _log.debug("RPC start {} - RPC end {} - topic {}".format(rpc_start_str, rpc_end_str, topic))
                # Currently historian is limited to 1000 records per query.
                result = self.vip.rpc.call(self.data_source,
                                           'query',
                                           topic=topic,
                                           start=rpc_start_str,
                                           end=rpc_end_str,
                                           order='FIRST_TO_LAST',
                                           count=1000,
                                           external_platform=self.external_platform).get(timeout=300)
                _log.debug(result)
                if not bool(result) or "values" not in result or \
                        ("values" in result and not bool(result["values"])):
                    _log.debug('ERROR: empty RPC return for '
                               'coefficient *%s* at %s', token, rpc_start)
                    break
                # TODO:  check if enough data is present and compensate for significant missing data
                data = pd.DataFrame(result['values'], columns=['Date', token])
                data['Date'] = pd.to_datetime(data['Date'])
                # Data is aggregated to some common frequency.
                # This is important if data has different seconds/minutes.
                # For minute trended data this is set to 1Min.
                data = data.groupby([pd.Grouper(key='Date', freq=self.data_aggregation_frequency)]).mean()
                df = data if df is None else pd.merge(df, data, how='outer', left_index=True, right_index=True)

            if aggregated_df is None:
                aggregated_df = df
            else:
                aggregated_df = aggregated_df.append(df)

            # Currently 8 hours is the maximum interval that the historian
            # will support for one minute data.  1000 max records can be
            # returned per query and each query has 2 fields timestamp, value.
            # Note:  If trending is at sub-minute interval this logic would
            # need to be revised to account for this or the count in historian
            # could be increased.
            rpc_start = rpc_start + td(hours=8)
            if rpc_start + td(minutes=479) <= self.end.astimezone(pytz.UTC):
                rpc_end = rpc_start + td(minutes=479)  #
            else:
                rpc_end = self.end.astimezone(pytz.UTC)
        return aggregated_df

    def localize_df(self, df, device):
        """
        Data from the VOLTTRON historian will be in UTC timezone.
        Regressions typically are meaningful for localtime as TCC
        agents utilize local time for predictions and control.
        :param df:
        :param device:
        :return:
        """
        df = df.reset_index()
        try:
            # Convert UTC time to local time in configuration file.
            df['Date'] = df['Date'].dt.tz_convert(self.local_tz)
        except Exception as e:
            _log.error('Failed to convert Date column to localtime - {}'.format(e))
        if self.debug:
            filename = '{}/{}-{} - {}.csv'.format(WORKING_DIR, self.start, self.end, device.replace('/', '_'))
            try:
                with open(filename, 'w+') as outfile:
                    df.to_csv(outfile, mode='a', index=True)
                    _log.debug('*** Finished outputting data ***')
            except Exception as e:
                _log.error('File output failed, check whether the dataframe is empty - {}'.format(e))

        # Weekends and holidays will only be present if
        # one_shot is true.  For scheduled regression those
        # days are excluded from query to historian.
        if self.exclude_weekends_holidays:
            holiday = CustomBusinessDay(calendar=calendar()).onOffset
            match = df["Date"].map(holiday)
            df = df[match]
        return df

    @RPC.export
    def get_coefficients(self, device_id, **kwargs):
        """
        TCC agent can do RPC call to get latest regression coefficients.
        :param device_id: str; device/subdevice
        :param kwargs:
        :return:
        """
        if self.coefficient_results:
            try:
                result = self.coefficient_results[device_id]
            except KeyError as ex:
                _log.debug("device_id provided is not known: %s", device_id)
                result = None
        else:
            _log.debug("No regression results exist: %s", device_id)
            result = None
        return result


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(RegressionAgent)
    except Exception as e:
        _log.exception('unhandled exception - {}'.format(e))


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
