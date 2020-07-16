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
import os
import re
import shutil
import subprocess
import time

from osrmlearning import config, start_time


# http://download.geofabrik.de/europe/germany-latest.osm.pbf


def _run_command(command, log=True) -> str:
    logging.debug(' '.join(command))
    p = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    output = []
    for line in p.stdout:
        output.append(line)
        if log:
            logging.debug(line.strip())
    # if p.wait() != 0:
    #     raise ChildProcessError(p.returncode, ''.join(output))
    p.wait()
    return ''.join(output)


def _run_commands(*commands, log=True) -> list:
    return [_run_command(command, log=log) for command in commands]


class OsrmContainer(object):
    instances = []

    def __init__(
            self,
            time_window='00-00-24-00',
            region_path=config.osrm.region,
            profile='car_scaled.lua',
            base_image_name='xtl/osrm-v5:distances',
            port=5000,
            plain=False,
    ):
        self.plain = plain
        if plain:
            self.base_image_name = config.docker.registry + 'xtl/osrm-v5-de-car:distances'
            self.container_name = 'xtl-osrm-run'
            self.port = port
            self.region = 'germany'
            self.volume = ''
            return
        self.time_window = time_window
        self.profile = profile
        self.scaling_factors_file = '{}--{}.csv'.format(start_time, time_window)
        # if not os.path.isfile(self.scaling_factors_file):
        #     # use latest scaling factors instead
        #     d = 'data/results/scaling_factors'
        #     self.scaling_factors_file = [f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))][-1]
        self.region_path, self.region = os.path.split(region_path)
        self.osm_file = '{}-latest.osm.pbf'.format(self.region)
        self.container_name = 'xtl-osrm-{}-{}-{}-run'.format(
            profile.split('.')[0].replace('_', '-'),
            self.region,
            time_window,
        )
        self.directory = os.path.join(
            os.getcwd(),
            'data/docker',
            self.container_name,
        )
        os.makedirs(self.directory, exist_ok=True)
        self.volume = '{}:/data'.format(self.directory.replace(os.getcwd(), config.docker.host_pwd))
        self.base_image_name = base_image_name
        self.port = port
        if not self._image_ready():
            raise RuntimeError('Missing the following docker images:'
                               'xtl/osrm-v5:distances and xtl/osrm-v5-de-car:distances')
            # self.build_image()
            # self.pull_image()
        OsrmContainer.instances.append(self)
        logging.debug('OSRM docker image ready')

    def _image_ready(self) -> bool:
        docker_images = ['docker', 'images']
        return self.base_image_name.split(':')[0] in _run_command(docker_images, log=False)

    def _running(self) -> bool:
        docker_ps = ['docker', 'ps']
        return self.container_name in _run_command(docker_ps, log=False)

    def timeout(self, run: bool):
        wait_seconds = int(config.docker.wait)
        timeout_seconds = int(config.docker.timeout)
        t1 = time.time()
        while True:
            logging.debug('Waiting {} seconds for OSRM docker container to {}...'.format(
                wait_seconds,
                'start' if run else 'stop',
            ))
            time.sleep(wait_seconds)
            if run and self._running() or not self._running():
                break
            t2 = time.time()
            if t2 - t1 > timeout_seconds:
                raise RuntimeError('Timeout')

    def build_image(self, osrm_source_path='../osrm-backend/'):
        # TODO git clone source code
        # logging.debug('Build OSRM docker image')
        docker_build = [
            'docker', 'build',
            '-t', self.base_image_name,
            osrm_source_path,
        ]
        _run_command(docker_build)

    def pull_image(self, registry=config.docker.registry):
        docker_login = [
            'docker', 'login',
            '-u', config.docker.user,
            '-p', config.docker.password,
            registry,
        ]
        docker_pull = [
            'docker', 'pull',
            '{}/{}'.format(registry, self.base_image_name),
        ]
        _run_commands(
            docker_login,
            docker_pull,
        )

    def build_container(self):
        osrm_extract = [
            'docker', 'run', '-t',
            '-v', self.volume,
            self.base_image_name,
            'osrm-extract',
            '-p', '/data/{}'.format(self.profile),
            '/data/{}-latest.osm.pbf'.format(self.region),
        ]
        osrm_contract = [
            'docker', 'run', '-t',
            '-v', self.volume,
            self.base_image_name,
            'osrm-contract',
            '/data/{}-latest.osrm'.format(self.region),
        ]
        try:
            os.rename(
                os.path.join('data/osm/', self.osm_file),
                os.path.join(self.directory, self.osm_file),
            )
            shutil.copy(
                config.osm.highway_tags_whitelist_file,
                os.path.join(self.directory, os.path.basename(config.osm.highway_tags_whitelist_file)),
            )
            shutil.copy(
                os.path.join('data/lua_profiles/', self.profile),
                os.path.join(self.directory, self.profile),
            )
            shutil.copy(
                os.path.join('data/results/scaling_factors/', self.scaling_factors_file),
                os.path.join(self.directory, self.scaling_factors_file.replace(
                    os.path.splitext(os.path.basename(self.scaling_factors_file))[0],
                    'scaling_factors',
                )),
            )
            _run_commands(
                osrm_extract,
                osrm_contract,
            )
        finally:
            os.rename(
                os.path.join(self.directory, self.osm_file),
                os.path.join('data/osm/', self.osm_file),
            )

    # sudo docker rm -f $(sudo docker ps | grep osrm | grep ":$port->" | grep -o ^[0-9a-z]*)
    @staticmethod
    def stop_all(port=None):
        docker_ps = ['docker', 'ps']
        osrm_containers = [
            re.findall(r'^[0-9a-z]*', container)[0]
            for container in _run_command(docker_ps).split('\n')
            if 'osrm' in container and (port is None or ':{}->'.format(port) in container)
        ]
        docker_rm = ['docker', 'rm', '-f'] + osrm_containers
        _run_command(docker_rm)

    def stop(self):
        docker_remove = [
            'docker', 'rm',  '-f',
            self.container_name,
        ]
        _run_command(docker_remove)
        self.timeout(run=False)

    def start(self):
        for instance in OsrmContainer.instances:
            if instance.port == self.port:
                instance.stop()
        # self.stop_all(self.port)
        osrm_routed = [
            'docker', 'run', '-d',
            '-v', self.volume,
            '-p', '{}:5000'.format(self.port),
            # '--network', config.docker.network,
            '--name', self.container_name,
            self.base_image_name,
            'osrm-routed',
            '--max-viaroute-size', '2500',
            '--max-table-size', '10000',
            '/data/{}-latest.osrm'.format(self.region),
        ]
        if self.plain:
            osrm_routed = [
                'docker', 'run', '-d',
                '-p', '{}:5000'.format(self.port),
                # '--network', config.docker.network,
                '--name', self.container_name,
                self.base_image_name,
            ]
        _run_command(osrm_routed)
        self.timeout(run=True)


if __name__ == '__main__':
    osrm_container = OsrmContainer(time_window='00-00-01-00', region_path=config.osrm.region)
    osrm_container.build_container()
    osrm_container.start()
    osrm_container.stop()
