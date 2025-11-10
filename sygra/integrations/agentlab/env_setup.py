"""Environment variable mapping for SyGra-AgentLab integration.

Maps SyGra's model-specific environment variables to AgentLab's expected format:
- SYGRA_<MODEL>_URL → AZURE_OPENAI_ENDPOINT
- SYGRA_<MODEL>_TOKEN → AZURE_OPENAI_API_KEY
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from sygra.logger.logger_config import logger

__all__ = ["EnvironmentMapper"]


class EnvironmentMapper:
    """Maps SyGra environment variables to AgentLab's expected format."""

    @staticmethod
    def load_env() -> bool:
        """Load environment variables from .env file in current directory.

        Returns:
            True if .env file was found and loaded
        """
        env_file = Path.cwd() / ".env"

        if env_file.exists():
            load_dotenv(env_file, override=False)
            logger.info(f"Loaded environment from {env_file}")
            return True

        return False

    @staticmethod
    def map_model_credentials(model_name: str) -> bool:
        """Map SyGra model credentials to AgentLab format.

        Args:
            model_name: Model identifier (e.g., "gpt-4o", "gpt-4o-mini")

        Returns:
            True if both URL and token were successfully mapped
        """
        model_env_name = model_name.upper()
        sygra_url_var = f"SYGRA_{model_env_name}_URL"
        sygra_token_var = f"SYGRA_{model_env_name}_TOKEN"

        url_mapped = sygra_url_var in os.environ
        token_mapped = sygra_token_var in os.environ

        if url_mapped:
            os.environ["AZURE_OPENAI_ENDPOINT"] = os.environ[sygra_url_var]
            logger.info(f"Mapped {sygra_url_var} to AZURE_OPENAI_ENDPOINT")
        else:
            logger.warning(f"Missing {sygra_url_var} in environment")

        if token_mapped:
            os.environ["AZURE_OPENAI_API_KEY"] = os.environ[sygra_token_var]
            logger.info(f"Mapped {sygra_token_var} to AZURE_OPENAI_API_KEY")
        else:
            logger.warning(f"Missing {sygra_token_var} in environment")

        return url_mapped and token_mapped

    @staticmethod
    def setup(model_name: str) -> bool:
        """Perform complete environment setup: load .env and map credentials.

        Args:
            model_name: Model identifier to map credentials for

        Returns:
            True if credentials were successfully mapped
        """
        EnvironmentMapper.load_env()
        return EnvironmentMapper.map_model_credentials(model_name)
