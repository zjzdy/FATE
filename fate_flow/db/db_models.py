#
#  Copyright 2019 The FATE Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import datetime
import inspect
import os
import sys
import json

import __main__
from peewee import (Model, CharField, IntegerField, BigIntegerField, TextField, CompositeKey,
                    BigAutoField, ManyToManyField, DeferredThroughModel, ForeignKeyField)
from playhouse.apsw_ext import APSWDatabase
from playhouse.pool import PooledMySQLDatabase

from arch.api.utils import log_utils
from arch.api.utils.core_utils import current_timestamp
from fate_flow.entity.constant import WorkMode
from fate_flow.settings import DATABASE, WORK_MODE, stat_logger, USE_LOCAL_DATABASE
from fate_flow.entity.runtime_config import RuntimeConfig

LOGGER = log_utils.getLogger()


def singleton(cls, *args, **kw):
    instances = {}

    def _singleton():
        key = str(cls) + str(os.getpid())
        if key not in instances:
            instances[key] = cls(*args, **kw)
        return instances[key]

    return _singleton


class JSONField(TextField):
    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        if value is not None:
            return json.loads(value)


@singleton
class BaseDataBase(object):
    def __init__(self):
        database_config = DATABASE.copy()
        db_name = database_config.pop("name")
        if WORK_MODE == WorkMode.STANDALONE:
            if USE_LOCAL_DATABASE:
                self.database_connection = APSWDatabase('fate_flow_sqlite.db')
                RuntimeConfig.init_config(USE_LOCAL_DATABASE=True)
                stat_logger.info('init sqlite database on standalone mode successfully')
            else:
                self.database_connection = PooledMySQLDatabase(db_name, **database_config)
                stat_logger.info('init mysql database on standalone mode successfully')
                RuntimeConfig.init_config(USE_LOCAL_DATABASE=False)
        elif WORK_MODE == WorkMode.CLUSTER:
            self.database_connection = PooledMySQLDatabase(db_name, **database_config)
            stat_logger.info('init mysql database on cluster mode successfully')
            RuntimeConfig.init_config(USE_LOCAL_DATABASE=False)
        else:
            raise Exception('can not init database')


MAIN_FILE_PATH = os.path.realpath(__main__.__file__)
if MAIN_FILE_PATH.endswith('fate_flow_server.py') or \
        MAIN_FILE_PATH.endswith('task_executor.py') or \
        MAIN_FILE_PATH.find("/unittest/__main__.py"):
    DB = BaseDataBase().database_connection
else:
    # Initialize the database only when the server is started.
    DB = None


def close_connection():
    try:
        if DB:
            DB.close()
    except Exception as e:
        LOGGER.exception(e)


class DataBaseModel(Model):
    class Meta:
        database = DB

    def to_json(self):
        return self.__dict__['__data__']

    def to_human_model_dict(self, only_primary_with: list = None):
        model_dict = self.__dict__["__data__"]
        human_model_dict = {}
        if not only_primary_with:
            for k, v in model_dict.items():
                human_model_dict[k.lstrip("f_")] = v
        else:
            for k in self._meta.primary_key.field_names:
                human_model_dict[k.lstrip("f_")] = model_dict[k]
            for k in only_primary_with:
                human_model_dict[k] = model_dict["f_%s" % k]
        return human_model_dict

    def save(self, *args, **kwargs):
        if hasattr(self, "f_update_date"):
            self.f_update_date = datetime.datetime.now()
        if hasattr(self, "f_update_time"):
            self.f_update_time = current_timestamp()
        return super(DataBaseModel, self).save(*args, **kwargs)


def init_database_tables():
    with DB.connection_context():
        members = inspect.getmembers(sys.modules[__name__], inspect.isclass)
        table_objs = []
        for name, obj in members:
            if obj != DataBaseModel and issubclass(obj, DataBaseModel):
                table_objs.append(obj)
        DB.create_tables(table_objs)


class Queue(DataBaseModel):
    f_job_id = CharField(max_length=100)
    f_event = CharField(max_length=500)
    f_is_waiting = IntegerField(default=1)
    # 0: out; 1: in queue one; 2 :cancel; 3: in queue two; 4: out because of Over limit; 5: Intermediate queue
    f_frequency = IntegerField(default=0)

    class Meta:
        db_table = "t_queue"


class Job(DataBaseModel):
    # multi-party common configuration
    f_job_id = CharField(max_length=25)
    f_name = CharField(max_length=500, null=True, default='')
    f_description = TextField(null=True, default='')
    f_tag = CharField(max_length=50, null=True, index=True, default='')
    f_dsl = JSONField()
    f_runtime_conf = JSONField()
    f_train_runtime_conf = JSONField(null=True)
    f_roles = JSONField()
    f_work_mode = IntegerField()
    f_initiator_role = CharField(max_length=50, index=True)
    f_initiator_party_id = CharField(max_length=50, index=True, default=-1)
    f_status = CharField(max_length=50)
    f_status_level = BigIntegerField()
    # this party configuration
    f_role = CharField(max_length=50, index=True)
    f_party_id = CharField(max_length=10, index=True)
    f_is_initiator = IntegerField(null=True, index=True, default=-1)
    f_progress = IntegerField(null=True, default=0)
    f_create_time = BigIntegerField()
    f_update_time = BigIntegerField(null=True)
    f_start_time = BigIntegerField(null=True)
    f_end_time = BigIntegerField(null=True)
    f_elapsed = BigIntegerField(null=True)

    class Meta:
        db_table = "t_job"
        primary_key = CompositeKey('f_job_id', 'f_role', 'f_party_id')


class TaskSet(DataBaseModel):
    # multi-party common configuration
    f_job_id = CharField(max_length=25)
    f_task_set_id = BigIntegerField()
    f_initiator_role = CharField(max_length=50, index=True)
    f_initiator_party_id = CharField(max_length=50, index=True, default=-1)
    f_status = CharField(max_length=50)
    f_status_level = BigIntegerField()
    # this party configuration
    f_role = CharField(max_length=50, index=True)
    f_party_id = CharField(max_length=10, index=True)
    f_create_time = BigIntegerField()
    f_update_time = BigIntegerField(null=True)
    f_start_time = BigIntegerField(null=True)
    f_end_time = BigIntegerField(null=True)
    f_elapsed = BigIntegerField(null=True)

    class Meta:
        db_table = "t_task_set"
        primary_key = CompositeKey('f_job_id', 'f_task_set_id', 'f_role', 'f_party_id')


class Task(DataBaseModel):
    # multi-party common configuration
    f_job_id = CharField(max_length=25)
    f_task_set_id = BigIntegerField()
    f_component_name = TextField()
    f_task_id = CharField(max_length=100)
    f_task_version = BigIntegerField()
    f_initiator_role = CharField(max_length=50, index=True)
    f_initiator_party_id = CharField(max_length=50, index=True, default=-1)
    f_status = CharField(max_length=50)
    f_status_level = BigIntegerField()
    # this party configuration
    f_role = CharField(max_length=50, index=True)
    f_party_id = CharField(max_length=10, index=True)
    f_run_ip = CharField(max_length=100, null=True)
    f_run_pid = IntegerField(null=True)
    f_party_status = CharField(max_length=50)
    f_party_status_level = BigIntegerField()
    f_create_time = BigIntegerField()
    f_update_time = BigIntegerField(null=True)
    f_start_time = BigIntegerField(null=True)
    f_end_time = BigIntegerField(null=True)
    f_elapsed = BigIntegerField(null=True)

    class Meta:
        db_table = "t_task"
        primary_key = CompositeKey('f_job_id', 'f_task_id', 'f_task_version', 'f_role', 'f_party_id')


class TrackingMetric(DataBaseModel):
    _mapper = {}

    @classmethod
    def model(cls, table_index=None, date=None):
        if not table_index:
            table_index = date.strftime(
                '%Y%m%d') if date else datetime.datetime.now().strftime(
                '%Y%m%d')
        class_name = 'TrackingMetric_%s' % table_index

        ModelClass = TrackingMetric._mapper.get(class_name, None)
        if ModelClass is None:
            class Meta:
                db_table = '%s_%s' % ('t_tracking_metric', table_index)

            attrs = {'__module__': cls.__module__, 'Meta': Meta}
            ModelClass = type("%s_%s" % (cls.__name__, table_index), (cls,),
                              attrs)
            TrackingMetric._mapper[class_name] = ModelClass
        return ModelClass()

    f_id = BigAutoField(primary_key=True)
    f_job_id = CharField(max_length=25)
    f_component_name = TextField()
    f_task_id = CharField(max_length=100, null=True)
    f_task_version = BigIntegerField(null=True)
    f_role = CharField(max_length=50, index=True)
    f_party_id = CharField(max_length=10, index=True)
    f_metric_namespace = CharField(max_length=180, index=True)
    f_metric_name = CharField(max_length=180, index=True)
    f_key = CharField(max_length=200)
    f_value = TextField()
    f_type = IntegerField(index=True)  # 0 is data, 1 is meta
    f_create_time = BigIntegerField()
    f_update_time = BigIntegerField(null=True)


class TrackingOutputDataInfo(DataBaseModel):
    _mapper = {}

    @classmethod
    def model(cls, table_index=None, date=None):
        if not table_index:
            table_index = date.strftime(
                '%Y%m%d') if date else datetime.datetime.now().strftime(
                '%Y%m%d')
        class_name = 'TrackingOutputDataInfo_%s' % table_index

        ModelClass = TrackingOutputDataInfo._mapper.get(class_name, None)
        if ModelClass is None:
            class Meta:
                db_table = '%s_%s' % ('t_tracking_output_data_info', table_index)
                primary_key = CompositeKey('f_job_id', 'f_task_id', 'f_task_version', 'f_data_name', 'f_role', 'f_party_id')

            attrs = {'__module__': cls.__module__, 'Meta': Meta}
            ModelClass = type("%s_%s" % (cls.__name__, table_index), (cls,),
                              attrs)
            TrackingOutputDataInfo._mapper[class_name] = ModelClass
        return ModelClass()

    # multi-party common configuration
    f_job_id = CharField(max_length=25)
    f_component_name = TextField()
    f_task_id = CharField(max_length=100, null=True)
    f_task_version = BigIntegerField(null=True)
    f_data_name = CharField(max_length=30)
    # this party configuration
    f_role = CharField(max_length=50, index=True)
    f_party_id = CharField(max_length=10, index=True)
    f_table_name = CharField(max_length=500, null=True)
    f_table_namespace = CharField(max_length=500, null=True)
    f_create_time = BigIntegerField()
    f_update_time = BigIntegerField(null=True)
    f_description = TextField(null=True, default='')


class MachineLearningModelMeta(DataBaseModel):
    f_id = BigIntegerField(primary_key=True)
    f_role = CharField(max_length=50, index=True)
    f_party_id = CharField(max_length=10, index=True)
    f_roles = TextField()
    f_job_id = CharField(max_length=25)
    f_model_id = CharField(max_length=100, index=True)
    f_model_version = CharField(max_length=100, index=True)
    f_loaded_times = IntegerField(default=0)
    f_size = BigIntegerField(default=0)
    f_create_time = BigIntegerField(default=0)
    f_update_time = BigIntegerField(default=0)
    f_description = TextField(null=True, default='')
    # f_tag = CharField(max_length=50, null=True, index=True, default='')

    class Meta:
        db_table = "t_machine_learning_model_meta"


Model_Tag = DeferredThroughModel()


class Tag(DataBaseModel):
    f_id = BigAutoField(primary_key=True)
    f_name = CharField(max_length=100, index=True, unique=True)
    f_desc = TextField(null=True)
    f_model = ManyToManyField(MachineLearningModelMeta, backref='tags', through_model=Model_Tag)
    f_create_time = BigIntegerField(default=current_timestamp())
    f_update_time = BigIntegerField(default=current_timestamp())

    class Meta:
        db_table = "t_tags"


class ModelTag(DataBaseModel):
    f_m_id = ForeignKeyField(MachineLearningModelMeta, db_column='f_m_id', on_delete='CASCADE')
    f_t_id = ForeignKeyField(Tag, db_column='f_t_id', on_delete='CASCADE')

    class Meta:
        db_table = "t_model_tag"


Model_Tag.set_model(ModelTag)


class ComponentSummary(DataBaseModel):
    f_id = BigAutoField(primary_key=True)
    f_job_id = CharField(max_length=25)
    f_role = CharField(max_length=50, index=True)
    f_party_id = CharField(max_length=10, index=True)
    f_component_name = TextField()
    f_summary = TextField()
    f_create_time = BigIntegerField(default=0)
    f_update_time = BigIntegerField(default=0)

    class Meta:
        db_table = "t_component_summary"


class ModelOperationLog(DataBaseModel):
    f_operation_type = CharField(max_length=20, null=False, index=True)
    f_operation_status = CharField(max_length=20, null=True, index=True)
    f_initiator_role = CharField(max_length=50, index=True, null=True)
    f_initiator_party_id = CharField(max_length=10, index=True, null=True)
    f_request_ip = CharField(max_length=20, null=True)
    f_model_id = CharField(max_length=100, index=True)
    f_model_version = CharField(max_length=100, index=True)
    f_create_time = BigIntegerField(default=current_timestamp())
    f_update_time = BigIntegerField(default=current_timestamp())

    class Meta:
        db_table = "t_model_operation_log"


def fill_db_model_object(model_object, human_model_dict):
    for k, v in human_model_dict.items():
        attr_name = 'f_%s' % k
        if hasattr(model_object.__class__, attr_name):
            setattr(model_object, attr_name, v)
    return model_object
