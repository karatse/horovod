# Copyright 2019 Uber Technologies, Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

from __future__ import absolute_import

import horovod.spark.common._namedtuple_fix

import io
import numbers
import time

from horovod.run.common.util import codec
from pyspark import keyword_only
from pyspark.ml import Estimator, Model
from pyspark.ml.param.shared import Param, Params
from pyspark.ml.util import MLWritable, MLReadable

from horovod.spark.common import util
from horovod.spark.common.backend import SparkBackend
from horovod.spark.common.params import EstimatorParams, ModelParams
from horovod.spark.common.serialization import \
    HorovodParamsWriter, HorovodParamsReader
from horovod.spark.torch import remote

import torch
import torch.utils.data


def _torch_param_serialize(param_name, param_val):
    if param_name in [EstimatorParams.backend.name, EstimatorParams.store.name]:
        # We do not serialize backend and store. These params have to be regenerated for each
        # run of the pipeline
        return None

    if param_val is None:
        return None

    return codec.dumps_base64(param_val)


class TorchEstimatorParamsWriter(HorovodParamsWriter):
    def saveImpl(self, path):
        # Write the parameters
        HorovodParamsWriter.saveMetadata(self.instance, path, self.sc,
                                         param_serializer_fn=_torch_param_serialize)


class TorchEstimatorParamsWritable(MLWritable):
    def write(self):
        return TorchEstimatorParamsWriter(self)


class TorchEstimatorParamsReader(HorovodParamsReader):
    def _deserialize_dict(self, dict_values):
        deserialized_dict = dict()
        for key, val in dict_values.items():
            if val is None:
                deserialized_dict[key] = None
            else:
                deserialized_dict[key] = codec.loads_base64(val)
        return deserialized_dict


class TorchEstimatorParamsReadable(MLReadable):
    @classmethod
    def read(cls):
        """Returns a DefaultParamsReader instance for this class."""
        return TorchEstimatorParamsReader(cls)


class TorchEstimator(Estimator, EstimatorParams, TorchEstimatorParamsWritable,
                     TorchEstimatorParamsReadable):
    input_shapes = Param(Params._dummy(), 'input_shapes', 'input layer shapes')
    loss_constructor = Param(Params._dummy(), 'loss_constructor',
                             'functions that construct the loss')

    @keyword_only
    def __init__(self,
                 num_proc=None,
                 model=None,
                 backend=None,
                 store=None,
                 optimizer=None,
                 loss=None,
                 loss_constructor=None,
                 metrics=None,
                 loss_weights=None,
                 sample_weight_col=None,
                 compression=None,
                 feature_cols=None,
                 input_shapes=None,
                 validation_col=None,
                 label_cols=None,
                 callbacks=None,
                 batch_size=None,
                 epochs=None,
                 validation_split=None,
                 verbose=1,
                 shuffle_buffer_size=None,
                 partitions_per_process=None,
                 run_id=None):
        super(TorchEstimator, self).__init__()
        self._setDefault(loss_constructor=None)

        kwargs = self._input_kwargs

        if EstimatorParams.loss.name in kwargs and TorchEstimator.loss_constructor.name in kwargs:
            raise ValueError("only one of loss_constructor and loss parameters can be specified.")

        if EstimatorParams.loss.name in kwargs and not \
                (isinstance(loss, list) or isinstance(loss, tuple)):
            kwargs[EstimatorParams.loss.name] = [kwargs[EstimatorParams.loss.name]]

        if TorchEstimator.loss_constructor.name in kwargs and not \
                (isinstance(loss_constructor, list) or isinstance(loss_constructor, tuple)):
            kwargs[TorchEstimator.loss_constructor.name] = [
                kwargs[TorchEstimator.loss_constructor.name]]

        self.setParams(**kwargs)

    def setInputShapes(self, value):
        return self._set(input_shapes=value)

    def getInputShapes(self):
        return self.getOrDefault(self.input_shapes)

    def getLossConstructors(self):
        return self.getOrDefault(self.loss_constructor)

    def _get_optimizer(self):
        return self.getOrDefault(self.optimizer)

    def getOptimizer(self):
        model = self.getModel()
        if model:
            optimizer = self._get_optimizer()
            optimizer_cls = optimizer.__class__
            optimizer_state = optimizer.state_dict()
            optimzer = optimizer_cls(model.parameters(), lr=1)
            optimzer.load_state_dict(optimizer_state)
            return optimzer
        else:
            return self._get_optimizer()

    def _check_model_compatibility(self, metadata):
        util.check_shape_compatibility(metadata,
                                       self.getFeatureCols(),
                                       self.getLabelCols(),
                                       input_shapes=self.getInputShapes())

    def fit_on_parquet(self, params=None):
        if params:
            return self.copy(params)._fit_on_parquet()
        else:
            return self._fit_on_parquet()

    def _fit_on_parquet(self):
        backend = self.getBackend()
        store = self.getStore()
        label_columns = self.getLabelCols()
        feature_columns = self.getFeatureCols()
        sample_weight_col = self.getSampleWeightCol()

        train_rows, val_rows, metadata, avg_row_size = \
            util.get_simple_meta_from_parquet(store,
                                              label_columns=label_columns,
                                              feature_columns=feature_columns,
                                              sample_weight_col=sample_weight_col)

        return self._fit_on_prepared_data(backend, train_rows, val_rows, metadata, avg_row_size)

    def _fit(self, df):
        validation_split = self.getValidationSplit()
        validation_col = self.getValidationCol()
        backend = self.getBackend()
        store = self.getStore()
        label_columns = self.getLabelCols()
        feature_columns = self.getFeatureCols()
        sample_weight_col = self.getSampleWeightCol()
        partitions_per_process = self.getPartitionsPerProcess()

        num_processes = self.getNumProc()
        if (num_processes is None) == (backend is None):
            raise ValueError('Exactly one of parameters "num_processes" and "backend" '
                             'must be specified')
        elif backend is None:
            backend = SparkBackend(num_processes)
        elif num_processes is None:
            num_processes = backend.num_processes()

        train_rows, val_rows, metadata, avg_row_size = \
            util.prepare_data(num_processes,
                              store,
                              df,
                              label_columns=label_columns,
                              feature_columns=feature_columns,
                              validation_col=validation_col,
                              validation_split=validation_split,
                              sample_weight_col=sample_weight_col,
                              partitions_per_process=partitions_per_process)

        return self._fit_on_prepared_data(backend, train_rows, val_rows, metadata, avg_row_size)

    def _fit_on_prepared_data(self, backend, train_rows, val_rows, metadata, avg_row_size):
        model_pre_train = self.getModel()
        if not model_pre_train:
            raise ValueError('Model parameter is required')

        self._check_model_compatibility(metadata)

        run_id = self.getRunId()
        if run_id is None:
            run_id = 'pytorch_' + str(int(time.time()))

        last_checkpoint_state = None
        if self._has_checkpoint(run_id):
            last_checkpoint_state = self._load_checkpoint(run_id)

        serialized_model = util.serialize(model_pre_train)

        trainer = remote.RemoteTrainer(self, metadata, last_checkpoint_state, run_id)
        handle = backend.run(trainer,
                             args=(serialized_model, train_rows, val_rows, avg_row_size),
                             env={})
        return self._create_model(handle, run_id, metadata)

    def _has_checkpoint(self, run_id):
        store = self.getStore()
        last_ckpt_path = store.get_checkpoint_path(run_id)
        return last_ckpt_path is not None and store.exists(last_ckpt_path)

    def _load_checkpoint(self, run_id):
        store = self.getStore()
        last_ckpt_path = store.get_checkpoint_path(run_id)

        if self.getVerbose():
            print('Resuming training from last checkpoint: {}'.format(last_ckpt_path))

        ckpt_file = io.BytesIO(store.read(last_ckpt_path))
        return torch.load(ckpt_file)

    def _create_model(self, run_results, run_id, metadata):
        history, serialized_model, serialized_optimizer = run_results[0]
        model = codec.loads_base64(serialized_model)

        # torch.load correctly moves all the optimizer state values to cpu
        # before creating the object.
        optimizer_bio = codec.loads_base64(serialized_optimizer)
        opt = torch.load(optimizer_bio, map_location=torch.device('cpu'))

        return self.get_model_class()(**self._get_model_kwargs(
            model, history, opt, run_id, metadata))

    def get_model_class(self):
        return TorchModel

    def _get_model_kwargs(self, model, history, optimizer, run_id, metadata):
        return dict(history=history,
                    model=model,
                    optimizer=optimizer,
                    feature_columns=self.getFeatureCols(),
                    input_shapes=self.getInputShapes(),
                    label_columns=self.getLabelCols(),
                    run_id=run_id,
                    _metadata=metadata)


class TorchModel(Model, ModelParams, TorchEstimatorParamsWritable, TorchEstimatorParamsReadable):
    optimizer = Param(Params._dummy(), 'optimizer', 'optimizer')
    input_shapes = Param(Params._dummy(), 'input_shapes', 'input layer shapes')

    @keyword_only
    def __init__(self,
                 history=None,
                 model=None,
                 feature_columns=None,
                 input_shapes=None,
                 label_columns=None,
                 optimizer=None,
                 run_id=None,
                 _metadata=None):
        super(TorchModel, self).__init__()

        if label_columns:
            self.setOutputCols([col + '__output' for col in label_columns])
        kwargs = self._input_kwargs

        self.setParams(**kwargs)

    def setInputShapes(self, value):
        return self._set(input_shapes=value)

    def getInputShapes(self):
        return self.getOrDefault(self.input_shapes)

    def setOptimizer(self, value):
        return self._set(optimizer=value)

    def _get_optimizer(self):
        return self.getOrDefault(self.optimizer)

    def getOptimizer(self):
        model = self.getModel()
        if model:
            _optimizer = self._get_optimizer()
            optimizer_cls = _optimizer.__class__
            optimizer_state = _optimizer.state_dict()
            optimzer = optimizer_cls(model.parameters(), lr=1)
            optimzer.load_state_dict(optimizer_state)
            return optimzer
        else:
            return self._get_optimizer()

    # To run locally on OS X, need export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
    def _transform(self, df):
        model_pre_predict = self.getModel()
        model_pre_predict.eval()
        serialized_model = util.serialize(model_pre_predict)

        input_shapes = self.getInputShapes()
        label_cols = self.getLabelColumns()
        output_cols = self.getOutputCols()
        feature_cols = self.getFeatureColumns()
        metadata = self._get_metadata()

        # Functions
        deserialize_fn = util.deserialize_fn()

        def predict(rows):
            from pyspark import Row
            from pyspark.ml.linalg import DenseVector, SparseVector

            model = deserialize_fn(serialized_model)
            # Perform predictions.
            for row in rows:
                fields = row.asDict().copy()

                # Note: if the col is SparseVector, torch.tensor(col) correctly converts it to a
                # dense torch tensor.
                data = [torch.tensor([row[col]]).reshape(shape) for
                        col, shape in zip(feature_cols, input_shapes)]

                preds = model(*data)
                if not isinstance(preds, list) and not isinstance(preds, tuple):
                    preds = [preds]

                for label_col, output_col, pred in zip(label_cols, output_cols, preds):
                    meta = metadata[label_col]
                    col_type = meta['spark_data_type']
                    # dtype for dense and spark tensor is always np.float64
                    if col_type == DenseVector:
                        shape = meta['shape']
                        flattened_pred = pred.reshape(shape, )
                        field = DenseVector(flattened_pred)
                    elif col_type == SparseVector:
                        shape = meta['shape']
                        flattened_pred = pred.reshape(shape, )
                        nonzero_indices = flattened_pred.nonzero()[0]
                        field = SparseVector(shape, nonzero_indices,
                                             flattened_pred[nonzero_indices])
                    else:
                        # If the column is scalar type, int, float, etc.
                        value = pred.item()
                        python_type = util.spark_scalar_to_python_type(col_type)
                        if issubclass(python_type, numbers.Integral):
                            value = round(value)
                        field = python_type(value)

                    fields[output_col] = field

                yield Row(**fields)

        return df.rdd.mapPartitions(predict).toDF()
