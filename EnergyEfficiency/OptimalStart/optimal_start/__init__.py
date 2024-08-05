
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
import os
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Optional

from volttron.platform.messaging import topics, utils
from .points import DaysOfWeek, Points, PointValue

_log = logging.getLogger(__name__)


@dataclass
class Schedule:
    day: DaysOfWeek
    start: time = None
    end: time = None
    always_on: bool = False
    always_off: bool = False
    earliest_start_time: int = 120

    def is_always_off(self) -> bool:
        return self.always_off

    def is_always_on(self) -> bool:
        return self.always_on

    @cached_property
    def earliest_start(self) -> time:
        if self.always_on or self.always_off:
            return None
        bastion = datetime.now().replace(hour=self.start.hour, minute=self.start.minute, second=0, microsecond=0)
        bastion = bastion - timedelta(minutes=self.earliest_start_time)
        return datetime.time(bastion)

    def __post_init__(self):
        if self.always_on and self.always_off:
            raise ValueError('Schedule cannot be always on and always off.')
        if self.always_on or self.always_off:
            self.start = None
            self.end = None
        else:
            if not self.start or not self.end:
                raise ValueError('Schedule must have start and end times.')

            self.start = time(*[int(x) for x in str(self.start).split(':')])
            self.end = time(*[int(x) for x in str(self.end).split(':')])
            if self.start > self.end:
                raise ValueError('Schedule start time must be before end time.')


@dataclass
class OptimalStartConfig:
    latest_start_time: int
    earliest_start_time: int
    allowable_setpoint_deviation: int
    optimal_start_lockout_temperature: int = 30
    training_period_window: int = 10


@dataclass
class DefaultConfig:
    system: str
    campus: str = ''
    building: str = ''
    outdoor_temperature_topic: str = ''
    system_status_point: str = 'OccupancyCommand'
    local_tz: str = 'UTC'
    optimal_start: OptimalStartConfig = field(
        default_factory=lambda: OptimalStartConfig(latest_start_time=10,
                                                   earliest_start_time=180,
                                                   allowable_setpoint_deviation=1,
                                                   optimal_start_lockout_temperature=30))
    zone_point_names: dict[str, str] = field(default_factory=dict)
    schedule: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            'Monday': {
                'start': '6:30',
                'end': '18:00'
            },
            'Tuesday': {
                'start': '6:30',
                'end': '18:00'
            },
            'Wednesday': {
                'start': '6:30',
                'end': '18:00'
            },
            'Thursday': {
                'start': '6:30',
                'end': '18:00'
            },
            'Friday': {
                'start': '6:30',
                'end': '18:00'
            },
            'Saturday': 'always_off',
            'Sunday': 'always_off'
        })
    occupancy_values: dict[str, int] = field(default_factory=lambda: {'occupied': 1, 'unoccupied': 0})
    occupancy_current: str = 'occupied'
    actuator_identity: str = 'platform.driver'

    # Path for data being read from the thermostat and stored in dataframes for csv.
    data_dir: str = '~/.optimal_start'
    model_dir: str = '~/.optimal_start/models'
    data_file: Optional[Path] = None
    setpoint_offset: float = None

    def __post_init__(self):
        for k, v in self.zone_point_names.items():
            Points.add_item(k, v)
        if self.data_dir:
            self.data_dir = Path(self.data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.model_dir:
            self.model_dir = Path(self.model_dir).expanduser()
        self.model_dir.mkdir(parents=True, exist_ok=True)
        if isinstance(self.optimal_start, dict):
            self.optimal_start = OptimalStartConfig(**self.optimal_start)
        os.environ['LOCAL_TZ'] = self.local_tz
        self.data_file = self.data_dir / f"{self.system}.csv"
        self.validate()

    def __hash__(self):
        return hash(self.__repr__())

    def validate(self):
        # Make more assertions here.
        assert os.path.isdir(self.data_dir)

    @cached_property
    def timezone(self):
        from dateutil import tz
        return tz.gettz(self.local_tz)

    @property
    def base_device_topic(self) -> utils.Topic:
        return topics.DEVICES_VALUE(campus=self.campus, building=self.building, unit=self.system, path='', point='all')

    @property
    def system_rpc_path(self) -> utils.Topic:
        return topics.RPC_DEVICE_PATH(campus=self.campus, building=self.building, unit=self.system, path='', point='')

    @property
    def base_record_topic(self) -> utils.Topic:
        return self.base_device_topic.replace('devices', 'record').rstrip('/all')

    def update(self, other: DefaultConfig):
        for k, v in other.__dict__.items():
            if k == 'schedule':
                self.schedule.update(v)
            elif k == 'occupancy_values':
                self.occupancy_values.update(v)
            else:
                self.__setattr__(k, v)
        self.validate()

    @lru_cache
    def get_current_day_schedule(self) -> Schedule:
        """
        Returns the current days schedule based on the current day of the week.

        :return: Occupancy schedule for the current day.
        :rtype: Schedule
        """
        current_day = DaysOfWeek(datetime.now().weekday())
        current_schedule = None
        if self.schedule and current_day.name in self.schedule:
            sched = self.schedule[current_day.name]
            if isinstance(sched, dict):
                current_schedule = Schedule(current_day,
                                            earliest_start_time=self.optimal_start.earliest_start_time,
                                            **self.schedule[current_day.name])
            else:
                _log.debug(f'Using {sched} for {current_day.name}')
                if sched == 'always_on':
                    current_schedule = Schedule(current_day, always_on=True)
                elif sched == 'always_off':
                    current_schedule = Schedule(current_day, always_off=True)
                else:
                    raise ValueError(f'Invalid schedule value: {sched}')
        return current_schedule
