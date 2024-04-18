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
import json
import logging
from datetime import datetime as dt
from datetime import timedelta as td

import numpy as np
from volttron.platform.agent.utils import format_timestamp, get_aware_utc_now
from volttron.platform.scheduling import cron

from . import DefaultConfig, OptimalStartConfig
from .data_utils import Data
from .holiday_manager import HolidayManager
from .optimal_start_models import Carrier, Johnson, Sbs, Siemens
from .points import OccupancyTypes
from .utils import get_cls_attrs

_log = logging.getLogger(__name__)

OPTIMAL_START = 'OptimalStart'
OPTIMAL_START_MODEL = 'OptimalStartModel'
OPTIMAL_START_TIME = 'OptimalStartTimes'
MODELS = {'j': Johnson, 's': Siemens, 'c': Carrier, 'sbs': Sbs}
CONFIG_STORE = 'optimal_start.models'
NUMBER_TYPE = (int, float, complex)


class OptimalStartManager:
    """
    Manages model storage and training, scheduling, and running optimal start.
    """

    def __init__(self, *, schedule: dict[str:dict[str, str]], config: DefaultConfig, identity: str,
                 config_get_fn: callable, scheduler_fn: callable, change_occupancy_fn: callable,
                 holiday_manager: HolidayManager, data_handler: Data, publish_fn: callable, config_set_fn: callable):
        """
        Manages the optimal start time for a device.

        :param schedule: A dictionary containing the schedule.
        :type schedule: dict[str:dict[str, str]]
        :param config: The default configuration.
        :type config: DefaultConfig
        :param identity: The identity string.
        :type identity: str
        :param config_get_fn: A callable for getting the configuration.
        :type config_get_fn: callable
        :param scheduler_fn: A callable for scheduling.
        :type scheduler_fn: callable
        :param change_occupancy_fn: A callable for changing occupancy.
        :type change_occupancy_fn: callable
        :param holiday_manager: The holiday manager.
        :type holiday_manager: HolidayManager
        :param data_handler: The data handler.
        :type data_handler: Data
        :param publish_fn: A callable for publishing.
        :type publish_fn: callable
        :param config_set_fn: A callable for setting the configuration.
        :type config_set_fn: callable
        """
        self.models = {}
        self.weekend_holiday_models = {}
        self.result = {}
        self.run_schedule = None
        self.training_time = None
        self.schedule = schedule
        self.config = config
        self.model_dir = config.model_dir
        self.device = config.system
        self.identity = identity

        self.weekend_holiday_trained = False
        self.base_record_topic = config.base_record_topic

        self.earliest_start_time = config.optimal_start.earliest_start_time
        self.latest_start_time = config.optimal_start.latest_start_time

        self.holiday_manager = holiday_manager
        self.data_handler = data_handler
        self.scheduler_fn = scheduler_fn
        self.change_occupancy_fn = change_occupancy_fn
        self.scheduler_greenlets = []
        self.publish_fn = publish_fn
        self.config_set_fn = config_set_fn
        self.config_get_fn = config_get_fn
        # Set and canceled in run_method.
        self.start_obj = None
        self.end_obj = None

    def setup_optimal_start(self):
        """
        Set up optimal start by loading models and scheduling.
        :return: None
        :rtype: None
        """
        self.models = self.load_models(self.config.optimal_start)
        self.weekend_holiday_models = self.load_models(self.config.optimal_start, weekend=True)
        if self.scheduler_greenlets is not None:
            for greenlet in self.scheduler_greenlets:
                greenlet.kill()
        self.scheduler_greenlets = []
        self.scheduler_greenlets.append(self.scheduler_fn(cron('1 0 * * *'), self.set_up_run))
        self.scheduler_greenlets.append(self.scheduler_fn(cron('0 9 * * *'), self.train_models))

    def update_model_configurations(self, config: OptimalStartConfig) -> None:
        """
        Receives configuration parameters for optimal start from config store callback.

        :param config: Optimal start configuration parameters
        """
        for tag, cls in self.models.items():
            cls.update_config(config, self.schedule)
        for tag, cls in self.weekend_holiday_models.items():
            cls.update_config(config, self.schedule)

    def set_up_run(self):
        """
        Run based daily based on cron schedule.  This method calculates the earliest start time
        and schedules the run_method.
        :return:
        :rtype:
        """
        current_schedule = self.config.get_current_day_schedule()
        is_holiday = self.holiday_manager.is_holiday(dt.now())
        try:
            if current_schedule:
                if current_schedule == 'always_off' or is_holiday:
                    self.change_occupancy_fn(OccupancyTypes.UNOCCUPIED)
                elif current_schedule == 'always_on':
                    self.change_occupancy_fn(OccupancyTypes.OCCUPIED)
                else:
                    earliest = current_schedule.earliest_start
                    if earliest:
                        e_hour = earliest.hour
                        e_minute = earliest.minute
                        run_time = dt.now().replace(hour=e_hour, minute=e_minute)
                        _log.debug('Schedule run method: %s', format_timestamp(run_time))
                        self.run_schedule = self.scheduler_fn(run_time, self.run_method)
        except Exception as ex:
            _log.debug('Error setting up optimal start run: %s', ex)
        finally:
            self.data_handler.process_data()

    def get_start_time(self):
        """
        Get optimal start time from active controller
        :return:
        :rtype:
        """
        try:
            start_times = [value for value in self.result.values() if isinstance(value, NUMBER_TYPE)]
            active_minutes = np.median(start_times)
            _log.debug(f'OPTIMAL START - start_times: {self.result} -- median: {active_minutes}')
        except Exception as ex:
            _log.debug(f'OPTIMAL START ERROR - start_times: {self.result} -- error: {ex}')
            active_minutes = self.earliest_start_time
        return max(self.latest_start_time, min(active_minutes, self.earliest_start_time))

    def is_weekend_holiday(self):
        """
        Check if previous day was a weekend or holiday for model training.
        :return: True if previous day was weekend or holiday False otherwise
        :rtype: bool
        """
        yesterday = dt.now() - td(days=1)
        yesterday_holiday = self.holiday_manager.is_holiday(yesterday)
        yesterday_weekend = yesterday.weekday() >= 5
        return yesterday_holiday or yesterday_weekend

    def run_method(self):
        """
        Run at the earliest start time for the day.  Use models to calculate needed
        prestart time to meet room temperature requirements.
        :return:
        :rtype:
        """
        self.result = {}
        current_schedule = self.config.get_current_day_schedule()
        if not current_schedule:
            _log.debug(f'{self.identity } - no schedule configured returned for current day!')
            return
        start = current_schedule.start
        end = current_schedule.end
        s_hour = start.hour
        s_minute = start.minute
        e_hour = end.hour
        e_minute = end.minute
        occupancy_time = dt.now().replace(hour=s_hour, minute=s_minute)
        unoccupied_time = dt.now().replace(hour=e_hour, minute=e_minute)

        # If previous day was weekend or holiday and holiday models exist
        # calculate optimal start time using weekend/holiday models.
        if self.is_weekend_holiday() and self.weekend_holiday_trained:
            models = self.weekend_holiday_models
        else:
            models = self.models

        for tag, model in models.items():
            data = self.data_handler.df.ffill()
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
        if self.run_schedule is not None:
            self.run_schedule.cancel()

        if reschedule_time < optimal_start_time:
            _log.debug('Reschedule run method!')
            self.run_schedule = self.scheduler_fn(reschedule_time, self.run_method)
            return

        _log.debug('%s - Optimal start result: %s', self.identity, self.result)
        headers = {'Date': format_timestamp(get_aware_utc_now())}
        topic = '/'.join([self.base_record_topic, OPTIMAL_START_TIME])
        self.publish_fn(topic, headers, self.result)
        if self.start_obj is not None:
            self.start_obj.cancel()
            self.start_obj = None
        if self.end_obj is not None:
            self.end_obj.cancel()
            self.end_obj = None

        self.start_obj = self.scheduler_fn(optimal_start_time, self.change_occupancy_fn, OccupancyTypes.OCCUPIED)
        self.end_obj = self.scheduler_fn(unoccupied_time, self.change_occupancy_fn, OccupancyTypes.UNOCCUPIED)

    def load_models(self, config: OptimalStartConfig, weekend=False):
        """
        Create or load model from the config store.
        :param config:
        :type config:
        :param weekend:
        :type weekend:
        :return:
        :rtype: Class Model
        """
        models = {}
        if weekend:
            config.training_period_window = 5
        for name, cls in MODELS.items():
            tag = '_'.join([name, 'we']) if weekend else name
            _cls = cls(config, self.config.get_current_day_schedule)
            try:
                cls_attrs = self.config_get_fn(tag)
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
        :return:
        :rtype:
        """
        training_time = int(self.training_time) + 5 if self.training_time else None
        data = self.data_handler.df.ffill()
        models = self.models
        if self.is_weekend_holiday():
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
                if 'cfg' in cls_attrs:
                    cls_attrs.pop('cfg')
                self.config_set_fn(tag, cls_attrs)
                _file = self.model_dir / f'{self.device}_{tag}.json'
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
                    self.publish_fn(topic, headers, record)
            except Exception as ex:
                _log.debug(f'{self.identity} - ERROR publishing optimal start model information: {ex}')
                continue
