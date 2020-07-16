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

import gc
import itertools
import logging

from progress.bar import Bar

from osrmlearning import config, init, start_time
from osrmlearning.evaluation import evaluate
from osrmlearning.learning import Learning
from osrmlearning.osmdatabase import OsmDatabase
from osrmlearning.osrmdocker import OsrmContainer
from osrmlearning.routeprovider import (
    get_routes,
    # reject_outliers,
    remove_min_max_routes,
    remove_non_moving_routes,
    enforce_max_count,
    randomize,
    Source,
)
from osrmlearning.timewindow import get_time_windows, TimeWindow


def get_osrm_containers_by_time_windows() -> dict:
    train_source = Source[config.routes.train_source]
    eval_source = Source[config.routes.eval_source]
    logging.info('Train source: {}, Eval source {}'.format(train_source, eval_source))
    logging.info('Train routes:')
    train_routes = enforce_max_count(randomize(remove_min_max_routes(remove_non_moving_routes(
        get_routes(train_source)))))
    logging.info('Eval routes:')
    eval_routes = enforce_max_count(randomize(remove_min_max_routes(remove_non_moving_routes(
        get_routes(eval_source)))))

    cross_validation = config.tensorflow.cross_validation
    cross_validation = cross_validation == '1' and cross_validation != '0'
    if train_source == eval_source and cross_validation:
        routes = train_routes
        sep = int(float(config.tensorflow.train_eval_ratio) * len(routes))
        train_routes = routes[:sep]
        eval_routes = routes[sep:]
    else:
        routes = train_routes + eval_routes

    bar = Bar('Getting Here travel times:', max=len(routes), suffix=config.progress.suffix)
    for route in routes:
        route.set_here_travel_time()
        bar.next()
    bar.finish()
    logging.info('Got Here travel times for {} routes in {} seconds'.format(bar.index, bar.elapsed))

    osrm_container = OsrmContainer(plain=True)
    osrm_container.start()
    bar = Bar('Getting OSRM travel times:', max=len(routes), suffix=config.progress.suffix)
    for route in routes:
        route.set_osrm_travel_time()
        bar.next()
    bar.finish()
    logging.info('Got OSRM travel times for {} routes in {} seconds'.format(bar.index, bar.elapsed))
    osrm_container.stop()

    original_routes_count = len(routes)
    routes = [
        route for route in routes
        if route.reference_travel_time > 0.0
        and route.osrm_travel_time > 0.0
        and route.here_travel_time > 0.0
    ]
    train_routes = list(set(train_routes) & set(routes))
    eval_routes = list(set(eval_routes) & set(routes))
    logging.info('Zero-time routes: Removed {} out of {} routes keeping {}'.format(
        original_routes_count - len(routes),
        original_routes_count,
        len(routes),
    ))

    bar = Bar('Getting OSM tag counts:', max=len(routes), suffix=config.progress.suffix)
    for route in routes:
        route.set_osm_tag_counts()
        bar.next()
    bar.finish()
    logging.info('Got OSM tag counts for {} routes in {} seconds'.format(bar.index, bar.elapsed))

    osrm_containers_by_time_windows = dict()
    time_windows = get_time_windows()
    iterators = []
    for time_window in time_windows:
        # print(len(time_window.filter_routes(routes)))
        osrm_container, iterate_eval_routes = create_osrm_container(
            train_routes=train_routes,
            eval_routes=eval_routes,
            time_window=time_window,
        )
        osrm_containers_by_time_windows[time_window] = osrm_container
        iterators.append(iterate_eval_routes())

    for osrm_container in osrm_containers_by_time_windows.values():
        osrm_container.start()
    evaluate(lambda: itertools.chain(*iterators))
    return osrm_containers_by_time_windows


def create_osrm_container(train_routes: list, eval_routes: list, time_window: TimeWindow) -> tuple:
    logging.info('####################################################')
    logging.info('Preparing OSRM container for time window {}'.format(time_window))
    logging.info('####################################################')
    logging.info('Train routes:')
    train_routes = time_window.filter_routes(train_routes)
    logging.info('Eval routes:')
    eval_routes = time_window.filter_routes(eval_routes)
    # if not len(train_routes) or not len(eval_routes):
    if not len(train_routes) or time_window.is_default and config.time_windows.keep_default:
        logging.warning('No routes for time window {}'.format(time_window))

        # noinspection PyUnreachableCode
        def empty_iterator():
            return
            yield

        return OsrmContainer(plain=True), empty_iterator
    # routes = train_routes + eval_routes

    travel_time_ratios_by_way_ids = {}
    bar = Bar('Assigning travel time ratios:', max=len(train_routes), suffix=config.progress.suffix)
    for route in train_routes:
        bar.next()
        if not int(config.routes.min_travel_time_for_direct_scaling) * int(config.courier_locations.step) < \
                route.reference_travel_time < \
                int(config.routes.max_travel_time_for_direct_scaling) * int(config.courier_locations.step):
            continue
        route.set_ways()
        for way in route.ways:
            if way in travel_time_ratios_by_way_ids:
                travel_time_ratios_by_way_ids[way].append(route.travel_time_ratio)
            else:
                travel_time_ratios_by_way_ids[way] = [route.travel_time_ratio]
    bar.finish()

    for way, travel_time_ratios in travel_time_ratios_by_way_ids.items():
        travel_time_ratios_by_way_ids[way] = sum(travel_time_ratios) / len(travel_time_ratios)
    logging.info('Assigned travel time ratios for {} ways and {} routes in {} seconds'.format(
        len(travel_time_ratios_by_way_ids), bar.index, bar.elapsed))
    # eval_routes = set(eval_routes) -= set(train_routes)

    tensorflow_enabled = config.tensorflow.enabled == '1' or config.tensorflow.enabled != '0'
    if tensorflow_enabled:
        learning = Learning(train_routes, eval_routes)
        # del routes
        # del train_routes
        # del eval_routes
        # gc.collect()
        learning.learn()
        scaling_factors_by_way_ids = learning.predict_all_scaling_factors_by_way_ids()
        scaling_factors_by_way_ids.update(travel_time_ratios_by_way_ids)
        logging.info('Using {} learned scaling factors and {} direct scaling factors'.format(
            len(scaling_factors_by_way_ids) - len(travel_time_ratios_by_way_ids), len(travel_time_ratios_by_way_ids)))
    else:
        scaling_factors_by_way_ids = travel_time_ratios_by_way_ids
        logging.info('Using {} direct scaling factors'.format(len(scaling_factors_by_way_ids)))
    del travel_time_ratios_by_way_ids
    gc.collect()

    max_scaling_factor = float(config.tensorflow.max_scaling_factor)
    exceeding_scaling_factors = 0
    missing_scaling_factors = 0
    db = OsmDatabase.get_instance()
    for way in db.get_all_way_ids():
        if way in scaling_factors_by_way_ids:
            if scaling_factors_by_way_ids[way] > max_scaling_factor:
                scaling_factors_by_way_ids[way] = max_scaling_factor
                exceeding_scaling_factors += 1
            elif scaling_factors_by_way_ids[way] < 1 / max_scaling_factor:
                scaling_factors_by_way_ids[way] = 1 / max_scaling_factor
                exceeding_scaling_factors += 1
        else:
            # scaling_factors_by_way_ids[way] = max_scaling_factor
            missing_scaling_factors += 1
    logging.info('Maximum allowed scaling factor {} was set for {} ways where the original was above the max'.format(
        max_scaling_factor,
        exceeding_scaling_factors,
    ))
    logging.info('Number of ways without a scaling factor: {}'.format(missing_scaling_factors))
    logging.info('Writing scaling factors to CSV file...')

    csv_file = 'data/results/scaling_factors/{}--{}.csv'.format(start_time, time_window)
    with open(csv_file, 'w') as f:
        bar = Bar('Writing scaling factors:', max=len(scaling_factors_by_way_ids), suffix=config.progress.suffix)
        for way_id, scaling_factor in scaling_factors_by_way_ids.items():
            scaling_factor = 1 / scaling_factor  # In the lua profile, we scale speed rather than travel time!
            f.write('{};{}\n'.format(way_id, scaling_factor))
            bar.next()
        bar.finish()
    logging.info('Wrote {} scaling factors to CSV file in {} seconds'.format(bar.index, bar.elapsed))
    # del scaling_factors_by_way_ids
    # gc.collect()

    osrm_container = OsrmContainer(time_window=time_window.name, port=time_window.port, region_path=config.osrm.region)
    osrm_container.build_container()
    if tensorflow_enabled:
        # osrm_container.start()
        # evaluate(learning.iterate_eval_routes)
        # osrm_container.stop()  # don't stop when used productively
        # noinspection PyUnboundLocalVariable
        return osrm_container, learning.iterate_eval_routes
    else:
        def iterate_eval_routes():
            for route in eval_routes:
                yield route, scale_route(route, scaling_factors_by_way_ids)
        return osrm_container, iterate_eval_routes


def scale_route(route, scaling_factors_by_way_ids):
    if route.ways is None:
        route.set_ways()
    if not len(route.ways):
        logging.info('Route without ways')
        return 1
    scaling_factors = []
    for way in route.ways:
        if way in scaling_factors_by_way_ids:
            scaling_factors.append(scaling_factors_by_way_ids[way])
    if not len(scaling_factors):
        logging.info('Route without scaling factors')
        return 1
    return sum(scaling_factors) / len(scaling_factors)


# if __name__ == '__main__':
#     main(now=True, schedule=False)
#     # while True:
#     #     try:
#     #         main(now=True, schedule=False, source=Source[config.routes.source])
#     #         init()
#     #     except StopIteration:
#     #         break
