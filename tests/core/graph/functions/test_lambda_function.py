import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from sygra.core.graph.functions.lambda_function import AsyncLambdaFunction, LambdaFunction


class TestLambdaFunctionABC(unittest.TestCase):
    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            LambdaFunction()

    def test_concrete_subclass_can_be_instantiated(self):
        class MyLambda(LambdaFunction):
            @staticmethod
            def apply(config, state):
                return state

        fn = MyLambda()
        self.assertIsInstance(fn, LambdaFunction)

    def test_apply_is_callable_on_concrete_subclass(self):
        class MyLambda(LambdaFunction):
            @staticmethod
            def apply(config, state):
                return {**state, "processed": True}

        result = MyLambda.apply({}, {"x": 1})
        self.assertTrue(result["processed"])

    def test_incomplete_subclass_cannot_be_instantiated(self):
        class IncompleteLambda(LambdaFunction):
            pass

        with self.assertRaises(TypeError):
            IncompleteLambda()


class TestAsyncLambdaFunctionABC(unittest.TestCase):
    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            AsyncLambdaFunction()

    def test_concrete_subclass_can_be_instantiated(self):
        class MyAsyncLambda(AsyncLambdaFunction):
            @staticmethod
            async def apply(config, state):
                return state

        fn = MyAsyncLambda()
        self.assertIsInstance(fn, AsyncLambdaFunction)

    def test_apply_is_async(self):
        import asyncio

        class MyAsyncLambda(AsyncLambdaFunction):
            @staticmethod
            async def apply(config, state):
                return {**state, "async_processed": True}

        result = asyncio.get_event_loop().run_until_complete(
            MyAsyncLambda.apply({}, {"x": 1})
        )
        self.assertTrue(result["async_processed"])

    def test_incomplete_subclass_cannot_be_instantiated(self):
        class IncompleteAsync(AsyncLambdaFunction):
            pass

        with self.assertRaises(TypeError):
            IncompleteAsync()


if __name__ == "__main__":
    unittest.main()
