import json
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, cast

import numpy as np

from sygra.logger.logger_config import logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class GraphPostProcessor(ABC):
    """
    Post-processor for whole graph level, not the node level
    Important: do not use graph level post processor for large amount of data generation as it is memory inefficient
    """

    @abstractmethod
    def process(self, data: list, metadata: dict) -> list:
        # implement post processing logic with whole data, return the final data list
        pass


class SemanticDedupPostProcessor(GraphPostProcessor):
    def __init__(
        self,
        field: str = "text",
        similarity_threshold: float = 0.9,
        id_field: str = "id",
        embedding_backend: str = "sentence_transformers",
        embedding_model: str = "all-MiniLM-L6-v2",
        report_filename: Optional[str] = None,
        keep: str = "first",
        max_pairs_in_report: int = 2000,
    ):
        self.field = field
        self.similarity_threshold = float(similarity_threshold)
        self.id_field = id_field
        self.embedding_backend = embedding_backend
        self.embedding_model = embedding_model
        self.report_filename = report_filename
        self.keep = keep
        self.max_pairs_in_report = int(max_pairs_in_report)

        self._embedder: Optional["SentenceTransformer"] = None

    def _get_embedder(self) -> "SentenceTransformer":
        if self.embedding_backend == "sentence_transformers":
            if self._embedder is None:
                from sentence_transformers import SentenceTransformer

                self._embedder = SentenceTransformer(self.embedding_model)
            return self._embedder

        raise ValueError(f"Unsupported embedding_backend: {self.embedding_backend}")

    @staticmethod
    def _cosine_sim_matrix(a: np.ndarray) -> np.ndarray:
        a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-12)
        return cast(np.ndarray, a @ a.T)

    def _get_text(self, item: Any) -> str:
        if not isinstance(item, dict):
            return str(item)
        v = item.get(self.field, "")
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            return "\n".join("" if x is None else str(x) for x in v)
        return str(v)

    def _get_id(self, item: Any, fallback: str) -> str:
        if isinstance(item, dict) and self.id_field in item and item[self.id_field] is not None:
            return str(item[self.id_field])
        return fallback

    def _resolve_report_path(self, output_file: str) -> str:
        if self.report_filename:
            if os.path.isabs(self.report_filename):
                return self.report_filename
            return os.path.join(os.path.dirname(output_file), self.report_filename)

        base = os.path.basename(output_file)
        # output_*.json -> semantic_dedup_report_*.json
        report_base = base.replace("output_", "semantic_dedup_report_", 1)
        return os.path.join(os.path.dirname(output_file), report_base)

    def process(self, data: list, metadata: dict) -> list:
        if not data:
            return data

        output_file = str(metadata.get("output_file", ""))
        logger.info(
            "SemanticDedupPostProcessor: field=%s threshold=%s n=%s",
            self.field,
            self.similarity_threshold,
            len(data),
        )

        texts = [self._get_text(item) for item in data]
        embedder = self._get_embedder()
        embs = embedder.encode(texts, normalize_embeddings=True)
        embs = np.asarray(embs, dtype=np.float32)

        sims = self._cosine_sim_matrix(embs)

        kept: list[int] = []
        dropped: set[int] = set()
        duplicate_pairs: list[dict[str, Any]] = []

        def should_keep(i: int, j: int) -> bool:
            # i and j are indices where sim(i, j) is above threshold and j is candidate duplicate.
            # keep='first' means keep earlier index, drop later one.
            if self.keep == "first":
                return i < j
            if self.keep == "last":
                return i > j
            return i < j

        # Greedy pass: keep an item if it isn't too-similar to a previously kept one
        for i in range(len(data)):
            if i in dropped:
                continue

            kept.append(i)
            # mark duplicates of i
            row = sims[i]
            dup_indices = np.where(row >= self.similarity_threshold)[0]
            for j in dup_indices:
                if j == i:
                    continue
                if j in dropped:
                    continue
                if j in kept:
                    continue

                # Decide drop based on keep strategy
                if should_keep(i, int(j)):
                    dropped.add(int(j))
                    if len(duplicate_pairs) < self.max_pairs_in_report:
                        duplicate_pairs.append(
                            {
                                "kept_index": i,
                                "dropped_index": int(j),
                                "kept_id": self._get_id(data[i], str(i)),
                                "dropped_id": self._get_id(data[int(j)], str(j)),
                                "similarity": float(row[int(j)]),
                            }
                        )

        deduped = [data[i] for i in kept]

        report = {
            "processor": "SemanticDedupPostProcessor",
            "field": self.field,
            "id_field": self.id_field,
            "embedding_backend": self.embedding_backend,
            "embedding_model": self.embedding_model,
            "similarity_threshold": self.similarity_threshold,
            "keep": self.keep,
            "input_count": len(data),
            "output_count": len(deduped),
            "dropped_count": len(data) - len(deduped),
            "pairs_reported": len(duplicate_pairs),
            "max_pairs_in_report": self.max_pairs_in_report,
            "duplicates": duplicate_pairs,
        }

        if output_file:
            try:
                report_path = self._resolve_report_path(output_file)
                with open(report_path, "w") as f:
                    json.dump(report, f, indent=4)
                logger.info("Semantic dedup report written to %s", report_path)
            except Exception as e:
                logger.error("Failed to write semantic dedup report: %s", e)

        return deduped
