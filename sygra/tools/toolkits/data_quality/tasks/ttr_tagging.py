import json
import os
from concurrent.futures import ThreadPoolExecutor

from lexicalrichness import LexicalRichness
from tqdm import tqdm

from sygra.utils import utils


class TTRTaggingTask:
    """
    A task to compute and save Type-Token Ratio (TTR) and MTLD scores for a dataset.

    This task processes input data, computes lexical richness metrics for each document,
    and saves the results to an output file.

    Args:
        input_file (str): Path to the input file (JSON/JSONL) with pretokenized content.
        output_dir (str): Directory to save the output file.
        num_records (int): Number of records in the dataset.
        kwargs (dict): Optional parameters like thread count.
    """

    def __init__(self, input_file: str, output_dir: str, num_records: int, **kwargs: dict):
        self.input_file = input_file
        self.output_dir = output_dir
        self.num_records = num_records
        self.task_params = kwargs
        self.num_threads = kwargs.get("num_threads", 4)

    @staticmethod
    def _compute_ttr(document: str) -> float:
        """
        Computes the Type-Token Ratio (TTR) for a single document.

        Args:
            document (str): The input document.

        Returns:
            float: The TTR score.
        """
        return LexicalRichness(document).ttr

    @staticmethod
    def _compute_mtld(document: str) -> float:
        """
        Computes the Measure of Textual Lexical Diversity (MTLD) for a single document.

        Args:
            document (str): The input document.

        Returns:
            float: The MTLD score.
        """
        return LexicalRichness(document).mtld()

    def execute(self) -> str:
        """
        Executes the TTR tagging task. Computes TTR and MTLD scores for each document
        in the dataset and saves the results to a JSONL file.

        Returns:
            str: Path to the output file.
        """
        # Load input data
        if self.input_file.endswith(".json"):
            data = utils.load_json_file(self.input_file)
        elif self.input_file.endswith(".jsonl"):
            data = utils.load_jsonl_file(self.input_file)
        else:
            raise ValueError("Unsupported input file format.")

        documents = [d["conversation_pretokenized"] for d in data]

        # Compute TTR
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            ttr_scores = list(
                tqdm(
                    executor.map(self._compute_ttr, documents),
                    total=len(documents),
                    desc="Computing TTR",
                )
            )

        # Compute MTLD
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            mtld_scores = list(
                tqdm(
                    executor.map(self._compute_mtld, documents),
                    total=len(documents),
                    desc="Computing MTLD",
                )
            )

        # Add scores to the data
        for i, record in enumerate(data):
            metadata_lexical = {
                "metadata": {
                    "quality_characteristics": {
                        "heuristic_based": {
                            "lexical_richness": {
                                "mtld_score": mtld_scores[i],
                                "ttr_score": ttr_scores[i],
                            }
                        }
                    }
                }
            }
            utils.deep_update(record, metadata_lexical)
        # Save the results
        output_file = os.path.join(self.output_dir, "ttr_tagging_output.jsonl")
        with open(output_file, "w") as f:
            for record in data:
                f.write(f"{json.dumps(record, ensure_ascii=False)}\n")
        return output_file
