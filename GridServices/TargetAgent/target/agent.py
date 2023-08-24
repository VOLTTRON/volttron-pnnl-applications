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
from datetime import datetime, timedelta
import pytz
import dateutil.tz
from dateutil import parser
import gevent
from time import mktime
import csv

from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now,
                                           format_timestamp)

__version__ = '1.0.0'

utils.setup_logging()
_log = logging.getLogger(__name__)


class TargetAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(TargetAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)

        # Building info
        self.site = self.config.get('campus')
        self.building = self.config.get('building')
        self.wbe_csv = self.config.get('wbe_file')
        self.prediction_method = self.config.get('prediction_method')

        # Local timezone
        self.tz = self.config.get('tz')
        self.local_tz = pytz.timezone(self.tz)

        # Bidding value
        self.cbps = self.config.get('cbp', None)
        if self.cbps is None:
            raise "CBP values are required"
        if len(self.cbps)<24:
            raise "CBP is required for every hour (i.e., 24 values)"

        #Occupancy
        self.cont_after_dr = self.config.get('cont_after_dr')
        self.occ_time = self.config.get('occ_time')
        if self.cont_after_dr == 'yes':
            try:
                self.occ_time = parser.parse(self.occ_time)
                self.occ_time = self.local_tz.localize(self.occ_time)
                self.occ_time_utc = self.occ_time.astimezone(pytz.utc)
            except:
                raise "The DR was set to continue after end time " \
                      "but could not parse occupancy end time"

        # DR mode
        self.dr_mode = self.config.get('dr_mode')
        if self.dr_mode == 'open_adr':
            self.start_time = None
            self.end_time = None
            self.cur_time = None
        else:
            self.start_time = self.config.get('start_time')
            self.end_time = self.config.get('end_time')
            self.cur_time = self.config.get('cur_time')
            try:
                self.start_time = parser.parse(self.start_time)
                self.end_time = parser.parse(self.end_time)
                self.cur_time = parser.parse(self.cur_time)
            except:
                raise "The DR mode is manual mode but could not " \
                      "parse start, end, or current time"

        #Simulation
        self.last_publish_time = None

        _log.debug("TargetAgent: Running DR mode {}".format(self.dr_mode))

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        _log.debug('TargetAgent: OnStart ')
        one_hour = timedelta(hours=1)
        cur_time = self.local_tz.localize(datetime.now())
        if self.dr_mode == 'manual' or self.dr_mode == 'dev':
            cur_time = self.local_tz.localize(self.cur_time)

        # Set cur_time to previous hour to get current hour baseline values
        cur_time_utc = cur_time.astimezone(pytz.utc)
        prev_time_utc = cur_time_utc - one_hour

        # subscribe to ILC start event
        ilc_start_topic = '/'.join([self.site, self.building, 'ilc/start'])
        _log.debug('TargetAgent: Subscribing to ' + ilc_start_topic)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=ilc_start_topic,
                                  callback=self.on_ilc_start)

        if self.dr_mode == 'manual':
            manual_periodic = '/'.join(['devices', self.site, self.building, 'METERS'])
            _log.debug("TargetAgent: Simulation handler topic -- {}".format(manual_periodic))
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=manual_periodic,
                                      callback=self.simulation_publish_handler)
        elif self.dr_mode == 'auto_adr':
            adr_topic = '/'.join(['openadr', 'event_update'])
            _log.debug("TargetAgent: OpenADR handler topic -- {}".format(adr_topic))
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=adr_topic,
                                      callback=self.open_adr_handler)
        adr_topic = '/'.join(['openadr', 'event'])
        _log.debug("TargetAgent: OpenADR handler topic -- {}".format(adr_topic))
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=adr_topic,
                                  callback=self.open_adr_handler)

        # Always put this line(s) at the end of the method
        self.publish_target_info(format_timestamp(cur_time_utc))

    def simulation_publish_handler(self, peer, sender, bus, topic, headers, message):
        _log.debug("TARGET_AGENT_DEBUG: Running simulation publish handler")
        tz_replace = dateutil.tz.gettz(self.tz)
        current_time = parser.parse(headers['Date']).replace(tzinfo=tz_replace)

        if self.last_publish_time is None:
            self.last_publish_time = current_time

        _log.debug("TARGET_AGENT_DEBUG: current time - {} "
                   "----- last publish time - {}".format(current_time,
                                                         self.last_publish_time))
        if self.last_publish_time is not None and (current_time - self.last_publish_time) >= timedelta(minutes=5):
            _log.debug("TARGET_AGENT_DEBUG: Running periodic publish.")
            self.publish_target_info(format_timestamp(current_time))
            self.last_publish_time = current_time

    def open_adr_handler(self, peer, sender, bus, topic, headers, message):
        _log.debug("TARGET_AGENT_DEBUG: Running OpenADR publish handler")
        self.start_time = parser.parse(message['start_time'])
        self.end_time = parser.parse(message['end_time'])
        current_time = datetime.utcnow()

        # OpenADR uses UTC
        if self.start_time.tzinfo is not None:
            tz_replace = dateutil.tz.gettz('UTC')
            self.start_time = self.start_time.replace(tzinfo=tz_replace)
        if self.end_time.tzinfo is not None:
            tz_replace = dateutil.tz.gettz('UTC')
            self.end_time = self.end_time.replace(tzinfo=tz_replace)

        _log.debug("TARGET_AGENT_DEBUG: publish target info.")
        self.publish_target_info(format_timestamp(current_time))

    def on_ilc_start(self, peer, sender, bus, topic, headers, message):
        cur_time = self.local_tz.localize(datetime.now())
        cur_time_utc = cur_time.astimezone(pytz.utc)
        one_hour = timedelta(hours=1)
        prev_time_utc = cur_time_utc - one_hour
        self.publish_target_info(format_timestamp(prev_time_utc))
        self.publish_target_info(format_timestamp(cur_time_utc))

    def get_prev_dr_days(self):
        """
        Get DR days from historian previous published by OpenADR agent
        Returns:
            A list of dr event days
        """
        dr_days = self.config.get('dr_days', [])
        parsed_dr_days = []
        for dr_day in dr_days:
            try:
                parsed_dr_day = parser.parse(dr_day)
                if parsed_dr_day.tzinfo is None:
                    parsed_dr_day = self.local_tz.localize(parsed_dr_day)
                parsed_dr_day_utc = parsed_dr_day.astimezone(pytz.utc)
                parsed_dr_days.append(format_timestamp(parsed_dr_day_utc))
            except:
                _log.error(
                    "TargetAgent: Could not parse DR day {d}".format(d=dr_day))

        return parsed_dr_days

    def get_event_info(self):
        """
        Get event start and end datetime from OpenADR agent
        Returns:
            A dictionary that has start & end time for event day
        """

        import json

        event_info = {}

        # Get info from OpenADR, with timezone info
        start_time = None
        end_time = None

        if self.dr_mode == 'open_adr': #from OpenADR agent
            #start_time = self.local_tz.localize(datetime(2017, 5, 3, 13, 0, 0))
            #end_time = self.local_tz.localize(datetime(2017, 5, 3, 17, 0, 0))
            start_time = self.start_time
            end_time = self.end_time
            # RPC call to OpenADR VEN to get OpenADR info
            if start_time is None or end_time is None:
                try:
                    events = self.vip.rpc.call(
                        'openadr', 'get_events').get(timeout=60)
                    for event in events:
                        start_time = parser.parse(event['start_time'])
                        end_time = parser.parse(event['end_time'])
                        if start_time.tzinfo is None:
                            tz_replace = dateutil.tz.gettz(self.tz)
                            start_time = self.start_time.replace(tzinfo=tz_replace)
                        if end_time.tzinfo is None:
                            tz_replace = dateutil.tz.gettz(self.tz)
                            end_time = self.end_time.replace(tzinfo=tz_replace)
                except Exception as e:
                    _log.debug("TargetAgentError: Cannot RPC call to OpenADR agent")
                    _log.debug(e.message)
        else:
            start_time = self.local_tz.localize(self.start_time)
            end_time = self.local_tz.localize(self.end_time)

        if start_time is not None and end_time is not None:
            event_info['start'] = start_time.astimezone(pytz.utc)
            event_info['end'] = end_time.astimezone(pytz.utc)

        return event_info

    def get_baseline_targets(self, cur_time_utc, start_utc, end_utc, cbps):
        """
        Get baseline value from PGNE agent
        Returns:
            Average value of the next 2 baseline prediction
        """
        baseline_target = None
        message = []
        prev_dr_days = self.get_prev_dr_days()
        try:
            message = self.vip.rpc.call(
                'baseline_agent', 'get_prediction',
                format_timestamp(cur_time_utc),
                format_timestamp(start_utc),
                format_timestamp(end_utc),
                'UTC', prev_dr_days).get(timeout=60)
        except:
            _log.debug("TargetAgentError: Cannot RPC call to PGnE baseline agent")

        if len(message) > 0:
            values = message[0]
            prediction0 = float(values["value_hr0"]) #next hour
            prediction1 = float(values["value_hr1"]) #next hour+1
            prediction2 = float(values["value_hr2"]) #next hour+2
            #baseline_target = (prediction1+prediction2)/2.0
            #baseline_target = [prediction1-x for x in cbp]
            #Approach after 07/31
            # delta = (prediction2 - prediction1) / float(len(cbps))
            # baseline_target = []
            # for index, cbp in enumerate(cbps):
            #     baseline_target.append(prediction1+index*delta - cbp)
            #Approach after Aug6
            delta = (prediction1 - prediction0) / float(len(cbps))
            baseline_target = []
            for index, cbp in enumerate(cbps):
                #baseline_target.append(prediction0 + index * delta - cbp)
                baseline_target.append(prediction1)

        return baseline_target

    def get_target_info_wbe(self, in_time, in_tz):
        """
        Combine event start, end, and baseline target
        Inputs:
            in_time: string cur_time
            in_tz: string timezone
        Returns:
            A dictionary of start, end datetime and baseline target
        """
        target_info = []
        event_info = self.get_event_info()
        _log.debug("TargetAgent: event info length is " +
                   str(len(event_info.keys())))
        if len(event_info.keys()) > 0:
            start = event_info['start']
            end = event_info['end']
            _log.debug('TargetAgent: EventInfo '
                       'Start: {start} End: {end} '.format(start=start,
                                                           end=end))
            cur_time = parser.parse(in_time)
            if cur_time.tzinfo is None:
                tz = pytz.timezone(in_tz)
                cur_time = tz.localize(cur_time)

            # Convert to UTC before doing any processing
            start_utc = start.astimezone(pytz.utc)
            end_utc = end.astimezone(pytz.utc)
            cur_time_utc = cur_time.astimezone(pytz.utc)
            one_hour = timedelta(hours=1)
            start_utc_prev_hr = start_utc - one_hour
            end_utc_prev_hr = end_utc - one_hour

            # Use occupancy time if cont_after_dr is enabled
            if self.cont_after_dr == 'yes' and self.dr_mode != 'open_adr':
                end_utc_prev_hr = self.occ_time_utc - one_hour

            if start_utc_prev_hr <= cur_time_utc < end_utc_prev_hr:
                next_hour_utc = \
                    cur_time_utc.replace(minute=0, second=0, microsecond=0) + one_hour
                next_hour_end = next_hour_utc.replace(minute=59, second=59)

                # Decide cpb value
                cur_time_local = cur_time_utc.astimezone(self.local_tz)
                cbp_idx = cur_time_local.hour + 1
                if cbp_idx >= len(self.cbps):
                    cbp_idx = 0
                cbps = self.cbps[cbp_idx]
                if cur_time_utc > end_utc:
                    cbps = [0, 0, 0, 0]

                ####### Calculate baseline target
                baseline = []
                with open(self.wbe_csv, 'rb') as csvfile:
                    reader = csv.reader(csvfile, delimiter=',')
                    for row in reader:
                        wbe_ts = parser.parse(row[0])
                        if wbe_ts.year == cur_time_local.year \
                                and wbe_ts.month == cur_time_local.month \
                                and wbe_ts.day == cur_time_local.day:
                            baseline = row[1:]
                            break
                baseline = [float(i) for i in baseline]

                value = {}
                meta2 = {'type': 'string', 'tz': 'UTC', 'units': ''}
                for i in range(0, 24):
                    ts = cur_time_local.replace(hour=i, minute=0, second=0)
                    ts_epoch = mktime(ts.timetuple())*1000
                    value[ts_epoch] = baseline[i]
                baseline_msg = [{
                    "value": value
                }, {
                    "value": meta2
                }]
                headers = {'Date': format_timestamp(get_aware_utc_now())}
                target_topic = '/'.join(['analysis', 'PGnE', self.site, self.building, 'baseline'])
                self.vip.pubsub.publish(
                    'pubsub', target_topic, headers, baseline_msg).get(timeout=10)
                _log.debug("PGnE {topic}: {value}".format(
                    topic=target_topic,
                    value=baseline_msg))

                meta = {'type': 'float', 'tz': self.tz, 'units': 'kW'}
                idx = cur_time_local.hour
                next_idx = idx+1
                if next_idx >= len(baseline):
                    next_idx = idx
                next_hr_baseline = baseline[next_idx]
                cur_idx = idx
                cur_hr_baseline = baseline[cur_idx]

                delta = (next_hr_baseline - cur_hr_baseline) / float(len(cbps))
                baseline_targets = []
                for index, cbp in enumerate(cbps):
                    baseline_targets.append(cur_hr_baseline + index * delta - cbp)

                ######End target calculation

                # Package output
                if baseline_targets is not None:
                    meta2 = {'type': 'string', 'tz': 'UTC', 'units': ''}
                    delta = timedelta(minutes=0)
                    for idx, cbp in enumerate(cbps):
                        new_start = next_hour_utc + delta
                        new_end = new_start + timedelta(minutes=14, seconds=59)
                        new_target = baseline_targets[idx]
                        target_info.append([{
                            "value": {
                                "id": format_timestamp(new_start),
                                "start": format_timestamp(new_start),
                                "end": format_timestamp(new_end),
                                "target": new_target,
                                "cbp": cbp
                            }
                        }, {
                            "value": meta2
                        }])
                        delta += timedelta(minutes=15)

                _log.debug(
                    "TargetAgent: At time (UTC) {ts}"
                    " TargetInfo is {ti}".format(ts=cur_time_utc,
                                                 ti=target_info))
            else:
                _log.debug('TargetAgent: Not in event time frame'
                           ' {start} {cur} {end}'.format(start=start_utc_prev_hr,
                                                         cur=cur_time_utc,
                                                         end=end_utc_prev_hr))
        return target_info

    def get_target_info_pgne(self, in_time, in_tz):
        """
        Combine event start, end, and baseline target
        Inputs:
            in_time: string cur_time
            in_tz: string timezone
        Returns:
            A dictionary of start, end datetime and baseline target
        """
        target_info = []
        event_info = self.get_event_info()
        _log.debug("TargetAgent: event info length is " +
                   str(len(event_info.keys())))
        if len(event_info.keys()) > 0:
            start = event_info['start']
            end = event_info['end']
            _log.debug('TargetAgent: EventInfo '
                       'Start: {start} End: {end} '.format(start=start,
                                                           end=end))
            cur_time = parser.parse(in_time)
            if cur_time.tzinfo is None:
                tz = pytz.timezone(in_tz)
                cur_time = tz.localize(cur_time)

            # Convert to UTC before doing any processing
            start_utc = start.astimezone(pytz.utc)
            end_utc = end.astimezone(pytz.utc)
            cur_time_utc = cur_time.astimezone(pytz.utc)
            one_hour = timedelta(hours=1)
            start_utc_prev_hr = start_utc - one_hour
            end_utc_prev_hr = end_utc - one_hour

            # Use occupancy time if cont_after_dr is enabled
            if self.cont_after_dr == 'yes' and self.dr_mode != 'open_adr':
                end_utc_prev_hr = self.occ_time_utc - one_hour

            # Progress only if current hour is in range of one hour before start_time and one hour before end_time
            if start_utc_prev_hr <= cur_time_utc < end_utc_prev_hr:
                next_hour_utc = \
                    cur_time_utc.replace(minute=0, second=0, microsecond=0) + one_hour
                next_hour_end = next_hour_utc.replace(minute=59, second=59)

                # Decide cpb value
                cur_time_local = cur_time_utc.astimezone(self.local_tz)
                cbp_idx = cur_time_local.hour + 1
                if cbp_idx >= len(self.cbps):
                    cbp_idx = 0
                cbps = self.cbps[cbp_idx]
                if cur_time_utc > end_utc:
                    cbps = [0, 0, 0, 0]

                # Calculate baseline target
                baseline_targets = self.get_baseline_targets(
                    cur_time_utc, start_utc, end_utc, cbps
                )

                # Package output
                if baseline_targets is not None:
                    #meta = {'type': 'float', 'tz': 'UTC', 'units': 'kW'}
                    #time_meta = {'type': 'datetime', 'tz': 'UTC', 'units': 'datetime'}
                    # target_info = [{
                    #     "id": format_timestamp(next_hour_utc),
                    #     "start": format_timestamp(next_hour_utc),
                    #     "end": format_timestamp(next_hour_end),
                    #     "target": baseline_target,
                    #     "cbp": cbp
                    # }, {
                    #     "id": time_meta,
                    #     "start": time_meta,
                    #     "end": time_meta,
                    #     "target": meta,
                    #     "cbp": meta
                    # }]
                    meta2 = {'type': 'string', 'tz': 'UTC', 'units': ''}
                    delta = timedelta(minutes=0)
                    for idx, cbp in enumerate(cbps):
                        new_start = next_hour_utc + delta
                        new_end = new_start + timedelta(minutes=14, seconds=59)
                        new_target = baseline_targets[idx]
                        target_info.append([{
                            "value": {
                                "id": format_timestamp(new_start),
                                "start": format_timestamp(new_start),
                                "end": format_timestamp(new_end),
                                "target": new_target,
                                "cbp": cbp
                            }
                        }, {
                            "value": meta2
                        }])
                        delta += timedelta(minutes=15)

                _log.debug(
                    "TargetAgent: At time (UTC) {ts}"
                    " TargetInfo is {ti}".format(ts=cur_time_utc,
                                                 ti=target_info))
            else:
                _log.debug('TargetAgent: Not in event time frame'
                           ' {start} {cur} {end}'.format(start=start_utc_prev_hr,
                                                         cur=cur_time_utc,
                                                         end=end_utc_prev_hr))
        return target_info

    def publish_target_info(self, cur_analysis_time_utc):
        if self.prediction_method == 'pge':
            self.publish_target_info_pgne(cur_analysis_time_utc)
        elif self.prediction_method == 'wbe':
            self.publish_target_info_wbe(cur_analysis_time_utc)

    def publish_target_info_wbe(self, cur_analysis_time_utc):
        cur_analysis_time_utc = parser.parse(cur_analysis_time_utc)
        try:
            target_messages = self.get_target_info_wbe(format_timestamp(cur_analysis_time_utc), 'UTC')
            if len(target_messages) > 0:

                target_topic = '/'.join(['analysis', 'target_agent', self.site, self.building, 'goal'])
                for target_message in target_messages:
                    headers = {'Date': format_timestamp(get_aware_utc_now())}
                    self.vip.pubsub.publish(
                        'pubsub', target_topic, headers, target_message).get(timeout=15)
                    _log.debug("TargetAgent {topic}: {value}".format(
                        topic=target_topic,
                        value=target_message))
                    gevent.sleep(2)
        except Exception as e:
            _log.error("TargetAgent: Exception " + str(e))

        # Schedule next run at min 30 of next hour only if current min >= 30
        one_hour = timedelta(hours=1)
        cur_min = cur_analysis_time_utc.minute
        next_analysis_time = cur_analysis_time_utc.replace(minute=30,
                                                           second=0,
                                                           microsecond=0)
        if cur_min >= 30:
            next_analysis_time += one_hour

        next_run_time = next_analysis_time
        if self.dr_mode == 'dev':
            next_run_time = get_aware_utc_now() + timedelta(seconds=15)

        if self.dr_mode != 'manual':
            self.core.schedule(next_run_time, self.publish_target_info,
                               format_timestamp(next_analysis_time))

    def publish_target_info_pgne(self, cur_analysis_time_utc):
        cur_analysis_time_utc = parser.parse(cur_analysis_time_utc)

        target_messages = self.get_target_info_pgne(format_timestamp(cur_analysis_time_utc), 'UTC')
        if len(target_messages) > 0:

            target_topic = '/'.join(['analysis', 'target_agent', self.site, self.building, 'goal'])
            for target_message in target_messages:
                headers = {'Date': format_timestamp(get_aware_utc_now())}
                self.vip.pubsub.publish(
                    'pubsub', target_topic, headers, target_message).get(timeout=15)
                _log.debug("TargetAgent {topic}: {value}".format(
                    topic=target_topic,
                    value=target_message))
                gevent.sleep(2)

        # Schedule next run at min 30 of next hour only if current min >= 30
        one_hour = timedelta(hours=1)
        cur_min = cur_analysis_time_utc.minute
        next_analysis_time = cur_analysis_time_utc.replace(minute=30,
                                                           second=0,
                                                           microsecond=0)
        if cur_min >= 30:
            next_analysis_time += one_hour

        next_run_time = next_analysis_time
        if self.dr_mode == 'dev':
            next_run_time = get_aware_utc_now() + timedelta(seconds=15)

        if self.dr_mode != 'manual':
            self.core.schedule(next_run_time, self.publish_target_info,
                               format_timestamp(next_analysis_time))


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(TargetAgent)
    except Exception as e:
        _log.exception('unhandled exception ' + str(e))


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
