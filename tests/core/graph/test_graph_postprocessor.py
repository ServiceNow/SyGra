import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from sygra.core.graph.graph_postprocessor import SemanticDedupPostProcessor


class DummyEmbedder:
    def __init__(self, vectors: list[list[float]]):
        self._vectors = np.asarray(vectors, dtype=np.float32)
        self.last_texts: list[str] | None = None

    def encode(self, texts: list[str], normalize_embeddings: bool = True):
        self.last_texts = list(texts)
        return self._vectors


class TestSemanticDedupPostProcessor:
    def test_keep_first_drops_later_duplicate(self, monkeypatch):
        processor = SemanticDedupPostProcessor(field="text", similarity_threshold=0.9, keep="first")
        embedder = DummyEmbedder([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
        monkeypatch.setattr(processor, "_get_embedder", lambda: embedder)

        data = [
            {"id": "a", "text": "dup"},
            {"id": "b", "text": "dup"},
            {"id": "c", "text": "unique"},
        ]

        out = processor.process(data, metadata={})
        assert [x["id"] for x in out] == ["a", "c"]

    def test_keep_last_drops_earlier_duplicate(self, monkeypatch):
        processor = SemanticDedupPostProcessor(field="text", similarity_threshold=0.9, keep="last")
        embedder = DummyEmbedder([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
        monkeypatch.setattr(processor, "_get_embedder", lambda: embedder)

        data = [
            {"id": "a", "text": "dup"},
            {"id": "b", "text": "dup"},
            {"id": "c", "text": "unique"},
        ]

        out = processor.process(data, metadata={})
        assert [x["id"] for x in out] == ["b", "c"]

    def test_matrix_mode_works(self, monkeypatch):
        processor = SemanticDedupPostProcessor(
            field="text",
            similarity_threshold=0.9,
            keep="first",
            dedup_mode="all_pairs",
        )
        embedder = DummyEmbedder([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
        monkeypatch.setattr(processor, "_get_embedder", lambda: embedder)

        data = [
            {"id": "a", "text": "dup"},
            {"id": "b", "text": "dup"},
            {"id": "c", "text": "unique"},
        ]

        out = processor.process(data, metadata={})
        assert [x["id"] for x in out] == ["a", "c"]

    def test_invalid_dedup_mode_raises(self, monkeypatch):
        embedder = DummyEmbedder([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])

        data = [
            {"id": "a", "text": "dup"},
            {"id": "b", "text": "dup"},
            {"id": "c", "text": "unique"},
        ]

        for mode in ["not_a_real_mode", "matrix", "vectorstore"]:
            processor = SemanticDedupPostProcessor(
                field="text",
                similarity_threshold=0.9,
                dedup_mode=mode,
            )
            monkeypatch.setattr(processor, "_get_embedder", lambda: embedder)
            with pytest.raises(ValueError, match="Unsupported dedup_mode"):
                _ = processor.process(data, metadata={})

    def test_field_list_is_joined_before_embedding(self, monkeypatch):
        processor = SemanticDedupPostProcessor(field="parts", similarity_threshold=0.9)
        embedder = DummyEmbedder([[1.0, 0.0], [0.0, 1.0]])
        monkeypatch.setattr(processor, "_get_embedder", lambda: embedder)

        data = [
            {"id": "a", "parts": ["hello", "world"]},
            {"id": "b", "parts": ("x", None)},
        ]

        _ = processor.process(data, metadata={})
        assert embedder.last_texts == ["hello\nworld", "x\n"]

    def test_writes_default_report_next_to_output_file(self, monkeypatch, tmp_path):
        processor = SemanticDedupPostProcessor(
            field="text",
            similarity_threshold=0.9,
            max_pairs_in_report=10,
        )
        embedder = DummyEmbedder([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
        monkeypatch.setattr(processor, "_get_embedder", lambda: embedder)

        data = [
            {"id": "a", "text": "dup"},
            {"id": "b", "text": "dup"},
            {"id": "c", "text": "unique"},
        ]

        output_file = tmp_path / "output_2026-01-12_11-15-00.json"
        _ = processor.process(data, metadata={"output_file": str(output_file)})

        report_file = tmp_path / "semantic_dedup_report_2026-01-12_11-15-00.json"
        assert report_file.exists()

        report = json.loads(report_file.read_text())
        assert report["input_count"] == 3
        assert report["output_count"] == 2
        assert report["dropped_count"] == 1
        assert report["pairs_reported"] == 1
        assert len(report["duplicates"]) == 1

    def test_respects_custom_report_filename(self, monkeypatch, tmp_path):
        processor = SemanticDedupPostProcessor(
            field="text",
            similarity_threshold=0.9,
            report_filename="my_report.json",
            max_pairs_in_report=10,
        )
        embedder = DummyEmbedder([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
        monkeypatch.setattr(processor, "_get_embedder", lambda: embedder)

        data = [
            {"id": "a", "text": "dup"},
            {"id": "b", "text": "dup"},
            {"id": "c", "text": "unique"},
        ]

        output_file = tmp_path / "output_any.json"
        _ = processor.process(data, metadata={"output_file": str(output_file)})

        report_file = tmp_path / "my_report.json"
        assert report_file.exists()

        report = json.loads(report_file.read_text())
        assert report["processor"] == "SemanticDedupPostProcessor"
