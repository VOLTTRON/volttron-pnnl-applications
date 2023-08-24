# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
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
import json
import pytz
from dateutil import parser
from datetime import datetime, timedelta
import sqlite3
import numpy as np
import gevent

from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now,
                                           format_timestamp)
from volttron.platform.messaging import headers as headers_mod, topics

__version__ = '1.0.0'

HEADER_NAME_DATE = headers_mod.DATE
HEADER_NAME_CONTENT_TYPE = headers_mod.CONTENT_TYPE

utils.setup_logging()
_log = logging.getLogger(__name__)


class WbeAgent(Agent):
    """Whole building energy diagnostics
    To predict energy usage (dependent variable) by analyzing historical data using OutdoorTemp, Humidity, etc.
    Note:
        - Currently supports only 1 independent variable (e.g. OAT)
        - Removed prediction validation code
        - To add HourOfWeek OR Weekday to configuration file later
    """
    def __init__(self, config_path, **kwargs):
        super(WbeAgent, self).__init__(**kwargs)

        self.config = utils.load_config(config_path)
        self.site = self.config.get('campus')
        self.building = self.config.get('building')
        self.out_temp_unit = self.config.get('out_temp_unit', '')
        self.out_temp_name = self.config.get('out_temp_name')
        self.power_unit = self.config.get('power_unit', '')
        self.power_name = self.config.get('power_name')
        self.zip = self.config.get('zip')

        self.object_id = self.config.get('object_id')
        self.variable_id = self.config.get('variable_id')
        self.n_degrees = self.config.get('n_degrees')
        self.deviation = self.config.get('deviation')
        self.time_diff_tol = self.config.get('time_diff_tol')
        self.oat_diff_tol = self.config.get('oat_diff_tol')
        self.cost_limit = self.config.get('cost_limit')
        self.price = self.config.get('price')
        self.threshold = self.config.get('threshold')

        self.out_temp_topic = '/'.join([self.site, self.building,
                                        self.out_temp_unit, self.out_temp_name])
        self.out_temp_topic = self.out_temp_topic.replace('//', '/')

        self.power_topic = '/'.join([self.site, self.building,
                                     self.power_unit, self.power_name])
        self.power_topic = self.power_topic.replace('//', '/')

        self.tz = self.config.get('tz')
        self.local_tz = pytz.timezone(self.tz)
        self.utc_tz = pytz.timezone('UTC')

        self.model_start = self.config.get('model_start', None)
        self.model_stop = self.config.get('model_stop', None)
        self.actual_start = self.config.get('prediction_start', None)
        self.actual_stop = self.config.get('prediction_stop', None)
        self.operation_mode = self.config.get('operation_mode')
        if self.operation_mode == 1:
            self.cur_analysis_time_utc = datetime.utcnow()
        else:
            self.cur_analysis_time = self.local_tz.localize(parser.parse(self.config.get('cur_time')))
            self.cur_analysis_time_utc = self.cur_analysis_time.astimezone(pytz.utc)
        self.configure_start_stop()

        self.db_folder = self.config.get('db_folder') + '/'
        self.db_folder = self.db_folder.replace('//', '/')
        self.debug_folder = self.config.get('debug_folder') + '/'
        self.debug_folder = self.debug_folder.replace('//', '/')

        #Wbe/request/start/end
        self.request_topic_prefix = 'wbe/request'
        self.weather_req_topic = 'weather2/request/forecast10/ZIP/{zip}/all'.format(zip=self.zip)
        self.weather_resp_topic = 'weather2/response/forecast10/ZIP/{zip}/all'.format(zip=self.zip)

        self.forecast_data = None

    def configure_start_stop(self):
        if self.model_start is None:
            self.model_start_utc = datetime.utcfromtimestamp(0)
        else:
            self.model_start = self.local_tz.localize(parser.parse(self.model_start))
            self.model_start_utc = self.model_start.astimezone(pytz.utc)

        if self.model_stop is None:
            self.model_stop_utc = self.cur_analysis_time_utc
        else:
            self.model_stop = self.local_tz.localize(parser.parse(self.model_stop))
            self.model_stop_utc = self.model_stop.astimezone(pytz.utc)

        if self.actual_start is None:
            self.actual_start_utc = self.cur_analysis_time_utc + timedelta(hours=1)
        else:
            self.actual_start = self.local_tz.localize(parser.parse(self.actual_start))
            self.actual_start_utc = self.actual_start.astimezone(pytz.utc)

        if self.actual_stop is None:
            self.actual_stop_utc = self.cur_analysis_time_utc + timedelta(days=10)
        else:
            self.actual_stop = self.local_tz.localize(parser.parse(self.actual_stop))
            self.actual_stop_utc = self.actual_stop.astimezone(pytz.utc)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.request_topic_prefix,
                                  callback=self.on_request)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.weather_resp_topic,
                                  callback=self.on_forecast_response)

        self.vip.pubsub.publish(
            'pubsub', self.request_topic_prefix, {}, '').get(timeout=10)

    def on_request(self, peer, sender, bus, topic, headers, message):
        #
        # weather2/request/{feature}/{region}/{city}/all
        # weather2/request/{feature}/{region}/{city}/{point}
        #
        feature = region = city = zip_code = point = start = end = None

        # Analyze request topic
        try:
            topic_parts = topic.split('/')
            topic_parts = [x.lower() for x in topic_parts]
            # start = topic_parts[2]
            # end = topic_parts[3]
            # start_local = self.local_tz.localize(parser.parse(start))
            # end_local = self.local_tz.localize(parser.parse(end))
            # start_utc = start_local.astimezone(pytz.utc)
            # end_utc = end_local.astimezone(pytz.utc)
        except ValueError as (errno, strerror):
            _log.debug("Unpack request error: " + strerror)
            return

        # Delete existing db
        cur_dir = os.path.dirname(os.path.realpath(__file__))
        db_file = self.db_folder + 'wbe_data.sqlite'
        if os.path.isfile(db_file):
            os.remove(db_file)

        # Create input tables
        self.create_variables_table(db_file)
        self.create_oat_table(db_file)
        self.create_power_table(db_file)
        self.create_data_table(db_file)
        self.add_forecast_data(db_file)

        # Do diagnostics
        wbe = Wbe(self.zip, self.object_id, self.variable_id,
                  self.n_degrees, self.deviation,
                  self.time_diff_tol, self.oat_diff_tol, self.cost_limit,
                  self.price, self.threshold,
                  self.model_start_utc, self.model_stop_utc,
                  self.actual_start_utc, self.actual_stop_utc)
        wbe.process(db_file, self.db_folder)

        # TODO: do something with result
        _log.debug('WBEAgent completed.')


        # if len(publish_items) > 0:
        #     headers = {
        #         HEADER_NAME_DATE: format_timestamp(utils.get_aware_utc_now()),
        #         HEADER_NAME_CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON
        #     }
        #     resp_topic = topic.replace('request', 'response')
        #     self.vip.pubsub.publish(peer='pubsub',
        #                             topic=resp_topic,
        #                             message=publish_items,
        #                             headers=headers)

    def create_variables_table(self, db_file):
        _log.debug("Create variables table...")
        con = sqlite3.connect(db_file)
        try:
            with con:
                cur = con.cursor()
                cur.execute("DROP TABLE IF EXISTS variables;")
                cur.execute("""CREATE TABLE variables(id INTEGER,
                                                            Name TEXT,
                                                            Unit TEXT,
                                                            Format TEXT,
                                                            HighLimit REAL,
                                                            LowLimit REAL);""")
                #to_db = [(i['id'], i['Name'], i['Unit'], i['Format'], i['HighLimit'], i['LowLimit']) for i in dr]
                to_db = [(self.object_id, 'Tout', 'F', '%.1F', 140, -40),
                         (self.variable_id, 'Power', 'kW', '%.1F', 100000, 0)]
                cur.executemany("INSERT INTO variables "
                                "(id, Name, Unit, Format, HighLimit, LowLimit) "
                                "VALUES (?, ?, ?, ?, ?, ?);", to_db)
                con.commit()
        except Exception as ex:
            _log.debug(ex)
            con.close()

    def create_oat_table(self, db_file):
        _log.debug("Query data for wbe_oat table {}...".format(self.actual_start_utc))
        result = self.vip.rpc.call('platform.historian',
                                   'query',
                                   topic=self.out_temp_topic,
                                   start=self.model_start_utc.isoformat(' '),
                                   end=self.model_stop_utc.isoformat(' '),
                                   count=100000000,
                                   order="LAST_TO_FIRST").get(timeout=1000)
        _log.debug("WbeAgent: dataframe length is {len}".format(len=len(result)))

        if len(result) > 0:
            if 'values' in result:
                to_db = []
                for item in result['values']:
                    to_db.append((self.object_id, item[0][0:19].replace('T', ' '), item[1]))
                con = sqlite3.connect(db_file)
                try:
                    with con:
                        cur = con.cursor()
                        cur.execute("DROP TABLE IF EXISTS wbe_oat;")
                        cur.execute("""CREATE TABLE wbe_oat(id INTEGER PRIMARY KEY,
                                                            var_id INTEGER,
                                                            ts DATETIME,
                                                            value REAL);""")
                        cur.executemany("INSERT INTO wbe_oat "
                                        "(id, var_id, ts, value) "
                                        "VALUES (NULL, ?, ?, ?);", to_db)
                        con.commit()
                except Exception as ex:
                    _log.debug(ex)
                    con.close()

    def create_power_table(self, db_file):
        _log.debug("Query data for wbe_power table...")
        result = self.vip.rpc.call('platform.historian',
                                   'query',
                                   topic=self.power_topic,
                                   start=self.model_start_utc.isoformat(' '),
                                   end=self.model_stop_utc.isoformat(' '),
                                   count=100000000,
                                   order="LAST_TO_FIRST").get(timeout=1000)
        _log.debug("WbeAgent: dataframe length is {len}".format(len=len(result)))

        if len(result) > 0:
            if 'values' in result:
                to_db = []
                for item in result['values']:
                    to_db.append((self.variable_id, item[0][0:19].replace('T', ' '), item[1]))
                con = sqlite3.connect(db_file)
                try:
                    with con:
                        cur = con.cursor()
                        cur.execute("DROP TABLE IF EXISTS wbe_power;")
                        cur.execute("""CREATE TABLE wbe_power(id INTEGER PRIMARY KEY,
                                                              var_id INTEGER,
                                                              ts DATETIME,
                                                              value REAL);""")
                        cur.executemany("INSERT INTO wbe_power "
                                        "(id, var_id, ts, value) "
                                        "VALUES (NULL, ?, ?, ?);", to_db)
                        con.commit()
                except Exception as ex:
                    _log.debug(ex)
                    con.close()

    def create_data_table(self, db_file):
        _log.debug("Create wbe_data table...")
        con = sqlite3.connect(db_file)
        with con:
            cur = con.cursor()
            cur.execute("DROP TABLE IF EXISTS data;")
            cur.execute("""CREATE TABLE wbe_data(id INTEGER PRIMARY KEY,
                                                    ObjectId INTEGER,
                                                    VariableId INTEGER,
                                                    PostTime DATETIME,
                                                    dependent_val REAL,
                                                    independent_val1 REAL,
                                                    independent_val2 REAL,
                                                    independent_val3 REAL,
                                                    independent_val4 REAL,
                                                    independent_val5 REAL);""")

            cur.execute("""INSERT INTO wbe_data (id, ObjectId, VariableId, PostTime, dependent_val, independent_val1)
                        SELECT NULL, A.var_id, B.var_id, A.ts, AVG(B.value), AVG(A.value) 
                        FROM wbe_oat A INNER JOIN wbe_power B ON A.ts = B.ts
                        GROUP BY  strftime('%Y', A.ts),
                                  strftime('%m', A.ts),
                                  strftime('%d', A.ts),
                                  strftime('%H', A.ts)""")

    def on_forecast_response(self, peer, sender, bus, topic, headers, message):
        self.forecast_data = message

    def add_forecast_data(self, db_file):
        if self.operation_mode == 1:
            # Pull weather underground info
            headers = {'Date': format_timestamp(get_aware_utc_now())}
            target_msg = ''
            self.vip.pubsub.publish(
                'pubsub', self.weather_req_topic, headers, target_msg).get(timeout=10)

            while self.forecast_data is None:
                gevent.sleep(5)

            to_db = []
            for item in self.forecast_data:
                ts = datetime.fromtimestamp(float(item['observation_epoch']), pytz.utc).replace(tzinfo=None)
                out_temp = item['temp']
                to_db.append((self.object_id, self.variable_id, ts, out_temp))
            self.forecast_data = None

            _log.debug("Add weather forecast data...")
            con = sqlite3.connect(db_file)
            try:
                with con:
                    cur = con.cursor()
                    cur.executemany("""INSERT INTO wbe_data (ObjectId, VariableId, PostTime, dependent_val, independent_val1)
                                            VALUES(?,?,?,NULL,?)""", to_db)
                    con.commit()
            except Exception as ex:
                _log.debug(ex)
                con.close()
        else:
            _log.debug("Query forecast data for wbe_oat table {}...".format(self.actual_start_utc))
            result = self.vip.rpc.call('platform.historian',
                                       'query',
                                       topic=self.out_temp_topic,
                                       start=self.actual_start_utc.isoformat(' '),
                                       end=self.actual_stop_utc.isoformat(' '),
                                       count=100000000,
                                       order="LAST_TO_FIRST").get(timeout=1000)
            _log.debug("WbeAgent: length is {len}".format(len=len(result)))

            if len(result) > 0:
                if 'values' in result:
                    to_db = []
                    for item in result['values']:
                        to_db.append((self.object_id, self.variable_id, item[0][0:19].replace('T', ' '), item[1]))
                    con = sqlite3.connect(db_file)
                    try:
                        with con:
                            cur = con.cursor()
                            cur.executemany("""INSERT INTO wbe_data (id, ObjectId, VariableId, PostTime, dependent_val, independent_val1)
                                            VALUES(NULL, ?, ?, ?, NULL, ?)""", to_db)
                            con.commit()
                    except Exception as ex:
                        _log.debug(ex)
                        con.close()

class Wbe:
    """Whole building energy diagnostics
    To predict energy usage (dependent variable) by analyzing historical data using OutdoorTemp, Humidity, etc.
    Note:
        - Currently supports only 1 independent variable (e.g. OAT)
        - Removed prediction validation code
        - To add HourOfWeek OR Weekday to configuration file later
    """
    def __init__(self, zip, object_id, variable_id, n_degrees, deviation,
                 time_diff_tol, oat_diff_tol, cost_limit,
                 price, threshold,
                 model_start, model_stop,
                 actual_start, actual_stop):
        self.zip = zip
        self.object_id = object_id
        self.variable_id = variable_id
        self.n_degrees = n_degrees
        self.deviation = deviation
        self.time_diff_tol = time_diff_tol
        self.oat_diff_tol = oat_diff_tol
        self.cost_limit = cost_limit
        self.price = price
        self.threshold = threshold

        self.actual_start = actual_start
        self.actual_stop = actual_stop
        self.model_start = model_start
        self.model_stop = model_stop

    def create_result_table(self, con):
        print("Create result table...")
        # TODO: add other configurable inputs as in output tables
        cur = con.cursor()
        sql = """CREATE TABLE IF NOT EXISTS Results
                    (ObjectId INT, VariableId INT, PostTime DATETIME,
                        dependent_val REAL, Rmse REAL, Mbe REAL, Samples INT,
                        PRIMARY KEY (ObjectId, VariableId, PostTime));"""
        cur.execute(sql)

        time_cond = """AND (ABS((strftime('%H',actual.PostTime)
            +{deviation}*strftime('%w',actual.PostTime))
            -(strftime('%H',model.PostTime)
            +{deviation}*strftime('%w',model.PostTime))))
            <={time_tol}""".format(deviation=self.deviation,
                                   time_tol=self.time_diff_tol)
        # Weekday & weekend cond
        # Weekday & Sat & Sun cond
        # HourOfWeek cond
        first_dependence_cond = "AND ABS(actual.independent_val1-model.independent_val1)<={}".format(self.oat_diff_tol)
        sql = """
                SELECT actual.ObjectId, actual.VariableId, actual.PostTime,
                        median(model.dependent_val),
                        rmse(model.dependent_val, {n_degrees}),
                        mbe(model.dependent_val, {n_degrees}),
                        count(*)
                FROM wbe_data AS actual, wbe_data AS model
                WHERE actual.ObjectId = {object} AND actual.VariableId = {variable}
                    AND model.ObjectId = {object} AND model.VariableId = {variable}
                    AND actual.PostTime BETWEEN '{actual_start}'  AND '{actual_stop}'
                    AND model.PostTime BETWEEN '{model_start}' AND '{model_stop}'
                    {schedule_cond} {conditions}
                GROUP BY actual.ObjectId, actual.variableId,
                        strftime('%Y',actual.PostTime),
                        strftime('%m',actual.PostTime),
                        strftime('%d',actual.PostTime),
                        strftime('%H',actual.PostTime);""".format(n_degrees=self.n_degrees,
                                                                  object=self.object_id,
                                                                  variable=self.variable_id,
                                                                  actual_start=self.actual_start.replace(tzinfo=None),
                                                                  actual_stop=self.actual_stop.replace(tzinfo=None),
                                                                  model_start=self.model_start.replace(tzinfo=None),
                                                                  model_stop=self.model_stop.replace(tzinfo=None),
                                                                  schedule_cond=time_cond,
                                                                  conditions=first_dependence_cond)
        cur.execute(sql)
        rows = []
        for row in cur:
            rows.append(row)
        cur.executemany("""INSERT INTO Results (ObjectId, VariableId, PostTime, dependent_val, Rmse, Mbe, Samples)
                            VALUES(?,?,?,?,?,?,?)""", rows)

    def process(self, db_file, out_dir):
        self.out_dir = out_dir
        con = sqlite3.connect(db_file)

        with con:
            create_funcs(con)  # Create necessary functions
            self.create_result_table(con)  # Create result table


class Median:
    def __init__(self):
        self.values = []

    def step(self, value):
        self.values.append(value)

    def finalize(self):
        return np.median(np.array(self.values))


class Rmse:
    def __init__(self):
        self.values = []

    def step(self, value, dof):
        self.values.append(value)
        self.dof = dof  # degrees of freedom

    def finalize(self):
        median = np.median(np.array(self.values))
        f = lambda x: (x - median) ** 2
        se = map(f, self.values)
        rmse = 0
        if (len(self.values) - self.dof > 0):
            rmse = np.sqrt(np.sum(np.array(se)) / (len(self.values) - self.dof))
        return rmse


class Mbe:
    def __init__(self):
        self.values = []

    def step(self, value, dof):
        self.values.append(value)
        self.dof = dof

    def finalize(self):
        median = np.median(np.array(self.values))
        f = lambda x: x - median
        mbe = 0
        if (len(self.values) - self.dof > 0):
            mbe = np.sum(np.array(map(f, self.values))) / (len(self.values) - self.dof)
        return mbe


def add_1(x):
    return x + 1


def create_funcs(con):
    _log.debug("Create custom functions...")
    con.create_aggregate("median", 1, Median)
    con.create_aggregate("rmse", 2, Rmse)
    con.create_aggregate("mbe", 2, Mbe)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(WbeAgent)
    except Exception as e:
        _log.exception('unhandled exception')

if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
