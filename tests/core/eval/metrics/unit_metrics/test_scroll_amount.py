"""Tests for ScrollAmountMetric"""

import pytest

from sygra.core.eval.metrics.unit_metrics.scroll_amount import ScrollAmountMetric


class TestScrollAmountMetric:
    def test_get_metric_name(self):
        metric = ScrollAmountMetric()
        assert metric.get_metric_name() == "scroll_amount"

    def test_within_tolerance_percent(self):
        metric = ScrollAmountMetric(tolerance_percent=20.0)
        results = metric.evaluate(golden=[{"amount": 100.0}], predicted=[{"amount": 110.0}])
        assert results[0].correct is True

    def test_outside_tolerance_percent(self):
        metric = ScrollAmountMetric(tolerance_percent=5.0)
        results = metric.evaluate(golden=[{"amount": 100.0}], predicted=[{"amount": 110.0}])
        assert results[0].correct is False

    def test_golden_zero_uses_scroll_threshold(self):
        metric = ScrollAmountMetric(scroll_threshold=10.0)
        results_ok = metric.evaluate(golden=[{"amount": 0.0}], predicted=[{"amount": 5.0}])
        results_bad = metric.evaluate(golden=[{"amount": 0.0}], predicted=[{"amount": 20.0}])
        assert results_ok[0].correct is True
        assert results_bad[0].correct is False

    def test_mismatched_list_lengths_raises(self):
        metric = ScrollAmountMetric()
        with pytest.raises(ValueError):
            metric.evaluate(golden=[{}], predicted=[{}, {}])
