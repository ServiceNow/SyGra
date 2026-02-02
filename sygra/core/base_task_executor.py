import ast
import copy
import hashlib
import json
import os
from abc import ABC
from datetime import datetime
from typing import Any, Optional, Union, cast

import datasets  # type: ignore[import-untyped]
import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from langgraph.graph import StateGraph
from PIL import Image

from sygra.core.dataset.dataset_config import (
    DataSourceConfig,
    DataSourceType,
    OutputConfig,
    OutputType,
)
from sygra.core.dataset.dataset_processor import DatasetProcessor
from sygra.core.dataset.file_handler import FileHandler
from sygra.core.dataset.huggingface_handler import HuggingFaceHandler
from sygra.core.dataset.servicenow_handler import ServiceNowHandler
from sygra.core.graph.graph_config import GraphConfig
from sygra.core.graph.langgraph.graph_builder import LangGraphBuilder
from sygra.core.graph.sygra_state import SygraState
from sygra.logger.logger_config import logger
from sygra.metadata.metadata_collector import get_metadata_collector
from sygra.processors.output_record_generator import BaseOutputGenerator
from sygra.tools.toolkits.data_quality.processor import DataQuality
from sygra.utils import constants, utils


class BaseTaskExecutor(ABC):
    def __init__(self, args: Any, graph_config_dict: Optional[dict] = None):
        self.args = args
        self.task_name = args.task
        logger.info(f"Loading graph config for task {self.task_name}")
        self.output_dir = args.output_dir
        self.source_config: Optional[DataSourceConfig] = None
        self.output_config: Optional[Union[OutputConfig, list[OutputConfig]]] = None
        # Store metadata and source configs per alias for multi-dataset scenarios
        self._dataset_metadata_by_alias: dict[str, dict] = {}
        self._source_configs_by_alias: dict[str, DataSourceConfig] = {}

        config_file_path = utils.get_file_in_task_dir(self.task_name, "graph_config.yaml")
        self.config = graph_config_dict or utils.load_yaml_file(filepath=config_file_path)

        data_config = self.config.get("data_config", {})
        config_resumable = data_config.get("resumable", False)
        self.id_column = data_config.get("id_column") or None

        self.resumable = self._configure_resume_behavior(args, config_resumable)

        self.dataset = self.init_dataset()
        output_transform_args = {"oasst": args.oasst, "quality": args.quality}

        graph_props = self.config.get("graph_config", {}).get("graph_properties", {})

        self.graph_config = GraphConfig(
            self.config,
            self.dataset,
            output_transform_args,
            graph_properties=graph_props,
        )
        self.output_generator: Optional[BaseOutputGenerator] = self._init_output_generator()
        self._init_metadata_collector(args)

    def _init_metadata_collector(self, args):
        """Initialize metadata collection for this execution."""
        collector = get_metadata_collector()

        # Check if metadata collection should be disabled
        disable_metadata = getattr(args, "disable_metadata", False)
        if disable_metadata:
            collector.set_enabled(False)
            logger.info("Metadata collection disabled via --disable_metadata flag")
            return

        # Reset collector to clear any data from health checks or previous runs
        collector.reset()
        collector.set_execution_context(
            task_name=self.task_name,
            run_name=getattr(args, "run_name", None),
            output_dir=getattr(args, "output_dir", None),
            batch_size=getattr(args, "batch_size", 50),
            checkpoint_interval=getattr(args, "checkpoint_interval", 100),
            resumable=getattr(args, "resume", False),
            debug=getattr(args, "debug", False),
        )

        # Set dataset metadata if available
        if self.source_config is not None:
            # Single dataset scenario
            source_path = None
            # Try to get source path from repo_id (HuggingFace) or file_path (local files)
            if self.source_config.repo_id:
                source_path = self.source_config.repo_id
            elif self.source_config.file_path:
                source_path = self.source_config.file_path

            # Use captured dataset version and hash (captured before transformations)
            dataset_version = getattr(self, "_dataset_version", None)
            dataset_hash = getattr(self, "_dataset_hash", None)

            collector.set_dataset_metadata(
                source_type=(
                    str(self.source_config.type.value)
                    if hasattr(self.source_config.type, "value")
                    else str(self.source_config.type)
                ),
                source_path=source_path,
                start_index=getattr(args, "start_index", 0),
                dataset_version=dataset_version,
                dataset_hash=dataset_hash,
            )

        # Multi-dataset scenario: re-register sources captured during dataset loading
        # (metadata was captured before reset, so we need to re-register it)
        if self._source_configs_by_alias:
            source_types: set[str] = set()

            for alias, source_cfg in self._source_configs_by_alias.items():
                metadata = self._dataset_metadata_by_alias.get(alias, {})

                # Determine source path
                source_path = None
                if source_cfg.repo_id:
                    source_path = source_cfg.repo_id
                elif source_cfg.file_path:
                    source_path = source_cfg.file_path
                elif source_cfg.table:
                    source_path = source_cfg.table

                # Get source type as string
                source_type = (
                    str(source_cfg.type.value)
                    if hasattr(source_cfg.type, "value")
                    else str(source_cfg.type)
                )
                source_types.add(source_type)

                collector.add_dataset_source(
                    alias=alias,
                    source_type=source_type,
                    source_path=source_path,
                    dataset_version=metadata.get("version"),
                    dataset_hash=metadata.get("hash"),
                    join_type=source_cfg.join_type,
                )

            # Set top-level dataset metadata for multi-source scenario
            # Use clear "multi-source" indicator with human-readable summary
            len(self._source_configs_by_alias)
            sorted_types = sorted(source_types)  # Consistent ordering
            ", ".join(sorted_types)

            collector.set_dataset_metadata(
                source_type="multi-source",
                source_path="multi-source",
                start_index=getattr(args, "start_index", 0),
            )

    @staticmethod
    def _configure_resume_behavior(args: Any, config_resumable: bool) -> bool:
        """
        Configure resumable behavior based on command-line arguments and configuration

        Args:
            args: Command-line arguments
            config_resumable: Whether resumable is enabled in the configuration

        Returns:
            bool: Whether resumable execution is enabled
        """
        if hasattr(args, "resume") and args.resume is not None:
            resumable = (
                args.resume if isinstance(args.resume, bool) else ast.literal_eval(str(args.resume))
            )
            logger.info(
                f"Resumable execution {'enabled' if resumable else 'disabled'} by command-line argument"
            )
            return resumable
        else:
            if config_resumable:
                logger.info("Resumable execution enabled by configuration")
            return config_resumable

    def _fetch_variable_value(self, value, config):
        """
        It updates direct string value, dictionary or list having value starts with $

        Args:
            value: to be parsed and replace $ path from config
            config: complete config dictionary
        """
        # process a string value if it starts with $, else just return the value
        if isinstance(value, str) and value.startswith("$"):
            json_node_keys = value[1:].split(".")
            json_node = config
            # recursively reach to the leave node and get the value
            for key in json_node_keys:
                index = -1
                # if it has subscript operator, json_node should be an array
                if "[" in key and key.endswith("]"):
                    key, index_str = key.split("[")
                    try:
                        index = int(index_str.rstrip("]"))
                    except ValueError:
                        logger.error(f"Invalid index: {index_str}")
                        raise
                try:
                    json_node = json_node[key]
                except KeyError:
                    logger.error(f"Key '{key}' not found in config path: {value}")
                    raise
                if index >= 0:
                    json_node = json_node[index]
            return json_node
        elif isinstance(value, dict):
            # update each value of the dictionary and return
            return {k: self._fetch_variable_value(v, config) for k, v in value.items()}
        elif isinstance(value, list):
            # update each value of the list
            return [self._fetch_variable_value(v, config) for v in value]
        else:
            # just return the value as it is
            return value

    def _process_static_variables(self, output_config: dict, config: dict) -> dict:
        """
        Process the variable with $, they are the static values from the config(dict path)
        For example: $data_config.source.repo_id
        It should be path from root, it also supports subscript operator for array
        """
        output_map = output_config.get("output_map")
        if output_map is None:
            return output_config
        for k, v in output_map.items():
            value = v.get("value")
            # replace the final value
            if value:
                output_map[k]["value"] = self._fetch_variable_value(value, config)
        return output_config

    def _init_output_generator(self) -> Optional[BaseOutputGenerator]:
        """
        Check if there's an 'output_config' block in the top-level config (graph_config.yaml).
        If present, check if it has 'generator'. If present, try to import & instantiate it.
        Otherwise, return None.

        Returns:
            Optional[BaseOutputGenerator]: The output generator object
        """
        config = self.graph_config.config
        output_config = config.get("output_config", {})
        if not output_config:
            return None
        output_config = self._process_static_variables(output_config, config)

        if "output_map" in output_config and not output_config.get("generator"):
            logger.info("Using default output generator with output_map")
            return BaseOutputGenerator(output_config)

        gen_class_str = output_config.get("generator", "")
        if not gen_class_str:
            return None

        try:
            generator_cls = utils.get_func_from_str(gen_class_str)
            output_generator = cast(BaseOutputGenerator, generator_cls(output_config))
            logger.info(f"Initialized output generator: {gen_class_str}")
            return output_generator
        except Exception as e:
            logger.error(f"Could not initialize output generator '{gen_class_str}': {e}")
            return None

    # Initialize and return the langgraph StateGraph object for the task
    def init_graph(self) -> StateGraph:
        graph_builder = LangGraphBuilder(self.graph_config)
        return cast(StateGraph, graph_builder.build())

    def _process_feilds(self, data, select_columns: Optional[list] = None):
        """
        Iterate through each record and filter fields based on select_columns
        If select_columns is not defined, then return all fields
        Also perform data transformation for unsupported datatype, which fails to write because of serialization error
        Currently supported non-serialized data type: ndarray
        """
        select_columns = select_columns or []
        final_data = []
        filter_column = select_columns is not None and len(select_columns) > 0
        # make sure id column is preserved, if filter_column are defined
        if filter_column and "id" not in select_columns:
            select_columns.append("id")

        for record in data:
            new_record = {}
            for k, v in record.items():
                # skip the fields not in select_columns, when select list is defined
                if filter_column and k not in select_columns:
                    continue
                # convert the value to list if it is numpy array
                if isinstance(v, np.ndarray):
                    v = v.tolist()
                # store the updated key-value
                new_record[k] = v
            # now add into final dataset
            # Allow empty records through when no field filtering is applied
            # (empty records are valid for tasks with no data source that use samplers)
            if len(new_record) > 0 or not filter_column:
                final_data.append(new_record)
        return final_data

    # Initialize and return the dataset for the task
    def init_dataset(
        self,
    ) -> Union[list[dict], datasets.Dataset, datasets.IterableDataset]:
        data_config = self.config.get("data_config", {})

        # Configure output
        self._configure_sink(data_config)

        # Configure and load source data
        data = self._load_source_data(data_config)
        # get select fields if defined
        select_fields = data_config.get("source", {}).get("fields", [])
        # select only required fields
        data = self._process_feilds(data, select_fields)

        # Infer features for IterableDataset if they're missing/unknown
        if isinstance(data, datasets.IterableDataset):
            features = self._get_or_infer_features(data)
            return self.assign_ids(data, features=features)
        else:
            return self.assign_ids(data)

    def _get_or_infer_features(self, dataset: datasets.IterableDataset) -> datasets.Features:
        """Get existing features or infer them if missing/unknown."""
        features = dataset.features or datasets.Features()

        # Only infer if features are empty (Unknown case)
        if len(features) == 0:
            logger.info("Features are Unknown/empty, inferring from sample...")
            features = self._infer_features_from_sample(dataset)
        else:
            logger.info("Using existing dataset features")
            features = features.copy()

        return features

    def _infer_features_from_sample(self, dataset: datasets.IterableDataset) -> datasets.Features:
        """Infer dataset features by sampling the first record - only called when needed."""
        features = datasets.Features()

        try:
            sample_record = next(iter(dataset.take(1)))
            for field_name, field_value in sample_record.items():
                features[field_name] = self._infer_field_type(field_name, field_value)
        except (StopIteration, Exception) as e:
            logger.warning(f"Could not sample a record to determine features: {e}")

        return features

    def _infer_field_type(self, field_name: str, field_value: Any) -> datasets.Features.type:
        """Infer the appropriate datasets feature type for a field value."""
        if isinstance(field_value, str):
            return datasets.Value("string")
        elif isinstance(field_value, bool):
            return datasets.Value("bool")
        elif isinstance(field_value, int):
            return datasets.Value("int32")
        elif isinstance(field_value, float):
            return datasets.Value("float32")
        elif isinstance(field_value, Image.Image):
            return datasets.Image()
        elif isinstance(field_value, dict):
            # Check for special cases like Audio, Image, etc.
            if isinstance(field_value.get("array"), np.ndarray) and isinstance(
                field_value.get("sampling_rate"), (int, float)
            ):
                # HuggingFace audio dict
                return datasets.Audio()
            elif (
                "path" in field_value
                and "bytes" in field_value
                and ("audio" in field_name.lower() or "image" in field_name.lower())
            ):
                return datasets.Audio() if "audio" in field_name.lower() else datasets.Image()
            elif field_value:
                return datasets.Features(
                    {
                        key: self._infer_field_type(f"{field_name}.{key}", val)
                        for key, val in field_value.items()
                    }
                )
            else:
                # Empty dictionary
                return datasets.Features({})
        elif isinstance(field_value, (list, tuple)):
            if field_value:  # Non-empty list
                first_item = field_value[0]
                if isinstance(first_item, dict):
                    # List of dictionaries
                    return datasets.Sequence(
                        datasets.Features(
                            {
                                key: self._infer_field_type(f"{field_name}[].{key}", value)
                                for key, value in first_item.items()
                            }
                        )
                    )
                elif isinstance(first_item, (list, tuple)):
                    # Potential multidimensional array
                    array = np.array(field_value)
                    shape = array.shape
                    dtype = str(array.dtype)
                    if array.ndim == 2:
                        return datasets.Array2D(shape=shape, dtype=dtype)
                    elif array.ndim == 3:
                        return datasets.Array3D(shape=shape, dtype=dtype)
                    elif array.ndim == 4:
                        return datasets.Array4D(shape=shape, dtype=dtype)
                    elif array.ndim == 5:
                        return datasets.Array5D(shape=shape, dtype=dtype)
                    else:
                        return datasets.Sequence(
                            self._infer_field_type(f"{field_name}[]", first_item)
                        )
                else:
                    # List of primitives
                    return datasets.Sequence(self._infer_field_type(f"{field_name}[]", first_item))
            else:
                # Empty list - default to sequence of strings
                return datasets.Sequence(datasets.Value("string"))
        elif hasattr(field_value, "item") and isinstance(
            field_value.item(), (int, float, bool, str)
        ):
            return self._infer_field_type(field_name, field_value.item())
        elif field_value is None:
            return datasets.Value("null")
        else:
            logger.warning(
                f"Unsupported field type {type(field_value)} for field {field_name}. Defaulting to string."
            )
            return datasets.Value("string")

    def _configure_sink(self, data_config: dict) -> None:
        """Configure the sink settings from data config"""
        sink_config = data_config.get("sink")
        if not sink_config:
            # No sink configured - this is valid (sink is optional)
            return
        if isinstance(sink_config, dict):
            self.output_config = OutputConfig.from_dict(sink_config)
        elif isinstance(sink_config, list):
            self.output_config = []
            for cfg in sink_config:
                self.output_config.append(OutputConfig.from_dict(cfg))
        else:
            logger.error(
                "Sink data configuration error. It can only be dict or list if multiple sink."
            )

    # validation if list of data config set in source or sink
    # rule 1: alias and join_type is mandatory if source/sink config is a list
    # rule 2: all dataset should be vstack join type, vstack cant mix with other horizontal concat
    def validate_data_config(self, source_config: list, sink_config: list) -> bool:
        alias = set()
        join_type_list = set()
        is_vstack = False
        if isinstance(source_config, list):
            for source_config_obj in source_config:
                if not source_config_obj.get(
                    constants.DATASET_JOIN_TYPE
                ) or not source_config_obj.get(constants.DATASET_ALIAS):
                    # if the source data config is a list, it should have join_type and alias
                    logger.error("One of the source data config has missing alias or join_type.")
                    return False
                else:
                    alias.add(source_config_obj[constants.DATASET_ALIAS])
                    join_type_list.add(source_config_obj[constants.DATASET_JOIN_TYPE])
                    is_vstack = (
                        (
                            source_config_obj[constants.DATASET_JOIN_TYPE]
                            == constants.JOIN_TYPE_VSTACK
                        )
                        if is_vstack is False
                        else is_vstack
                    )
            if len(alias) != len(source_config):
                logger.error("Duplicate alias in source data config list.")

        # if vstack, all dataset should be set with vstack
        # alias name will not be used for column rename in this case
        if is_vstack and len(join_type_list) > 1:
            logger.error(
                "All dataset must set with vstack or none should have join_type as vstack."
            )
            return False

        alias = set()
        if isinstance(sink_config, list):
            for sink_config_obj in sink_config:
                if not sink_config_obj.get(constants.DATASET_ALIAS):
                    # if the sink data config is a list, it should have alias name
                    logger.error("One of the sink data config has missing alias.")
                    return False
                else:
                    alias.add(sink_config_obj[constants.DATASET_ALIAS])
            if len(alias) != len(sink_config):
                logger.error("Duplicate alias in sink data config list.")
        return True

    # Rename columns with alias prefix
    def _rename_dataframe(self, df: pd.DataFrame, alias: str) -> pd.DataFrame:
        column_names = list(df.columns)
        # check if anyone column has alias prefix, skip it
        for column_name in column_names:
            if column_name.startswith(alias + constants.ALIAS_JOINER):
                return df

        column_rename_map = {c: constants.ALIAS_JOINER.join([alias, c]) for c in list(df.columns)}
        df = df.rename(columns=column_rename_map)
        return df

    # merge dataframes horizontally with repeated secondary rows sequentially if secondary is small
    # if secondary is large, trim to max length of primary and merge
    # primary: a columns, secondary: b columns, merged: a+b columns
    def _repeat_to_merge_sequentially(
        self, primary_df: pd.DataFrame, secondary_df: pd.DataFrame
    ) -> pd.DataFrame:
        # primary: [1,2,3,4,5] secondary: [a,b] merged[[1,a], [2,b], [3,a], [4,b],[5,a]]
        # primary: [1,2,3] secondary: [a,b,c,d,e] merged[[1,a], [2,b], [3,c]]
        primary_length = len(primary_df)
        secondary_length = len(secondary_df)
        repeats = (primary_length // secondary_length) + 1
        # repeat the dataset till max length(primary dataset)
        df_repeated = pd.concat([secondary_df] * repeats, ignore_index=True).iloc[:primary_length]
        # now both dataset are same length, merge and return
        return pd.concat([primary_df, df_repeated], axis=1)

    # merge the primary and secondary dataframe horizontally by randomlly picking one and adding into primary
    # primary : M rows(a columns), secondary: N rows(b columns), merged: M rows(a+b columns)
    def _shuffle_and_extend(
        self, primary_df: pd.DataFrame, secondary_df: pd.DataFrame
    ) -> pd.DataFrame:
        max_len = len(primary_df)
        # Shuffle the secondary dataframe
        shuffled_secondary = secondary_df.sample(frac=1).reset_index(drop=True)
        # If already at or above max length, just return the truncated shuffled df
        if len(shuffled_secondary) >= max_len:
            final_secondary = shuffled_secondary.iloc[:max_len].reset_index(drop=True)
        else:
            # Number of additional rows needed
            needed = max_len - len(shuffled_secondary)
            # Sample duplicate rows randomly (with replacement)
            extra_rows = shuffled_secondary.sample(needed, replace=True).reset_index(drop=True)
            # Concatenate original + duplicates to make is same length as primary dataset
            final_secondary = pd.concat([shuffled_secondary, extra_rows], ignore_index=True)

        # now both dataset are same length, merge and return
        return cast(pd.DataFrame, pd.concat([primary_df, final_secondary], axis=1))

    def _load_source_data(
        self, data_config: dict
    ) -> Union[list[dict], datasets.Dataset, datasets.IterableDataset]:
        """Load data from the configured source"""
        source_config = data_config.get("source")
        if not source_config:
            logger.info("No data source configured. Generating empty dataset with IDs.")
            return self._generate_empty_dataset()

        full_data: list[dict[str, Any]] = []
        if isinstance(source_config, dict):
            # if single dataset configured as dict - existing flow
            source_config_obj = DataSourceConfig.from_dict(source_config)
            # Store source config for metadata collection
            self.source_config = source_config_obj
            reader = self._get_data_reader(source_config_obj)
            full_data = self._read_data(reader, source_config_obj)

            # Capture dataset metadata from reader (which stores it before conversion)
            self._capture_dataset_metadata(full_data, reader)

            # Apply transformations to the dataset
            full_data = self.apply_transforms(source_config_obj, full_data)
        elif isinstance(source_config, list):
            # if multiple dataset configured as list
            dataset_list: list[dict[str, Any]] = []
            primary_df: Optional[pd.DataFrame] = None
            primary_config = None
            # if multiple dataset, verify if join_type and alias is defined in each config(@source and @sink)
            if isinstance(source_config, list):
                sink_config = data_config.get("sink", [])
                if not self.validate_data_config(source_config, sink_config if sink_config else []):
                    logger.error("Invalid source or sink config.")
                    return []

            # Read primary and secondary dataset into dataframes
            is_vstack = False
            for conf in source_config:
                join_type = conf.get(constants.DATASET_JOIN_TYPE)
                alias = conf.get(constants.DATASET_ALIAS)
                conf_obj = DataSourceConfig.from_dict(conf)
                reader = self._get_data_reader(conf_obj)
                # store if join type is vstack(all should be vstack, so checking last element only)
                is_vstack = join_type == constants.JOIN_TYPE_VSTACK
                if join_type == constants.JOIN_TYPE_PRIMARY:
                    primary_config = conf
                    # read the dataset
                    primary_dataset = self._read_data(reader, conf_obj)
                    # Capture metadata for this dataset keyed by alias
                    self._capture_dataset_metadata_for_alias(
                        primary_dataset, reader, alias, conf_obj
                    )
                    # Apply transformations to the dataset
                    primary_dataset = self.apply_transforms(conf_obj, primary_dataset)
                    # convert to dataframe
                    primary_df = pd.DataFrame(primary_dataset)
                    # add alias prefix in the column name(join_type cant be vstack if it is set to primary)
                    primary_df = self._rename_dataframe(primary_df, alias)
                else:
                    # read the dataset
                    sec_dataset = self._read_data(reader, conf_obj)
                    # Capture metadata for this dataset keyed by alias
                    self._capture_dataset_metadata_for_alias(sec_dataset, reader, alias, conf_obj)
                    # Apply transformations to the dataset
                    sec_dataset = self.apply_transforms(conf_obj, sec_dataset)
                    # convert to dataframe
                    sec_df = pd.DataFrame(sec_dataset)
                    # add alias prefix in the column name (avoid column rename for join_type==vstack)
                    sec_df = self._rename_dataframe(sec_df, alias) if is_vstack is False else sec_df
                    # store the dataframe in to the list
                    dataset_list.append({"conf": conf, "dataset": sec_df})

            # if join type is vstack
            if len(dataset_list) > 0 and is_vstack:
                logger.info("All datasets are vertically stacking.")
                # fetch all dataframes
                all_df = [ds.get("dataset") for ds in dataset_list]
                vmerged_df = pd.concat(all_df, axis=0, join="inner")
                # now convert dataframe to list of dict (full_data)
                full_data = vmerged_df.to_dict(orient="records")
            elif primary_df is None or len(primary_dataset) == 0:
                logger.error("Primary dataset is not defined for horizontal stack/concatenation.")
            else:
                # merge datasets into primary
                for ds in dataset_list:
                    ds_conf: dict[str, Any] = ds.get("conf", {})
                    join_type = ds_conf.get(constants.DATASET_JOIN_TYPE)
                    current_df = ds.get("dataset")
                    if current_df is None or not isinstance(current_df, pd.DataFrame):
                        logger.error("Dataset is missing or not a dataframe")
                        continue
                    if join_type == constants.JOIN_TYPE_COLUMN:
                        sec_alias_name = ds_conf.get(constants.DATASET_ALIAS)
                        pri_alias_name = (
                            primary_config.get(constants.DATASET_ALIAS) if primary_config else None
                        )
                        # convert the keys with alias prefix (table1.column1)
                        primary_column = constants.ALIAS_JOINER.join(
                            [pri_alias_name or "", ds_conf.get(constants.PRIMARY_KEY, "")]
                        )
                        join_column = constants.ALIAS_JOINER.join(
                            [sec_alias_name or "", ds_conf.get(constants.JOIN_KEY, "")]
                        )
                        # where_clause = ds.get("conf").get("where_clause")
                        primary_df = pd.merge(
                            primary_df,
                            cast(pd.DataFrame, current_df),
                            left_on=primary_column,
                            right_on=join_column,
                            how="left",
                        )
                    elif join_type == constants.JOIN_TYPE_SEQUENTIAL:
                        primary_df = self._repeat_to_merge_sequentially(
                            primary_df, cast(pd.DataFrame, current_df)
                        )
                    elif join_type == constants.JOIN_TYPE_CROSS:
                        primary_df = primary_df.merge(cast(pd.DataFrame, current_df), how="cross")
                    elif join_type == constants.JOIN_TYPE_RANDOM:
                        primary_df = self._shuffle_and_extend(
                            primary_df, cast(pd.DataFrame, current_df)
                        )
                    else:
                        logger.error("Not implemented join_type")

                # now convert dataframe to list of dict (full_data)
                full_data = cast(list[dict[str, Any]], primary_df.to_dict(orient="records"))
        else:
            logger.error("Unsupported source config type.")

        if isinstance(full_data, list):
            assert len(full_data) > 0, "No data found in the dataset"
        elif not isinstance(full_data, datasets.IterableDataset):
            raise ValueError(
                f"Unsupported data format: {type(full_data)}. Expected list or IterableDataset."
            )

        return full_data

    def _capture_dataset_metadata(self, dataset: Any, reader: Any) -> None:
        """Capture dataset version and hash before transformations."""
        try:
            # First try to get from reader (HuggingFaceHandler stores it before conversion)
            if hasattr(reader, "dataset_version") and hasattr(reader, "dataset_hash"):
                self._dataset_version = reader.dataset_version
                self._dataset_hash = reader.dataset_hash
                logger.debug(
                    f"Captured dataset metadata from reader: version={self._dataset_version}, hash={self._dataset_hash}"
                )
                return

            # Fallback: try to extract from dataset object directly
            import datasets

            if isinstance(dataset, (datasets.Dataset, datasets.IterableDataset)):
                self._dataset_version = None
                self._dataset_hash = None

                # Try to get version info
                if hasattr(dataset, "info") and dataset.info:
                    version_obj = getattr(dataset.info, "version", None)
                    if version_obj:
                        self._dataset_version = str(version_obj)

                # Try to get fingerprint/hash
                if hasattr(dataset, "_fingerprint"):
                    self._dataset_hash = dataset._fingerprint
                elif hasattr(dataset, "n_shards"):
                    self._dataset_hash = f"iterable_{dataset.n_shards}_shards"

                logger.debug(
                    f"Captured dataset metadata from dataset: version={self._dataset_version}, hash={self._dataset_hash}"
                )
        except Exception as e:
            logger.debug(f"Could not capture dataset metadata: {e}")

    def _capture_dataset_metadata_for_alias(
        self, dataset: Any, reader: Any, alias: str, source_config: DataSourceConfig
    ) -> None:
        """Capture dataset version and hash for a specific alias in multi-dataset scenarios.

        Stores metadata locally for later registration with MetadataCollector in
        _init_metadata_collector (after the collector is reset).

        Args:
            dataset: The loaded dataset
            reader: The data reader used to load the dataset
            alias: The alias identifier for this dataset
            source_config: The source configuration for this dataset
        """
        try:
            dataset_version: Optional[str] = None
            dataset_hash: Optional[str] = None

            # First try to get from reader (HuggingFaceHandler stores it before conversion)
            if hasattr(reader, "dataset_version") and hasattr(reader, "dataset_hash"):
                dataset_version = reader.dataset_version
                dataset_hash = reader.dataset_hash
            else:
                # Fallback: try to extract from dataset object directly
                if isinstance(dataset, (datasets.Dataset, datasets.IterableDataset)):
                    # Try to get version info
                    if hasattr(dataset, "info") and dataset.info:
                        version_obj = getattr(dataset.info, "version", None)
                        if version_obj:
                            dataset_version = str(version_obj)

                    # Try to get fingerprint/hash
                    if hasattr(dataset, "_fingerprint"):
                        dataset_hash = dataset._fingerprint
                    elif hasattr(dataset, "n_shards"):
                        dataset_hash = f"iterable_{dataset.n_shards}_shards"

            # Store in instance variables for:
            # 1. Registration with MetadataCollector in _init_metadata_collector (after reset)
            # 2. Sink upload source config mapping
            self._dataset_metadata_by_alias[alias] = {
                "version": dataset_version,
                "hash": dataset_hash,
            }
            self._source_configs_by_alias[alias] = source_config

            logger.debug(
                f"Captured metadata for alias '{alias}': version={dataset_version}, hash={dataset_hash}"
            )
        except Exception as e:
            logger.debug(f"Could not capture dataset metadata for alias '{alias}': {e}")

    def _generate_empty_dataset(self) -> list[dict]:
        """Generate empty dataset with specified number of records"""
        num_records = self.args.num_records
        logger.info(f"Generating {num_records} empty records")
        return [{} for _ in range(num_records)]

    def _get_data_reader(
        self, source_config: DataSourceConfig
    ) -> Union[HuggingFaceHandler, FileHandler, ServiceNowHandler]:
        """Get appropriate data reader based on source type"""
        if source_config is None:
            raise ValueError("source_config must be set to get a data reader")

        if source_config.type == DataSourceType.HUGGINGFACE:
            return HuggingFaceHandler(source_config)
        elif source_config.type == DataSourceType.DISK_FILE:
            return FileHandler(source_config)
        elif source_config.type == DataSourceType.SERVICENOW:
            return ServiceNowHandler(source_config)
        else:
            raise ValueError(f"Unsupported data source type: {source_config.type}")

    def _read_data(
        self, reader, source_config
    ) -> Union[list[dict], datasets.Dataset, datasets.IterableDataset]:
        """Read data from the configured source using the provided reader"""
        try:
            if source_config is None:
                raise ValueError("source_config must be set to read data")

            if source_config.shard is None:
                return reader.read()
            else:
                full_data = []
                shard_files = reader.get_files()
                for shard_path in shard_files:
                    data = reader.read(shard_path)
                    full_data.extend(data)
                return full_data
        except Exception as e:
            logger.error(f"Error reading data: {str(e)}")
            raise RuntimeError(f"Failed to read data: {str(e)}") from e

    def apply_transforms(
        self,
        source_config: DataSourceConfig,
        data: Union[list[dict[str, Any]], datasets.IterableDataset],
    ) -> Union[list[dict[str, Any]], datasets.IterableDataset]:
        """
        Apply each transformation in source_config.transformations
        (the default_transformations from config are applied first)
          - If `data` is a list of dicts, run transform(list, params) in‐memory.
          - If `data` is an IterableDataset, apply each transform one record at a time.
        """
        config = utils.load_yaml_file(constants.SYGRA_CONFIG)
        default_cfgs = (config or {}).get("default_transformations", [])
        custom_cfgs = [cfg.model_dump() for cfg in (source_config.transformations or [])]
        all_transforms = default_cfgs + custom_cfgs

        if not all_transforms:
            return data

        logger.info(
            f"Applying {len(all_transforms)} transforms in order (Default: {len(default_cfgs)}, Custom: {len(custom_cfgs)})"
        )

        if isinstance(data, list):
            return self._apply_transform_sequence(all_transforms, data)

        elif isinstance(data, datasets.IterableDataset):
            return self._apply_transforms_iterable(all_transforms, data)

        else:
            raise TypeError(f"Unsupported dataset type: {type(data)}")

    def _get_transform_instances(
        self, transform_cfgs: list[dict[str, Any]]
    ) -> list[tuple[Any, dict[str, Any]]]:
        """
        Get instances of transformation functions based on the provided configuration.
        """
        instances = []
        for cfg in transform_cfgs:
            if "transform" not in cfg:
                raise ValueError(f"Missing 'transform' key in transformation config: {cfg}")
            transform_fn = utils.get_func_from_str(cfg["transform"])()
            params = cfg.get("params", {})
            instances.append((transform_fn, params))
        return instances

    def _apply_transform_sequence(
        self, transform_cfgs: list[dict[str, Any]], data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Apply a sequence of transformations to a list of records.
        """
        transform_instances = self._get_transform_instances(transform_cfgs)
        data_input = copy.deepcopy(data)
        for instance, params in transform_instances:
            logger.info(f"Applying transform: {instance.name}")
            data_input = instance.transform(data_input, params)
        return data_input

    def _apply_transforms_iterable(
        self, transform_cfgs: list[dict[str, Any]], data: datasets.IterableDataset
    ) -> datasets.IterableDataset:
        """
        Apply a sequence of transformations to an IterableDataset.
        """
        transform_instances = self._get_transform_instances(transform_cfgs)

        def _apply_transform_record(record: dict[str, Any]) -> dict[str, Any]:
            for instance, params in transform_instances:
                record = instance.transform([record], params)[0]  # Apply transform to single record
            return record

        return data.map(_apply_transform_record)

    def add_id(self, record: dict[str, Any]) -> dict[str, Any]:
        """
        Add an "id" to the record. If the id_column is specified, use that value.
        If the id_column is not specified and the record does not have an "id", generate a hash of the record.

        Args:
            record: The input record (dict) to which the id will be added.
        Returns:
            dict: The record with the added "id" field.
        """

        if self.id_column:
            id_column = self.id_column
            if id_column in record and record[id_column] is not None:
                record["id"] = record[id_column]
            return record
        elif "id" in record and record["id"] is not None:
            return record
        else:
            record_for_hash = record.copy()
            record_str = json.dumps(record_for_hash, sort_keys=True)
            content_hash = hashlib.sha256(record_str.encode()).hexdigest()
            record["id"] = content_hash
            return record

    # Function to assign "id" to every record of full_data
    def assign_ids(self, full_data, features: Optional[datasets.Features] = None):
        """Assign unique IDs to dataset records. Features should be inferred beforehand."""
        if isinstance(full_data, datasets.IterableDataset):
            if features is None:
                raise ValueError("Features must be provided for IterableDataset")

            if "id" not in features:
                features = features.copy()
                features["id"] = datasets.Value("string")

            return full_data.map(self.add_id, features=features)

        # Handle list/dict data
        if full_data and full_data[0].get("id"):
            return full_data

        for i in range(len(full_data)):
            record = full_data[i]
            if isinstance(record, dict):
                full_data[i] = self.add_id(record)
            elif isinstance(record, list):
                for j in range(len(record)):
                    if isinstance(record[j], dict):
                        record[j] = self.add_id(record[j])
            else:
                raise ValueError(f"Unsupported data format: {type(record)}. Expected dict or list.")

        return full_data

    # Mapping function to convert input record to the format expected by the graph
    def input_record_generator(self, record: dict[str, Any]) -> dict[str, Any]:
        return record

    # Mapping function to convert the output state of the graph to the output results format
    def output_record_generator(self, state: SygraState) -> SygraState:
        """
        Convert the output state of the graph to the output results format.

        Args:
            state: SygraState object

        Returns:
            SygraState: The output state
        """
        if self.output_generator:
            return cast(SygraState, self.output_generator.generate(state))
        else:
            return state

    def execute(self, execution_callbacks=None):
        """
        Execute the task workflow.

        Args:
            execution_callbacks: Optional ExecutionCallbacks for real-time node tracking.
        """
        graph = self.init_graph()
        compiled_graph = graph.compile()
        logger.info("Graph compiled successfully")
        logger.info("\n" + compiled_graph.get_graph().draw_ascii())

        # Create timestamp for output file
        run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        ts_suffix = "" if not self.args.output_with_ts else "_" + run_timestamp

        # Update metadata collector with the run timestamp so metadata filename matches output filename
        if self.args.output_with_ts:
            collector = get_metadata_collector()
            collector.execution_context.run_timestamp = run_timestamp

        num_records_total = self.args.num_records
        if isinstance(self.dataset, list):
            num_records_total = (
                min(self.args.num_records, len(self.dataset))
                if self.args.num_records
                else len(self.dataset)
            )

        metadata_path = utils.get_file_in_task_dir(self.args.task, "metadata.json")

        existing_output_file = None

        if self.resumable and os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                    if metadata.get("task_name") == self.task_name:
                        existing_output_file = metadata.get("output_file")
            except Exception as e:
                logger.warning(f"Error reading metadata file: {e}")

        if self.resumable and existing_output_file and os.path.exists(existing_output_file):
            out_file = existing_output_file
            out_file_type = os.path.splitext(existing_output_file)[1].lstrip(".")
            logger.info(f"Resuming with existing output file: {out_file}")
        else:
            # output file type is jsonl if num_records_total > 25k
            # since the output file will also be big and its efficient to append to jsonl
            out_file_type = "jsonl" if num_records_total > 25000 else "json"
            run_name_prefix = f"{self.args.run_name}_" if self.args.run_name else ""
            if self.output_dir:
                if not os.path.exists(self.output_dir):
                    os.makedirs(self.output_dir)
                out_file = self.output_dir + f"/{run_name_prefix}output{ts_suffix}.{out_file_type}"
            else:
                out_file = utils.get_file_in_task_dir(
                    self.args.task,
                    f"{run_name_prefix}output{ts_suffix}.{out_file_type}",
                )
        if not self.resumable and os.path.exists(out_file):
            logger.info(f"Deleting existing output file since resumable=False: {out_file}")
            utils.delete_file(out_file)

            if os.path.exists(metadata_path):
                logger.info(f"Removing metadata file: {metadata_path}")
                utils.delete_file(metadata_path)

        if self.args.start_index != 0:
            logger.info(
                f"Creating a subset of the dataset starting from index {self.args.start_index}"
            )
            if isinstance(self.dataset, list):
                self.dataset = self.dataset[self.args.start_index :]
            else:
                self.dataset = self.dataset.skip(self.args.start_index)

        if self.args.num_records:
            logger.info(f"Setting target to process {self.args.num_records} records")
            if isinstance(self.dataset, list):
                self.dataset = self.dataset[: self.args.num_records]

        dataset_processor = DatasetProcessor(
            self.dataset,
            compiled_graph,
            self.graph_config,
            out_file,
            num_records_total=num_records_total,
            start_index=self.args.start_index,
            batch_size=self.args.batch_size,
            checkpoint_interval=self.args.checkpoint_interval,
            debug=self.args.debug,
            input_record_generator=self.input_record_generator,
            output_record_generator=self.output_record_generator,
            resumable=self.resumable,
            task_name=self.task_name,
            execution_callbacks=execution_callbacks,
        )
        dataset_processor.process_and_store_results()

        if "data_quality" in self.graph_config.config.get("output_config", {}):
            logger.info("Performing data quality checks")
            data_quality_processor = DataQuality(
                self.graph_config.config["output_config"].get("data_quality", {})
            )
            data_quality_processor.process(input_path=out_file, output_path=out_file)

        # Write to sink if configured
        if self.output_config and dataset_processor.is_valid_schema:
            try:
                with open(out_file, "r") as f:
                    data = (
                        json.load(f)
                        if out_file_type == "json"
                        else [json.loads(line) for line in f]
                    )
                # Ensure data is always a list for _split_data_per_alias
                if isinstance(data, dict):
                    data = [data]
            except Exception as e:
                logger.error(f"Error reading generated dataset. failed to write into sink: {e}")
                data = []

            # split the data if it has keys with multi dataset format dataset alias->key
            # store per dataset with key as "alias" name, remaning direct fields can be in "__others__"
            splitted_dataset = self._split_data_per_alias(data)

            # now we have multiple dataset under various alias as key including __others__ (default)
            if isinstance(self.output_config, list):
                # multiple output configs - iterate through each
                for output_cfg in self.output_config:
                    # if alias not defined, it will TRY to push default columns
                    alias = output_cfg.alias if output_cfg.alias else constants.DEFAULT_ALIAS
                    if alias not in splitted_dataset:
                        logger.warning(f"No data found for alias '{alias}', skipping sink upload.")
                        continue
                    # Get corresponding source config by alias for proper schema inference
                    corresponding_source_config = self._source_configs_by_alias.get(alias)
                    self._upload_into_sink(
                        output_cfg, splitted_dataset[alias], corresponding_source_config
                    )
                    logger.info(f"Successfully uploaded {alias} to sink.")
            else:
                # single output config
                default_data = splitted_dataset.get(constants.DEFAULT_ALIAS, [])
                if default_data:
                    self._upload_into_sink(
                        self.output_config,
                        default_data,
                        self.source_config,
                    )
                else:
                    logger.warning("No data found for default alias, skipping sink upload.")

        if dataset_processor.resume_manager:
            dataset_processor.resume_manager.force_save_state(is_final=True)

        self._save_metadata(dataset_processor)

    def _split_data_per_alias(self, data: list[dict]) -> dict[str, list[dict]]:
        """Split data into separate datasets based on column alias prefixes.

        Columns with alias prefix (e.g., 'table1->column1') are grouped by alias.
        Columns without prefix go to the default alias '__others__'.

        Args:
            data: List of records with potentially aliased column names

        Returns:
            Dictionary mapping alias names to their respective record lists
        """
        splitted_dataset: dict[str, list[dict[str, Any]]] = {}
        for row in data:
            # split the row into multiple dict with key as alias
            splitted_row: dict[str, dict[str, Any]] = {}
            for col, val in row.items():
                if constants.ALIAS_JOINER in col:
                    alias = col.split(constants.ALIAS_JOINER)[0]
                    actual_col = col.split(constants.ALIAS_JOINER)[1]
                else:
                    alias = constants.DEFAULT_ALIAS
                    actual_col = col
                if alias not in splitted_row:
                    splitted_row[alias] = {}
                splitted_row[alias][actual_col] = val

            # insert each split into different dataset
            for alias in splitted_row:
                # create empty dataset if does not exists for this alias
                if alias not in splitted_dataset:
                    splitted_dataset[alias] = []
                # insert the splitted row
                splitted_dataset[alias].append(splitted_row[alias])
        return splitted_dataset

    def _upload_into_sink(
        self,
        output_config: OutputConfig,
        data: list[dict],
        source_config: Optional[DataSourceConfig] = None,
    ) -> None:
        try:
            if output_config.type == OutputType.HUGGINGFACE:
                HuggingFaceHandler(
                    source_config=source_config,
                    output_config=output_config,
                ).write(data)
            elif output_config.type == OutputType.SERVICENOW:
                ServiceNowHandler(
                    source_config=None,
                    output_config=output_config,
                ).write(data)
            else:
                if output_config.file_path is None:
                    raise ValueError("file_path must be set for output_config")
                FileHandler(
                    source_config=source_config,
                    output_config=output_config,
                ).write(data, path=output_config.file_path)
            type_value = output_config.type.value if output_config.type is not None else "none"
            logger.info(
                f"Successfully wrote output to sink: {type_value}, {output_config.model_dump()}"
            )
        except Exception as e:
            logger.error(f"Error writing to sink: {e}")

    def _save_metadata(self, dataset_processor=None):
        """Finalize and save execution metadata."""
        try:
            from sygra.metadata.metadata_collector import get_metadata_collector

            collector = get_metadata_collector()

            # Update dataset metadata with actual processed count
            if dataset_processor:
                collector.dataset_metadata.num_records_processed = (
                    dataset_processor.num_records_processed + dataset_processor.failed_records
                )

            collector.finalize_execution()
            metadata_path = collector.save_metadata()
            logger.info(f"Run metadata saved to: {metadata_path}")
        except Exception as e:
            logger.warning(f"Failed to save metadata: {e}")


class DefaultTaskExecutor(BaseTaskExecutor):
    """
    A universal executor for tasks that only need the YAML config
    and do NOT define their own TaskExecutor class.
    If the user doesn't define sygra.tasks.<task_name>.task_executor.TaskExecutor,
    we fall back to this class by default.
    """

    def __init__(self, args, graph_config_dict=None):
        super().__init__(args, graph_config_dict)
        logger.info("Using DefaultTaskExecutor for task: %s", self.task_name)
