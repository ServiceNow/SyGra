import os
from pathlib import Path
from typing import Optional

from sygra.logger.logger_config import logger


def parse_dotenv_file(file_path: str) -> dict[str, str]:
    """
    Parse a .env file and return a dictionary of key-value pairs.

    Args:
        file_path: Path to the .env file

    Returns:
        Dictionary of environment variables
    """
    env_vars = {}

    try:
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]

                    env_vars[key] = value
    except Exception as e:
        logger.warning(f"Error parsing .env file {file_path}: {str(e)}")

    return env_vars


def load_dotenv(dotenv_path: Optional[str] = None, override: bool = False) -> bool:
    """
    Load environment variables from a .env file.

    Args:
        dotenv_path: Path to the .env file. If None, it will look for a .env file
                    in the current directory and parent directories.
        override: Whether to override existing environment variables.

    Returns:
        True if the .env file was loaded successfully, False otherwise.
    """
    # If no path provided, try to find a .env file
    if dotenv_path is None:
        current_dir = Path.cwd()

        # Check current directory and parent directories
        for dir_path in [current_dir] + list(current_dir.parents):
            potential_path = dir_path / ".env"
            if potential_path.exists():
                dotenv_path = str(potential_path)
                break

    if dotenv_path is None or not os.path.exists(dotenv_path):
        logger.debug(f"No .env file found at {dotenv_path}")
        return False

    env_vars = parse_dotenv_file(dotenv_path)

    # Set environment variables
    for key, value in env_vars.items():
        if override or key not in os.environ:
            os.environ[key] = value

    logger.debug(f"Loaded {len(env_vars)} environment variables from {dotenv_path}")
    return True
