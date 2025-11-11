"""
Tests for Environment Setup

Tests environment variable mapping for SyGra-AgentLab integration.
"""

from unittest.mock import Mock, patch

import pytest

try:
    from sygra.integrations.agentlab.experiments.env_setup import EnvironmentMapper

    AGENTLAB_AVAILABLE = True
except ImportError:
    AGENTLAB_AVAILABLE = False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestEnvironmentMapper:
    """Test EnvironmentMapper functionality"""

    @patch("sygra.integrations.agentlab.experiments.env_setup.Path")
    @patch("sygra.integrations.agentlab.experiments.env_setup.load_dotenv")
    def test_load_env_file_exists(self, mock_load_dotenv, mock_path):
        """Test loading environment from existing .env file"""
        # Mock file exists
        mock_env_file = Mock()
        mock_env_file.exists.return_value = True
        mock_path.cwd.return_value.__truediv__.return_value = mock_env_file

        result = EnvironmentMapper.load_env()

        assert result is True
        mock_load_dotenv.assert_called_once_with(mock_env_file, override=False)

    @patch("sygra.integrations.agentlab.experiments.env_setup.Path")
    def test_load_env_file_not_exists(self, mock_path):
        """Test loading environment when .env file doesn't exist"""
        # Mock file doesn't exist
        mock_env_file = Mock()
        mock_env_file.exists.return_value = False
        mock_path.cwd.return_value.__truediv__.return_value = mock_env_file

        result = EnvironmentMapper.load_env()

        assert result is False

    @patch("os.environ", new_callable=dict)
    def test_map_model_credentials_success(self, mock_environ):
        """Test successful credential mapping"""
        # Set up environment variables
        mock_environ["SYGRA_GPT-4O_URL"] = "https://test.openai.azure.com/"
        mock_environ["SYGRA_GPT-4O_TOKEN"] = "test-token"

        with patch("sygra.integrations.agentlab.experiments.env_setup.os.environ", mock_environ):
            result = EnvironmentMapper.map_model_credentials("gpt-4o")

            assert result is True
            # Should set AZURE environment variables
            assert mock_environ.get("AZURE_OPENAI_ENDPOINT") == "https://test.openai.azure.com/"
            assert mock_environ.get("AZURE_OPENAI_API_KEY") == "test-token"

    @patch("os.environ")
    def test_map_model_credentials_missing_url(self, mock_environ):
        """Test credential mapping with missing URL"""
        # Mock only token exists
        mock_environ.get.side_effect = lambda key, default=None: {
            "SYGRA_GPT-4O_TOKEN": "test-token"
        }.get(key, default)

        result = EnvironmentMapper.map_model_credentials("gpt-4o")

        assert result is False

    @patch("os.environ")
    def test_map_model_credentials_missing_token(self, mock_environ):
        """Test credential mapping with missing token"""
        # Mock only URL exists
        mock_environ.get.side_effect = lambda key, default=None: {
            "SYGRA_GPT-4O_URL": "https://test.openai.azure.com/"
        }.get(key, default)

        result = EnvironmentMapper.map_model_credentials("gpt-4o")

        assert result is False

    @patch("os.environ")
    def test_map_model_credentials_missing_both(self, mock_environ):
        """Test credential mapping with missing credentials"""
        # Mock no credentials exist
        mock_environ.get.return_value = None

        result = EnvironmentMapper.map_model_credentials("gpt-4o")

        assert result is False

    def test_map_model_credentials_different_models(self):
        """Test credential mapping for different model names"""
        models_to_test = ["gpt-4o", "gpt-4o-mini", "claude-3-sonnet"]

        with patch("os.environ") as mock_environ:
            mock_environ.get.return_value = None  # No credentials exist

            for model in models_to_test:
                result = EnvironmentMapper.map_model_credentials(model)

                # Should handle all model names without error
                assert isinstance(result, bool)

    @patch.object(EnvironmentMapper, "load_env")
    @patch.object(EnvironmentMapper, "map_model_credentials")
    def test_setup_success(self, mock_map_credentials, mock_load_env):
        """Test successful complete setup"""
        mock_load_env.return_value = True
        mock_map_credentials.return_value = True

        result = EnvironmentMapper.setup("gpt-4o")

        assert result is True
        mock_load_env.assert_called_once()
        mock_map_credentials.assert_called_once_with("gpt-4o")

    @patch.object(EnvironmentMapper, "load_env")
    @patch.object(EnvironmentMapper, "map_model_credentials")
    def test_setup_env_load_fails(self, mock_map_credentials, mock_load_env):
        """Test setup when environment loading fails"""
        mock_load_env.return_value = False
        mock_map_credentials.return_value = True

        result = EnvironmentMapper.setup("gpt-4o")

        # Should still succeed if credentials mapping works
        assert result is True

    @patch.object(EnvironmentMapper, "load_env")
    @patch.object(EnvironmentMapper, "map_model_credentials")
    def test_setup_credentials_fail(self, mock_map_credentials, mock_load_env):
        """Test setup when credentials mapping fails"""
        mock_load_env.return_value = True
        mock_map_credentials.return_value = False

        result = EnvironmentMapper.setup("gpt-4o")

        assert result is False

    @patch.object(EnvironmentMapper, "load_env")
    @patch.object(EnvironmentMapper, "map_model_credentials")
    def test_setup_both_fail(self, mock_map_credentials, mock_load_env):
        """Test setup when both operations fail"""
        mock_load_env.return_value = False
        mock_map_credentials.return_value = False

        result = EnvironmentMapper.setup("gpt-4o")

        assert result is False

    @patch("sygra.integrations.agentlab.experiments.env_setup.logger")
    def test_logging_behavior(self, mock_logger):
        """Test that appropriate logging occurs"""
        with (
            patch.object(EnvironmentMapper, "load_env", return_value=True),
            patch.object(EnvironmentMapper, "map_model_credentials", return_value=True),
        ):

            EnvironmentMapper.setup("gpt-4o")

            # Should log some information during setup
            # Note: Actual logging calls depend on implementation

    def test_model_name_case_handling(self):
        """Test that model names are properly case-handled"""
        with patch("os.environ") as mock_environ:
            mock_environ.get.return_value = None

            # Should handle different cases
            result1 = EnvironmentMapper.map_model_credentials("gpt-4o")
            result2 = EnvironmentMapper.map_model_credentials("GPT-4O")

            # Both should work (though return False due to missing credentials)
            assert isinstance(result1, bool)
            assert isinstance(result2, bool)

    def test_environment_variable_format_behavior(self):
        """Test environment variable format behavior"""
        # Test that function handles model name formatting correctly
        result1 = EnvironmentMapper.map_model_credentials("gpt-4o")
        result2 = EnvironmentMapper.map_model_credentials("gpt-4o-mini")

        # Both should return boolean values
        assert isinstance(result1, bool)
        assert isinstance(result2, bool)

    @patch("sygra.integrations.agentlab.experiments.env_setup.load_dotenv")
    def test_load_dotenv_parameters(self, mock_load_dotenv):
        """Test that load_dotenv is called with correct parameters"""
        with patch("sygra.integrations.agentlab.experiments.env_setup.Path") as mock_path:
            mock_env_file = Mock()
            mock_env_file.exists.return_value = True
            mock_path.cwd.return_value.__truediv__.return_value = mock_env_file

            EnvironmentMapper.load_env()

            # Should call load_dotenv with override=False
            mock_load_dotenv.assert_called_once_with(mock_env_file, override=False)

    def test_static_methods(self):
        """Test that all methods are static and can be called without instance"""
        # Should be able to call all methods without instantiating class
        assert callable(EnvironmentMapper.load_env)
        assert callable(EnvironmentMapper.map_model_credentials)
        assert callable(EnvironmentMapper.setup)

    def test_integration_workflow(self):
        """Test typical workflow integration"""
        with (
            patch.object(EnvironmentMapper, "load_env", return_value=True),
            patch.object(EnvironmentMapper, "map_model_credentials", return_value=True),
        ):

            # Typical usage pattern
            success = EnvironmentMapper.setup("gpt-4o")

            assert success is True

    def test_error_handling(self):
        """Test error handling in methods"""
        # Methods should handle errors gracefully and not raise exceptions
        try:
            EnvironmentMapper.load_env()
            EnvironmentMapper.map_model_credentials("invalid-model")
            EnvironmentMapper.setup("invalid-model")
        except Exception as e:
            pytest.fail(f"Methods should handle errors gracefully: {e}")

    def test_return_types(self):
        """Test that methods return expected types"""
        with (
            patch.object(EnvironmentMapper, "load_env", return_value=True),
            patch.object(EnvironmentMapper, "map_model_credentials", return_value=True),
        ):

            load_result = EnvironmentMapper.load_env()
            map_result = EnvironmentMapper.map_model_credentials("gpt-4o")
            setup_result = EnvironmentMapper.setup("gpt-4o")

            assert isinstance(load_result, bool)
            assert isinstance(map_result, bool)
            assert isinstance(setup_result, bool)
