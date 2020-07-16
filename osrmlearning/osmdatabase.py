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

from collections import defaultdict
import logging

from postgres import Postgres

from osrmlearning import config


# TODO init DB, import OSM data with osmosis (pgsimp)
# http://download.geofabrik.de/europe/germany-latest.osm.pbf


class OsmDatabase(Postgres):
    _instance = None

    def __init__(self):
        # noinspection PyProtectedMember
        url = 'postgres://{}:{}@{}:{}/{}'.format(*config.postgres._asdict().values())
        # logging.debug(url)  # will log password!
        super().__init__(url)

    @staticmethod
    def get_instance():
        if not OsmDatabase._instance:
            OsmDatabase._instance = OsmDatabase()
        return OsmDatabase._instance

    @staticmethod
    def _format_tags(tags: list) -> dict:
        return {tag.tag: tag.counter for tag in tags}

    # # deprecated
    # @staticmethod
    # def _format_tags_list(tags: list) -> list:
    #     # return {tag.k: tag.v for tag in tags}  # -> dict:
    #     return [config.osm.separator.join([tag.k, tag.v]) for tag in tags]  # -> list:
    #
    # def get_nodes_count(self) -> int:
    #     logging.debug('get_nodes_count()')
    #     sql = 'SELECT COUNT(*) FROM nodes;'
    #     return self.one(sql)
    #
    # def get_ways_count(self) -> int:
    #     logging.debug('get_ways_count()')
    #     sql = 'SELECT COUNT(*) FROM ways;'
    #     return self.one(sql)
    #
    # def get_all_node_ids(self) -> list:
    #     logging.debug('get_all_node_ids()')
    #     sql = 'SELECT id FROM nodes ORDER BY id;'
    #     return self.all(sql)

    def get_all_way_ids(self) -> list:
        logging.debug('get_all_way_ids()')
        sql = 'SELECT id FROM ways ORDER BY id;'
        return self.all(sql)

    # def get_nodes_by_way(self, way_id: int) -> list:
    #     logging.debug('get_nodes_by_way({})'.format(way_id))
    #     sql = 'SELECT node_id FROM way_nodes WHERE way_id = %s;'
    #     params = way_id,
    #     return self.all(sql, params)
    #
    # def get_nodes_by_ways(self, way_ids: list) -> list:
    #     logging.debug('get_nodes_by_ways({})'.format(way_ids))
    #     sql = 'SELECT node_id FROM way_nodes WHERE way_id IN %s;'
    #     params = tuple(way_ids),
    #     return self.all(sql, params)
    #
    # def get_ways_by_node(self, node_id: int) -> list:
    #     logging.debug('get_ways_by_node({})'.format(node_id))
    #     sql = 'SELECT way_id FROM way_nodes WHERE node_id = %s;'
    #     params = node_id,
    #     return self.all(sql, params)

    def get_ways_by_nodes(self, node_ids: list) -> list:
        # logging.debug('get_ways_by_nodes({})'.format(node_ids))
        if not node_ids:
            return []
        sql = 'SELECT way_id FROM way_nodes WHERE node_id IN %s GROUP BY way_id HAVING COUNT(*) > 1;'
        params = tuple(node_ids),
        return self.all(sql, params)

    # def get_distance_by_way(self, way_id: int) -> float:
    #     ...

    def get_all_tags_by_nodes(self, node_ids: list) -> dict:
        # logging.debug('get_all_tags_by_nodes({})'.format(node_ids))
        if not node_ids:
            return {}
        sql = '''
            SELECT CONCAT(k, '=', v) AS tag, COUNT(*) AS counter FROM (
                SELECT k, v FROM node_tags WHERE node_id IN %s
                UNION ALL
                SELECT k, v FROM way_tags WHERE way_id IN (
                    SELECT way_id FROM way_nodes WHERE node_id IN %s
                    GROUP BY way_id HAVING COUNT(*) > 1
                )
            ) AS tags GROUP BY k, v;
        '''
        #     ) AS tags WHERE CONCAT(k, '=', v) IN %s GROUP BY k, v;
        # '''
        # params = tuple(node_ids), tuple(node_ids), config.osm.tags
        params = tuple(node_ids), tuple(node_ids)
        tags = self.all(sql, params)
        return self._format_tags(tags)

    # def get_all_tags_by_way(self, way_id: int) -> dict:
    #     logging.debug('get_all_tags_by_way({})'.format(way_id))
    #     sql = '''
    #         SELECT CONCAT(k, '=', v) AS tag, COUNT(*) AS counter FROM (
    #             SELECT k, v FROM way_tags WHERE way_id = %s
    #             UNION ALL
    #             SELECT k, v FROM node_tags WHERE node_id IN (
    #                 SELECT node_id FROM way_nodes WHERE way_id = %s
    #             )
    #         ) AS tags GROUP BY k, v;
    #     '''
    #     #     ) AS tags WHERE CONCAT(k, '=', v) IN %s GROUP BY k, v;
    #     # '''
    #     # params = way_id, way_id, config.osm.tags
    #     params = way_id, way_id
    #     tags = self.all(sql, params)
    #     return self._format_tags(tags)

    def get_all_tags_of_all_ways(self) -> list:
        # logging.debug('get_all_tags_of_all_ways()')
        sql = '''
            SELECT way_id, CONCAT(k, '=', v) AS tag, COUNT(*) AS counter FROM (
                SELECT way_id, k, v FROM
                    way_tags
                UNION ALL
                SELECT way_id, k, v FROM
                    way_nodes JOIN node_tags ON way_nodes.node_id = node_tags.node_id
            ) AS tags WHERE CONCAT(k, '=', v) IN %s GROUP BY way_id, k, v;
        '''
        params = tuple(config.osm.tags),
        return self.all(sql, params)

    # def get_tags_by_node(self, node_id: int) -> list:
    #     logging.debug('get_tags_by_node({})'.format(node_id))
    #     sql = 'SELECT k, v FROM node_tags WHERE node_id = %s;'
    #     params = node_id,
    #     tags = self.all(sql, params)
    #     return self._format_tags_list(tags)
    #
    # def get_tags_by_nodes(self, node_ids: list) -> list:
    #     logging.debug('get_tags_by_nodes({})'.format(node_ids))
    #     if not node_ids:
    #         return []
    #     sql = 'SELECT k, v FROM node_tags WHERE node_id IN %s;'
    #     params = tuple(node_ids),
    #     tags = self.all(sql, params)
    #     return self._format_tags_list(tags)
    #
    # def get_tags_by_way(self, way_id: int) -> list:
    #     logging.debug('get_tags_by_way({})'.format(way_id))
    #     sql = 'SELECT k, v FROM way_tags WHERE way_id = %s;'
    #     params = way_id,
    #     tags = self.all(sql, params)
    #     return self._format_tags_list(tags)
    #
    # def get_tags_by_ways(self, way_ids: list) -> list:
    #     logging.debug('get_tags_by_ways({})'.format(way_ids))
    #     if not way_ids:
    #         return []
    #     sql = 'SELECT k, v FROM way_tags WHERE way_id IN %s;'
    #     params = tuple(way_ids),
    #     tags = self.all(sql, params)
    #     return self._format_tags_list(tags)

    def get_all_way_tag_ratios(self) -> dict:
        way_tag_counts = defaultdict(lambda: defaultdict(lambda: 0))
        way_tag_ratios = defaultdict(lambda: defaultdict(lambda: 0.0))
        logging.info('Get all tags of all ways from the database...')
        result = self.get_all_tags_of_all_ways()
        logging.info('Got all tags of all ways from the database')
        for row in result:
            # column is called 'counter' because 'count' is reserved by the database lib
            way_tag_counts[row.way_id][row.tag] = row.counter
        logging.debug('Finished way_tag_counts')
        # if config.tensorflow.binary_tags != '0':
        if config.tensorflow.binary_tags == '1':
            for way in way_tag_counts.keys():
                way_tag_counts[way].update({tag: 1 for tag, count in way_tag_counts[way].items() if count > 0})
            logging.debug('Finished binary way_tag_counts')
            return way_tag_counts
        for way, tags in way_tag_counts.items():
            total = sum(tags.values()) or 1  # avoid ZeroDivisionError
            for tag, count in tags.items():
                way_tag_ratios[way][tag] = count / total
        logging.debug('Finished way_tag_ratios')
        # # TODO improve persistence
        # sep = config.route_data.outer_separator
        # lines = [sep.join([str(row.way_id), row.tag, str(row.counter)]) + '\n' for row in result]
        # logging.debug('Finished CSV lines')
        # way_tags_file = 'data/osm/way_tags.csv'
        # with open(way_tags_file, 'w') as f:
        #     f.writelines(lines)
        # logging.debug('Finished CSV file')
        return way_tag_ratios


# 150186847  # name=Fahrenheitstraße
# 24554411  # name=Wiener Straße
# 56043685  # name=Universitätsallee
#
# example nodes: 1835029415, 2134103308, 1982053901, 26574106, 1146801017, 20958816, 26574106
# example ways: 150186847, 24554411, 56043685, 3999496


if __name__ == '__main__':
    db = OsmDatabase.get_instance()
    db.get_all_way_tag_ratios()
