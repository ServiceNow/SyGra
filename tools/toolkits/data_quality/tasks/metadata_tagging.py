import os
from argparse import Namespace
from grasp.logger.logger_config import logger


class MetadataTaggingTask:
    """
    A task for tagging metadata in a dataset.

    This task processes input data, applies metadata tagging transformations, and executes
    a tagging pipeline using a task executor. The results are saved to an output file.

    Args:
        input_file (str): Path to the input file containing the dataset.
        output_dir (str): Directory where the output files will be saved.
        num_records (int): Total number of records to process.
        **kwargs: Additional task-specific parameters.
    """

    def __init__(self, input_file: str, output_dir: str, num_records: int, **kwargs):
        self.input_file = input_file
        self.output_dir = output_dir
        self.num_records = num_records
        self.task_params = kwargs

    def execute(self) -> str:
        """
        Executes the metadata tagging task.

        Returns:
            str: Path to the output file containing the results.
        """
        from tasks.data_quality.metadata_tagging.task_executor import TaskExecutor

        args = self._construct_args()
        TaskExecutor(args).execute()

        output_file = os.path.join(self.output_dir, "metadata_tagging_output.jsonl")
        if os.path.exists(output_file):
            return output_file
        return os.path.join(self.output_dir, "metadata_tagging_output.json")

    def _construct_args(self) -> Namespace:
        """
        Constructs the arguments required for the task execution.

        Returns:
            Namespace: A namespace object containing task arguments.
        """
        args = {
            "task": "data_quality.metadata_tagging",
            "start_index": 0,
            "num_records": self.num_records,
            "run_name": "metadata_tagging",
            "batch_size": self.task_params.get("batch_size", 25),
            "checkpoint_interval": 100,
            "debug": self.task_params.get("debug", False),
            "output_with_ts": self.task_params.get("output_with_ts", False),
            "output_dir": self.output_dir,
            "run_args": {"input": self.input_file},
            "oasst": False,
            "quality": False,
        }
        return Namespace(**args)
