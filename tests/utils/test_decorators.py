import sys
import unittest
import warnings
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from sygra.utils.decorators import future_deprecation


class TestFutureDeprecationDecorator(unittest.TestCase):
    def test_decorated_function_still_works(self):
        @future_deprecation()
        def my_func(x):
            return x * 2

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = my_func(5)

        self.assertEqual(result, 10)

    def test_emits_deprecation_warning(self):
        @future_deprecation()
        def deprecated_func():
            return "ok"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            deprecated_func()

        self.assertEqual(len(w), 1)
        self.assertTrue(issubclass(w[0].category, DeprecationWarning))

    def test_warning_message_contains_function_name(self):
        @future_deprecation()
        def my_deprecated_func():
            pass

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            my_deprecated_func()

        self.assertIn("my_deprecated_func", str(w[0].message))

    def test_warning_message_contains_reason_when_provided(self):
        @future_deprecation(reason="use new_func instead")
        def old_func():
            pass

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            old_func()

        self.assertIn("use new_func instead", str(w[0].message))

    def test_warning_message_without_reason(self):
        @future_deprecation()
        def no_reason_func():
            pass

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            no_reason_func()

        self.assertIn("scheduled for future deprecation", str(w[0].message))

    def test_preserves_function_name_via_functools_wraps(self):
        @future_deprecation(reason="test")
        def original_name():
            pass

        self.assertEqual(original_name.__name__, "original_name")

    def test_sets_future_deprecation_attribute(self):
        @future_deprecation()
        def tagged_func():
            pass

        self.assertTrue(tagged_func._future_deprecation)

    def test_decorated_function_passes_args_and_kwargs(self):
        @future_deprecation()
        def add(a, b, c=0):
            return a + b + c

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = add(1, 2, c=3)

        self.assertEqual(result, 6)


if __name__ == "__main__":
    unittest.main()
