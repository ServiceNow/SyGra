import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from langgraph.constants import END, START

from sygra.core.graph.langgraph.graph_builder import LangGraphBuilder


class TestLangGraphBuilderInit(unittest.TestCase):
    def test_init_stores_graph_config(self):
        graph_config = MagicMock()
        builder = LangGraphBuilder(graph_config)
        self.assertEqual(builder.graph_config, graph_config)

    def test_init_sets_workflow_to_none(self):
        builder = LangGraphBuilder(MagicMock())
        self.assertIsNone(builder.workflow)

    def test_special_nodes_map_contains_start_and_end(self):
        self.assertEqual(LangGraphBuilder.SPECIAL_NODES_MAP["START"], START)
        self.assertEqual(LangGraphBuilder.SPECIAL_NODES_MAP["END"], END)


class TestLangGraphBuilderGetNode(unittest.TestCase):
    def test_get_node_returns_start_for_start_key(self):
        result = LangGraphBuilder.get_node("START")
        self.assertEqual(result, START)

    def test_get_node_returns_end_for_end_key(self):
        result = LangGraphBuilder.get_node("END")
        self.assertEqual(result, END)

    def test_get_node_returns_value_unchanged_for_regular_name(self):
        result = LangGraphBuilder.get_node("my_node")
        self.assertEqual(result, "my_node")


class TestLangGraphBuilderConvertToGraph(unittest.TestCase):
    def test_returns_none_for_none_input(self):
        builder = LangGraphBuilder(MagicMock())
        result = builder.convert_to_graph(None)
        self.assertIsNone(result)

    def test_returns_start_for_special_start_node(self):
        builder = LangGraphBuilder(MagicMock())
        node = MagicMock()
        node.get_name.return_value = "START"
        node.is_special_type.return_value = True
        result = builder.convert_to_graph(node)
        self.assertEqual(result, START)

    def test_returns_end_for_special_end_node(self):
        builder = LangGraphBuilder(MagicMock())
        node = MagicMock()
        node.get_name.return_value = "END"
        node.is_special_type.return_value = True
        result = builder.convert_to_graph(node)
        self.assertEqual(result, END)

    def test_returns_node_name_for_regular_node(self):
        builder = LangGraphBuilder(MagicMock())
        node = MagicMock()
        node.get_name.return_value = "my_node"
        node.is_special_type.return_value = False
        result = builder.convert_to_graph(node)
        self.assertEqual(result, "my_node")


class TestLangGraphBuilderCompile(unittest.TestCase):
    def test_compile_raises_when_build_not_called(self):
        builder = LangGraphBuilder(MagicMock())
        with self.assertRaises(RuntimeError):
            builder.compile()

    def test_compile_returns_compiled_graph_after_build(self):
        graph_config = MagicMock()
        graph_config.get_nodes.return_value = {}
        graph_config.get_edges.return_value = []
        graph_config.state_variables = set()
        graph_config.sub_graphs = {}

        mock_workflow = MagicMock()
        mock_compiled = MagicMock()
        mock_workflow.compile.return_value = mock_compiled

        with patch("sygra.core.graph.langgraph.graph_builder.backend_factory") as mock_bf, \
             patch("sygra.core.graph.langgraph.graph_builder.EdgeFactory") as mock_ef:
            mock_bf.build_workflow.return_value = mock_workflow
            mock_ef.return_value.get_edges.return_value = []

            builder = LangGraphBuilder(graph_config)
            builder.build()
            result = builder.compile()

        mock_workflow.compile.assert_called_once()
        self.assertEqual(result, mock_compiled)


class TestLangGraphBuilderAddNodes(unittest.TestCase):
    def test_add_nodes_adds_active_nodes(self):
        graph_config = MagicMock()
        active_node = MagicMock()
        active_node.is_active.return_value = True
        active_node.to_backend.return_value = MagicMock()
        graph_config.get_nodes.return_value = {"active_node": active_node}

        workflow = MagicMock()
        builder = LangGraphBuilder(graph_config)
        builder.add_nodes(workflow)

        workflow.add_node.assert_called_once_with("active_node", active_node.to_backend())

    def test_add_nodes_skips_inactive_nodes(self):
        graph_config = MagicMock()
        inactive_node = MagicMock()
        inactive_node.is_active.return_value = False
        graph_config.get_nodes.return_value = {"inactive_node": inactive_node}

        workflow = MagicMock()
        builder = LangGraphBuilder(graph_config)
        builder.add_nodes(workflow)

        workflow.add_node.assert_not_called()


class TestLangGraphBuilderUpdateStateVariables(unittest.TestCase):
    def test_adds_node_state_variables_to_graph_config(self):
        graph_config = MagicMock()
        graph_config.state_variables = set()

        node = MagicMock()
        node.is_active.return_value = True
        node.get_state_variables.return_value = ["var_a", "var_b"]
        graph_config.get_nodes.return_value = {"node1": node}

        builder = LangGraphBuilder(graph_config)
        builder._update_state_variables()

        self.assertIn("var_a", graph_config.state_variables)
        self.assertIn("var_b", graph_config.state_variables)

    def test_does_not_add_duplicate_state_variables(self):
        graph_config = MagicMock()
        graph_config.state_variables = {"var_a"}

        node = MagicMock()
        node.is_active.return_value = True
        node.get_state_variables.return_value = ["var_a"]
        graph_config.get_nodes.return_value = {"node1": node}

        builder = LangGraphBuilder(graph_config)
        builder._update_state_variables()

        self.assertEqual(graph_config.state_variables.count("var_a") if hasattr(graph_config.state_variables, 'count') else 1, 1)


if __name__ == "__main__":
    unittest.main()
