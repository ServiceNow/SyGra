import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the parent directory to sys.path to import the necessary modules
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from sygra.core.models.custom_models import (
    CustomAzure,
    CustomClaudeProxy,
    CustomGeminiProxy,
    CustomMistralAPI,
    CustomOllama,
    CustomOpenAI,
    CustomTGI,
    CustomTriton,
    CustomVLLM,
)
from sygra.core.models.langgraph.openai_chat_model import CustomOpenAIChatModel
from sygra.core.models.langgraph.vllm_chat_model import CustomVLLMChatModel
from sygra.core.models.lite_llm.azure_model import CustomAzure as CustomLiteLLMAzure
from sygra.core.models.lite_llm.azure_openai_model import (
    CustomAzureOpenAI as CustomLiteLLMAzureOpenAI,
)
from sygra.core.models.lite_llm.bedrock_model import CustomBedrock as CustomLiteLLMBedrock
from sygra.core.models.lite_llm.ollama_model import CustomOllama as CustomLiteLLMOllama
from sygra.core.models.lite_llm.openai_model import CustomOpenAI as CustomLiteLLMOpenAI
from sygra.core.models.lite_llm.triton_model import CustomTriton as CustomLiteLLMTriton
from sygra.core.models.lite_llm.vertex_ai_model import CustomVertexAI as CustomLiteLLMVertexAI
from sygra.core.models.lite_llm.vllm_model import CustomVLLM as CustomLiteLLMVLLM
from sygra.core.models.model_factory import ModelFactory


class TestModelFactory(unittest.TestCase):
    """Unit tests for the ModelFactory class"""

    @patch("sygra.utils.utils.load_model_config")
    def test_update_model_config(self, mock_load_model_config):
        """Test _update_model_config static method"""
        # Mock the global model config
        mock_load_model_config.return_value = {
            "test_model": {
                "model_type": "vllm",
                "parameters": {"temperature": 0.7, "max_tokens": 100},
                "url": "http://test-url.com",
            }
        }

        # Test model config update
        model_config = {"name": "test_model", "parameters": {"temperature": 0.8}}
        updated_config = ModelFactory._update_model_config(model_config)

        # Verify the config was updated correctly
        self.assertEqual(updated_config["model_type"], "vllm")
        self.assertEqual(
            updated_config["parameters"]["temperature"], 0.8
        )  # Should use the provided value
        self.assertEqual(
            updated_config["parameters"]["max_tokens"], 100
        )  # Should retain the global value
        self.assertEqual(
            updated_config["url"], "http://test-url.com"
        )  # Should retain the global value

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_update_model_config_with_nested_dict(self, mock_validate, mock_load_model_config):
        """Test _update_model_config with nested dictionary values"""
        # Mock the global model config
        mock_load_model_config.return_value = {
            "test_model": {
                "model_type": "vllm",
                "parameters": {"temperature": 0.7, "max_tokens": 100},
                "additional_params": {"param1": "value1", "param2": "value2"},
            }
        }

        # Test model config update with nested dict
        model_config = {
            "name": "test_model",
            "parameters": {"temperature": 0.8},
            "additional_params": {"param1": "new_value"},
        }

        updated_config = ModelFactory._update_model_config(model_config)

        # Verify nested dictionary was updated correctly
        self.assertEqual(updated_config["additional_params"]["param1"], "new_value")
        self.assertEqual(updated_config["additional_params"]["param2"], "value2")

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_model_vllm(self, mock_validate, mock_load_model_config):
        """Test create_model with VLLM model type"""
        mock_load_model_config.return_value = {
            "test_vllm": {
                "model_type": "vllm",
                "url": "http://vllm-test.com",
                "auth_token": "test-token",
                "parameters": {},
            }
        }

        with patch.object(CustomVLLM, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_vllm", "model_type": "vllm"}
            ModelFactory.create_model(model_config, backend="custom")
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_litellm_model_vllm(self, mock_validate, mock_load_model_config):
        """Test create_model with VLLM model type"""
        mock_load_model_config.return_value = {
            "test_vllm": {
                "model_type": "vllm",
                "url": "http://vllm-test.com",
                "auth_token": "test-token",
                "parameters": {},
            }
        }

        with patch.object(CustomLiteLLMVLLM, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_vllm", "model_type": "vllm"}
            ModelFactory.create_model(model_config)
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_model_mistralai(self, mock_validate, mock_load_model_config):
        """Test create_model with MistralAI model type"""
        mock_load_model_config.return_value = {
            "test_mistral": {
                "model_type": "mistralai",
                "url": "http://mistral-test.com",
                "auth_token": "test-token",
                "parameters": {},
            }
        }

        with patch.object(CustomMistralAPI, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_mistral", "model_type": "mistralai"}
            ModelFactory.create_model(model_config)
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_model_tgi(self, mock_validate, mock_load_model_config):
        """Test create_model with TGI model type"""
        mock_load_model_config.return_value = {
            "test_tgi": {
                "model_type": "tgi",
                "url": "http://tgi-test.com",
                "auth_token": "test-token",
                "parameters": {},
            }
        }

        with patch.object(CustomTGI, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_tgi", "model_type": "tgi"}
            ModelFactory.create_model(model_config)
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_model_azure(self, mock_validate, mock_load_model_config):
        """Test create_model with Azure model type"""
        mock_load_model_config.return_value = {
            "test_azure": {
                "model_type": "azure",
                "url": "http://azure-test.com",
                "auth_token": "test-token",
                "parameters": {},
            }
        }

        with patch.object(CustomAzure, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_azure", "model_type": "azure"}
            ModelFactory.create_model(model_config, backend="custom")
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_litellm_model_azure(self, mock_validate, mock_load_model_config):
        """Test create_model with Azure model type"""
        mock_load_model_config.return_value = {
            "test_azure": {
                "model_type": "azure",
                "url": "http://azure-test.com",
                "auth_token": "test-token",
                "parameters": {},
            }
        }

        with patch.object(CustomLiteLLMAzure, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_azure", "model_type": "azure"}
            ModelFactory.create_model(model_config)
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_model_openai(self, mock_validate, mock_load_model_config):
        """Test create_model with OpenAI model type"""
        mock_load_model_config.return_value = {
            "test_openai": {
                "model_type": "azure_openai",
                "url": "http://openai-test.com",
                "api_key": "test-key",
                "api_version": "2023-05-15",
                "model": "gpt-4",
                "parameters": {},
            }
        }

        with patch.object(CustomOpenAI, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_openai", "model_type": "azure_openai"}
            ModelFactory.create_model(model_config, backend="custom")
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_litellm_model_azure_openai(self, mock_validate, mock_load_model_config):
        """Test create_model with OpenAI model type"""
        mock_load_model_config.return_value = {
            "test_openai": {
                "model_type": "azure_openai",
                "url": "http://openai-test.com",
                "api_key": "test-key",
                "api_version": "2023-05-15",
                "model": "gpt-4",
                "parameters": {},
            }
        }

        with patch.object(CustomLiteLLMAzureOpenAI, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_openai", "model_type": "azure_openai"}
            ModelFactory.create_model(model_config)
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_litellm_model_openai(self, mock_validate, mock_load_model_config):
        """Test create_model with OpenAI model type"""
        mock_load_model_config.return_value = {
            "test_openai": {
                "model_type": "openai",
                "url": "http://openai-test.com",
                "api_key": "test-key",
                "api_version": "2023-05-15",
                "model": "gpt-4",
                "parameters": {},
            }
        }

        with patch.object(CustomLiteLLMOpenAI, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_openai", "model_type": "openai"}
            ModelFactory.create_model(model_config)
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    def test_create_model_ollama(self, mock_load_model_config):
        """Test create_model with Ollama model type"""
        mock_load_model_config.return_value = {
            "test_ollama": {"model_type": "ollama", "parameters": {}}
        }

        with patch.object(CustomOllama, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_ollama", "model_type": "ollama"}
            ModelFactory.create_model(model_config, backend="custom")
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    def test_create_litellm_model_ollama(self, mock_load_model_config):
        """Test create_model with Ollama model type"""
        mock_load_model_config.return_value = {
            "test_ollama": {"model_type": "ollama", "parameters": {}}
        }

        with patch.object(CustomLiteLLMOllama, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_ollama", "model_type": "ollama"}
            ModelFactory.create_model(model_config)
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    def test_create_model_triton(self, mock_load_model_config):
        """Test create_model with Triton model type"""
        mock_load_model_config.return_value = {
            "test_triton": {
                "model_type": "triton",
                "url": "http://triton-test.com",
                "auth_token": "test-token",
                "payload_key": "default",
                "parameters": {},
            }
        }

        with patch.object(CustomTriton, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_triton", "model_type": "triton"}
            ModelFactory.create_model(model_config, backend="custom")
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    def test_create_litellm_model_triton(self, mock_load_model_config):
        """Test create_model with Triton model type"""
        mock_load_model_config.return_value = {
            "test_triton": {
                "model_type": "triton",
                "url": "http://triton-test.com",
                "auth_token": "test-token",
                "payload_key": "default",
                "parameters": {},
            }
        }

        with patch.object(CustomLiteLLMTriton, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_triton", "model_type": "triton"}
            ModelFactory.create_model(model_config)
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_litellm_model_bedrock(self, mock_validate, mock_load_model_config):
        """Test create_model with Bedrock model type (LiteLLM backend)"""
        mock_load_model_config.return_value = {
            "test_bedrock": {
                "model_type": "bedrock",
                "parameters": {},
                "aws_access_key_id": "AKIAxxx",
                "aws_secret_access_key": "secret",
                "aws_region_name": "us-east-1",
            }
        }

        with patch.object(CustomLiteLLMBedrock, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_bedrock", "model_type": "bedrock"}
            ModelFactory.create_model(model_config)
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_litellm_model_vertex_ai(self, mock_validate, mock_load_model_config):
        """Test create_model with Vertex AI model type (LiteLLM backend)"""
        mock_load_model_config.return_value = {
            "test_vertex": {
                "model_type": "vertex_ai",
                "parameters": {},
                "vertex_project": "my-gcp-project",
                "vertex_location": "us-central1",
                "vertex_credentials": {"type": "service_account", "client_email": "svc@x"},
            }
        }

        with patch.object(CustomLiteLLMVertexAI, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_vertex", "model_type": "vertex_ai"}
            ModelFactory.create_model(model_config)
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_model_langgraph_vllm(self, mock_validate, mock_load_model_config):
        """Test create_model with VLLM model type for langgraph backend"""
        mock_load_model_config.return_value = {
            "test_vllm": {
                "model_type": "vllm",
                "url": "http://vllm-test.com",
                "auth_token": "test-token",
                "parameters": {},
            }
        }

        with patch.object(CustomVLLMChatModel, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_vllm", "model_type": "vllm"}
            ModelFactory.create_model(model_config, "langgraph")
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_model_langgraph_openai(self, mock_validate, mock_load_model_config):
        """Test create_model with OpenAI model type for langgraph backend"""
        mock_load_model_config.return_value = {
            "test_openai": {
                "model_type": "azure_openai",
                "url": "http://openai-test.com",
                "api_key": "test-key",
                "api_version": "2023-05-15",
                "model": "gpt-4",
                "parameters": {},
            }
        }

        with patch.object(CustomOpenAIChatModel, "__init__", return_value=None) as mock_init:
            model_config = {"name": "test_openai", "model_type": "azure_openai"}
            ModelFactory.create_model(model_config, "langgraph")
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_model_unsupported_type(self, mock_validate, mock_load_model_config):
        """Test create_model with unsupported model type"""
        mock_load_model_config.return_value = {
            "test_unsupported": {
                "model_type": "unsupported",
                "url": "http://test.com",
                "auth_token": "test-token",
                "parameters": {},
            }
        }

        model_config = {"name": "test_unsupported", "model_type": "unsupported"}
        with self.assertRaises(NotImplementedError):
            ModelFactory.create_model(model_config)

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_error_message_for_invalid_model_custom_backend(
        self, mock_validate, mock_load_model_config
    ):
        """When backend is 'custom' and model type is unsupported, the error log should not repeat 'custom'."""
        mock_load_model_config.return_value = {
            "bad_model": {
                "model_type": "unsupported",
                "parameters": {},
            }
        }
        model_config = {"name": "bad_model", "model_type": "unsupported"}

        with patch("sygra.core.models.model_factory.logger.error") as mock_error:
            with self.assertRaises(NotImplementedError):
                ModelFactory.create_model(model_config, backend="custom")

            mock_error.assert_called_once()
            msg = mock_error.call_args[0][0]
            self.assertEqual(
                "No model implementation for unsupported found for backend(s): custom.", msg
            )

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_error_message_invalid_model_litellm_and_custom(
        self, mock_validate, mock_load_model_config
    ):
        """When backend is 'litellm' and no implementation exists in either mapping, error should list 'litellm, custom'."""
        mock_load_model_config.return_value = {
            "bad_model": {
                "model_type": "unsupported",
                "parameters": {},
            }
        }
        model_config = {"name": "bad_model", "model_type": "unsupported"}

        with patch("sygra.core.models.model_factory.logger.error") as mock_error:
            with self.assertRaises(NotImplementedError):
                ModelFactory.create_model(model_config)

            mock_error.assert_called_once()
            msg = mock_error.call_args[0][0]
            self.assertIn(
                "No model implementation for unsupported found for backend(s): litellm, custom.",
                msg,
            )

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_model_unsupported_backend(self, mock_validate, mock_load_model_config):
        """Test create_model with unsupported backend"""
        mock_load_model_config.return_value = {
            "test_model": {
                "model_type": "vllm",
                "url": "http://test.com",
                "auth_token": "test-token",
                "parameters": {},
            }
        }

        model_config = {"name": "test_model", "model_type": "vllm"}
        with self.assertRaises(NotImplementedError):
            ModelFactory.create_model(model_config, "unsupported_backend")

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    @patch("langchain_core.runnables.RunnableLambda")
    def test_get_default_model(self, mock_runnable, mock_validate, mock_load_model_config):
        """Test get_model method"""
        mock_load_model_config.return_value = {
            "test_model": {
                "model_type": "vllm",
                "url": "http://test.com",
                "auth_token": "test-token",
                "parameters": {},
            }
        }

        # Mock the model instance
        mock_model = MagicMock()
        with patch.object(ModelFactory, "create_model", return_value=mock_model) as mock_create:
            model_config = {"name": "test_model", "model_type": "vllm"}
            ModelFactory.get_model(model_config, "default")

            # Verify create_model was called
            mock_create.assert_called_once_with(model_config, "default")

            # Verify RunnableLambda was called
            mock_runnable.assert_called()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    @patch("langchain_core.runnables.RunnableLambda")
    def test_get_litellm_model(self, mock_runnable, mock_validate, mock_load_model_config):
        """Test get_model method"""
        mock_load_model_config.return_value = {
            "test_model": {
                "model_type": "vllm",
                "url": "http://test.com",
                "auth_token": "test-token",
                "parameters": {},
            }
        }

        # Mock the model instance
        mock_model = MagicMock()
        with patch.object(ModelFactory, "create_model", return_value=mock_model) as mock_create:
            model_config = {"name": "test_model", "model_type": "vllm"}
            ModelFactory.get_model(model_config)

            # Verify create_model was called
            mock_create.assert_called_once_with(model_config, "litellm")

            # Verify RunnableLambda was called
            mock_runnable.assert_called()

    # ============================================================================
    # PROXY BACKEND TESTS
    # ============================================================================

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_model_claude_proxy(self, mock_validate, mock_load_model_config):
        """Test create_model with claude_proxy model type and proxy backend"""
        mock_load_model_config.return_value = {
            "claude_large": {
                "model_type": "claude_proxy",
                "client_type": "http",
                "backend": "proxy",
                "url": "http://claude-proxy.com",
                "auth_token": None,
                "parameters": {"maxTokens": 2500},
            }
        }

        with patch.object(CustomClaudeProxy, "__init__", return_value=None) as mock_init:
            model_config = {"name": "claude_large", "model_type": "claude_proxy"}
            ModelFactory.create_model(model_config, backend="proxy")
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_model_gemini_proxy(self, mock_validate, mock_load_model_config):
        """Test create_model with gemini_proxy model type and proxy backend"""
        mock_load_model_config.return_value = {
            "gemini_2.5_proxy": {
                "model_type": "gemini_proxy",
                "client_type": "http",
                "backend": "proxy",
                "url": "http://gemini-proxy.com",
                "auth_token": None,
                "parameters": {"maxOutputTokens": 2500},
            }
        }

        with patch.object(CustomGeminiProxy, "__init__", return_value=None) as mock_init:
            model_config = {"name": "gemini_2.5_proxy", "model_type": "gemini_proxy"}
            ModelFactory.create_model(model_config, backend="proxy")
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_proxy_model_not_available_in_litellm_backend(
        self, mock_validate, mock_load_model_config
    ):
        """Test that proxy models are not available in litellm backend"""
        mock_load_model_config.return_value = {
            "claude_large": {
                "model_type": "claude_proxy",
                "url": "http://claude-proxy.com",
                "parameters": {},
            }
        }

        model_config = {"name": "claude_large", "model_type": "claude_proxy"}

        # Should raise NotImplementedError when trying to use proxy model with litellm backend
        with self.assertRaises(NotImplementedError) as context:
            ModelFactory.create_model(model_config, backend="litellm")

        self.assertIn("claude_proxy", str(context.exception))
        self.assertIn("litellm", str(context.exception))

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_proxy_model_not_available_in_custom_backend(
        self, mock_validate, mock_load_model_config
    ):
        """Test that proxy models are not available in custom backend"""
        mock_load_model_config.return_value = {
            "gemini_2.5_proxy": {
                "model_type": "gemini_proxy",
                "url": "http://gemini-proxy.com",
                "parameters": {},
                "backend": "custom",
            }
        }

        model_config = {"name": "gemini_2.5_proxy", "model_type": "gemini_proxy"}

        # Should raise NotImplementedError when trying to use proxy model with custom backend
        with self.assertRaises(NotImplementedError) as context:
            ModelFactory.create_model(model_config, backend="custom")

        self.assertIn("gemini_proxy", str(context.exception))
        self.assertIn("custom", str(context.exception))

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_proxy_model_not_available_in_langgraph_backend(
        self, mock_validate, mock_load_model_config
    ):
        """Test that proxy models are not available in langgraph backend"""
        mock_load_model_config.return_value = {
            "claude_large": {
                "model_type": "claude_proxy",
                "url": "http://claude-proxy.com",
                "parameters": {},
                "backend": "langgraph",
            }
        }

        model_config = {"name": "claude_large", "model_type": "claude_proxy"}

        # Should raise NotImplementedError for langgraph backend
        with self.assertRaises(NotImplementedError) as context:
            ModelFactory.create_model(model_config, backend="langgraph")

        self.assertIn("claude_proxy", str(context.exception))

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_backend_override_from_model_config(self, mock_validate, mock_load_model_config):
        """Test that backend in model_config overrides the parameter"""
        mock_load_model_config.return_value = {
            "claude_large": {
                "model_type": "claude_proxy",
                "client_type": "http",
                "backend": "proxy",  # Backend in config
                "url": "http://claude-proxy.com",
                "parameters": {},
            }
        }

        with patch.object(CustomClaudeProxy, "__init__", return_value=None) as mock_init:
            model_config = {
                "name": "claude_large",
                "model_type": "claude_proxy",
                "client_type": "http",
                "backend": "proxy",
            }
            # Pass different backend as parameter, but config should override
            ModelFactory.create_model(model_config, backend="litellm")
            mock_init.assert_called_once()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_create_model_claude_proxy_with_additional_params(
        self, mock_validate, mock_load_model_config
    ):
        """Test create_model for claude_proxy with additional_params (no auth_token needed)"""
        mock_load_model_config.return_value = {
            "claude_large": {
                "model_type": "claude_proxy",
                "client_type": "http",
                "backend": "proxy",
                "url": "http://claude-proxy.com",
                "parameters": {"maxTokens": 2500, "temperature": 0},
                "additional_params": {
                    "thinking": {"type": "disabled"},
                    "anthropic_beta": ["computer-use-2025-01-24"],
                },
            }
        }

        with patch.object(CustomClaudeProxy, "__init__", return_value=None) as mock_init:
            model_config = {"name": "claude_large", "model_type": "claude_proxy"}
            ModelFactory.create_model(model_config, backend="proxy")

            # Verify the model was initialized
            mock_init.assert_called_once()

            # Get the actual config passed to __init__
            call_args = mock_init.call_args[0][0]
            self.assertEqual(call_args["model_type"], "claude_proxy")
            self.assertIn("additional_params", call_args)

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    @patch("langchain_core.runnables.RunnableLambda")
    def test_get_model_with_proxy_backend(
        self, mock_runnable, mock_validate, mock_load_model_config
    ):
        """Test get_model method with proxy backend (no auth_token required)"""
        mock_load_model_config.return_value = {
            "claude_large": {
                "model_type": "claude_proxy",
                "backend": "proxy",
                "url": "http://claude-proxy.com",
                "parameters": {},
            }
        }

        # Mock the model instance
        mock_model = MagicMock()
        with patch.object(ModelFactory, "create_model", return_value=mock_model) as mock_create:
            model_config = {"name": "claude_large", "model_type": "claude_proxy"}
            ModelFactory.get_model(model_config, "proxy")

            # Verify create_model was called with proxy backend
            mock_create.assert_called_once_with(model_config, "proxy")

            # Verify RunnableLambda was called
            mock_runnable.assert_called()

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_proxy_backend_without_client_type_should_fail(
        self, mock_validate, mock_load_model_config
    ):
        """Test that proxy backend without client_type=http raises error during model usage"""
        mock_load_model_config.return_value = {
            "claude_large": {
                "model_type": "claude_proxy",
                # Missing client_type - should cause error when client is created
                "backend": "proxy",
                "url": "http://claude-proxy.com",
                "parameters": {},
            }
        }

        # The error will occur when the model tries to create a client
        model_config = {"name": "claude_large", "model_type": "claude_proxy"}

        with patch.object(CustomClaudeProxy, "__init__") as mock_init:
            # Mock the init to raise an error about missing client_type
            mock_init.side_effect = ValueError("client_type=http is required for backend=proxy")

            with self.assertRaises(ValueError) as context:
                ModelFactory.create_model(model_config, backend="proxy")

            self.assertIn("client_type", str(context.exception))

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_error_message_for_invalid_proxy_model(self, mock_validate, mock_load_model_config):
        """Test error message when proxy model type doesn't exist"""
        mock_load_model_config.return_value = {
            "invalid_proxy": {
                "model_type": "invalid_proxy",
                "backend": "proxy",
                "parameters": {},
            }
        }
        model_config = {"name": "invalid_proxy", "model_type": "invalid_proxy"}

        with patch("sygra.core.models.model_factory.logger.error") as mock_error:
            with self.assertRaises(NotImplementedError):
                ModelFactory.create_model(model_config, backend="proxy")

            mock_error.assert_called_once()
            msg = mock_error.call_args[0][0]
            self.assertIn(
                "No model implementation for invalid_proxy found for backend(s): proxy", msg
            )

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.utils.validate_required_keys")
    def test_missing_required_keys(self, mock_validate, mock_load_model_config):
        """Test handling of missing required keys"""
        mock_load_model_config.return_value = {}

        # Set up validate_required_keys to raise ValueError
        mock_validate.side_effect = ValueError("Missing required key")

        with self.assertRaises(ValueError):
            ModelFactory.create_model({"name": "test_model"})

    @patch("sygra.utils.utils.load_model_config")
    @patch("sygra.utils.constants.BACKEND", "langgraph")
    def test_agent_node_model_initialization(self, mock_load_model_config):
        """Test that AgentNode uses the correct model type based on backend"""
        from sygra.core.graph.nodes.agent_node import AgentNode

        # Mock model config loading
        mock_load_model_config.return_value = {
            "test_model": {
                "model_type": "vllm",
                "url": "http://test.com",
                "auth_token": "test-token",
                "parameters": {},
            }
        }

        # Mock create_model to verify it gets called with the right parameters
        with patch.object(ModelFactory, "create_model", return_value=MagicMock()) as mock_create:
            # Create an agent node with minimal config
            node_config = {"model": {"name": "test_model"}, "prompt": "test prompt"}

            # Patch any other required methods that might be called during initialization
            with patch("sygra.utils.utils.get_graph_factory", return_value=MagicMock()):
                with patch("sygra.utils.utils.get_func_from_str", return_value=MagicMock()):
                    with patch("sygra.utils.utils.get_graph_properties", return_value={}):
                        AgentNode("test_node", node_config)

                        # Verify create_model was called with langgraph backend
                        mock_create.assert_called_with({"name": "test_model"}, "langgraph")


if __name__ == "__main__":
    unittest.main()
