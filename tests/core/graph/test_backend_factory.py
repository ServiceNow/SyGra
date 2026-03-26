import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from sygra.core.graph.backend_factory import BackendFactory


class TestBackendFactoryIsABC(unittest.TestCase):
    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            BackendFactory()

    def test_has_all_abstract_methods(self):
        abstract_methods = {
            "create_lambda_runnable",
            "create_llm_runnable",
            "create_multi_llm_runnable",
            "create_weighted_sampler_runnable",
            "create_connector_runnable",
            "build_workflow",
            "get_message_content",
            "convert_to_chat_format",
            "get_test_message",
        }
        self.assertEqual(BackendFactory.__abstractmethods__, abstract_methods)

    def test_concrete_subclass_can_be_instantiated(self):
        class ConcreteFactory(BackendFactory):
            def create_lambda_runnable(self, exec_wrapper, async_func=True):
                return None

            def create_llm_runnable(self, exec_wrapper):
                return None

            def create_multi_llm_runnable(self, llm_dict, post_process):
                return None

            def create_weighted_sampler_runnable(self, exec_wrapper):
                return None

            def create_connector_runnable(self):
                return None

            def build_workflow(self, graph_config):
                return None

            def get_message_content(self, msg):
                return ""

            def convert_to_chat_format(self, msgs):
                return []

            def get_test_message(self, model_config):
                return None

        factory = ConcreteFactory()
        self.assertIsInstance(factory, BackendFactory)


if __name__ == "__main__":
    unittest.main()
