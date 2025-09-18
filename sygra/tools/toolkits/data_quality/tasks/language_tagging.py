import os
from concurrent.futures import ThreadPoolExecutor

import fasttext
import numpy as np
import pandas as pd
from huggingface_hub import hf_hub_download
from tqdm import tqdm

from sygra.logger.logger_config import logger
from sygra.utils import constants, dotenv, utils

dotenv.load_dotenv()


class LanguageTaggingTask:
    """
    A task for tagging languages in a dataset using a FastText model.
    Thread-safe alternative to multiprocessing for safe execution in test runners and tool pipelines.
    """

    def __init__(self, input_file: str, output_dir: str, num_records: int, **kwargs: dict):
        self.input_file = input_file
        self.output_dir = output_dir
        self.num_records = num_records
        self.batch_size = kwargs.get("batch_size", 256)
        self.num_threads = kwargs.get("num_threads", 4)

        # Load model once
        self.model_path = hf_hub_download(
            repo_id="julien-c/fasttext-language-id",
            filename="lid.176.ftz",  # using .ftz to save memory
            token=os.environ.get(constants.HF_TOKEN),
        )
        self.model = fasttext.load_model(self.model_path)

    def _predict_batch(self, batch: list) -> list:
        """Predict languages for a batch using the loaded model."""
        cleaned_texts = [text.replace("\n", " ") for text in batch]
        labels, probabilities = self.model.predict(cleaned_texts, k=2)
        return list(zip(labels, probabilities))

    def execute(self) -> str:
        """Run language tagging and save the updated dataset."""
        # --- Load data ---
        if self.input_file.endswith(".json"):
            data = utils.load_json_file(self.input_file)
        elif self.input_file.endswith(".jsonl"):
            data = utils.load_jsonl_file(self.input_file)
        else:
            raise ValueError("Unsupported input file format.")

        df = pd.DataFrame(data)

        if "conversation_pretokenized" not in df.columns:
            raise KeyError("'conversation_pretokenized' column not found in input data.")

        texts = df["conversation_pretokenized"].tolist()
        batches = [texts[i : i + self.batch_size] for i in range(0, len(texts), self.batch_size)]

        # --- Parallel prediction ---
        all_predictions = []
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            results = list(
                tqdm(
                    executor.map(self._predict_batch, batches),
                    total=len(batches),
                    desc="Processing Batches",
                )
            )
            for batch_result in results:
                all_predictions.extend(batch_result)

        # --- Post-process predictions ---
        filtered_langs = []
        for labels, scores in all_predictions:
            filtered = np.array(labels)[np.array(scores) > 0.1]
            filtered = [label.replace("__label__", "") for label in filtered]
            filtered_langs.append(filtered)

        # --- Update dataset safely ---
        metadata_list = []
        for row, langs in zip(df.to_dict("records"), filtered_langs):
            metadata = row.get("metadata", {}) or {}
            metadata["languages"] = langs
            metadata_list.append(metadata)
        df["metadata"] = metadata_list

        # --- Save output ---
        output_path = os.path.join(self.output_dir, "language_tagged.jsonl")
        df.to_json(output_path, orient="records", lines=True)
        logger.info(f"Language-tagged data saved to: {output_path}")
        return output_path
