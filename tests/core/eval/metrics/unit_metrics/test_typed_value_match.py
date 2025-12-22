"""Tests for TypedValueMatchMetric"""

import pytest

from sygra.core.eval.metrics.unit_metrics.typed_value_match import TypedValueMatchMetric


class TestTypedValueMatchMetric:
    def test_get_metric_name(self):
        metric = TypedValueMatchMetric()
        assert metric.get_metric_name() == "typed_value_match"

    def test_exact_match_case_insensitive_and_whitespace(self):
        metric = TypedValueMatchMetric(golden_text_key="text", predicted_text_key="text")
        results = metric.evaluate(
            golden=[{"text": "Hello   World"}],
            predicted=[{"text": "  hello world "}],
        )
        assert results[0].correct is True
        assert results[0].metadata["exact_match"] is True

    def test_fuzzy_match_threshold(self):
        metric = TypedValueMatchMetric(fuzzy_match_threshold=0.5)
        results = metric.evaluate(
            golden=[{"text": "hello world"}],
            predicted=[{"text": "hello wurld"}],
        )
        assert results[0].metadata["similarity_score"] >= 0.0
        assert results[0].correct is True

    def test_fuzzy_match_rejects_when_threshold_high(self):
        metric = TypedValueMatchMetric(fuzzy_match_threshold=0.99)
        results = metric.evaluate(
            golden=[{"text": "hello world"}],
            predicted=[{"text": "hello wurld"}],
        )
        assert results[0].correct is False

    def test_mismatched_list_lengths_raises(self):
        metric = TypedValueMatchMetric()
        with pytest.raises(ValueError):
            metric.evaluate(golden=[{}], predicted=[{}, {}])
