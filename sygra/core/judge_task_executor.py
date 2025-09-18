from argparse import Namespace

from sygra.core.base_task_executor import BaseTaskExecutor
from sygra.logger.logger_config import logger


class JudgeQualityTaskExecutor(BaseTaskExecutor):
    """
    A task executor for tasks that require a specific task executor.
    This is a placeholder for future task-specific implementations.
    """

    def __init__(self, args: Namespace, data_quality_graph_config):
        super().__init__(args, graph_config_dict=data_quality_graph_config)
        logger.info("Using JudgeQualityTaskExecutor for task: %s", self.task_name)
