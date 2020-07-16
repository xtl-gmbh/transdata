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

"""
Package module for OSRM-Learning

- Initializes logging, reads config, creates directories

Logging

- Log lines are formatted
- Log to console and to file with timestamp

Config

- Config is read from data/config.ini and returned as a namedtuple that can be dot-accessed.
- config.osm.tags are read from config.osm.tags_file.
- config.docker.host_pwd is important if this runs in a Docker container.
- Double quotes are removed from values.
- Comma-separated numbers are turned into a list of ints.
"""

from collections import defaultdict, namedtuple
from configparser import ConfigParser
import datetime
import logging
import os
import re
import sys

from osrmlearning.osmtags import get_osm_tags, get_osm_highway_tags_whitelist

for directory in [
    'data/',
    'data/config/',
    'data/docker/',
    'data/here_databases/',
    'data/lua_profiles/',
    'data/osm/',
    'data/server/locations/',
    'data/server/plans/',
    'data/results/',
    'data/results/config/',
    'data/results/highway_tags_whitelists/',
    'data/results/logs/',
    'data/results/osm_tags/',
    'data/results/plots/',
    'data/results/scaling_factors/',
    'data/results/summaries/',
    'data/results/values/',
    'data/route_data/',
    'data/scenarios/',
    'data/sql/',
]:
    os.makedirs(directory, exist_ok=True)

start_time = datetime.datetime.now().strftime('%Y-%m-%d--%H-%M-%S')

logging.basicConfig(
    level=logging.DEBUG,
    # level=logging.INFO,
    format='%(asctime)s: %(name)s: %(filename)s: %(funcName)s(): %(lineno)d: %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data/results/logs/{}.log'.format(start_time)),
    ],
)
logging.debug('Init logging')

if os.path.exists('data/config/config.csv'):
    _override_config = []
    with open('data/config/config.csv') as f:
        lines = f.readlines()
        names = [name.split('.') for name in lines[0].strip().split(';')]
        lines = lines[1:]
        for line in lines:
            if names[0][0].startswith('#'):
                _override_config = None
                break
            if line.startswith('#'):
                continue
            values = line.strip().split(';')
            _override_config.append(defaultdict(lambda: defaultdict(lambda: None)))
            for i in range(len(names)):
                _override_config[-1][names[i][0]][names[i][1]] = values[i]
    logging.debug(_override_config)
    _override_config = iter(_override_config) if _override_config is not None else None
    config = None


def _init_config():
    global config
    copy_config = config
    config = ConfigParser()
    config.read('data/config/config.ini')

    config = {section: dict(config.items(section)) for section in config.sections()}
    # noinspection PyArgumentList
    config = defaultdict(lambda: defaultdict(lambda: None), config)
    if _override_config is not None:
        try:
            next_override_config = next(_override_config)
            for section in next_override_config:
                config[section].update(**next_override_config[section])
        except StopIteration:
            raise
    config['osm']['tags'] = get_osm_tags(
        config['osm']['tags_file']
    )
    config['osm']['highway_tags_whitelist'] = get_osm_highway_tags_whitelist(
        config['osm']['highway_tags_whitelist_file']
    )
    docker_host_pwd_arg = '--docker-host-pwd='
    docker_host_pwd = [arg for arg in sys.argv if docker_host_pwd_arg in arg]
    if len(docker_host_pwd) == 0:
        config['docker']['host_pwd'] = os.getcwd()
    elif len(docker_host_pwd) == 1:
        config['docker']['host_pwd'] = docker_host_pwd[0].replace(docker_host_pwd_arg, '')
        config['osrm']['host'] = config['docker']['host']
        config['postgres']['host'] = config['docker']['host']
    else:
        raise RuntimeError(ValueError('Argument {} cannot be used more than once'.format(docker_host_pwd_arg)))

    _config_sections = []
    for section in config:
        for option in config[section]:
            if type(config[section][option]) is not str:
                continue
            config[section][option] = config[section][option].replace('"', '')
            if re.match(r'[0-9]+,', config[section][option]):
                if config[section][option].endswith(','):
                    config[section][option] = config[section][option][:-1]
                config[section][option] = [int(number) for number in config[section][option].split(',')]
            # elif re.match(r'^[0-9]+$,', config[section][option]):
            #     config[section][option] = int(config[section][option])
            # elif re.match(r'^[0-9]*\.[0-9]*$,', config[section][option]):
            #     config[section][option] = float(config[section][option])
        _config_sections.append(namedtuple('ConfigSection', config[section].keys())(*config[section].values()))
    config = namedtuple('Config', config.keys())(*_config_sections)
    logging.debug(config)  # turn off this line if the config contains sensitive data
    if copy_config == config:
        raise StopIteration


def init():
    global start_time
    start_time = datetime.datetime.now().strftime('%Y-%m-%d--%H-%M-%S')
    logger = logging.getLogger()
    logger.removeHandler(logger.handlers[-1])
    logger.addHandler(logging.FileHandler('data/results/logs/{}.log'.format(start_time)))
    try:
        _init_config()
    except StopIteration:
        raise


_init_config()
