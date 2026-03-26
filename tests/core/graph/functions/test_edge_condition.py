import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from sygra.core.graph.functions.edge_condition import EdgeCondition


class TestEdgeConditionABC(unittest.TestCase):
    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            EdgeCondition()

    def test_concrete_subclass_can_be_instantiated(self):
        class MyCondition(EdgeCondition):
            @staticmethod
            def apply(state) -> str:
                return "path_a"

        cond = MyCondition()
        self.assertIsInstance(cond, EdgeCondition)

    def test_apply_is_called_on_concrete_subclass(self):
        class MyCondition(EdgeCondition):
            @staticmethod
            def apply(state) -> str:
                return "path_b"

        result = MyCondition.apply({"key": "val"})
        self.assertEqual(result, "path_b")

    def test_incomplete_subclass_cannot_be_instantiated(self):
        class IncompleteCondition(EdgeCondition):
            pass

        with self.assertRaises(TypeError):
            IncompleteCondition()


if __name__ == "__main__":
    unittest.main()
