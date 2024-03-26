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
from datetime import datetime
from typing import Optional

import pandas as pd
from pandas.tseries.holiday import (FR, AbstractHolidayCalendar, Holiday,
                                    USLaborDay, USMemorialDay,
                                    USThanksgivingDay, nearest_workday)

from .holiday_utils import ALL_HOLIDAYS, OBSERVANCE

_log = logging.getLogger(__name__)
# Default holiday list
RULES = [
    Holiday("New Year's Day", month=1, day=1, observance=nearest_workday),
    USMemorialDay,
    Holiday(
        'Juneteenth National Independence Day',
        month=6,
        day=19,
        start_date='2021-06-18',
        observance=nearest_workday,
    ),
    Holiday('Independence Day', month=7, day=4, observance=nearest_workday),
    USLaborDay,
    USThanksgivingDay,
    Holiday('Black Friday', month=11, day=1, offset=pd.DateOffset(weekday=FR(4))),
    Holiday('Christmas Eve', month=12, day=24),
    Holiday('Christmas', month=12, day=25, observance=nearest_workday),
]


class HolidayManager(AbstractHolidayCalendar):
    """
    A class representing a holiday manager.

    This class extends the AbstractHolidayCalendar class and provides functionality
    for managing and checking holidays.

    Attributes:
        ALL_HOLIDAYS (dict): A dictionary containing all the predefined holidays.
        OBSERVANCE (dict): A dictionary containing different observance options.

    Methods:
        __init__(self, rules=None): Initializes the HolidayManager object.
        update_rules(self, rules): Updates the holiday rules.
        create_rules(self, rules): Creates holiday rules based on the provided parameters.
        get_holiday(self, name, params): Retrieves a holiday based on the name and parameters.
        is_holiday(self, dt): Checks if a given date is a holiday.

    """

    def __init__(self, rules: Optional[list[Holiday]] = None):
        """
        Initialize the HolidayManager object.

        :param rules: Optional list of Holiday objects representing the holiday rules.
                      If not provided, the default RULES will be used.
        """
        if rules is None:
            rules = RULES
        super(HolidayManager, self).__init__(name='holidays', rules=rules)
        self.rules = rules
        self.hdays = pd.to_datetime(self.holidays(start='2023-01-01', end='2099-01-01'))

    def update_rules(self, rules: list[Holiday]):
        """
        Update the holiday rules.

        :param rules: List of Holiday objects representing the updated holiday rules.
        """
        self._cache = None
        self.rules = rules

    def create_rules(self, rules: dict[str, dict[str, int | str]]):
        """
        Create holiday rules based on the provided parameters.

        :param rules: Dictionary containing the holiday names and their parameters.
        :return: List of Holiday objects representing the created holiday rules.
        """
        _rules = []
        for name, params in rules.items():
            holiday = self.get_holiday(name, params)
            if holiday is not None:
                _rules.append(holiday)
        return _rules

    def get_holiday(self, name, params) -> Holiday | None:
        """
        Retrieve a holiday based on the name and parameters.

        :param name: Name of the holiday.
        :param params: Dictionary containing the parameters of the holiday.
        :return: Holiday object representing the retrieved holiday, or None if not found.
        """
        holiday = None

        if name in ALL_HOLIDAYS:
            holiday = ALL_HOLIDAYS[name]
        else:
            problems: list[str] = []
            try:
                _month = int(params.get('month'))
            except (ValueError, TypeError):
                problems.append(f"Invalid month: {params.get('month')}\n")
                _month = None
            try:
                _day = int(params.get('day'))
            except (ValueError, TypeError):
                problems.append(f"Invalid day: {params.get('day')}\n")
                _day = None

            if problems:
                _log.error(f'{[x for x in problems]}')
                return None

            observance = params.get('observance')

            if observance is not None and observance in OBSERVANCE:
                observance = OBSERVANCE[observance]
                holiday = Holiday(name, month=_month, day=_day, observance=observance)
            else:
                holiday = Holiday(name, month=_month, day=_day)

        return holiday

    def is_holiday(self, dt: datetime):
        """
        Check if a given date is a holiday.

        :param dt: Date to check.
        :return: True if the date is a holiday, False otherwise.
        """
        _date = datetime(year=dt.year, month=dt.month, day=dt.day)
        return (_date in self.hdays)
