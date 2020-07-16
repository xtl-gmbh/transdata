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
import random

import tensorflow as tf
from progress.bar import Bar

from osrmlearning import config
from osrmlearning.osmdatabase import OsmDatabase


def _escape_tag(tag: str) -> str:
    return tag.replace(config.osm.separator, config.osm.escaped_separator)


def _get_dataset(routes: list) -> tf.data.Dataset:
    logging.info('Getting dataset...')
    features = {
        _escape_tag(tag): [
            route.osm_tag_fractions[tag]
            for route in routes
        ] for tag in config.osm.tags
    }
    labels = [route.travel_time_ratio for route in routes]
    dataset = tf.data.Dataset.from_tensor_slices((features, labels))
    buffer_size = len(labels)
    # batch_size = len(labels)
    batch_size = int(config.tensorflow.batch_size)
    dataset = dataset.shuffle(buffer_size).repeat().batch(batch_size)
    return dataset


def _get_hidden_units(size: int) -> list:  # no useful topology so far
    divisor = 2
    size //= divisor
    if size < divisor:
        raise ValueError('More input features required')
    hidden_units = []
    while size > divisor:
        hidden_units.append(size)
        size //= divisor
    logging.debug('hidden_units =', hidden_units)
    return hidden_units


class Learning(object):
    def __init__(self, train_routes: list, eval_routes: list):
        logging.info('Got {} train routes and {} eval routes'.format(
            len(train_routes),
            len(eval_routes),
        ))
        if not len(train_routes) or not len(eval_routes):
            raise RuntimeError('No train routes or eval routes')
        self.train_routes = train_routes
        self.eval_routes = eval_routes
        random.shuffle(self.train_routes)
        random.shuffle(self.eval_routes)
        feature_columns = [tf.feature_column.numeric_column(_escape_tag(tag)) for tag in config.osm.tags]
        hidden_units = config.tensorflow.hidden_units
        # hidden_units = _get_hidden_units(len(feature_columns))
        # self.estimator = tf.estimator.DNNRegressor(hidden_units, feature_columns, model_dir='data/saved_models/')
        self.estimator = tf.estimator.DNNRegressor(hidden_units, feature_columns)
        self.eval_predictions = None

    def learn(self):
        logging.info('Begin training...')
        train_steps = max(len(self.train_routes) * int(config.tensorflow.repetitions), int(config.tensorflow.min_steps))
        self.estimator.train(lambda: _get_dataset(self.train_routes), steps=train_steps)
        logging.info('Finished training')
        eval_result = self.estimator.evaluate(lambda: _get_dataset(self.eval_routes), steps=len(self.eval_routes))
        logging.info('Quick evaluation: {}'.format(eval_result))
        self.eval_predictions = self.estimator.predict(lambda: _get_dataset(self.eval_routes))
        logging.info('Finished evaluation predictions')

    def iterate_eval_routes(self):
        if not self.eval_predictions:
            raise RuntimeError('No predictions. Need to learn first.')
        for route in self.eval_routes:
            try:
                yield route, next(self.eval_predictions)['predictions'][0]
            except StopIteration:
                raise

    def predict_all_scaling_factors_by_way_ids(self) -> dict:
        logging.info('Predicting all scaling factors of all OSM way IDs...')
        scaling_factors_by_way_ids = {}
        db = OsmDatabase.get_instance()
        way_tag_ratios = db.get_all_way_tag_ratios()
        way_ids = sorted(way_tag_ratios.keys())

        def input_fn():
            tag_ratios = {
                _escape_tag(tag): [
                    way_tag_ratios[way_id][tag]
                    for way_id in way_ids
                ] for tag in config.osm.tags
            }
            logging.info('Number of tag ratios: {}'.format(len(tag_ratios)))
            dataset = tf.data.Dataset.from_tensor_slices((tag_ratios,))
            return dataset.batch(len(tag_ratios))

        logging.info('Preparing TensorFlow predictions...')
        predictions = self.estimator.predict(input_fn)
        logging.info('Finished predictions')
        logging.info('Mapping the predictions to OSM way IDs...')
        logging.info('The first iteration will take longer than the rest.')
        bar = Bar('Predictions:', max=len(way_ids), suffix=config.progress.suffix)
        for way_id in way_ids:
            bar.next()
            scaling_factors_by_way_ids[way_id] = next(predictions)['predictions'][0]
        bar.finish()
        logging.info('Predicted {} scaling factors in {} seconds'.format(bar.index, bar.elapsed))
        return scaling_factors_by_way_ids


# def main(argv):
#     Learning().learn()
#
#
# if __name__ == '__main__':
#     # tf.logging.set_verbosity(tf.logging.DEBUG)
#     # tf.app.run(main)
#     Learning().learn()
