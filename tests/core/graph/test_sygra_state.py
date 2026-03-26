import sys
import unittest
from pathlib import Path
from typing import TypedDict

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from sygra.core.graph.sygra_state import SygraState


class TestSygraState(unittest.TestCase):
    def test_is_typed_dict_subclass(self):
        self.assertTrue(issubclass(SygraState, dict))

    def test_can_be_instantiated_empty(self):
        state = SygraState()
        self.assertEqual(state, {})

    def test_can_hold_arbitrary_keys(self):
        state = SygraState(messages=["hello"], count=1)
        self.assertEqual(state["messages"], ["hello"])
        self.assertEqual(state["count"], 1)

    def test_has_total_false_so_no_required_fields(self):
        # total=False means all fields are optional; instantiation with no args should succeed
        state = SygraState()
        self.assertIsInstance(state, dict)


if __name__ == "__main__":
    unittest.main()
