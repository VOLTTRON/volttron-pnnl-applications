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
# from __future__ import annotations
from typing import Dict, Tuple, Union, List
from datetime import datetime as dt, timedelta as td
import logging
import numpy as np
from .model import Johnson, Siemens, Carrier, Sbs
from .utils import get_cls_attrs
from volttron.platform.agent.utils import (setup_logging, format_timestamp, get_aware_utc_now)
from volttron.platform.scheduling import cron
from volttron.platform.vip.agent import Agent
import json

setup_logging()
_log = logging.getLogger(__name__)

OPTIMAL_START = 'OptimalStart'
OPTIMAL_START_MODEL = 'OptimalStartModel'
OPTIMAL_START_TIME = 'OptimalStartTimes'
MODELS = {'j': Johnson, 's': Siemens, 'c': Carrier, 'sbs': Sbs}
CONFIG_STORE = 'optimal_start.model'


class OptimalStartManager:

    def __init__(self, parent: Agent):
        self.base: Agent = parent
        self.models = {}
        self.weekend_holiday_models = {}
        self.result = {}
        self.previous_weekend_holiday = False
        self.run_schedule = None
        self.training_time = None
        self.schedule = parent.schedule
        self.config = parent.config

        self.core = parent.core
        self.vip = parent.vip
        self.identity = parent.core.identity
        self.weekend_holiday_trained = False
        self.base_record_topic = parent.base_record_topic
        self.earliest_start_time = self.base.earliest_start_time
        self.latest_start_time = self.base.latest_start_time

    def setup_optimal_start(self):
        """

        @return:
        @rtype:
        """
        self.models = self.load_models(self.config)
        self.weekend_holiday_models = self.load_models(self.config, weekend=True)
        self.core.schedule(cron('1 0 * * *'), self.set_up_run)
        self.core.schedule(cron('0 9 * * *'), self.train_models)

    def update_configurations(self, data):
        """

        @param data:
        @type data:
        @return:
        @rtype:
        """
        for tag, cls in self.models.items():
            cls._start(data, self.schedule)
        for tag, cls in self.weekend_holiday_models.items():
            cls._start(data, self.schedule)

    def set_up_run(self):
        """
        Run based daily based on cron schedule.  This method calculates the earliest start time
        and schedules the run_method.
        @return:
        @rtype:
        """
        _log.debug('Setting up run!')
        current_schedule = self.base.get_current_schedule()
        is_holiday = self.base.holiday_manager.is_holiday(dt.now())
        try:
            if current_schedule:
                if current_schedule == 'always_off' or is_holiday:
                    self.base.occupancy_control('unoccupied')
                elif current_schedule == 'always_on':
                    self.base.occupancy_control('occupied')
                else:
                    earliest = current_schedule.get('earliest')
                    if earliest:
                        e_hour = earliest.hour
                        e_minute = earliest.minute
                        run_time = dt.now().replace(hour=e_hour, minute=e_minute)
                        _log.debug('Schedule run method: %s', format_timestamp(run_time))
                        self.run_schedule = self.core.schedule(run_time, self.run_method)
        except Exception as ex:
            _log.debug('Error setting up optimal start run: %s', ex)
        finally:
            self.base.data_handler.process_data()

    def get_start_time(self):
        """
        Get optimal start time from active controller
        @return:
        @rtype:
        """
        try:
            start_times = [value for key, value in self.result.items() if key in MODELS.keys()]
            active_minutes = np.median(start_times)
            _log.debug(f'OPTIMAL START - start_times: {self.result} -- median: {active_minutes}')
        except Exception as ex:
            _log.debug(f'OPTIMAL START ERROR - start_times: {self.result} -- error: {ex}')
            active_minutes = self.earliest_start_time
        return max(self.latest_start_time, min(active_minutes, self.earliest_start_time))

    def run_method(self):
        """
        Run at the earliest start time for the day.  Use models to calculate needed
        prestart time to meet room temperature requirements.
        @return:
        @rtype:
        """
        self.result = {}
        current_schedule = self.base.get_current_schedule()
        if not current_schedule:
            _log.debug(f'{self.identity } - no schedule configured returned for current day!')
            return
        if 'start' not in current_schedule:
            _log.debug(f'{self.identity } - no occupancy start time in current schedule!')
            return
        if 'end' not in current_schedule:
            _log.debug(f'{self.identity } - no occupancy end time in current schedule!')
            return
        start = current_schedule.get('start')
        end = current_schedule.get('end')
        s_hour = start.hour
        s_minute = start.minute
        e_hour = end.hour
        e_minute = end.minute
        occupancy_time = dt.now().replace(hour=s_hour, minute=s_minute)
        unoccupied_time = dt.now().replace(hour=e_hour, minute=e_minute)

        # If previous day was weekend or holiday and holiday models exist
        # calculate optimal start time using weekend/holiday models.
        yesterday = dt.now() - td(days=1)
        yesterday_holiday = self.base.holiday_manager.is_holiday(yesterday)
        yesterday_weekend = yesterday.weekday() >= 5
        self.previous_weekend_holiday = True if yesterday_holiday or yesterday_weekend else False
        if self.previous_weekend_holiday and self.weekend_holiday_trained:
            models = self.weekend_holiday_models
        else:
            models = self.models

        for tag, model in models.items():
            data = self.base.data_handler.df
            try:
                optimal_start_time = model.calculate_prestart(data)
            except Exception as ex:
                _log.debug(f'{self.identity} - Error for optimal start: {tag} -- {ex}')
                continue
            self.result[tag] = optimal_start_time

        self.result['occupancy'] = format_timestamp(occupancy_time)
        active_minutes = self.get_start_time()
        self.training_time = active_minutes
        optimal_start_time = occupancy_time - td(minutes=active_minutes)
        reschedule_time = dt.now() + td(minutes=15)
        if reschedule_time < optimal_start_time:
            _log.debug('Reschedule run method!')
            self.run_schedule = self.core.schedule(reschedule_time, self.run_method)
            return

        _log.debug('%s - Optimal start result: %s', self.identity, self.result)
        headers = {"Date": format_timestamp(get_aware_utc_now())}
        topic = '/'.join([self.base_record_topic, OPTIMAL_START_TIME])
        self.vip.pubsub.publish('pubsub', topic, headers, self.result).get(timeout=10)
        self.start_obj = self.core.schedule(optimal_start_time, self.base.occupancy_control, "occupied")
        self.end_obj = self.core.schedule(unoccupied_time, self.base.occupancy_control, "unoccupied")

    def load_models(self, config, weekend=False):
        """
        Create or load model pickle (trained model instance).
        @param config:
        @type config:
        @param weekend:
        @type weekend:
        @return:
        @rtype: Class Model
        """
        models = {}
        if weekend:
            config.update({'training_interval': 5})
        for name, cls in MODELS.items():
            tag = "_".join([name, 'we']) if weekend else name
            _cls = cls(config, self.schedule)
            try:
                cls_attrs = self.vip.config.get(tag)
                _cls.load_model(cls_attrs)
            except KeyError as ex:
                _log.debug(f'{self.identity}: config not in store: {tag} - {ex}')
            models[tag] = _cls
        return models

    def train_models(self):
        """
        Run daily after startup to update model coefficients.
        Save each model class as a pickle to allow saving state.
         - train each model with morning startup data.
         - Save model as pickle on disk for saving state.
        @return:
        @rtype:
        """
        training_time = int(self.training_time) + 5 if self.training_time else None
        data = self.base.data_handler.df
        models = self.models
        if self.previous_weekend_holiday:
            models = self.weekend_holiday_models
            self.weekend_holiday_trained = True

        for tag, model in models.items():
            try:
                model.train(data, training_time)
            except Exception as ex:
                _log.debug(f'{self.identity} - ERROR training model {tag}: -- {ex}')
                continue
            try:
                cls_attrs = get_cls_attrs(model)
                cls_attrs.pop('schedule')
                cls_attrs.pop('config')
                self.vip.config.set(tag, cls_attrs, send_update=False)
                _file = self.base.model_path + f'/{self.base.device}_{tag}.json'
                with open(_file, 'w') as fp:
                    json.dump(cls_attrs, fp, indent=4)
            except Exception as ex:
                _log.debug(f'{self.identity} - Could not store object {tag} -- {ex}')
            try:
                record = model.record
                _log.debug(f'{self.identity}: MODEL parameters: {record}')
                if record:
                    headers = {'Date': format_timestamp(get_aware_utc_now())}
                    topic = '/'.join([self.base_record_topic, OPTIMAL_START_MODEL, tag])
                    self.vip.pubsub.publish('pubsub', topic, headers, record)
            except Exception as ex:
                _log.debug(f'{self.identity} - ERROR publishing optimal start model information: {ex}')
                continue
