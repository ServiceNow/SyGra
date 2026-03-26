import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent.parent))

from sygra.utils.graph_utils import convert_graph_output_to_records, execute_graph


class TestConvertGraphOutputToRecords(unittest.TestCase):
    def test_returns_all_records_when_no_generator(self):
        results = [{"a": 1}, {"b": 2}]
        output = convert_graph_output_to_records(results)
        self.assertEqual(output, results)

    def test_applies_output_record_generator_to_each_result(self):
        results = [{"raw": "data1"}, {"raw": "data2"}]
        generator = lambda r: {**r, "transformed": True}
        output = convert_graph_output_to_records(results, output_record_generator=generator)
        self.assertTrue(all(r["transformed"] for r in output))

    def test_skips_none_results_from_generator(self):
        results = [{"a": 1}, {"b": 2}, {"c": 3}]
        generator = lambda r: None if r.get("b") else r
        output = convert_graph_output_to_records(results, output_record_generator=generator)
        self.assertEqual(len(output), 2)

    def test_skips_results_where_generator_raises_exception(self):
        results = [{"a": 1}, {"bad": "data"}, {"c": 3}]

        def generator(r):
            if "bad" in r:
                raise ValueError("bad data")
            return r

        output = convert_graph_output_to_records(results, output_record_generator=generator)
        self.assertEqual(len(output), 2)
        self.assertNotIn({"bad": "data"}, output)

    def test_returns_empty_list_for_empty_input(self):
        output = convert_graph_output_to_records([])
        self.assertEqual(output, [])

    def test_none_results_skipped_without_generator(self):
        results = [{"a": 1}, None, {"b": 2}]
        output = convert_graph_output_to_records(results)
        # None items are skipped
        self.assertEqual(len(output), 2)


class TestExecuteGraph(unittest.IsolatedAsyncioTestCase):
    async def test_execute_graph_calls_graph_ainvoke(self):
        record = {"id": "1", "input": "hello"}
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"output": "world"}

        result = await execute_graph(record, mock_graph)

        mock_graph.ainvoke.assert_called_once()
        self.assertEqual(result, {"output": "world"})

    async def test_execute_graph_applies_input_record_generator(self):
        record = {"id": "1"}
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"result": "ok"}
        generator = lambda r: {**r, "extra": "added"}

        await execute_graph(record, mock_graph, input_record_generator=generator)

        call_args = mock_graph.ainvoke.call_args[0][0]
        self.assertEqual(call_args["extra"], "added")

    async def test_execute_graph_returns_error_dict_on_exception(self):
        record = {"id": "1"}
        mock_graph = AsyncMock()
        mock_graph.ainvoke.side_effect = RuntimeError("graph exploded")

        result = await execute_graph(record, mock_graph)

        self.assertIn("execution_error", result)
        self.assertTrue(result["execution_error"])

    async def test_execute_graph_passes_debug_flag(self):
        record = {"id": "1"}
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {}

        await execute_graph(record, mock_graph, debug=True)

        call_kwargs = mock_graph.ainvoke.call_args[1]
        self.assertTrue(call_kwargs.get("debug"))


if __name__ == "__main__":
    unittest.main()
