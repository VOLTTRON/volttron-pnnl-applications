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

import re
import logging
from typing import List, Set, Dict, Tuple, Iterable, Union
from sympy.parsing.sympy_parser import parse_expr
from sympy.logic.boolalg import Boolean

_log = logging.getLogger(__name__)


def clean_text(text: str, rep: dict = {}) -> str:
    """
    Removes special characters associated with mathematics from a string.

    :param text: string with special characters
    :type text: str
    :param rep: dictionary of special character replacements.
    :type rep: dict
    :return: string where special characters have been removed (replaced).
    :rtype: str
    """
    rep = rep if rep else {".": "_", "-": "_", "+": "_", "/": "_", ":": "_", " ": "_"}
    rep = dict((re.escape(k), v) for k, v in rep.items())
    pattern = re.compile("|".join(rep.keys()))
    new_key = pattern.sub(lambda m: rep[re.escape(m.group(0))], text)
    return new_key


def sympy_evaluate(condition: str, points: Iterable[Tuple[str, float]]) -> Union[bool, float]:
    """
    Calls clean_text to remove special characters from string in points,
    does string replace to for cleaned point in condition, and evaluates symbolic math
    condition.

    :param condition: string equation or condition.
    :type condition: str
    :param points: list of tuples with - [(point_name, value)] =
    :type points: list[tuples]
    :return: evaluated sympy expression
    :rtype: float or bool
    """
    cleaned_points = []
    cleaned_condition = condition
    for point, value in points:
        cleaned = clean_text(point)
        cleaned_condition = cleaned_condition.replace(point, cleaned)
        cleaned_points.append((cleaned, value))
    _log.debug(f"Sympy debug condition: {condition} -- {cleaned_condition}")
    _log.debug(f"Sympy debug points: {points} -- {cleaned_points}")
    equation = parse_expr(cleaned_condition)
    return_value = equation.subs(cleaned_points)
    if isinstance(return_value, Boolean):
        return bool(return_value)
    else:
        return float(return_value)


def parse_sympy(data: Union[List[str], str]) -> str:
    """
    Creates conditional from list of conditional components.

    :param data: List of conditional parts
    :type data: list

    :return: string of constructed condition for sympy
    :rtype: str
    """
    if isinstance(data, list):
        return_data = ""
        for item in data:
            parsed_string = "(" + item + ")" if item not in ("&", "|") else item
            return_data += parsed_string
    else:
        return_data = data
    return return_data


def create_device_topic_map(arg_list: Union[List[str], List[Tuple[str, str]]],
                            default_topic: str = ""
                            ) -> Tuple[Dict[str, str], Set[str]]:
    """
    Create device topic map for ingestion of data.

    :param arg_list: list of point names or point name, device topic pairs.
    :type arg_list: list
    :param default_topic: full topic for device
    :type default_topic: str
    :return result: dictionary of full point path: point
    :rtype result: dict
    :return topics: set of device topic strings
    :rtype topics: set
    """
    result = {}
    topics = set()
    for item in arg_list:
        if isinstance(item, str):
            point = item
            result[default_topic + '/' + point] = point
            topics.add(default_topic)
        elif isinstance(item, (list, tuple)):
            device, point = item
            result[device+'/'+point] = point
            topics.add(device)
    return result, topics


def fix_up_point_name(point: Union[str, List[str]], default_topic: str = "") -> Tuple[str, str]:
    """
    Create full point path from point and device topic.

    :param point: point name from device
    :type point: str
    :param default_topic: full topic for device
    :type default_topic: str
    :return: tuple with full point path and device topic
    :rtype: tuple
     """
    if isinstance(point, list):
        device, point = point
        return device + '/' + point, device
    elif isinstance(point, str):
        return default_topic + '/' + point, default_topic
