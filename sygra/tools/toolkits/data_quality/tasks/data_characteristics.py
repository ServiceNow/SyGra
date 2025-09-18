import os

from transformers import AutoTokenizer, PreTrainedTokenizer

from sygra.logger.logger_config import logger
from sygra.utils import constants, utils
from sygra.utils.utils import save_json_file


class DataCharacteristicsTask:
    """
    A task to compute and save data characteristics for a dataset, such as the number of tokens,
    input tokens, target tokens, and conversation turns. It supports models from the Hugging Face,
    and locally stored models
    """

    def __init__(self, input_file, output_dir, num_records, **kwargs):
        """
        Initializes the DataCharacteristicsTask.

        Args:
            input_file (str): Path to the input file containing the dataset.
            output_dir (str): Directory where the output file will be saved.
            num_records (int): Total number of records in the dataset.
            **kwargs: task specific parameters.
        """
        self.input_file = input_file
        self.output_dir = output_dir
        self.num_records = num_records
        self.task_params = kwargs

    def execute(self) -> str:
        """
        Executes the data characteristics task. Computes token-related statistics for each
        conversation in the dataset and saves the results to a JSON file.

        Returns:
            str: Path to the output file containing the computed data characteristics.
        """
        model_path = self.task_params.get("model")
        if not model_path:
            logger.warning("No model provided. Skipping data characteristics check.")
            return self.input_file

        tokenizer = self._set_tokenizer(model_path)

        if self.input_file.endswith(".json"):
            data = utils.load_json_file(self.input_file)
        elif self.input_file.endswith(".jsonl"):
            data = utils.load_jsonl_file(self.input_file)
        else:
            raise ValueError("Unsupported file format for input_file.")

        missing_convo_ids = []

        for record in data:
            convo = record.get("conversation")
            if not convo:
                missing_convo_ids.append(record.get("id", "unknown_id"))
                continue

            tokens = 0
            for turn in convo:
                content = turn.get("content", "")
                tokens += len(tokenizer.encode(content, add_special_tokens=False))

            target_tokens = len(
                tokenizer.encode(convo[-1].get("content", ""), add_special_tokens=False)
            )

            record.setdefault("metadata", {})
            record["metadata"]["data_characteristics"] = {
                "num_turns": len(convo) // 2,
                "num_tokens": tokens,
                "num_input_tokens": tokens - target_tokens,
                "num_target_tokens": target_tokens,
            }
            record["input_token_len"] = tokens - target_tokens
            record["target_token_len"] = target_tokens
            record["full_token_len"] = tokens

        if missing_convo_ids:
            to_log = missing_convo_ids[:10]
            logger.warning(
                "Skipped records with missing conversation field. Example IDs: %s%s",
                to_log,
                (
                    f" and {len(missing_convo_ids) - 10} more..."
                    if len(missing_convo_ids) > 10
                    else ""
                ),
            )

        output_file = os.path.join(self.output_dir, "data_characteristics.json")
        save_json_file(output_file, data)
        logger.info("Data characteristics saved to %s", output_file)
        return output_file

    @staticmethod
    def _set_tokenizer(model_path) -> PreTrainedTokenizer:
        return AutoTokenizer.from_pretrained(model_path, token=os.environ.get(constants.HF_TOKEN))
