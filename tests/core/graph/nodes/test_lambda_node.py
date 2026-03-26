import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from sygra.core.graph.nodes.lambda_node import LambdaNode


def _make_config(lambda_path="some.module.my_func", extra=None):
    config = {"node_type": "lambda", "lambda": lambda_path}
    if extra:
        config.update(extra)
    return config


class TestLambdaNodeInit(unittest.TestCase):
    @patch("sygra.core.graph.nodes.lambda_node.utils")
    def test_init_sync_function_sets_func_type_sync(self, mock_utils):
        sync_func = MagicMock()
        mock_utils.get_func_from_str.return_value = sync_func
        mock_utils.backend_factory = MagicMock()

        node = LambdaNode("my_node", _make_config())

        mock_utils.get_func_from_str.assert_called_once_with("some.module.my_func")
        self.assertEqual(node.func_type, "sync")
        self.assertEqual(node.func_to_execute, sync_func)

    @patch("sygra.core.graph.nodes.lambda_node.utils")
    def test_init_async_function_sets_func_type_async(self, mock_utils):
        async def async_func(config, state):
            pass

        mock_utils.get_func_from_str.return_value = async_func
        mock_utils.backend_factory = MagicMock()

        node = LambdaNode("my_node", _make_config())

        self.assertEqual(node.func_type, "async")

    @patch("sygra.core.graph.nodes.lambda_node.utils")
    def test_init_with_class_uses_apply_method(self, mock_utils):
        class MyClass:
            @staticmethod
            def apply(config, state):
                return state

        mock_utils.get_func_from_str.return_value = MyClass
        mock_utils.backend_factory = MagicMock()

        node = LambdaNode("my_node", _make_config())

        self.assertEqual(node.func_to_execute, MyClass.apply)
        self.assertEqual(node.func_type, "sync")


class TestLambdaNodeValidate(unittest.TestCase):
    @patch("sygra.core.graph.nodes.lambda_node.utils")
    def test_validate_node_raises_when_lambda_key_missing(self, mock_utils):
        mock_utils.validate_required_keys.side_effect = ValueError("Missing key: lambda")
        mock_utils.backend_factory = MagicMock()

        with self.assertRaises((ValueError, Exception)):
            LambdaNode("my_node", {"node_type": "lambda"})


class TestLambdaNodeToBackend(unittest.TestCase):
    @patch("sygra.core.graph.nodes.lambda_node.utils")
    def test_to_backend_sync_calls_create_lambda_runnable_with_async_false(self, mock_utils):
        sync_func = MagicMock()
        mock_utils.get_func_from_str.return_value = sync_func
        mock_utils.backend_factory = MagicMock()
        expected = MagicMock()
        mock_utils.backend_factory.create_lambda_runnable.return_value = expected

        node = LambdaNode("my_node", _make_config())
        result = node.to_backend()

        mock_utils.backend_factory.create_lambda_runnable.assert_called_once_with(
            node._sync_exec_wrapper, async_func=False
        )
        self.assertEqual(result, expected)

    @patch("sygra.core.graph.nodes.lambda_node.utils")
    def test_to_backend_async_calls_create_lambda_runnable(self, mock_utils):
        async def async_func(config, state):
            pass

        mock_utils.get_func_from_str.return_value = async_func
        mock_utils.backend_factory = MagicMock()
        expected = MagicMock()
        mock_utils.backend_factory.create_lambda_runnable.return_value = expected

        node = LambdaNode("my_node", _make_config())
        result = node.to_backend()

        mock_utils.backend_factory.create_lambda_runnable.assert_called_once_with(
            node._async_exec_wrapper
        )
        self.assertEqual(result, expected)


class TestLambdaNodeSyncExecWrapper(unittest.TestCase):
    @patch("sygra.core.graph.nodes.lambda_node.utils")
    def test_sync_exec_wrapper_calls_func_and_records_metadata(self, mock_utils):
        state = {"input": "hello"}
        expected_result = {"output": "world"}
        sync_func = MagicMock(return_value=expected_result)
        mock_utils.get_func_from_str.return_value = sync_func
        mock_utils.backend_factory = MagicMock()

        node = LambdaNode("my_node", _make_config())

        with patch.object(node, "_record_execution_metadata") as mock_record:
            result = node._sync_exec_wrapper(state)

        sync_func.assert_called_once_with(node.node_config, state)
        self.assertEqual(result, expected_result)
        mock_record.assert_called_once()
        self.assertTrue(mock_record.call_args[0][1])

    @patch("sygra.core.graph.nodes.lambda_node.utils")
    def test_sync_exec_wrapper_records_failure_on_exception(self, mock_utils):
        sync_func = MagicMock(side_effect=RuntimeError("boom"))
        mock_utils.get_func_from_str.return_value = sync_func
        mock_utils.backend_factory = MagicMock()

        node = LambdaNode("my_node", _make_config())

        with patch.object(node, "_record_execution_metadata") as mock_record:
            with self.assertRaises(RuntimeError):
                node._sync_exec_wrapper({"x": 1})

        mock_record.assert_called_once()
        self.assertFalse(mock_record.call_args[0][1])


class TestLambdaNodeAsyncExecWrapper(unittest.IsolatedAsyncioTestCase):
    @patch("sygra.core.graph.nodes.lambda_node.utils")
    async def test_async_exec_wrapper_calls_func_and_records_metadata(self, mock_utils):
        state = {"input": "hello"}
        expected_result = {"output": "world"}

        async def async_func(config, st):
            return expected_result

        mock_utils.get_func_from_str.return_value = async_func
        mock_utils.backend_factory = MagicMock()

        node = LambdaNode("my_node", _make_config())

        with patch.object(node, "_record_execution_metadata") as mock_record:
            result = await node._async_exec_wrapper(state)

        self.assertEqual(result, expected_result)
        mock_record.assert_called_once()
        self.assertTrue(mock_record.call_args[0][1])

    @patch("sygra.core.graph.nodes.lambda_node.utils")
    async def test_async_exec_wrapper_records_failure_on_exception(self, mock_utils):
        async def async_func(config, state):
            raise ValueError("async boom")

        mock_utils.get_func_from_str.return_value = async_func
        mock_utils.backend_factory = MagicMock()

        node = LambdaNode("my_node", _make_config())

        with patch.object(node, "_record_execution_metadata") as mock_record:
            with self.assertRaises(ValueError):
                await node._async_exec_wrapper({"x": 1})

        mock_record.assert_called_once()
        self.assertFalse(mock_record.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
