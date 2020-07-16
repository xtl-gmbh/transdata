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

import logging

import yaml


def get_osm_tags(filename: str) -> list:
    with open(filename) as f:
        tag_dict = yaml.load(f)
    tag_set = set()
    for tag_type in tag_dict:
        for key in tag_dict[tag_type]:
            for value in tag_dict[tag_type][key]:
                if value is True:
                    value = 'yes'
                elif value is False:
                    value = 'no'
                elif type(value) is not str:
                    value = str(value)
                tag_set.add('='.join([key, value]))
    logging.debug('Got {} OSM tags'.format(len(tag_set)))
    # logging.debug(tag_set)
    return list(tag_set)


def get_osm_highway_tags_whitelist(filename: str) -> list:
    with open(filename) as f:
        return [line.strip() for line in f.readlines() if not line.startswith('#')]


if __name__ == '__main__':
    print(get_osm_tags('data/osm/osm_tags.yaml'))
