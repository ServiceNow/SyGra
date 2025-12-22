"""Tests for ActionWithinBboxMetric"""

import pytest

from sygra.core.eval.metrics.unit_metrics.action_within_bbox import ActionWithinBboxMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class TestActionWithinBboxMetric:
    def test_get_metric_name(self):
        metric = ActionWithinBboxMetric()
        assert metric.get_metric_name() == "action_within_bbox"

    def test_action_inside_bbox(self):
        metric = ActionWithinBboxMetric()
        results = metric.evaluate(
            golden=[{"bbox": {"x": 0, "y": 0, "width": 10, "height": 10}}],
            predicted=[{"x": 5, "y": 5}],
        )
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], UnitMetricResult)
        assert results[0].correct is True

    def test_action_outside_bbox(self):
        metric = ActionWithinBboxMetric()
        results = metric.evaluate(
            golden=[{"bbox": {"x": 0, "y": 0, "width": 10, "height": 10}}],
            predicted=[{"x": 11, "y": 5}],
        )
        assert results[0].correct is False

    def test_action_on_bbox_boundary(self):
        metric = ActionWithinBboxMetric()
        results = metric.evaluate(
            golden=[{"bbox": {"x": 0, "y": 0, "width": 10, "height": 10}}],
            predicted=[{"x": 10, "y": 10}],
        )
        assert results[0].correct is True

    def test_invalid_bbox_returns_false(self):
        metric = ActionWithinBboxMetric()
        results = metric.evaluate(golden=[{"bbox": None}], predicted=[{"x": 1, "y": 1}])
        assert results[0].correct is False

    def test_mismatched_list_lengths_raises(self):
        metric = ActionWithinBboxMetric()
        with pytest.raises(ValueError):
            metric.evaluate(golden=[{}], predicted=[{}, {}])
