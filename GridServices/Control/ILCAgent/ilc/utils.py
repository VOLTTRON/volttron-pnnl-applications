"""
-*- coding: utf-8 -*- {{{
vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

Copyright (c) 2017, Battelle Memorial Institute
All rights reserved.

1.  Battelle Memorial Institute (hereinafter Battelle) hereby grants
    permission to any person or entity lawfully obtaining a copy of this
    software and associated documentation files (hereinafter "the Software")
    to redistribute and use the Software in source and binary forms, with or
    without modification.  Such person or entity may use, copy, modify, merge,
    publish, distribute, sublicense, and/or sell copies of the Software, and
    may permit others to do so, subject to the following conditions:

    -   Redistributions of source code must retain the above copyright notice,
        this list of conditions and the following disclaimers.

    -	Redistributions in binary form must reproduce the above copyright
        notice, this list of conditions and the following disclaimer in the
        documentation and/or other materials provided with the distribution.

    -	Other than as used herein, neither the name Battelle Memorial Institute
        or Battelle may be used in any form whatsoever without the express
        written consent of Battelle.

2.	THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
    AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
    IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
    ARE DISCLAIMED. IN NO EVENT SHALL BATTELLE OR CONTRIBUTORS BE LIABLE FOR
    ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
    DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
    SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
    CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
    LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
    OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
    DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.

This material was prepared as an account of work sponsored by an agency of the
United States Government. Neither the United States Government nor the United
States Department of Energy, nor Battelle, nor any of their employees, nor any
jurisdiction or organization that has cooperated in the development of these
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
operated by
BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
}}}
"""

import re


def clean_text(text, rep={" ": ""}):
    rep = dict((re.escape(k), v) for k, v in rep.items())
    pattern = re.compile("|".join(rep.keys()))
    new_key = pattern.sub(lambda m: rep[re.escape(m.group(0))], text)
    return new_key


def parse_sympy(data, condition=False):
    """
    :param condition:
    :param data:
    :return:
    """
    if isinstance(data, dict):
        return_data = {}
        for key, value in data.items():
            new_key = clean_text(key)
            return_data[new_key] = value

    elif isinstance(data, list):
        if condition:
            return_data = ""
            for item in data:
                parsed_string = clean_text(item)
                parsed_string = "(" + clean_text(item) + ")" if parsed_string not in ("&", "|") else parsed_string
                return_data += parsed_string
        else:
            return_data = []
            for item in data:
                return_data.append(clean_text(item))
    else:
        return_data = clean_text(data)
    return return_data

def create_device_topic_map(arg_list, default_topic=""):
    result = {}
    topics = set()
    for item in arg_list:
        if isinstance(item, str):
            point = clean_text(item)
            result[default_topic + '/' + point] = point
            topics.add(default_topic)
        elif isinstance(item, (list, tuple)):
            device, point = item
            point = clean_text(point)
            result[device+'/'+point] = point
            topics.add(device)


    return result, topics

def fix_up_point_name(point, default_topic=""):
    if isinstance(point, list):
        device, point = point
        point = clean_text(point)
        return device + '/' + point, device
    elif isinstance(point, str):
        point = clean_text(point)
        return default_topic + '/' + point, default_topic