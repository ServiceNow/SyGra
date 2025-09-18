import argparse
import os
from typing import Any, Dict, List

import torch
from tqdm import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from sygra.logger.logger_config import logger
from sygra.utils import constants, dotenv, utils

dotenv.load_dotenv()


class RewardScoringTask:
    """
    A task for computing reward scores for conversations in a dataset using a pre-trained reward model.
    """

    def __init__(self, input_file: str, output_dir: str, num_records: int = None, **kwargs: dict):
        self.input_file = input_file
        self.output_dir = output_dir
        self.num_records = num_records
        self.batch_size = kwargs.get("batch_size", 2)
        self.model_name = kwargs.get("model_name", "Ray2333/GRM-Llama3.2-3B-rewardmodel-ft")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.max_length = kwargs.get("max_length", 8192)

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

    def _load_model_and_tokenizer(self):
        """Load the reward model and tokenizer."""
        logger.info(f"Loading model and tokenizer from {self.model_name}")

        tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, token=os.environ.get(constants.HF_TOKEN)
        )

        model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        ).to(self.device)

        if torch.cuda.device_count() > 1:
            model = torch.nn.DataParallel(model)
            logger.info(f"Using {torch.cuda.device_count()} GPUs")

        model.eval()
        return model, tokenizer

    def _get_max_token_length(self, data: List[Dict[str, Any]], tokenizer) -> int:
        """Compute the maximum token length for the dataset."""
        max_tokens = 0
        messages = [
            tokenizer.apply_chat_template(sample["conversation"], tokenize=False) for sample in data
        ]

        for i in range(0, len(messages), self.batch_size):
            batch = messages[i : i + self.batch_size]
            tokens = tokenizer(batch, padding=True, truncation=False, return_tensors="pt")
            max_tokens = max(max_tokens, tokens["input_ids"].shape[1])

        return min(int(max_tokens * 1.1), tokenizer.model_max_length)

    def _compute_rewards_batch(self, data: List[Dict[str, Any]], model, tokenizer) -> None:
        """Compute reward scores for each sample in the dataset."""
        current_batch_size = self.batch_size
        total_samples = len(data)
        i = 0

        pbar = tqdm(total=total_samples, desc="Computing Rewards", unit="samples")

        while i < total_samples:
            try:
                batch = data[i : i + current_batch_size]
                messages = [
                    tokenizer.apply_chat_template(sample["conversation"], tokenize=False)
                    for sample in batch
                ]

                tokens = tokenizer(
                    messages,
                    padding="longest",
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )

                input_ids = tokens["input_ids"].to(self.device)
                attention_mask = tokens["attention_mask"].to(self.device)

                with torch.no_grad():
                    outputs = model(input_ids, attention_mask=attention_mask)[0]

                scores = outputs.cpu().tolist()
                for j, score in enumerate(scores):
                    metadata_reward = {
                        "metadata": {
                            "quality_characteristics": {
                                "heuristic_based": {
                                    "reward_score": {
                                        "reward_model": self.model_name,
                                        "score": score,
                                    }
                                }
                            }
                        }
                    }
                    utils.deep_update(batch[j], metadata_reward)

                i += current_batch_size
                pbar.update(len(batch))

                # Save checkpoint periodically
                if i % 1000 == 0 or i >= total_samples:
                    checkpoint_path = os.path.join(self.output_dir, f"reward_score_chkpt_{i}.jsonl")
                    utils.save_jsonl_file(checkpoint_path, data[:i])
                    logger.info(f"Saved checkpoint: {checkpoint_path}")

            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                current_batch_size = max(1, current_batch_size // 2)
                logger.warning(f"CUDA OOM. Reducing batch size to {current_batch_size}")

        pbar.close()

    def execute(self) -> str:
        """Execute the reward scoring task."""
        # Load input data
        if self.input_file.endswith(".json"):
            data = utils.load_json_file(self.input_file)
        elif self.input_file.endswith(".jsonl"):
            data = utils.load_jsonl_file(self.input_file)
        else:
            raise ValueError("Unsupported input file format.")

        # Limit number of records if specified
        if self.num_records:
            data = data[: self.num_records]

        # Skip if dataset contains tools
        if any(sample.get("tools") is not None for sample in data):
            logger.warning("Tools detected in data. Skipping reward scoring task.")
            return None

        # Load model and tokenizer
        model, tokenizer = self._load_model_and_tokenizer()

        # Optional: Compute dynamic token length
        # self.max_length = self._get_max_token_length(data, tokenizer)
        # logger.info(f"Using max token length of {self.max_length}")

        # Compute rewards
        self._compute_rewards_batch(data, model, tokenizer)

        # Save the final output
        output_file = os.path.join(self.output_dir, "reward_scores.jsonl")
        utils.save_jsonl_file(output_file, data)
        logger.info(f"Reward scores saved to {output_file}")
        return output_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute reward scores for a dataset.")
    parser.add_argument("--input_file", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--batch_size", type=int, default=128)
    parser.add_argument("--num_records", type=int, default=None)
    args = parser.parse_args()

    task = RewardScoringTask(
        input_file=args.input_file,
        output_dir=args.output_dir,
        num_records=args.num_records,
        batch_size=args.batch_size,
    )
    task.execute()
