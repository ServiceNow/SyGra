import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from sygra.workflow import AutoNestedDict, Workflow, create_graph


class TestAutoNestedDict:
    """Test suite for AutoNestedDict class."""

    def test_auto_creation_of_nested_keys(self):
        """Test that accessing non-existent keys creates nested AutoNestedDict."""
        d = AutoNestedDict()

        d["level1"]["level2"]["level3"] = "value"

        assert d["level1"]["level2"]["level3"] == "value"
        assert isinstance(d["level1"], AutoNestedDict)
        assert isinstance(d["level1"]["level2"], AutoNestedDict)

    def test_getitem_creates_autodict_on_missing_key(self):
        """Test that __getitem__ creates AutoNestedDict for missing keys."""
        d = AutoNestedDict()

        nested = d["new_key"]

        assert isinstance(nested, AutoNestedDict)
        assert "new_key" in d

    def test_setitem_converts_regular_dict_to_autodict(self):
        """Test that __setitem__ converts regular dicts to AutoNestedDict."""
        d = AutoNestedDict()
        regular_dict = {"inner": {"deep": "value"}}

        d["key"] = regular_dict

        assert isinstance(d["key"], AutoNestedDict)
        assert isinstance(d["key"]["inner"], AutoNestedDict)
        assert d["key"]["inner"]["deep"] == "value"

    def test_setitem_preserves_autodict(self):
        """Test that setting an AutoNestedDict value preserves its type."""
        d = AutoNestedDict()
        auto_dict = AutoNestedDict({"a": 1})

        d["key"] = auto_dict

        assert isinstance(d["key"], AutoNestedDict)
        assert d["key"]["a"] == 1

    def test_setitem_with_primitive_values(self):
        """Test that primitive values are stored without conversion."""
        d = AutoNestedDict()

        d["string"] = "hello"
        d["int"] = 42
        d["float"] = 3.14
        d["bool"] = True
        d["none"] = None

        assert d["string"] == "hello"
        assert d["int"] == 42
        assert d["float"] == 3.14
        assert d["bool"] is True
        assert d["none"] is None

    def test_convert_dict_simple_dict(self):
        """Test convert_dict with a simple dictionary."""
        regular_dict = {"a": 1, "b": 2, "c": 3}

        result = AutoNestedDict.convert_dict(regular_dict)

        assert isinstance(result, AutoNestedDict)
        assert result["a"] == 1
        assert result["b"] == 2
        assert result["c"] == 3

    def test_convert_dict_nested_dict(self):
        """Test convert_dict with nested dictionaries."""
        nested_dict = {"level1": {"level2": {"level3": "deep_value"}}}

        result = AutoNestedDict.convert_dict(nested_dict)

        assert isinstance(result, AutoNestedDict)
        assert isinstance(result["level1"], AutoNestedDict)
        assert isinstance(result["level1"]["level2"], AutoNestedDict)
        assert result["level1"]["level2"]["level3"] == "deep_value"

    def test_convert_dict_with_lists(self):
        """Test convert_dict handles lists correctly."""
        dict_with_lists = {
            "simple_list": [1, 2, 3],
            "dict_list": [{"a": 1}, {"b": 2}],
            "mixed_list": [1, {"nested": "dict"}, "string"],
        }

        result = AutoNestedDict.convert_dict(dict_with_lists)

        assert result["simple_list"] == [1, 2, 3]
        assert isinstance(result["dict_list"][0], AutoNestedDict)
        assert isinstance(result["dict_list"][1], AutoNestedDict)
        assert result["dict_list"][0]["a"] == 1
        assert isinstance(result["mixed_list"][1], AutoNestedDict)
        assert result["mixed_list"][1]["nested"] == "dict"

    def test_convert_dict_empty_dict(self):
        """Test convert_dict with empty dictionary."""
        result = AutoNestedDict.convert_dict({})

        assert isinstance(result, AutoNestedDict)
        assert len(result) == 0

    def test_to_dict_simple(self):
        """Test to_dict converts AutoNestedDict to regular dict."""
        d = AutoNestedDict({"a": 1, "b": 2})

        result = d.to_dict()

        assert isinstance(result, dict)
        assert not isinstance(result, AutoNestedDict)
        assert result == {"a": 1, "b": 2}

    def test_to_dict_nested(self):
        """Test to_dict recursively converts nested AutoNestedDict."""
        d = AutoNestedDict()
        d["level1"]["level2"]["level3"] = "value"
        d["level1"]["other"] = 42

        result = d.to_dict()

        assert isinstance(result, dict)
        assert not isinstance(result, AutoNestedDict)
        assert isinstance(result["level1"], dict)
        assert not isinstance(result["level1"], AutoNestedDict)
        assert result["level1"]["level2"]["level3"] == "value"
        assert result["level1"]["other"] == 42

    def test_to_dict_with_lists(self):
        """Test to_dict handles lists with nested dicts correctly."""
        d = AutoNestedDict()
        d["list"] = [AutoNestedDict({"a": 1}), {"b": 2}, "string", 42]

        result = d.to_dict()

        assert isinstance(result["list"], list)
        assert isinstance(result["list"][0], dict)
        assert not isinstance(result["list"][0], AutoNestedDict)
        assert result["list"][0] == {"a": 1}
        assert result["list"][1] == {"b": 2}
        assert result["list"][2] == "string"
        assert result["list"][3] == 42

    def test_to_dict_deeply_nested_with_lists(self):
        """Test to_dict with complex nested structure including lists."""
        d = AutoNestedDict()
        d["data"]["items"] = [{"nested": {"deep": "value1"}}, {"nested": {"deep": "value2"}}]

        result = d.to_dict()

        assert isinstance(result, dict)
        assert isinstance(result["data"]["items"], list)
        assert isinstance(result["data"]["items"][0], dict)
        assert result["data"]["items"][0]["nested"]["deep"] == "value1"

    def test_convert_dict_to_regular_static_method(self):
        """Test _convert_dict_to_regular static method."""
        auto_dict = AutoNestedDict({"a": 1})
        result = AutoNestedDict._convert_dict_to_regular(auto_dict)
        assert isinstance(result, dict)
        assert not isinstance(result, AutoNestedDict)

        regular_dict = {"b": 2}
        result = AutoNestedDict._convert_dict_to_regular(regular_dict)
        assert result == {"b": 2}

        nested = {"outer": {"inner": "value"}}
        result = AutoNestedDict._convert_dict_to_regular(nested)
        assert result == nested

        list_data = [{"a": 1}, {"b": 2}]
        result = AutoNestedDict._convert_dict_to_regular(list_data)
        assert result == list_data

        assert AutoNestedDict._convert_dict_to_regular(42) == 42
        assert AutoNestedDict._convert_dict_to_regular("string") == "string"

    def test_mixed_operations(self):
        """Test combination of auto-creation, conversion, and serialization."""
        d = AutoNestedDict()

        # Auto-create nested structure
        d["config"]["database"]["host"] = "localhost"
        d["config"]["database"]["port"] = 5432

        d["settings"] = {"debug": True, "nested": {"value": 123}}

        assert isinstance(d["config"]["database"], AutoNestedDict)
        assert isinstance(d["settings"], AutoNestedDict)
        assert isinstance(d["settings"]["nested"], AutoNestedDict)

        result = d.to_dict()

        assert not isinstance(result, AutoNestedDict)
        assert result["config"]["database"]["host"] == "localhost"
        assert result["settings"]["nested"]["value"] == 123

    def test_roundtrip_conversion(self):
        """Test converting regular dict to AutoNestedDict and back."""
        original = {"level1": {"level2": {"data": [1, 2, {"nested": "value"}]}}, "simple": "value"}

        auto_dict = AutoNestedDict.convert_dict(original)

        result = auto_dict.to_dict()

        assert result == original

    def test_empty_autodict_to_dict(self):
        """Test to_dict on empty AutoNestedDict."""
        d = AutoNestedDict()
        result = d.to_dict()

        assert result == {}
        assert isinstance(result, dict)
        assert not isinstance(result, AutoNestedDict)


class TestWorkflowInitialization:
    """Test suite for Workflow class initialization."""

    def test_workflow_default_initialization(self):
        """Test Workflow initialization with default parameters."""
        workflow = Workflow()

        assert workflow.name is not None
        assert workflow.name.startswith("workflow_")
        assert isinstance(workflow._config, AutoNestedDict)
        assert workflow._node_counter == 0
        assert workflow._last_node is None
        assert workflow._temp_files == []
        assert workflow._node_builders == {}
        assert workflow._messages == []
        assert workflow._is_existing_task is False

    def test_workflow_with_custom_name(self):
        """Test Workflow initialization with custom name."""
        workflow = Workflow("my_custom_workflow")

        assert workflow.name == "my_custom_workflow"

    def test_workflow_default_config_structure(self):
        """Test default configuration structure."""
        workflow = Workflow()

        assert "graph_config" in workflow._config
        assert "data_config" in workflow._config
        assert "output_config" in workflow._config

        assert "nodes" in workflow._config["graph_config"]
        assert "edges" in workflow._config["graph_config"]
        assert "graph_properties" in workflow._config["graph_config"]

        assert isinstance(workflow._config, AutoNestedDict)

        assert isinstance(workflow._config["graph_config"], dict)
        assert not isinstance(workflow._config["graph_config"], AutoNestedDict)
        assert isinstance(workflow._config["graph_config"]["nodes"], dict)
        assert isinstance(workflow._config["graph_config"]["edges"], list)

    def test_workflow_feature_flags(self):
        """Test that feature support flags are initialized correctly."""
        workflow = Workflow()

        assert workflow._supports_subgraphs is True
        assert workflow._supports_multimodal is True
        assert workflow._supports_resumable is True
        assert workflow._supports_quality is True
        assert workflow._supports_oasst is True

    def test_workflow_config_is_autodict(self):
        """Test that workflow config is AutoNestedDict."""
        workflow = Workflow()

        assert isinstance(workflow._config, AutoNestedDict)

        workflow._config["new"]["nested"]["key"] = "value"
        assert workflow._config["new"]["nested"]["key"] == "value"

    def test_workflow_unique_names(self):
        """Test that default workflow names are unique."""
        workflow1 = Workflow()
        workflow2 = Workflow()

        assert workflow1.name != workflow2.name

    def test_workflow_name_generation_format(self):
        """Test that generated names follow expected format."""
        workflow = Workflow()

        assert workflow.name.startswith("workflow_")
        suffix = workflow.name.replace("workflow_", "")
        assert len(suffix) == 8
        assert all(c in "0123456789abcdef" for c in suffix)


class TestCreateGraph:
    """Test suite for create_graph factory function."""

    def test_create_graph_returns_workflow(self):
        """Test that create_graph returns a Workflow instance."""
        graph = create_graph("test_graph")

        assert isinstance(graph, Workflow)

    def test_create_graph_with_name(self):
        """Test create_graph sets the workflow name correctly."""
        graph = create_graph("my_graph")

        assert graph.name == "my_graph"

    def test_create_graph_initializes_properly(self):
        """Test that create_graph creates properly initialized Workflow."""
        graph = create_graph("test")

        assert isinstance(graph._config, AutoNestedDict)
        assert graph._node_counter == 0
        assert graph._last_node is None
        assert graph._is_existing_task is False


class TestWorkflowIntegration:
    """Integration tests combining multiple features."""

    def test_workflow_config_manipulation(self):
        """Test manipulating workflow configuration through AutoNestedDict."""
        workflow = Workflow("integration_test")

        workflow._config["graph_config"]["nodes"]["node1"] = {"type": "llm", "model": "gpt-4"}

        workflow._config["graph_config"]["edges"].append({"from": "START", "to": "node1"})

        assert isinstance(workflow._config["graph_config"]["nodes"]["node1"], dict)
        assert not isinstance(workflow._config["graph_config"]["nodes"]["node1"], AutoNestedDict)
        assert workflow._config["graph_config"]["nodes"]["node1"]["type"] == "llm"
        assert len(workflow._config["graph_config"]["edges"]) == 1

        workflow._config["new_section"] = {"nested": {"deep": "value"}}
        assert isinstance(workflow._config["new_section"], AutoNestedDict)
        assert isinstance(workflow._config["new_section"]["nested"], AutoNestedDict)

    def test_workflow_nodes_dict_behavior(self):
        """Test the nuanced behavior of nodes dict vs AutoNestedDict."""
        workflow = Workflow("test")

        # nodes starts as a regular dict (set during __init__)
        nodes_dict = workflow._config["graph_config"]["nodes"]
        assert isinstance(nodes_dict, dict)
        assert not isinstance(nodes_dict, AutoNestedDict)

        workflow._config["graph_config"]["nodes"]["node1"] = {"type": "test"}

        assert isinstance(workflow._config["graph_config"]["nodes"]["node1"], dict)
        assert not isinstance(workflow._config["graph_config"]["nodes"]["node1"], AutoNestedDict)

        workflow._config["custom_nodes"]["node2"]["nested"]["deep"]["value"] = 42
        assert isinstance(workflow._config["custom_nodes"], AutoNestedDict)
        assert isinstance(workflow._config["custom_nodes"]["node2"], AutoNestedDict)
        assert workflow._config["custom_nodes"]["node2"]["nested"]["deep"]["value"] == 42

    def test_workflow_config_to_dict_conversion(self):
        """Test converting workflow config to regular dict."""
        workflow = Workflow("test")

        # Add some configuration
        workflow._config["graph_config"]["nodes"]["test_node"] = {
            "type": "processor",
            "settings": {"param": "value"},
        }

        # Convert to dict
        config_dict = workflow._config.to_dict()

        assert isinstance(config_dict, dict)
        assert not isinstance(config_dict, AutoNestedDict)
        assert config_dict["graph_config"]["nodes"]["test_node"]["type"] == "processor"

    def test_workflow_with_complex_nested_config(self):
        """Test workflow with deeply nested configuration."""
        workflow = Workflow("complex")

        workflow._config["custom_data"]["source"]["type"] = "disk"
        workflow._config["custom_data"]["source"]["params"]["path"] = "/data/input.json"

        workflow._config["graph_config"]["nodes"]["node1"] = {
            "model": {"config": {"temperature": 0.7, "max_tokens": 100}}
        }

        assert isinstance(workflow._config["custom_data"], AutoNestedDict)
        assert isinstance(workflow._config["custom_data"]["source"]["params"], AutoNestedDict)

        assert isinstance(workflow._config["graph_config"], dict)
        assert isinstance(workflow._config["data_config"], dict)
        assert isinstance(workflow._config["graph_config"]["nodes"], dict)
        assert isinstance(workflow._config["graph_config"]["nodes"]["node1"], dict)

        assert (
            workflow._config["graph_config"]["nodes"]["node1"]["model"]["config"]["temperature"]
            == 0.7
        )
        assert workflow._config["custom_data"]["source"]["params"]["path"] == "/data/input.json"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_autodict_with_none_values(self):
        """Test AutoNestedDict handles None values correctly."""
        d = AutoNestedDict()
        d["key"] = None

        assert d["key"] is None
        assert d.to_dict() == {"key": None}

    def test_autodict_with_empty_list(self):
        """Test AutoNestedDict handles empty lists."""
        d = AutoNestedDict({"empty": []})

        assert d["empty"] == []
        assert d.to_dict() == {"empty": []}

    def test_autodict_with_empty_nested_dict(self):
        """Test AutoNestedDict with empty nested dictionaries."""
        d = AutoNestedDict({"outer": {"inner": {}}})

        result = d.to_dict()
        assert result == {"outer": {"inner": {}}}

    def test_workflow_with_empty_name(self):
        """Test Workflow with empty string name generates default name."""
        workflow = Workflow("")

        assert workflow.name.startswith("workflow_")

    def test_autodict_overwrite_existing_key(self):
        """Test overwriting existing keys in AutoNestedDict."""
        d = AutoNestedDict({"key": "old_value"})
        d["key"] = "new_value"

        assert d["key"] == "new_value"

    def test_autodict_list_with_autodicts(self):
        """Test list containing AutoNestedDict instances."""
        d1 = AutoNestedDict({"a": 1})
        d2 = AutoNestedDict({"b": 2})

        container = AutoNestedDict()
        container["list"] = [d1, d2]

        result = container.to_dict()
        assert result["list"] == [{"a": 1}, {"b": 2}]
        assert not isinstance(result["list"][0], AutoNestedDict)

    def test_autodict_init_vs_setitem_conversion(self):
        """Test the difference between __init__ and __setitem__ for dict conversion."""
        d1 = AutoNestedDict({"level1": {"level2": "value"}})
        assert isinstance(d1, AutoNestedDict)
        assert isinstance(d1["level1"], dict)
        assert not isinstance(d1["level1"], AutoNestedDict)

        d2 = AutoNestedDict()
        d2["level1"] = {"level2": "value"}
        assert isinstance(d2, AutoNestedDict)
        assert isinstance(d2["level1"], AutoNestedDict)
        assert isinstance(d2["level1"]["level2"], str)

        d3 = AutoNestedDict.convert_dict({"level1": {"level2": "value"}})
        assert isinstance(d3, AutoNestedDict)
        assert isinstance(d3["level1"], AutoNestedDict)
