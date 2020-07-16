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
import schedule
import sys
import threading
import time

from flask import Flask, request

from osrmlearning import config
from osrmlearning.osrmclient import osrm_request
from osrmlearning.run import get_osrm_containers_by_time_windows
from osrmlearning.timewindow import get_time_windows, get_time_window_by_hour

app = Flask(__name__)
learning_thread = None


def init_osrm_containers():
    global learning_thread
    if learning_thread and learning_thread.is_alive():
        logging.warning('Learning is still running. Did not start a new run.')
        return
    logging.info('Start new run...')
    learning_thread = threading.Thread(target=get_osrm_containers_by_time_windows)
    learning_thread.start()


@app.route('/learn', methods=['GET', 'POST'])
def learn():
    # print(request.args)
    # print(request.query_string)
    # print(request.url)
    # print(request.base_url)
    # print(request.url_root)
    # print(request.full_path)
    thread = threading.Thread(target=init_osrm_containers)
    thread.start()
    return 'Re-starting learning...'


# http://flask.pocoo.org/snippets/67/
@app.route('/shutdown', methods=['GET', 'POST'])
def shutdown():
    request.environ.get('werkzeug.server.shutdown')()
    return 'Server shutting down...'


# http://flask.pocoo.org/snippets/57/
@app.route('/', defaults=dict(path=''))
@app.route('/<path:path>')
def osrm_proxy_request(path):
    timestamp = request.args.get('timestamp')
    query = '/{}?{}'.format(path, request.query_string.decode())
    logging.debug(query)
    query = query.replace('timestamp={}'.format(timestamp), '')
    query = query.replace('?&', '?')
    query = query.replace('&&', '&')
    query = query[:-1] if query.endswith('&') else query
    query = query[:-1] if query.endswith('?') else query
    date_format = config.rest_api.date_format
    time_windows = get_time_windows()
    if timestamp:
        timestamp = datetime.datetime.strptime(timestamp, date_format)
        time_window = get_time_window_by_hour(timestamp.hour)
    else:
        time_window = [time_window for time_window in time_windows if 'default' in time_window.name][0]
    # port = osrm_containers[time_window].port
    port = time_window.port
    logging.debug(query)
    logging.debug('timestamp={}'.format(timestamp))
    logging.debug('time_window={}'.format(time_window))
    logging.debug('port={}'.format(port))
    return app.response_class(
        response=osrm_request(query, port=port),
        status=200,
        mimetype='application/json',
    )


def serve_rest_api():
    app.run(host=config.rest_api.host, port=int(config.rest_api.port))


def test():
    import time
    import urllib.request
    from osrmlearning.osrmdocker import OsrmContainer
    thread = threading.Thread(target=serve_rest_api)
    thread.start()
    port = config.rest_api.port
    try:
        osrm_container = OsrmContainer(plain=True)
        osrm_container.start()
        time.sleep(1)
        url = 'http://127.0.0.1:{}' \
              '/route/v1/driving/13.388860,52.517037;13.397634,52.529407' \
              '?overview=false&annotations=true&timestamp=2018-06-06T11:00:00.000Z'.format(port)
        print(urllib.request.urlopen(url).read().decode())
        osrm_container.stop()
    except Exception as e:
        print(e)
    time.sleep(1)
    print(urllib.request.urlopen('http://127.0.0.1:{}/shutdown'.format(port), b'post-data').read().decode())
    thread.join()


def schedule_updates():
    weekdays = [
        'monday',
        'tuesday',
        'wednesday',
        'thursday',
        'friday',
        'saturday',
        'sunday',
    ]
    getattr(schedule.every(), weekdays[int(config.schedule.weekday)]).at(config.schedule.time).do(init_osrm_containers)
    while True:
        schedule.run_pending()
        time.sleep(int(config.schedule.sleep_interval_minutes) * 60)


def main():
    if '--skip-init' not in sys.argv:
        init_osrm_containers()
    if '--skip-api' not in sys.argv:
        serve_rest_api()
    if '--schedule' in sys.argv:
        schedule_updates()


if __name__ == '__main__':
    # test()
    main()
