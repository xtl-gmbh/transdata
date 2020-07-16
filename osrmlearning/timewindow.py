# mFund TransData
# Copyright (C) 2020 XTL Kommunikationssysteme GmbH <info@xtl-gmbh.de>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import datetime
import logging

from osrmlearning import config
from osrmlearning.route import Route

_time_windows = None


# TODO support for hour AND minute?
class TimeWindow(object):
    def __init__(self, start_hour: int, end_hour: int, port: int):
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.port = port

    @property
    def is_default(self):
        return self.start_hour > self.end_hour

    @property
    def name(self):
        name = '{:02d}-00-{:02d}-00'.format(self.start_hour, self.end_hour)
        if self.is_default:
            return name + '-default'
        return name

    def __repr__(self):
        return self.name

    def __eq__(self, o: 'TimeWindow'):
        return self.name == o.name

    __hash__ = object.__hash__

    def filter_routes(self, routes: list, log=True) -> list:
        filtered_routes = [  # regular time window
            route for route in routes
            if self.start_hour <= route.start_timestamp.hour < self.end_hour
            or self.start_hour <= route.end_timestamp.hour < self.end_hour
            # and self.start_hour <= route.end_timestamp.hour < self.end_hour
            # TODO and/or?
        ] if self.start_hour < self.end_hour else [  # default time window for all remaining routes
            route for route in routes
            if route.start_timestamp.hour >= self.start_hour
            or route.start_timestamp.hour < self.end_hour
            or route.end_timestamp.hour >= self.start_hour
            or route.end_timestamp.hour < self.end_hour
        ]
        if log:
            logging.debug('Time window {} filter: Got {} routes, kept {} routes'.format(
                self.name,
                len(routes),
                len(filtered_routes),
            ))
        return filtered_routes


def get_time_window_by_route(route: Route) -> TimeWindow:
    return [
        time_window
        for time_window in get_time_windows()
        if len(time_window.filter_routes({route}, log=False))
    ][0]


def get_time_window_by_hour(hour: int) -> TimeWindow:
    timestamp = datetime.datetime(year=2018, month=1, day=1, hour=hour)
    return [
        time_window
        for time_window in get_time_windows()
        if len(time_window.filter_routes({Route(
            coordinates='temp', start_timestamp=timestamp, end_timestamp=timestamp)}, log=False))
    ][0]


def get_time_windows() -> list:
    global _time_windows
    if _time_windows is not None:
        return _time_windows
    first_window = int(config.time_windows.first_window)
    last_window = int(config.time_windows.last_window)
    window_step = int(config.time_windows.window_step)
    first_port = int(config.time_windows.first_port)
    last_port = int(first_port + (last_window - first_window) / window_step)
    _time_windows = []
    for time_window, port in zip(
            range(first_window, last_window + 1, window_step),
            range(first_port + 1, last_port + 1),
    ):
        _time_windows.append(TimeWindow(time_window, time_window + window_step, port))
    _time_windows.append(TimeWindow(last_window, first_window, first_port))
    return _time_windows


def test():
    import datetime
    time_windows = get_time_windows()
    print(time_windows)
    routes = [
        Route(
            coordinates='0.0,0.0;0.0,0.0',
            start_timestamp=datetime.datetime(year=2018, month=1, day=1, hour=hour),
            end_timestamp=datetime.datetime(year=2018, month=1, day=1, hour=hour),
        )
        for hour in range(24)
    ]
    for time_window in time_windows:
        print([route.start_timestamp.hour for route in time_window.filter_routes(routes)])


if __name__ == '__main__':
    test()
