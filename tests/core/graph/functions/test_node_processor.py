import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from sygra.core.graph.functions.node_processor import (
    NodePostProcessor,
    NodePostProcessorWithState,
    NodePreProcessor,
)


class TestNodePreProcessorABC(unittest.TestCase):
    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            NodePreProcessor()

    def test_concrete_subclass_can_be_instantiated(self):
        class MyPreProcessor(NodePreProcessor):
            def apply(self, state):
                return state

        proc = MyPreProcessor()
        self.assertIsInstance(proc, NodePreProcessor)

    def test_apply_receives_state_and_returns_state(self):
        class MyPreProcessor(NodePreProcessor):
            def apply(self, state):
                state["preprocessed"] = True
                return state

        proc = MyPreProcessor()
        result = proc.apply({"x": 1})
        self.assertTrue(result["preprocessed"])


class TestNodePostProcessorABC(unittest.TestCase):
    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            NodePostProcessor()

    def test_concrete_subclass_can_be_instantiated(self):
        class MyPostProcessor(NodePostProcessor):
            def apply(self, resp):
                return {"result": resp.message}

        proc = MyPostProcessor()
        self.assertIsInstance(proc, NodePostProcessor)

    def test_apply_receives_sygra_message(self):
        from sygra.core.graph.sygra_message import SygraMessage

        class MyPostProcessor(NodePostProcessor):
            def apply(self, resp):
                return {"content": resp.message}

        proc = MyPostProcessor()
        msg = SygraMessage("hello")
        result = proc.apply(msg)
        self.assertEqual(result["content"], "hello")


class TestNodePostProcessorWithStateABC(unittest.TestCase):
    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            NodePostProcessorWithState()

    def test_concrete_subclass_can_be_instantiated(self):
        class MyPostProcessorWithState(NodePostProcessorWithState):
            def apply(self, resp, state):
                return {**state, "response": resp.message}

        proc = MyPostProcessorWithState()
        self.assertIsInstance(proc, NodePostProcessorWithState)

    def test_apply_receives_response_and_state(self):
        from sygra.core.graph.sygra_message import SygraMessage

        class MyPostProcessorWithState(NodePostProcessorWithState):
            def apply(self, resp, state):
                return {**state, "response": resp.message}

        proc = MyPostProcessorWithState()
        msg = SygraMessage("world")
        result = proc.apply(msg, {"existing": "val"})
        self.assertEqual(result["response"], "world")
        self.assertEqual(result["existing"], "val")


if __name__ == "__main__":
    unittest.main()
