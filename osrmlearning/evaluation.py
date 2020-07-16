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
import math
import re
import shutil
from types import FunctionType
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
from progress.bar import Bar

from osrmlearning import config, start_time
# from osrmlearning.hereclient import get_travel_time_by_route
from osrmlearning.route import get_random_example_routes
from osrmlearning.timewindow import get_time_window_by_route


def evaluate(iterate_routes: FunctionType):
    count = 0
    routes = []
    # noinspection PyArgumentList
    for route in iterate_routes():
        try:
            route, prediction = route
            route.set_tf_scaled_osrm_travel_time(prediction)
        except TypeError:
            # no prediction in iterator item -> no route-level scaling
            route.tf_scaled_osrm_travel_time = route.osrm_travel_time
        port = get_time_window_by_route(route).port
        # logging.debug('port={}'.format(port))
        route.set_tf_final_osrm_travel_time(port)
        # route.here_travel_time = get_travel_time_by_route(route)
        # route.set_here_travel_time()
        routes.append(route)
        count += 1
        if count > int(config.evaluation.log_limit):
            continue
        message = '''
            Route # {}
            Coordinates: {}

            reference time:        {: 9.1f} s
            OSRM time:             {: 9.1f} s
            TF scaled OSRM time:   {: 9.1f} s
            TF final OSRM time:    {: 9.1f} s
            Here time:             {: 9.1f} s

            OSRM error:            {: 9.3f} %
            TF scaled OSRM error:  {: 9.3f} %
            TF final OSRM error:   {: 9.3f} %
            Here error:            {: 9.3f} %

            TF scaled improvement: {: 9.3f} %
            TF final improvement:  {: 9.3f} %
        '''.format(
            count,
            route.coordinates,
            route.reference_travel_time,
            route.osrm_travel_time,
            route.tf_scaled_osrm_travel_time,
            route.tf_final_osrm_travel_time,
            route.here_travel_time,
            100 * route.plain_osrm_error,
            100 * route.tf_scaled_osrm_error,
            100 * route.tf_final_osrm_error,
            100 * route.here_error,
            100 * route.scaled_improvement,
            100 * route.final_improvement,
        )
        message = re.sub(r'\n\s+', '\n', message)
        logging.debug(message)
    logging.debug('Evaluation for {} ({}) routes'.format(count, len(routes)))

    original_routes_count = len(routes)
    if original_routes_count == 0:
        raise RuntimeError('No routes')

    def values(attribute: str, exclude_invalid=True):
        nonlocal routes
        if exclude_invalid:
            routes = [
                route
                for route in routes
                if math.isfinite(getattr(route, attribute))
            ]
        value_list = [
            getattr(route, attribute)
            for route in routes
        ]
        # FIXME this log line repeats the number of invalid routes from the previous check even if there are no new ones
        logging.info('Excluding {} invalid routes with invalid {} attribute'.format(
            original_routes_count - len(routes),
            attribute,
        ))
        return value_list

    def average(numbers: list):
        try:
            return sum(abs(number) for number in numbers) / len(numbers)
        except ZeroDivisionError as e:
            print(e)
            return 0.0

    reference_travel_times = values('reference_travel_time')
    plain_osrm_travel_times = values('osrm_travel_time')
    tf_scaled_osrm_travel_times = values('tf_scaled_osrm_travel_time')
    tf_final_osrm_travel_times = values('tf_final_osrm_travel_time')
    here_travel_times = values('here_travel_time')
    # here_travel_times = values('here_travel_time', exclude_invalid=False)

    plain_osrm_errors = values('plain_osrm_error')
    tf_scaled_osrm_errors = values('tf_scaled_osrm_error')
    tf_final_osrm_errors = values('tf_final_osrm_error')
    here_errors = values('here_error')
    # here_errors = values('here_error', exclude_invalid=False)

    tf_scaled_improvements = values('scaled_improvement')
    tf_final_improvements = values('final_improvement')

    logging.info('Excluding {} invalid routes with any invalid attribute, keeping {} routes out of {}'.format(
        original_routes_count - len(routes),
        len(routes),
        original_routes_count,
    ))
    logging.info('For any invalid route, multiple attributes may be invalid')
    if not len(routes):
        raise RuntimeError('No valid routes left')

    average_plain_osrm_error = average(plain_osrm_errors)
    average_tf_scaled_osrm_error = average(tf_scaled_osrm_errors)
    average_tf_final_osrm_error = average(tf_final_osrm_errors)
    average_here_error = average(here_errors)

    # average_tf_scaled_improvement = average(tf_scaled_improvements)
    # average_tf_final_improvement = average(tf_final_improvements)
    average_tf_scaled_improvement = abs(average_plain_osrm_error) - abs(average_tf_scaled_osrm_error)
    average_tf_final_improvement = abs(average_plain_osrm_error) - abs(average_tf_final_osrm_error)

    tf_scaled_improvement_frequency = len([
        improvement
        for improvement in tf_scaled_improvements
        if improvement > 0
    ]) / len(tf_scaled_improvements)
    tf_final_improvement_frequency = len([
        improvement
        for improvement in tf_final_improvements
        if improvement > 0
    ]) / len(tf_final_improvements)

    message = '''
        average OSRM error:                   {: 9.3f} %
        average TF OSRM scaled error:         {: 9.3f} %
        average TF OSRM final error:          {: 9.3f} %
        average Here error:                   {: 9.3f} %

        average TF OSRM scaled improvement:   {: 9.3f} %
        average TF OSRM final improvement:    {: 9.3f} %

        TF OSRM scaled improvement frequency: {: 9.3f} %
        TF OSRM final improvement frequency:  {: 9.3f} %
    '''.format(
        100 * average_plain_osrm_error,
        100 * average_tf_scaled_osrm_error,
        100 * average_tf_final_osrm_error,
        100 * average_here_error,
        100 * average_tf_scaled_improvement,
        100 * average_tf_final_improvement,
        100 * tf_scaled_improvement_frequency,
        100 * tf_final_improvement_frequency,
    )
    message = re.sub(r'\n\s+', '\n', message)
    logging.info(message)

    def percent(numbers: list) -> np.array:
        return np.array(numbers) * 100

    def grid(*datasets: Iterable):
        # min_data = min(min(dataset) for dataset in datasets)
        # max_data = max(max(dataset) for dataset in datasets)
        # labels = list(range(
        #     int(min_data),
        #     int(max_data + 1),
        #     int((max_data - min_data) / int(config.plot.resolution)),
        # ))
        # if 0 not in labels:
        #     labels.append(0)
        # plt.yticks(sorted(labels))
        plt.grid(axis='y')

    # for kwargs, filename in (
    #         (dict(), 'data/results/plots/{}--outliers.png'.format(start_time)),
    #         (dict(showfliers=False), 'data/results/plots/{}--no-outliers.png'.format(start_time)),
    # ):
    plt.switch_backend('agg')
    kwargs = dict(showfliers=False)
    # kwargs = dict()
    plt.figure(figsize=(18, 8))

    # plt.figure()
    plt.subplot(1, 3, 1)
    plt.boxplot(
        x=(
            reference_travel_times,
            plain_osrm_travel_times,
            tf_scaled_osrm_travel_times,
            tf_final_osrm_travel_times,
            here_travel_times,
        ),
        labels=(
            'Reference',
            'Plain\nOSRM',
            'TF scaled\nOSRM',
            'TF final\nOSRM',
            'Here',
        ),
        **kwargs,
    )
    grid(
        reference_travel_times,
        plain_osrm_travel_times,
        tf_scaled_osrm_travel_times,
        tf_final_osrm_travel_times,
        here_travel_times,
    )
    plt.xlabel('Travel Times')
    plt.ylabel('time (seconds)')
    # plt.savefig('data/results/plots/{}--travel-times.png'.format(start_time))

    # plt.figure()
    plt.subplot(1, 3, 2)
    plt.boxplot(
        x=(
            percent(plain_osrm_errors),
            percent(tf_scaled_osrm_errors),
            percent(tf_final_osrm_errors),
            percent(here_errors),
        ),
        labels=(
            'Plain\nOSRM',
            'TF scaled\nOSRM',
            'TF final\nOSRM',
            'Here',
        ),
        **kwargs,
    )
    grid(
        percent(plain_osrm_errors),
        percent(tf_scaled_osrm_errors),
        percent(tf_final_osrm_errors),
        percent(here_errors),
    )
    plt.xlabel('Travel Time Errors')
    plt.ylabel('error (percent)')
    # plt.savefig('data/results/plots/{}--errors.png'.format(start_time))

    # plt.figure()
    plt.subplot(1, 3, 3)
    plt.boxplot(
        x=(
            percent(tf_scaled_improvements),
            percent(tf_final_improvements),
        ),
        labels=(
            'TF scaled\nOSRM',
            'TF final\nOSRM',
        ),
        **kwargs,
    )
    grid(
        percent(tf_scaled_improvements),
        percent(tf_final_improvements),
    )
    plt.xlabel('Travel Time Error Improvements')
    plt.ylabel('improvement (percent)')
    # plt.savefig('data/results/plots/{}--improvements.png'.format(start_time))

    plt.savefig('data/results/plots/{}.png'.format(start_time))

    with open('data/results/values/{}.csv'.format(start_time), 'x') as f:
        f.write(';'.join([
            'coordinates',
            'input_count',
            'reference_travel_time',
            'osrm_travel_time',
            'tf_scaled_osrm_travel_time',
            'tf_final_osrm_travel_time',
            'here_travel_time',
            'plain_osrm_error',
            'tf_scaled_osrm_error',
            'tf_final_osrm_error',
            'here_error',
            'tf_scaled_improvement',
            'tf_final_improvement',
        ]))
        f.write('\n')
        bar = Bar('Writing results to file:', max=len(routes), suffix=config.progress.suffix)
        for route in routes:
            f.write(';'.join(
                [route.coordinates.replace(';', ','), str(route.input_count)]
                + ['{:.1f}'.format(value) for value in [
                    route.reference_travel_time,
                    route.osrm_travel_time,
                    route.tf_scaled_osrm_travel_time,
                    route.tf_final_osrm_travel_time,
                    route.here_travel_time,
                ]]
                + ['{:.3f}'.format(value) for value in [
                    100 * route.plain_osrm_error,
                    100 * route.tf_scaled_osrm_error,
                    100 * route.tf_final_osrm_error,
                    100 * route.here_error,
                    100 * route.scaled_improvement,
                    100 * route.final_improvement,
                ]]
            ))
            f.write('\n')
            bar.next()
        bar.finish()

    shutil.copy(
        'data/config/highway_tags_whitelist.txt',
        'data/results/highway_tags_whitelists/{}.txt'.format(start_time),
    )
    shutil.copy(
        'data/osm/osm_tags.yaml',
        'data/results/osm_tags/{}.yaml'.format(start_time),
    )
    shutil.copy(
        'data/config/config.ini',
        'data/results/config/{}.ini'.format(start_time),
    )

    # FIXME Config namedtuple should be converted to dict first
    # with open('data/results/config/{}.json'.format(start_time), 'x') as f:
    #     json.dump(config, f, indent=2)

    result = dict(
        average_plain_osrm_error=100 * average_plain_osrm_error,
        average_tf_scaled_osrm_error=100 * average_tf_scaled_osrm_error,
        average_tf_final_osrm_error=100 * average_tf_final_osrm_error,
        average_tf_scaled_improvement=100 * average_tf_scaled_improvement,
        average_tf_final_improvement=100 * average_tf_final_improvement,
        tf_scaled_improvement_frequency=100 * tf_scaled_improvement_frequency,
        tf_final_improvement_frequency=100 * tf_final_improvement_frequency,
        start_time=start_time,
        end_time=datetime.datetime.now().strftime('%Y-%m-%d--%H-%M-%S'),
        postgres_db=config.postgres.db,
        routes=dict(
            outlier_tolerance=config.routes.outlier_tolerance,
            min_travel_time=config.routes.min_travel_time,
            max_travel_time=config.routes.max_travel_time,
            train_source=config.routes.train_source,
            eval_source=config.routes.eval_source,
            scenario_ids=config.routes.scenario_ids,
        ),
        tensorflow=dict(
            batch_size=config.tensorflow.batch_size,
            hidden_units=config.tensorflow.hidden_units,
            cross_validation=config.tensorflow.cross_validation,
            train_eval_ratio=config.tensorflow.train_eval_ratio,
            binary_tags=config.tensorflow.binary_tags,
        ),
        highway_tags_whitelist=config.osm.highway_tags_whitelist,
        server=dict(
            base_url='{}://{}:{}'.format(
                config.server.protocol,
                config.server.host,
                config.server.port,
            ),
        ),
    )
    with open('data/results/summaries/{}.json'.format(start_time), 'x') as f:
        json.dump(result, f, indent=2)

    logging.info('Finished evaluation')

# FIXME Exception ignored for end of iterator?
# Exception ignored in: <generator object Estimator.predict at ...>
# AssertionError: Nesting violated for default stack of <class 'tensorflow.python.framework.ops.Graph'> objects


if __name__ == '__main__':
    def iterate_examples():
        routes = get_random_example_routes()
        for route in routes:
            yield route
    evaluate(iterate_routes=iterate_examples)
