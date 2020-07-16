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
from urllib.request import Request, urlopen

from osrmlearning import config, start_time
from osrmlearning.route import Route


def get_base_url_and_headers(protocol=None, host=None, port=None) -> tuple:
    base_url = '{}://{}:{}'.format(
        protocol or config.server.protocol,
        host or config.server.host,
        port or config.server.port,
    )
    headers = {'X-Api-Key': config.server.apikey}
    return base_url, headers


def get_routes(executed=True, scenario_ids=None, timestamps=True) -> list:
    base_url, headers = get_base_url_and_headers()
    date_format = config.server.date_format
    executed = 'executed-' if executed else ''

    def get(query: str, cache=None):
        filename = 'data/server/plans/{}.json'.format(query.replace('/', '').replace('?', '-').replace('=', '-'))
        if cache is None:
            cache = config.server.cache
            cache = cache == '1'
            # cache = cache != '0'
        exists = os.path.isfile(filename)
        if cache and exists:
            logging.debug(filename)
            with open(filename) as f:
                return json.load(f)
        url = ''.join([base_url, query])
        logging.debug(url)
        request = Request(url, headers=headers)
        try:
            response = json.loads(urlopen(request).read().decode())
        except urllib.error.HTTPError:
            print(url)
            raise
        with open(filename, 'w' if exists else 'x') as f:
            json.dump(response, f, indent=2)
        return response

    routes = []
    coordinates_travel_times = dict()
    scenarios = get('/scenarios', cache=False)
    logging.debug('Scenario IDs in server: {}'.format(sorted(scenario['id'] for scenario in scenarios)))
    # raise RuntimeError  # uncomment to only query scenario IDs
    scenario_ids = scenario_ids or config.routes.scenario_ids
    # TODO do scenario ids start at 0 or 1? Change handling if 0
    defined = all(int(scenario_id) > 0 for scenario_id in scenario_ids)
    scenario_ids = scenario_ids if defined else [scenario['id'] for scenario in scenarios]
    non_ready_scenarios = 0
    empty_scenarios = 0
    for scenario_id in scenario_ids:
        scenario = [scenario for scenario in scenarios if scenario['id'] == scenario_id]
        if len(scenario):
            scenario = scenario[0]
        else:
            logging.debug('No scenario with id {}'.format(scenario_id))
            continue
        if scenario['state'] != 'AWAITING_INPUT':
            non_ready_scenarios += 1
            continue
        plans = get('/{}plans?scenario={}'.format(executed, scenario['id']))
        if not len(plans):
            empty_scenarios += 1
            continue
        for plan in plans:
            stops = plan['stops']
            for stop1, stop2 in zip(stops[:-1], stops[1:]):
                coordinates = '{},{};{},{}'.format(
                    stop1['address']['locationLat'], stop1['address']['locationLon'],
                    stop2['address']['locationLat'], stop2['address']['locationLon'],
                )
                # coordinates = (
                #     (str(stop1['address']['locationLat']), str(stop1['address']['locationLon'])),
                #     (str(stop2['address']['locationLat']), str(stop2['address']['locationLon'])),
                # )
                start_timestamp = datetime.datetime.strptime(stop1['etd'], date_format)
                end_timestamp = datetime.datetime.strptime(stop2['eta'], date_format)
                if timestamps:
                    routes.append(Route(coordinates, start_timestamp, end_timestamp))
                    continue
                travel_time = (end_timestamp - start_timestamp).seconds
                if not travel_time:
                    continue
                if coordinates not in coordinates_travel_times:
                    coordinates_travel_times[coordinates] = [travel_time]
                else:
                    coordinates_travel_times[coordinates].append(travel_time)
    if not timestamps:
        for coordinates, travel_times in coordinates_travel_times.items():
            average_travel_time = sum(travel_times) / len(travel_times)
            routes.append(Route(coordinates, reference_travel_time=average_travel_time, input_count=len(travel_times)))
    logging.debug('Read {} scenarios, skipped {} non-ready scenarios and {} empty scenarios and kept {}'.format(
        len(scenario_ids),
        non_ready_scenarios,
        empty_scenarios,
        len(scenario_ids) - non_ready_scenarios - empty_scenarios,
    ))
    logging.debug('Got {} distinct routes and {} duplicates from {} valid scenarios'.format(
        len(routes),
        sum(route.input_count for route in routes) - len(routes),
        len(scenario_ids) - non_ready_scenarios - empty_scenarios,
    ))
    return routes


def get_routes_from_locations(timestamp=datetime.datetime.now() - datetime.timedelta(days=365), step=1) -> list:
    # TODO persistent cache
    # with open('data/server/locations/locations.csv') as f:
    #     ...
    base_url, headers = get_base_url_and_headers()
    date_format = config.server.date_format
    if type(timestamp) is str:
        # noinspection PyTypeChecker
        timestamp = datetime.datetime.strptime(timestamp, date_format)
    timestamp = datetime.datetime.strftime(timestamp, date_format)
    query = '/couriers/locations?timestamp={}&step={}'.format(timestamp, step)
    url = ''.join([base_url, query])
    logging.debug(url)
    request = Request(url, headers=headers)
    try:
        response = urlopen(request).read().decode()
    except urllib.error.HTTPError:
        print(url)
        raise
    filename = 'data/server/locations/{}.json'.format(start_time)
    if not os.path.isfile(filename):
        with open(filename, 'x') as f:
            f.write(response)
    try:
        # response = json.loads(response)[0]
        response = json.loads(response)[1]['rows']  # 'old API'
    except (TypeError, KeyError):
        response = json.loads(response)  # 'new API'
    routes = []
    for route in response:
        coordinates = '{},{};{},{}'.format(
            route['latitude1'], route['longitude1'],
            route['latitude2'], route['longitude2'],
        )
        routes.append(Route(
            coordinates,
            start_timestamp=datetime.datetime.strptime(route['timestamp1'], date_format),
            end_timestamp=datetime.datetime.strptime(route['timestamp2'], date_format),
        ))
    return routes


if __name__ == '__main__':
    routes1 = get_routes(executed=False, scenario_ids=(0,))
    routes2 = get_routes(executed=True, scenario_ids=(0,))
    routes3 = get_routes_from_locations()
    # print(routes3)
    print('''
        Routes from planned plans: {}
        Routes from executed plans: {}
        Routes from courier locations: {}
    '''.format(len(routes1), len(routes2), len(routes3)))
