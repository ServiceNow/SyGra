"""
Tests for ExactMatchMetric

Comprehensive test suite for exact match validation functionality.
"""

import pytest

from sygra.core.eval.metrics.unit_metrics.exact_match import ExactMatchMetric
from sygra.core.eval.metrics.unit_metrics.unit_metric_result import UnitMetricResult


class TestExactMatchMetric:
    """Test suite for ExactMatchMetric"""

    def test_initialization_default_config(self):
        """Test initialization with default configuration"""
        validator = ExactMatchMetric()
        assert validator.case_sensitive is False
        assert validator.normalize_whitespace is True
        assert validator.key is None

    def test_initialization_custom_config(self):
        """Test initialization with custom configuration"""
        validator = ExactMatchMetric(case_sensitive=True, normalize_whitespace=False)
        assert validator.case_sensitive is True
        assert validator.normalize_whitespace is False

    def test_initialization_with_key(self):
        """Test initialization with specific key"""
        validator = ExactMatchMetric(key="text")
        assert validator.key == "text"

    def test_get_metric_name(self):
        """Test get_metric_name returns correct name"""
        validator = ExactMatchMetric()
        assert validator.get_metric_name() == "exact_match"

    def test_metadata(self):
        """Test metadata is correctly set"""
        validator = ExactMatchMetric()
        assert validator.metadata.name == "exact_match"
        assert validator.metadata.display_name == "Exact Match"
        assert validator.metadata.range == (0.0, 1.0)
        assert validator.metadata.higher_is_better is True
        assert validator.metadata.metric_type == "industry"

    def test_exact_match_identical_strings(self):
        """Test exact match with identical strings"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(
            golden=[{"text": "hello world"}], predicted=[{"text": "hello world"}]
        )
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], UnitMetricResult)
        assert results[0].correct is True
        assert results[0].golden == {"text": "hello world"}
        assert results[0].predicted == {"text": "hello world"}

    def test_exact_match_case_insensitive_default(self):
        """Test case-insensitive matching (default behavior)"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(
            golden=[{"text": "Hello World"}], predicted=[{"text": "hello world"}]
        )
        assert results[0].correct is True

    def test_exact_match_case_sensitive(self):
        """Test case-sensitive matching"""
        validator = ExactMatchMetric(key="text", case_sensitive=True)
        results = validator.evaluate(
            golden=[{"text": "Hello World"}], predicted=[{"text": "hello world"}]
        )
        assert results[0].correct is False

    def test_exact_match_case_sensitive_identical(self):
        """Test case-sensitive matching with identical case"""
        validator = ExactMatchMetric(key="text", case_sensitive=True)
        results = validator.evaluate(
            golden=[{"text": "Hello World"}], predicted=[{"text": "Hello World"}]
        )
        assert results[0].correct is True

    def test_normalize_whitespace_default(self):
        """Test whitespace normalization (default behavior)"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(
            golden=[{"text": "hello  world"}], predicted=[{"text": "hello world"}]
        )
        assert results[0].correct is True

    def test_normalize_whitespace_leading_trailing(self):
        """Test whitespace normalization with leading/trailing spaces"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(
            golden=[{"text": "  hello world  "}], predicted=[{"text": "hello world"}]
        )
        assert results[0].correct is True

    def test_no_normalize_whitespace(self):
        """Test without whitespace normalization"""
        validator = ExactMatchMetric(key="text", normalize_whitespace=False)
        results = validator.evaluate(
            golden=[{"text": "hello  world"}], predicted=[{"text": "hello world"}]
        )
        assert results[0].correct is False

    def test_exact_match_different_strings(self):
        """Test with completely different strings"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(golden=[{"text": "hello"}], predicted=[{"text": "goodbye"}])
        assert results[0].correct is False

    def test_exact_match_empty_strings(self):
        """Test with empty strings"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(golden=[{"text": ""}], predicted=[{"text": ""}])
        assert results[0].correct is True

    def test_exact_match_one_empty_string(self):
        """Test with one empty string"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(golden=[{"text": "hello"}], predicted=[{"text": ""}])
        assert results[0].correct is False

    def test_exact_match_missing_key_in_golden(self):
        """Test when key is missing in golden dict"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(golden=[{"other": "value"}], predicted=[{"text": "hello"}])
        # Missing key returns empty string, so should not match
        assert results[0].correct is False

    def test_exact_match_missing_key_in_predicted(self):
        """Test when key is missing in predicted dict"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(golden=[{"text": "hello"}], predicted=[{"other": "value"}])
        assert results[0].correct is False

    def test_exact_match_missing_key_in_both(self):
        """Test when key is missing in both dicts"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(golden=[{"other": "value1"}], predicted=[{"other": "value2"}])
        # Both missing keys return empty strings, so should match
        assert results[0].correct is True

    def test_exact_match_no_key_compares_full_dict(self):
        """Test comparison of full dict when no key specified"""
        validator = ExactMatchMetric()
        results = validator.evaluate(golden=[{"text": "hello"}], predicted=[{"text": "hello"}])
        assert results[0].correct is True

    def test_exact_match_no_key_different_dicts(self):
        """Test comparison of different dicts when no key specified"""
        validator = ExactMatchMetric()
        results = validator.evaluate(golden=[{"text": "hello"}], predicted=[{"text": "goodbye"}])
        assert results[0].correct is False

    def test_exact_match_numeric_values(self):
        """Test with numeric values"""
        validator = ExactMatchMetric(key="value")
        results = validator.evaluate(golden=[{"value": 42}], predicted=[{"value": 42}])
        assert results[0].correct is True

    def test_exact_match_numeric_string_mismatch(self):
        """Test numeric vs string comparison"""
        validator = ExactMatchMetric(key="value")
        results = validator.evaluate(golden=[{"value": 42}], predicted=[{"value": "42"}])
        # Both converted to string, so should match
        assert results[0].correct is True

    def test_exact_match_float_values(self):
        """Test with float values"""
        validator = ExactMatchMetric(key="value")
        results = validator.evaluate(golden=[{"value": 3.14}], predicted=[{"value": 3.14}])
        assert results[0].correct is True

    def test_exact_match_boolean_values(self):
        """Test with boolean values"""
        validator = ExactMatchMetric(key="flag")
        results = validator.evaluate(golden=[{"flag": True}], predicted=[{"flag": True}])
        assert results[0].correct is True

    def test_exact_match_boolean_mismatch(self):
        """Test with mismatched boolean values"""
        validator = ExactMatchMetric(key="flag")
        results = validator.evaluate(golden=[{"flag": True}], predicted=[{"flag": False}])
        assert results[0].correct is False

    def test_result_metadata_contains_validator_name(self):
        """Test that result metadata contains validator name"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(golden=[{"text": "hello"}], predicted=[{"text": "hello"}])
        assert results[0].metadata["validator"] == "exact_match"

    def test_result_metadata_contains_texts(self):
        """Test that result metadata contains compared texts"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(golden=[{"text": "hello"}], predicted=[{"text": "world"}])
        assert results[0].metadata["golden_text"] == "hello"
        assert results[0].metadata["predicted_text"] == "world"

    def test_result_metadata_contains_config(self):
        """Test that result metadata contains configuration"""
        validator = ExactMatchMetric(key="text", case_sensitive=True)
        results = validator.evaluate(golden=[{"text": "hello"}], predicted=[{"text": "hello"}])
        assert results[0].metadata["case_sensitive"] is True
        assert results[0].metadata["normalize_whitespace"] is True

    def test_normalize_text_method(self):
        """Test _normalize_text method directly"""
        validator = ExactMatchMetric()
        assert validator._normalize_text("  Hello  World  ") == "hello world"

    def test_normalize_text_case_sensitive(self):
        """Test _normalize_text with case sensitivity"""
        validator = ExactMatchMetric(case_sensitive=True)
        assert validator._normalize_text("  Hello  World  ") == "Hello World"

    def test_normalize_text_no_whitespace_normalization(self):
        """Test _normalize_text without whitespace normalization"""
        validator = ExactMatchMetric(normalize_whitespace=False)
        assert validator._normalize_text("  Hello  World  ") == "  hello  world  "

    def test_compare_text_method(self):
        """Test _compare_text method directly"""
        validator = ExactMatchMetric()
        assert validator._compare_text("Hello", "hello") is True
        assert validator._compare_text("Hello", "World") is False

    def test_multiple_items_in_list(self):
        """Test evaluation with multiple items in lists"""
        validator = ExactMatchMetric(key="text")

        results = validator.evaluate(
            golden=[{"text": "hello"}, {"text": "world"}, {"text": "foo"}],
            predicted=[{"text": "hello"}, {"text": "WORLD"}, {"text": "bar"}],
        )

        assert len(results) == 3
        assert results[0].correct is True  # "hello" == "hello"
        assert results[1].correct is True  # "world" == "WORLD" (case-insensitive)
        assert results[2].correct is False  # "foo" != "bar"

    def test_mismatched_list_lengths_raises_error(self):
        """Test that mismatched list lengths raise ValueError"""
        validator = ExactMatchMetric(key="text")

        with pytest.raises(ValueError) as exc_info:
            validator.evaluate(
                golden=[{"text": "hello"}, {"text": "world"}], predicted=[{"text": "hello"}]
            )

        assert "must have same length" in str(exc_info.value)
        assert "got 2 and 1" in str(exc_info.value)

    def test_empty_lists(self):
        """Test with empty lists"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(golden=[], predicted=[])
        assert results == []

    def test_complex_dict_comparison(self):
        """Test with complex nested dicts"""
        validator = ExactMatchMetric()
        results = validator.evaluate(
            golden=[{"a": 1, "b": {"c": 2}}], predicted=[{"a": 1, "b": {"c": 2}}]
        )
        # String comparison of dicts
        assert results[0].correct is True

    def test_special_characters(self):
        """Test with special characters"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(
            golden=[{"text": "hello@world.com"}], predicted=[{"text": "hello@world.com"}]
        )
        assert results[0].correct is True

    def test_unicode_characters(self):
        """Test with unicode characters"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(
            golden=[{"text": "héllo wörld"}], predicted=[{"text": "héllo wörld"}]
        )
        assert results[0].correct is True

    def test_newlines_and_tabs(self):
        """Test with newlines and tabs"""
        validator = ExactMatchMetric(key="text")
        results = validator.evaluate(
            golden=[{"text": "hello\nworld"}], predicted=[{"text": "hello world"}]
        )
        # Whitespace normalization converts \n to space
        assert results[0].correct is True

    def test_config_from_dict(self):
        """Test initialization from config dict"""
        config = {"case_sensitive": True, "normalize_whitespace": False, "key": "text"}
        validator = ExactMatchMetric(**config)
        assert validator.case_sensitive is True
        assert validator.normalize_whitespace is False
        assert validator.key == "text"

    def test_batch_evaluation_mixed_results(self):
        """Test batch evaluation with mixed correct/incorrect results"""
        validator = ExactMatchMetric(key="answer")

        results = validator.evaluate(
            golden=[
                {"answer": "Paris"},
                {"answer": "42"},
                {"answer": "True"},
                {"answer": "Python"},
            ],
            predicted=[
                {"answer": "paris"},  # Correct (case-insensitive)
                {"answer": "42"},  # Correct
                {"answer": "False"},  # Incorrect
                {"answer": "  Python  "},  # Correct (whitespace normalized)
            ],
        )

        assert len(results) == 4
        assert results[0].correct is True
        assert results[1].correct is True
        assert results[2].correct is False
        assert results[3].correct is True

        # Check that all results have proper structure
        for result in results:
            assert isinstance(result, UnitMetricResult)
            assert "validator" in result.metadata
            assert result.metadata["validator"] == "exact_match"
