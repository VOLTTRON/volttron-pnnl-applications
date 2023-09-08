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
from datetime import datetime as dt
import logging
from volttron.platform.agent.utils import setup_logging
from pandas.tseries.holiday import AbstractHolidayCalendar, Holiday, USFederalHolidayCalendar, USLaborDay, USThanksgivingDay, USMemorialDay, USMartinLutherKingJr, USColumbusDay, USPresidentsDay
from pandas.tseries.holiday import *
from .holiday_utils import ALL_HOLIDAYS, OBSERVANCE

setup_logging()
_log = logging.getLogger(__name__)
# Default holiday list
RULES = [
        Holiday("New Year's Day", month=1, day=1, observance=nearest_workday),
        USMemorialDay,
        Holiday(
            "Juneteenth National Independence Day",
            month=6,
            day=19,
            start_date="2021-06-18",
            observance=nearest_workday,
        ),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Black Friday", month=11, day=1, offset=pd.DateOffset(weekday=FR(4))),
        Holiday("Christmas Eve", month=12, day=24),
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
]


class HolidayManager(AbstractHolidayCalendar):
    """
    ALL_HOLIDAYS = {
        "New Year's Day": Holiday("New Year's Day", month=1, day=1, observance=nearest_workday),
        "Marting Luther King Jr": USMartinLutherKingJr,
        "Presidents Day": USPresidentsDay,
        "Memorial Day": USMemorialDay,
        "JuneTeenth": Holiday(
            "Juneteenth National Independence Day",
            month=6,
            day=19,
            observance=nearest_workday,
            ),
        "Independence Day": Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        "Labor Day": USLaborDay,
        "Columbus Day": USColumbusDay,
        "Veterans Day": Holiday("Veterans Day", month=11, day=11, observance=nearest_workday),
        "Thanks Giving": USThanksgivingDay,
        "Black Friday": Holiday("Black Friday", month=11, day=1, offset=pd.DateOffset(weekday=FR(4))),
        "Christmas": Holiday("Christmas", month=12, day=25, observance=nearest_workday)
    }

    OBSERVANCE = {
        'after_nearest_workday': after_nearest_workday,
        'before_nearest_workday': before_nearest_workday,
        'nearest_workday': nearest_workday,
        'next_monday': next_monday,
        'next_workday': next_workday,
        'previous_workday': previous_workday,
        'previous_friday': previous_friday,
        'sunday_to_monday': sunday_to_monday
    }
    """
    def __init__(self, rules=RULES):
        super(HolidayManager, self).__init__(name='holidays', rules=rules)
        self.rules = rules
        self.hdays = pd.to_datetime(self.holidays(start='2023-01-01', end='2099-01-01'))

    def update_rules(self, rules):
        self._cache = None
        self.rules = rules
        self.hdays = pd.to_datetime(self.holidays(start='2023-01-01', end='2099-01-30'))

    def create_rules(self, rules):
        _rules = []
        for name, parms in rules.items():
            holiday = self.get_holiday(name, parms)
            if holiday is not None:
                _rules.append(holiday)
        return _rules

    def get_holiday(self, name, parms):
        holiday = None
        try:
            if name in ALL_HOLIDAYS:
                holiday = ALL_HOLIDAYS[name]
            else:
                _month = int(parms.get('month'))
                _day = int(parms.get('day'))
                observance = parms.get('observance')
                if observance is not None and observance in OBSERVANCE:
                    observance = OBSERVANCE[observance]
                    holiday = Holiday(name, month=_month, day=_day, observance=observance)
                else:
                    holiday = Holiday(name, month=_month, day=_day)
        except Exception as ex:
            holiday = None
            _log.debug(f'ERROR formulating holiday {name} -- {ex}')
        return holiday

    def is_holiday(self, _dt):
        _date = dt(year=_dt.year, month=_dt.month, day=_dt.day)
        return _date in self.hdays


