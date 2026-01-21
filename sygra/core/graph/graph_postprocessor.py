import json
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, cast

import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

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
    """Semantic deduplication over a graph's output list.

    This post-processor removes near-duplicate items by embedding the configured
    `field` and dropping items whose cosine similarity is above
    `similarity_threshold`.

    Configuration is done via `graph_post_process` in the task `graph_config.yaml`.
    Two working examples are in:
    - `tasks/examples/semantic_dedup/graph_config.yaml` (dedup over `answer`)
    - `tasks/examples/semantic_dedup_no_seed/graph_config.yaml` (dedup over `description`)

    Parameters (YAML `params` -> constructor args):
    - `field`: Name of the key in each output item to embed and compare.
      If the value is a list/tuple, values are joined with newlines.
    - `similarity_threshold`: Cosine similarity threshold (higher => fewer drops).
    - `id_field`: Optional ID key used in the report for readability.
    - `embedding_backend`: Currently only `sentence_transformers` is supported.
    - `embedding_model`: SentenceTransformers model name (default: `all-MiniLM-L6-v2`).
    - `report_filename`: Optional report JSON filename. If relative, it is written
      next to the graph output file. If omitted, the report name is derived from
      the output file name.
    - `keep`: Which item to keep when duplicates are found: `first` or `last`.
    - `max_pairs_in_report`: Max number of duplicate pairs written to the report.

    Output report:
    - If `metadata["output_file"]` is set, a JSON report is written containing
      counts and sampled duplicate pairs.
    """

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
        dedup_mode: str = "nearest_neighbor",
        vectorstore_k: int = 20,
    ):
        self.field = field
        self.similarity_threshold = float(similarity_threshold)
        self.id_field = id_field
        self.embedding_backend = embedding_backend
        self.embedding_model = embedding_model
        self.report_filename = report_filename
        self.keep = keep
        self.max_pairs_in_report = int(max_pairs_in_report)
        self.dedup_mode = dedup_mode
        self.vectorstore_k = int(vectorstore_k)

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

    def _dedup_via_langchain_vectorstore(
        self,
        data: list,
        texts: list[str],
        embs: np.ndarray,
    ) -> tuple[list, list[int], list[dict[str, Any]]]:

        if self.keep == "last":
            iter_indices = range(len(data) - 1, -1, -1)
        else:
            iter_indices = range(len(data))

        # Use unique keys as "texts" so the embedding cache is unambiguous even if
        # multiple records share identical content.
        keys = [f"__sygra_semantic_dedup__{i}__" for i in range(len(texts))]
        vec_map: dict[str, np.ndarray] = {keys[i]: embs[i] for i in range(len(keys))}

        class _CachedEmbeddings(Embeddings):
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return [[float(x) for x in vec_map[t]] for t in texts]

            def embed_query(self, text: str) -> list[float]:
                return [float(x) for x in vec_map[text]]

        store = InMemoryVectorStore(embedding=_CachedEmbeddings())

        kept: list[int] = []
        duplicate_pairs: list[dict[str, Any]] = []

        # Incrementally add only kept items to the store.
        for i in iter_indices:
            key = keys[i]
            if kept:
                try:
                    docs = store.similarity_search(key, k=max(1, self.vectorstore_k))
                except Exception:
                    docs = []

                best_sim = -1.0
                best_kept_idx: Optional[int] = None
                for d in docs:
                    idx = d.metadata.get("idx")
                    if idx is None:
                        continue
                    sim = float(embs[int(idx)] @ embs[i])
                    if sim > best_sim:
                        best_sim = sim
                        best_kept_idx = int(idx)

                if best_kept_idx is not None and best_sim >= self.similarity_threshold:
                    if len(duplicate_pairs) < self.max_pairs_in_report:
                        duplicate_pairs.append(
                            {
                                "kept_index": int(best_kept_idx),
                                "dropped_index": int(i),
                                "kept_id": self._get_id(
                                    data[int(best_kept_idx)], str(best_kept_idx)
                                ),
                                "dropped_id": self._get_id(data[int(i)], str(i)),
                                "similarity": float(best_sim),
                            }
                        )
                    continue

            store.add_texts([key], metadatas=[{"idx": int(i)}])

            kept.append(i)

        kept_sorted = sorted(kept) if self.keep == "last" else kept
        deduped = [data[i] for i in kept_sorted]
        return deduped, kept_sorted, duplicate_pairs

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

        duplicate_pairs: list[dict[str, Any]] = []

        if self.dedup_mode == "nearest_neighbor":
            deduped, kept_sorted, duplicate_pairs = self._dedup_via_langchain_vectorstore(
                data=data,
                texts=texts,
                embs=embs,
            )
        elif self.dedup_mode == "all_pairs":
            sims = self._cosine_sim_matrix(embs)

            kept: list[int] = []
            dropped: set[int] = set()

            # Greedy pass: keep an item if it isn't too-similar to a previously kept one
            if self.keep == "last":
                iter_indices = range(len(data) - 1, -1, -1)
            else:
                iter_indices = range(len(data))

            for i in iter_indices:
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

                    should_drop = False
                    if self.keep == "first":
                        should_drop = int(j) > i
                    elif self.keep == "last":
                        should_drop = int(j) < i
                    else:
                        should_drop = int(j) > i

                    if should_drop:
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

            kept_sorted = sorted(kept) if self.keep == "last" else kept
            deduped = [data[i] for i in kept_sorted]

        else:
            raise ValueError(f"Unsupported dedup_mode: {self.dedup_mode}")

        report = {
            "processor": "SemanticDedupPostProcessor",
            "field": self.field,
            "id_field": self.id_field,
            "embedding_backend": self.embedding_backend,
            "embedding_model": self.embedding_model,
            "similarity_threshold": self.similarity_threshold,
            "keep": self.keep,
            "dedup_mode": self.dedup_mode,
            "vectorstore_k": self.vectorstore_k,
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
