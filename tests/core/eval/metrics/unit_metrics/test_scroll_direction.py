"""Tests for ScrollDirectionMetric"""

import pytest

from sygra.core.eval.metrics.unit_metrics.scroll_direction import ScrollDirectionMetric


class TestScrollDirectionMetric:
    def test_get_metric_name(self):
        metric = ScrollDirectionMetric()
        assert metric.get_metric_name() == "scroll_direction"

    def test_valid_direction_match(self):
        metric = ScrollDirectionMetric()
        results = metric.evaluate(golden=[{"direction": "down"}], predicted=[{"direction": "down"}])
        assert results[0].correct is True

    def test_invalid_direction_value(self):
        metric = ScrollDirectionMetric()
        results = metric.evaluate(
            golden=[{"direction": "down"}], predicted=[{"direction": "diagonal"}]
        )
        assert results[0].correct is False

    def test_direction_mismatch(self):
        metric = ScrollDirectionMetric()
        results = metric.evaluate(golden=[{"direction": "up"}], predicted=[{"direction": "down"}])
        assert results[0].correct is False

    def test_mismatched_list_lengths_raises(self):
        metric = ScrollDirectionMetric()
        with pytest.raises(ValueError):
            metric.evaluate(golden=[{}], predicted=[{}, {}])
