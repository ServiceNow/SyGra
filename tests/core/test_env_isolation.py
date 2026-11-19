"""Tests for env isolation: library use doesn't load .env or override os.environ."""

import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent.parent))

from sygra import ConfigurationError, FakeProvider, LLMRequest, ModelResponse, Workflow
from sygra.core.models.model_factory import ModelFactory
from sygra.utils import utils


@pytest.fixture
def cwd_with_env(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("SYGRA_B3_FROM_CWD_ENV=leaked\n")
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    os.environ.pop("SYGRA_B3_FROM_CWD_ENV", None)


def _workflow(name: str, provider) -> Workflow:
    return (
        Workflow(name)
        .source([{"id": "1", "text": "x"}])
        .llm({"name": "gen", "model_type": "external"}, "{text}", output="answer")
        .llm_provider(provider)
    )


def test_load_model_config_does_not_load_dotenv(cwd_with_env):
    utils.load_model_config()
    assert "SYGRA_B3_FROM_CWD_ENV" not in os.environ


def test_importing_data_quality_tools_does_not_load_dotenv(cwd_with_env):
    import sygra.tools.toolkits.data_quality.processor as processor

    importlib.reload(processor)
    assert "SYGRA_B3_FROM_CWD_ENV" not in os.environ


def test_run_without_env_file_ignores_cwd_dotenv(cwd_with_env):
    _workflow("b3_no_env", FakeProvider("ok")).run(
        num_records=1, output_dir=str(cwd_with_env / "out")
    )
    assert "SYGRA_B3_FROM_CWD_ENV" not in os.environ


def test_run_with_env_file_loads_without_overriding(tmp_path, monkeypatch):
    env_file = tmp_path / "custom.env"
    env_file.write_text("SYGRA_B3_NEW=from_file\nSYGRA_B3_EXISTING=from_file\n")
    monkeypatch.setenv("SYGRA_B3_EXISTING", "from_host")
    seen = {}

    class _Provider:
        async def generate(self, request: LLMRequest) -> ModelResponse:
            seen["new"] = os.environ.get("SYGRA_B3_NEW")
            seen["existing"] = os.environ.get("SYGRA_B3_EXISTING")
            return ModelResponse(llm_response="ok", response_code=200)

    try:
        _workflow("b3_env_file", _Provider()).run(
            num_records=1, output_dir=str(tmp_path / "out"), env_file=env_file
        )
    finally:
        os.environ.pop("SYGRA_B3_NEW", None)

    assert seen == {"new": "from_file", "existing": "from_host"}


def test_missing_env_file_is_a_configuration_error(tmp_path):
    with pytest.raises(ConfigurationError, match="env_file not found"):
        _workflow("b3_missing", FakeProvider("ok")).run(
            num_records=1, output_dir=str(tmp_path), env_file=tmp_path / "nope.env"
        )


def test_model_config_can_carry_connection_settings_directly(monkeypatch):
    for key in list(os.environ):
        if key.startswith("SYGRA_B3_DIRECT_"):
            monkeypatch.delenv(key)
    model = ModelFactory.create_model(
        {
            "name": "b3_direct",
            "model_type": "openai",
            "model": "gpt-4o",
            "url": "https://example.invalid/v1",
            "auth_token": "sk-direct",
            "parameters": {"temperature": 0},
        }
    )
    assert model.model_config["url"] == "https://example.invalid/v1"
    assert model.model_config["auth_token"] == "sk-direct"
