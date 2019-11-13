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

from pyspark import keyword_only
from pyspark.ml.param.shared import HasOutputCols, Param, Params, TypeConverters


class EstimatorParams(Params):
    num_proc = Param(Params._dummy(), 'num_proc', 'number of processes')
    optimizer = Param(Params._dummy(), 'optimizer', 'optimizer')
    model = Param(Params._dummy(), 'model', 'model')
    backend = Param(Params._dummy(), 'backend', 'backend')
    store = Param(Params._dummy(), 'store', 'store')
    metrics = Param(Params._dummy(), 'metrics', 'metrics')
    loss = Param(Params._dummy(), 'loss', 'loss')
    compression = Param(Params._dummy(), 'compression', 'compression')

    loss_weights = Param(Params._dummy(), 'loss_weights', 'loss weights',
                         typeConverter=TypeConverters.toListFloat)
    sample_weight_col = Param(Params._dummy(), 'sample_weight_col',
                              'name of the column containing sample weights',
                              typeConverter=TypeConverters.toString)
    feature_cols = Param(Params._dummy(), "feature_cols", "feature column names",
                         typeConverter=TypeConverters.toListString)
    label_cols = Param(Params._dummy(), "label_cols", "label column names",
                       typeConverter=TypeConverters.toListString)
    validation_col = Param(Params._dummy(),
                           "validation_col",
                           "name of a column with 0 or 1 flag to specify using sample for validation",
                           typeConverter=TypeConverters.toString)
    callbacks = Param(Params._dummy(), 'callbacks', 'callbacks')
    batch_size = Param(Params._dummy(), 'batch_size', 'batch size',
                       typeConverter=TypeConverters.toInt)
    epochs = Param(Params._dummy(), 'epochs', 'epochs')
    validation_split = Param(Params._dummy(), 'validation_split', 'validation split',
                             typeConverter=TypeConverters.toFloat)

    shuffle_buffer_size = Param(Params._dummy(),
                                'shuffle_buffer_size',
                                'shuffling buffer size of data before training in number of samples',
                                typeConverter=TypeConverters.toInt)

    verbose = Param(Params._dummy(), 'verbose', 'verbose',
                    typeConverter=TypeConverters.toInt)

    partitions_per_process = Param(Params._dummy(), 'partitions_per_process',
                                   'partitions for parquet form of the DataFrame per process',
                                   typeConverter=TypeConverters.toInt)

    run_id = Param(Params._dummy(), 'run_id',
                   'unique ID for this run, if run already exists, '
                   'then training will resume from last checkpoint in the store',
                   typeConverter=TypeConverters.toString)

    def __init__(self):
        super(EstimatorParams, self).__init__()

        self._setDefault(
            num_proc=None,
            store=None,
            backend=None,
            model=None,
            optimizer=None,
            loss=None,
            loss_weights=None,
            sample_weight_col=None,
            metrics=[],
            feature_cols=None,
            label_cols=None,
            validation_col=None,
            compression=None,
            batch_size=32,
            epochs=1,
            verbose=1,
            callbacks=[],
            validation_split=0.0,
            shuffle_buffer_size=None,
            partitions_per_process=10,
            run_id=None)

    def _should_validate(self):
        return self.getValidationCol() is not None or self.getValidationSplit() > 0

    @keyword_only
    def setParams(self, **kwargs):
        return self._set(**kwargs)

    def setNumProc(self, value):
        return self._set(num_proc=value)

    def getNumProc(self):
        return self.getOrDefault(self.num_proc)

    def setModel(self, value):
        return self._set(model=value)

    def getModel(self):
        return self.getOrDefault(self.model)

    def setBackend(self, value):
        return self._set(backend=value)

    def getBackend(self):
        return self.getOrDefault(self.backend)

    def setStore(self, value):
        return self._set(store=value)

    def getStore(self):
        return self.getOrDefault(self.store)

    def setLoss(self, value):
        return self._set(loss=value)

    def getLoss(self):
        return self.getOrDefault(self.loss)

    def setLossWeights(self, value):
        return self._set(loss_weights=value)

    def getLossWeights(self):
        return self.getOrDefault(self.loss_weights)

    def setSampleWeightCol(self, value):
        return self._set(sample_weight_col=value)

    def getSampleWeightCol(self):
        return self.getOrDefault(self.sample_weight_col)

    def setMetrics(self, value):
        return self._set(metrics=value)

    def getMetrics(self):
        return self.getOrDefault(self.metrics)

    def setFeatureCols(self, value):
        return self._set(feature_cols=value)

    def getFeatureCols(self):
        return self.getOrDefault(self.feature_cols)

    def setLabelCols(self, value):
        return self._set(label_cols=value)

    def getLabelCols(self):
        return self.getOrDefault(self.label_cols)

    def setValidationCol(self, value):
        return self._set(validation_col=value)

    def getValidationCol(self):
        return self.getOrDefault(self.validation_col)

    def setCallbacks(self, value):
        return self._set(callbacks=value)

    def getCallbacks(self):
        return self.getOrDefault(self.callbacks)

    def setBatchSize(self, value):
        return self._set(batch_size=value)

    def getBatchSize(self):
        return self.getOrDefault(self.batch_size)

    def setEpochs(self, value):
        return self._set(epochs=value)

    def getEpochs(self):
        return self.getOrDefault(self.epochs)

    def setValidationSplit(self, value):
        return self._set(validation_split=value)

    def getValidationSplit(self):
        return self.getOrDefault(self.validation_split)

    def setVerbose(self, value):
        return self._set(verbose=value)

    def getVerbose(self):
        return self.getOrDefault(self.verbose)

    def setCompression(self, value):
        return self._set(compression=value)

    def getCompression(self):
        return self.getOrDefault(self.compression)

    def setShufflingBufferSize(self, value):
        return self._set(shuffle_buffer_size=value)

    def getShufflingBufferSize(self):
        return self.getOrDefault(self.shuffle_buffer_size)

    def setOptimizer(self, value):
        return self._set(optimizer=value)

    def getOptimizer(self):
        return self.getOrDefault(self.optimizer)

    def setPartitionsPerProcess(self, value):
        return self._set(partitions_per_process=value)

    def getPartitionsPerProcess(self):
        return self.getOrDefault(self.partitions_per_process)

    def setRunId(self, value):
        return self._set(run_id=value)

    def getRunId(self):
        return self.getOrDefault(self.run_id)


class ModelParams(HasOutputCols):
    history = Param(Params._dummy(), 'history', 'history')
    model = Param(Params._dummy(), 'model', 'model')
    feature_columns = Param(Params._dummy(), 'feature_columns', 'feature columns')
    label_columns = Param(Params._dummy(), 'label_columns', 'label columns')
    run_id = Param(Params._dummy(), 'run_id',
                   'unique ID for the run that generated this model, if no ID was given by the '
                   'user, defaults to current timestamp at the time of fit()',
                   typeConverter=TypeConverters.toString)
    _metadata = Param(Params._dummy(), '_metadata',
                      'metadata contains the shape and type of input and output')

    def __init__(self):
        super(ModelParams, self).__init__()

    @keyword_only
    def setParams(self, **kwargs):
        return self._set(**kwargs)

    def setHistory(self, value):
        return self._set(history=value)

    def getHistory(self):
        return self.getOrDefault(self.history)

    def setModel(self, value):
        return self._set(model=value)

    def getModel(self):
        return self.getOrDefault(self.model)

    def setFeatureColumns(self, value):
        return self._set(feature_columns=value)

    def getFeatureColumns(self):
        return self.getOrDefault(self.feature_columns)

    def setLabelColoumns(self, value):
        return self._set(label_columns=value)

    def getLabelColumns(self):
        return self.getOrDefault(self.label_columns)

    def setRunId(self, value):
        return self._set(run_id=value)

    def getRunId(self):
        return self.getOrDefault(self.run_id)

    # Only for internal use
    def _get_metadata(self):
        return self.getOrDefault(self._metadata)
