import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from sygra.core.graph.nodes.weighted_sampler_node import WeightedSamplerNode


def _make_config(attributes=None, extra=None):
    config = {
        "node_type": "weighted_sampler",
        "attributes": attributes or {"color": {"values": ["red", "blue", "green"]}},
    }
    if extra:
        config.update(extra)
    return config


class TestWeightedSamplerNodeInit(unittest.TestCase):
    @patch("sygra.core.graph.nodes.weighted_sampler_node.utils")
    def test_init_adds_attribute_keys_to_state_variables(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        config = _make_config(attributes={"color": {"values": ["red"]}, "size": {"values": ["S"]}})
        node = WeightedSamplerNode("sampler", config)
        self.assertIn("color", node.state_variables)
        self.assertIn("size", node.state_variables)

    @patch("sygra.core.graph.nodes.weighted_sampler_node.utils")
    def test_init_raises_when_attributes_not_dict(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        config = {"node_type": "weighted_sampler", "attributes": ["not", "a", "dict"]}
        with self.assertRaises(ValueError):
            WeightedSamplerNode("sampler", config)


class TestWeightedSamplerWeightedSampler(unittest.TestCase):
    @patch("sygra.core.graph.nodes.weighted_sampler_node.utils")
    def test_samples_from_static_list(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        config = _make_config(attributes={"color": {"values": ["red", "blue", "green"]}})
        node = WeightedSamplerNode("sampler", config)
        result = node._weighted_sampler(config["attributes"], {})
        self.assertIn("color", result)
        self.assertIn(result["color"], ["red", "blue", "green"])

    @patch("sygra.core.graph.nodes.weighted_sampler_node.utils")
    def test_respects_weights(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        config = _make_config(attributes={"color": {"values": ["red", "blue"], "weights": [0, 1]}})
        node = WeightedSamplerNode("sampler", config)
        results = {node._weighted_sampler(config["attributes"], {})["color"] for _ in range(10)}
        self.assertEqual(results, {"blue"})

    @patch("sygra.core.graph.nodes.weighted_sampler_node.utils")
    def test_samples_from_datasource(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        mock_utils.fetch_next_record.return_value = "persona_val"
        datasrc = {"type": "hf", "repo_id": "some/repo", "split": "train"}
        config = _make_config(attributes={"role": {"values": {"column": "persona", "source": datasrc}}})
        node = WeightedSamplerNode("sampler", config)
        result = node._weighted_sampler(config["attributes"], {})
        mock_utils.fetch_next_record.assert_called_once_with(datasrc, "persona")
        self.assertEqual(result["role"], "persona_val")


class TestWeightedSamplerNodeValidate(unittest.TestCase):
    @patch("sygra.core.graph.nodes.weighted_sampler_node.utils")
    def test_validate_raises_when_attributes_key_missing(self, mock_utils):
        mock_utils.validate_required_keys.side_effect = ValueError("Missing key: attributes")
        mock_utils.backend_factory = MagicMock()
        with self.assertRaises((ValueError, Exception)):
            WeightedSamplerNode("sampler", {"node_type": "weighted_sampler"})


class TestWeightedSamplerNodeExecWrapper(unittest.IsolatedAsyncioTestCase):
    @patch("sygra.core.graph.nodes.weighted_sampler_node.utils")
    async def test_exec_wrapper_merges_sampled_values_into_state(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        config = _make_config(attributes={"color": {"values": ["red"]}})
        node = WeightedSamplerNode("sampler", config)
        state = {"existing": "val"}
        with patch.object(node, "_record_execution_metadata"):
            result = await node._exec_wrapper(state)
        self.assertEqual(result["existing"], "val")
        self.assertEqual(result["color"], "red")

    @patch("sygra.core.graph.nodes.weighted_sampler_node.utils")
    async def test_exec_wrapper_records_failure_on_exception(self, mock_utils):
        mock_utils.backend_factory = MagicMock()
        config = _make_config()
        node = WeightedSamplerNode("sampler", config)
        with patch.object(node, "_weighted_sampler", side_effect=RuntimeError("err")):
            with patch.object(node, "_record_execution_metadata") as mock_record:
                with self.assertRaises(RuntimeError):
                    await node._exec_wrapper({})
        self.assertFalse(mock_record.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
