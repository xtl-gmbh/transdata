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

import collections
import json
import logging
import urllib.error
import urllib.request

from osrmlearning import config

# url = 'http://localhost:5000/route/v1/car/8.8473,53.1080;8.7859,53.0524?overview=false'


def get_osrm_route(coordinates: str, host=None, port=None, profile=None) -> collections.namedtuple:
    """Return an object containing the OSRM travel time and OSM nodes for given coordinates"""
    # logging.debug('get_osrm_route({})'.format(coordinates))  # function is called in a loop, so don't fill up the log
    route = ';'.join(','.join(reversed(lat_lon.split(','))) for lat_lon in coordinates.split(';'))
    url_root = 'http://{}:{}'.format(host or config.osrm.host, port or config.osrm.port)
    url = '{}/route/v1/{}/{}?overview=false&annotations=true'.format(url_root, profile or config.osrm.profile, route)
    # logging.debug(url)
    try:
        response = json.loads(urllib.request.urlopen(url).read().decode())
    except urllib.error.HTTPError:
        logging.warning(url)
        raise
    # logging.debug(response)
    data = response['routes'][0]['legs'][0]
    nodes = tuple(data['annotation']['nodes'])
    duration = data['duration']
    # distance = data['distance']
    # logging.debug('duration={}, nodes={}'.format(duration, nodes))
    return collections.namedtuple('OsrmRoute', ['travel_time', 'osm_nodes'])(duration, nodes)


def osrm_request(query: str, host=None, port=None) -> str:
    """Forward a request to an OSRM instance running on a specified host+port and return the plain response"""
    url = 'http://{}:{}{}'.format(host or config.osrm.host, port or config.osrm.port, query)
    logging.debug(url)
    try:
        response = urllib.request.urlopen(url).read().decode()
    except urllib.error.HTTPError:
        logging.warning(url)
        raise
    logging.debug(response)
    return response


if __name__ == '__main__':
    print(get_osrm_route('8.8473,53.1080;8.7859,53.0524', 'localhost', 5000))
