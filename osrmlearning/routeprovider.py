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
from enum import auto, Enum
import logging
import random

import numpy as np

from osrmlearning import hereclient, planclient, config


class Source(Enum):
    COURIER_LOCATIONS = auto()
    EXECUTED_PLANS = auto()
    PLANS = auto()
    HERE_DB_PLANS = auto()
    HERE_DB_ALL = auto()


def get_routes(source: Source) -> list:
    if source is Source.COURIER_LOCATIONS:
        routes = planclient.get_routes_from_locations(
            timestamp=datetime.datetime.strptime(config.courier_locations.timestamp, config.server.date_format),
            step=config.courier_locations.step,
        )
    elif source is Source.EXECUTED_PLANS:
        routes = planclient.get_routes(executed=True)
    elif source is Source.PLANS:
        routes = planclient.get_routes(executed=False)
    elif source is Source.HERE_DB_ALL:
        routes = hereclient.get_routes()
    elif source is Source.HERE_DB_PLANS:
        here_routes = hereclient.get_routes()
        planned_routes_coordinates = [
            planned_route.coordinates
            for planned_route in planclient.get_routes(executed=False)
        ]
        routes = [
            here_route
            for here_route in here_routes
            if here_route.coordinates in planned_routes_coordinates
        ]
        logging.info('Found travel times for {} out of {} routes in Here DB, skipping {} routes'.format(
            len(routes),
            len(here_routes),
            len(here_routes) - len(routes),
        ))
    else:
        raise ValueError('Invalid route source')
    return routes


# https://stackoverflow.com/a/16562028
def reject_outliers(routes: list, tolerance=float(config.routes.outlier_tolerance)) -> list:
    routes = list(route for route in routes if route.reference_travel_time > 0)
    data = np.array([route.reference_travel_time for route in routes])
    routes = np.array(routes)
    d = np.abs(data - np.median(data))
    mdev = np.median(d)
    s = d / mdev if mdev else 0.
    filtered_routes = list(routes[s < tolerance])
    logging.info('Outlier tolerance = {}. Filtered {} outliers from {} routes, keeping {} routes'.format(
        tolerance,
        len(routes) - len(filtered_routes),
        len(routes),
        len(filtered_routes),
    ))
    return filtered_routes


def remove_min_max_routes(routes: list) -> list:
    filtered_routes = [
        route for route in routes
        if int(config.routes.min_travel_time) * int(config.courier_locations.step)
        < route.reference_travel_time
        < int(config.routes.max_travel_time) * int(config.courier_locations.step)
    ]
    logging.info('Removed {} routes that are not ({} s < route < {} s) from {} routes, keeping {} routes'.format(
        len(routes) - len(filtered_routes),
        int(config.routes.min_travel_time) * int(config.courier_locations.step),
        int(config.routes.max_travel_time) * int(config.courier_locations.step),
        len(routes),
        len(filtered_routes),
    ))
    return filtered_routes


def remove_non_moving_routes(routes: list) -> list:
    return [route for route in routes if route.coordinates.split(';')[0] != route.coordinates.split(';')[1]]


def enforce_max_count(routes: list) -> list:
    max_count = int(config.routes.max_count)
    if len(routes) <= max_count:
        return routes
    return routes[:max_count]


def randomize(routes: list) -> list:
    random.shuffle(routes)
    return routes


if __name__ == '__main__':
    print(get_routes(Source.PLANS))
