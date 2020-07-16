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
import math
import random

from osrmlearning import config
# from osrmlearning.hereclient import get_travel_time_by_route  # avoid invalid cyclic import
import osrmlearning.hereclient
from osrmlearning.osmdatabase import OsmDatabase
from osrmlearning.osrmclient import get_osrm_route


# FIXME routes from here db break (as train source) because they do not have timestamps
class Route(object):
    def __init__(
            self,
            coordinates: str,
            start_timestamp: datetime.datetime = None,
            end_timestamp: datetime.datetime = None,
            reference_travel_time: float = None,
            osrm_travel_time: float = None,
            osm_tag_counts: dict = None,
            input_count=1,
    ):
        # if start_timestamp is None or end_timestamp is None:
        #     raise RuntimeError
        self.coordinates = coordinates
        self.start_timestamp = start_timestamp
        self.end_timestamp = end_timestamp
        self._reference_travel_time = reference_travel_time
        self.osrm_travel_time = osrm_travel_time
        self.osm_tag_counts = osm_tag_counts
        self.tf_scaled_osrm_travel_time = None
        self.tf_final_osrm_travel_time = None
        self.here_travel_time = None
        self.nodes = None
        self.ways = None
        self.input_count = input_count

    def set_osrm_travel_time(self):
        self.osrm_travel_time, self.nodes = get_osrm_route(self.coordinates)

    def set_osm_tag_counts(self):
        if self.nodes is None:
            raise RuntimeError('First initialize nodes by calling set_osrm_travel_time()')
        db = OsmDatabase.get_instance()
        osm_tag_counts = db.get_all_tags_by_nodes(self.nodes)
        self.osm_tag_counts = {tag: osm_tag_counts.get(tag, 0) for tag in config.osm.tags}

    def set_ways(self):
        if self.nodes is None:
            raise RuntimeError('First initialize nodes by calling set_osrm_travel_time()')
        db = OsmDatabase.get_instance()
        self.ways = db.get_ways_by_nodes(self.nodes)

    def set_tf_scaled_osrm_travel_time(self, prediction: float):
        self.tf_scaled_osrm_travel_time = self.osrm_travel_time * prediction

    def set_tf_final_osrm_travel_time(self, port: int):
        self.tf_final_osrm_travel_time = get_osrm_route(self.coordinates, port=port)[0]

    def set_here_travel_time(self):
        self.here_travel_time = osrmlearning.hereclient.get_here_route(self.coordinates)
        # self.here_travel_time = osrmlearning.hereclient.get_travel_time_by_route(self)

    @property
    def reference_travel_time(self):
        return self._reference_travel_time or float((self.end_timestamp - self.start_timestamp).seconds)

    @property
    def travel_time_ratio(self) -> float:
        """The reference travel time divided by the travel time returned by plain OSRM (without TensorFlow)."""
        try:
            return self.reference_travel_time / self.osrm_travel_time
        except ZeroDivisionError:
            # in doubt: assume no scaling factor
            return 1.0

    @property
    def plain_osrm_error(self) -> float:
        """The error of the travel time returned by plain OSRM (without TensorFlow)."""
        try:
            return (self.osrm_travel_time - self.reference_travel_time) / self.reference_travel_time
        except ZeroDivisionError:
            return float('nan')

    @property
    def tf_scaled_osrm_error(self) -> float:
        """The error of the travel time returned by plain OSRM scaled with TensorFlow (for the entire route)."""
        if self.tf_scaled_osrm_travel_time is None:
            raise RuntimeError('Value was not yet initialized')
        try:
            return (self.tf_scaled_osrm_travel_time - self.reference_travel_time) / self.reference_travel_time
        except ZeroDivisionError:
            return float('nan')

    @property
    def tf_final_osrm_error(self) -> float:
        """The error of the travel time returned by newly built OSRM (each way scaled individually by TensorFlow)."""
        if self.tf_final_osrm_travel_time is None:
            raise RuntimeError('Value was not yet initialized')
        try:
            return (self.tf_final_osrm_travel_time - self.reference_travel_time) / self.reference_travel_time
        except ZeroDivisionError:
            return float('nan')

    @property
    def here_error(self) -> float:
        # if self.here_travel_time is None:
        #     self.set_here_travel_time()
        if self.here_travel_time and math.isfinite(self.here_travel_time):
            return (self.here_travel_time - self.reference_travel_time) / self.reference_travel_time
        else:
            return float('nan')
            # return -1.0

    @property
    def scaled_improvement(self) -> float:
        """The level of improvement of the accuracy of the travel time returned by plain OSRM scaled with TensorFlow."""
        if math.isnan(self.plain_osrm_error) or math.isnan(self.tf_scaled_osrm_error):
            return 0
        return abs(self.plain_osrm_error) - abs(self.tf_scaled_osrm_error)

    @property
    def final_improvement(self) -> float:
        """The level of improvement of the accuracy of the travel time returned by newly built OSRM."""
        if math.isnan(self.plain_osrm_error) or math.isnan(self.tf_final_osrm_error):
            return 0
        return abs(self.plain_osrm_error) - abs(self.tf_final_osrm_error)

    @property
    def osm_tag_fractions(self) -> dict:
        # if config.tensorflow.binary_tags != '0':
        if config.tensorflow.binary_tags == '1':
            binary_tags = self.osm_tag_counts.copy()
            binary_tags.update({tag: 1 for tag, count in binary_tags.items() if count > 0})
            return binary_tags
        counts = self.osm_tag_counts
        fractions = dict.fromkeys(counts, 0.0)
        total = sum(counts.values())
        if not total:
            return fractions  # don't divide by zero
        for tag in fractions:
            fractions[tag] = counts[tag] / total
        return fractions

    def __str__(self):
        return 'Route({}, {})'.format(
            self.coordinates,
            self.reference_travel_time,
            # self.osrm_travel_time,
            # self.tf_scaled_osrm_travel_time,
            # self.tf_final_osrm_travel_time,
            # self.osm_tag_counts,
            # {tag: count for tag, count in self.osm_tag_counts.items() if count},
        )

    def __repr__(self):
        return str(self)

    # def __eq__(self, o: 'Route'):
    #     return self.coordinates == o.coordinates


# for testing only, TODO remove later
def get_random_example_routes(route_count=3, max_occurrences_per_tag=3, max_travel_time=600) -> list:
    routes = []
    for _ in range(route_count):
        coordinates = '8.8473,53.1080;8.7859,53.0524'
        reference_travel_time = random.random() * max_travel_time
        osrm_travel_time = random.random() * max_travel_time
        osm_tag_counts = {}
        for tag in config.osm.tags:
            osm_tag_counts[tag] = random.randint(0, max_occurrences_per_tag)
        routes.append(Route(
            coordinates=coordinates,
            reference_travel_time=reference_travel_time,
            osrm_travel_time=osrm_travel_time,
            osm_tag_counts=osm_tag_counts,
        ))
    return routes


if __name__ == '__main__':
    # print(get_random_example_routes())
    route = Route(coordinates='53.1080,8.8473;53.0524,8.7859', reference_travel_time=600)
    route.set_here_travel_time()
    print(route.here_travel_time)
    print(100 * route.here_error)
