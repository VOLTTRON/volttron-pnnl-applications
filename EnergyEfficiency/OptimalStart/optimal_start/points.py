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
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import List


class OccupancyTypes(Enum):
    OCCUPIED = 'occupied'
    UNOCCUPIED = 'unoccupied'


@dataclass
class PointValue:
    value: str
    name: str


class _Points:
    def __init__(self):
        self._points: dict[str, PointValue] = {}
        self._curitter = None

    def add_item(self, key: str, value: str):
        self._points[key] = PointValue(value, key)

    def __getattr__(self, key: str) -> PointValue:
        return self._points[key]

    def keys(self) -> List[str]:
        return list(self._points.keys())

    def values(self) -> List[PointValue]:
        return list(self._points.values())

    def __iter__(self):
        self._curitter = iter(self._points)
        return self._curitter

    def __len__(self):
        return len(self._points)

    def __next__(self):
        item = next(self._curitter)
        return item


Points = _Points()
Points.add_item('zonetemperature', 'ZoneTemperature')
Points.add_item('coolingsetpoint', 'OccupiedCoolingSetPoint')
Points.add_item('heatingsetpoint', 'OccupiedHeatingSetPoint')
Points.add_item('supplyfanstatus', 'SupplyFanStatus')
Points.add_item('outdoorairtemperature', 'OutdoorAirTemperature')
Points.add_item('heating', 'FirstStageHeating')
Points.add_item('cooling', 'FirstStageCooling')
Points.add_item('occupancy', 'OccupancyCommand')
Points.add_item('auxiliaryheatcommand', 'AuxiliaryHeatCommand')
Points.add_item('economizersetpoint', 'EconomizerSwitchOverSetPoint')
Points.add_item('deadband', 'DeadBand')
Points.add_item('unoccupiedheatingsetpoint', 'UnoccupiedHeatingSetPoint')
Points.add_item('unoccupiedcoolingsetpoint', 'UnoccupiedCoolingSetPoint')
Points.add_item('occupiedsetpoint', 'OccupiedSetPoint')


class DaysOfWeek(IntEnum):
    Monday = 0
    Tuesday = 1
    Wednesday = 2
    Thursday = 3
    Friday = 4
    Saturday = 5
    Sunday = 6
