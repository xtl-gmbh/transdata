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
import json
import logging
import os
import urllib.error
import urllib.request

from progress.bar import Bar

from osrmlearning import config
# from osrmlearning.route import Route  # avoid invalid cyclic import
import osrmlearning.route

_routes = None
_routes_dict = None
_rw_file_dict = None


def get_routes() -> list:
    global _routes
    global _routes_dict
    if _routes:
        return _routes
    with open(config.here.file) as database:
        bar = Bar('Reading Here DB:', max=(sum(1 for _ in database)), suffix=config.progress.suffix)
        database.seek(0)
        _routes = []
        _routes_dict = dict()
        for row in database:
            bar.next()
            items = row.split(';')
            coordinates = ';'.join(items[0:2])
            travel_time = int(items[3])
            route = osrmlearning.route.Route(coordinates, reference_travel_time=travel_time)
            _routes.append(route)
            _routes_dict[coordinates] = travel_time
        bar.finish()
        logging.info('Got {} routes from Here DB in {} seconds'.format(bar.index, bar.elapsed))
        return _routes


def get_travel_time_by_route(route: 'osrmlearning.route.Route') -> float:
    if config.routes.eval_source == 'COURIER_LOCATIONS':
        return 0.0
    if not _routes_dict:
        get_routes()
    coordinates = route.coordinates
    if coordinates in _routes_dict:
        return _routes_dict[coordinates]
    logging.info('No Here route for coordinates {}'.format(coordinates))
    return float('nan')


def get_here_route(coordinates: str) -> float:
    global _rw_file_dict
    if _rw_file_dict is None and os.path.exists(config.here.rw_file):
        with open(config.here.rw_file) as database:
            bar = Bar('Reading Here DB:', max=(sum(1 for _ in database)), suffix=config.progress.suffix)
            database.seek(0)
            _rw_file_dict = dict()
            for row in database:
                bar.next()
                items = row.split(';')
                local_coordinates = ';'.join(items[0:2])
                travel_time = int(items[3])
                _rw_file_dict[local_coordinates] = travel_time
            bar.finish()
            logging.info('Got {} routes from Here DB in {} seconds'.format(bar.index, bar.elapsed))
    if _rw_file_dict is not None and coordinates in _rw_file_dict:
        return _rw_file_dict[coordinates]
    return _get_here_route(coordinates)


def _get_here_route(coordinates: str) -> float:
    waypoint0, waypoint1 = coordinates.split(';')
    # https://developer.here.com/documentation/routing/topics/request-a-simple-route.html
    # url = '''
    #     https://route.api.here.com/routing/7.2/calculateroute.json
    #     ?app_id={}
    #     &app_code={}
    #     &waypoint0=geo!{}
    #     &waypoint1=geo!{}
    #     &mode={}
    # '''
    # https://developer.here.com/documentation/routing/topics/request-matrix-of-routes.html
    url = '''
        https://matrix.route.api.here.com/routing/7.2/calculatematrix.json
        ?app_id={}
        &app_code={}
        &start0=geo!{}
        &destination0=geo!{}
        &mode={}
        &summaryAttributes=traveltime,distance
    '''
    url = url.replace(' ', '').replace('\n', '').format(
        config.here.app_id,
        config.here.app_code,
        waypoint0,
        waypoint1,
        config.here.mode,
    )
    try:
        response = json.loads(urllib.request.urlopen(url).read().decode())
        # print(url)
        # print(response)
        # response = response['response']['route'][0]['summary']
        try:
            response = response['response']['matrixEntry'][0]['summary']
        except KeyError:
            logging.info('coordinates = ' + coordinates)
            logging.info('response = ' + str(response))
            return float('nan')
        distance = response['distance']
        travel_time = response['travelTime']
        fetched_at = int(datetime.datetime.now().timestamp())
        departure_time = 'empty'
        line = ';'.join(str(item) for item in [waypoint0, waypoint1, distance, travel_time, fetched_at, departure_time])
        with open(config.here.rw_file, 'a') as f:
            f.write(line + '\n')
            global _rw_file_dict
        if _rw_file_dict is None:
            _rw_file_dict = dict()
        _rw_file_dict[coordinates] = float(travel_time)
        return float(travel_time)
    except urllib.error.HTTPError:
        print(url)
        raise


if __name__ == '__main__':
    # print(get_here_route('52.5,13.4;52.5,13.45'))
    # print(get_here_route('53.108283,8.847891;53.109128,8.847592'))
    # print(get_here_route('48.272006,10.888085;48.04582,10.48295'))
    # print(get_here_route('48.93115,10.83972;53.109128,8.847592'))
    # print(get_here_route('48.29299,10.89572;48.29643,10.90232'))
    print(get_here_route('48.35306,10.89467;48.35344,10.90424'))
