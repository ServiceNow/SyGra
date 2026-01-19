"""
FastAPI Backend for SyGra Studio Integration.

Provides REST API endpoints for:
- Listing available SyGra workflows
- Getting workflow graph details for visualization
- Executing workflows
- Monitoring execution progress
- Code execution and debugging
"""

import asyncio
import os
import sys
import uuid
import subprocess
import threading
import queue
import signal
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

import yaml
import json as json_module
import traceback
import httpx
import re

from sygra.utils import utils as sygra_utils
from sygra.utils import constants as sygra_constants

from studio.graph_builder import SygraGraphBuilder
from studio.converter import SygraToStudioConverter
from studio.models import (
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
    NodeExecutionState,
    WorkflowCreateRequest,
    WorkflowExecution,
    WorkflowGraph,
    WorkflowListItem,
    WorkflowSaveResponse,
)
from studio.execution_storage import get_storage, ExecutionStorage


# Store for active executions (in-memory cache for running executions)
# Persistent storage is handled by ExecutionStorage class
_executions: Dict[str, WorkflowExecution] = {}


def _convert_prompts_to_yaml_format(prompts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Convert prompts from frontend format to SyGra YAML format.

    Frontend format: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    SyGra YAML format: [{"system": "..."}, {"user": "..."}]
    """
    if not prompts:
        return []

    yaml_prompts = []
    for msg in prompts:
        if isinstance(msg, dict):
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            yaml_prompts.append({role: content})
        elif hasattr(msg, 'role') and hasattr(msg, 'content'):
            # Handle PromptMessage objects
            yaml_prompts.append({msg.role: msg.content})
    return yaml_prompts

# Scalable execution storage instance (lazy initialized)
_execution_storage: ExecutionStorage = None

def _get_execution_storage() -> ExecutionStorage:
    """Get the execution storage instance (lazy initialization)."""
    global _execution_storage
    if _execution_storage is None:
        _execution_storage = get_storage()
    return _execution_storage

# Store for discovered workflows
_workflows: Dict[str, WorkflowGraph] = {}

# Store for cancelled execution IDs (for signaling background tasks to stop)
_cancelled_executions: set = set()

# Store for running processes (for actual process termination)
import multiprocessing
import json as json_module
import asyncio as asyncio_module
_running_processes: Dict[str, multiprocessing.Process] = {}

# Job queue for sequential execution
_execution_queue: asyncio_module.Queue = None
_queue_processor_task = None
_current_running_execution: str = None

# Persistence file for executions
_EXECUTIONS_FILE = Path(__file__).parent / ".executions_history.json"

# Code execution stores
_code_executions: Dict[str, Dict] = {}  # Active code execution sessions
_debug_sessions: Dict[str, Dict] = {}   # Active debug sessions
_websocket_connections: Dict[str, WebSocket] = {}  # WebSocket connections for streaming output

# Environment variables store (loaded from .env + runtime modifications)
_env_vars: Dict[str, str] = {}
_ENV_FILE = Path(__file__).parent / ".env"  # Local env file for UI-managed vars

# ==================== Models API (Module Level) ====================
# Models config file paths - use library constants for consistency
_BUILTIN_MODELS_CONFIG_PATH = Path(sygra_constants.MODEL_CONFIG_YAML)
_CUSTOM_MODELS_CONFIG_PATH = Path(sygra_constants.CUSTOM_MODELS_CONFIG_YAML)

# Legacy path for backwards compatibility
_MODELS_CONFIG_PATH = _BUILTIN_MODELS_CONFIG_PATH

# Cache for model status (lightweight - just connectivity info)
_models_status: Dict[str, Dict[str, Any]] = {}

# Supported model types with their configurations
_MODEL_TYPES = {
    "azure_openai": {
        "label": "Azure OpenAI",
        "description": "Azure-hosted OpenAI models (GPT-4, GPT-4o, etc.)",
        "env_vars": ["URL", "TOKEN"],
    },
    "openai": {
        "label": "OpenAI",
        "description": "OpenAI API models",
        "env_vars": ["URL", "TOKEN"],
    },
    "vllm": {
        "label": "vLLM",
        "description": "Self-hosted vLLM inference server",
        "env_vars": ["URL", "TOKEN"],
    },
    "ollama": {
        "label": "Ollama",
        "description": "Local Ollama models",
        "env_vars": ["URL"],
    },
    "tgi": {
        "label": "TGI (Text Generation Inference)",
        "description": "Hugging Face Text Generation Inference",
        "env_vars": ["URL", "TOKEN"],
    },
    "mistralai": {
        "label": "Mistral AI",
        "description": "Mistral AI API",
        "env_vars": ["URL", "TOKEN"],
    },
    "vertex_ai": {
        "label": "Google Vertex AI",
        "description": "Google Cloud Vertex AI models (Gemini)",
        "env_vars": ["VERTEX_PROJECT", "VERTEX_LOCATION", "VERTEX_CREDENTIALS"],
    },
    "bedrock": {
        "label": "AWS Bedrock",
        "description": "AWS Bedrock models (Claude, Titan, etc.)",
        "env_vars": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION_NAME"],
    },
    "triton": {
        "label": "Triton Inference Server",
        "description": "NVIDIA Triton Inference Server",
        "env_vars": ["URL", "TOKEN"],
    }
}


# ==================== Model Config Functions (Using Library) ====================
# These wrapper functions use the sygra library functions with Studio-specific additions

def _load_builtin_models_config() -> Dict[str, Any]:
    """Load builtin/core models from SyGra's models.yaml (read-only).
    Uses library function: sygra_utils.load_builtin_models()
    """
    return sygra_utils.load_builtin_models()


def _load_custom_models_config() -> Dict[str, Any]:
    """Load custom user-defined models from studio config.
    Uses library function: sygra_utils.load_custom_models()
    """
    return sygra_utils.load_custom_models()


def _save_custom_models_config(config: Dict[str, Any]) -> None:
    """Save custom models to studio config file.
    Uses library function: sygra_utils.save_custom_models()
    """
    sygra_utils.save_custom_models(config)


def _load_models_config_sync() -> Dict[str, Any]:
    """Load all models configuration (builtin + custom), synchronous, fast.

    Note: This is a simplified version that doesn't inject env vars.
    For env var injection, use sygra_utils.load_model_config() instead.
    """
    builtin = _load_builtin_models_config()
    custom = _load_custom_models_config()
    merged = {}
    merged.update(builtin)
    merged.update(custom)
    return merged


def _get_builtin_model_names() -> set:
    """Get the set of builtin model names.
    Uses library function: sygra_utils.get_builtin_model_names()
    """
    return sygra_utils.get_builtin_model_names()


def _get_model_env_value(model_name: str, env_suffix: str) -> tuple:
    """Get env var value trying multiple prefix formats. Returns (value, key_used).

    Studio-specific: Also checks _env_vars (UI-managed env vars) in addition
    to os.environ.
    """
    # First check Studio's UI-managed env vars
    prefixes = [
        f"SYGRA_{model_name.upper()}",  # SYGRA_GPT-4O (keep hyphens)
        f"SYGRA_{sygra_utils.get_env_name(model_name)}",  # SYGRA_GPT_4O (normalized)
    ]
    for prefix in prefixes:
        env_key = f"{prefix}_{env_suffix}"
        # Check Studio's _env_vars first, then os.environ
        value = _env_vars.get(env_key) or os.environ.get(env_key, "")
        if value:
            return value, env_key
    return "", f"{prefixes[0]}_{env_suffix}"


def _get_model_credentials_fast(model_name: str, model_config: Dict[str, Any]) -> Dict[str, Any]:
    """Get credentials for a model - fast, no heavy operations.

    Studio-specific: Uses Studio's _env_vars in addition to os.environ.
    """
    model_type = model_config.get("model_type", "")
    type_info = _MODEL_TYPES.get(model_type, {"env_vars": ["URL", "TOKEN"]})

    creds = {}
    for env_var in type_info.get("env_vars", ["URL", "TOKEN"]):
        value, key = _get_model_env_value(model_name, env_var)
        creds[env_var.lower()] = value
        creds[f"{env_var.lower()}_env_key"] = key
        creds[f"{env_var.lower()}_configured"] = bool(value)

    return creds


async def _ping_model_http(model_name: str, model_config: Dict[str, Any]) -> Dict[str, Any]:
    """Lightweight HTTP ping - just checks endpoint reachability."""
    model_type = model_config.get("model_type", "")
    url, _ = _get_model_env_value(model_name, "URL")

    if not url:
        return {
            "status": "unconfigured",
            "status_code": None,
            "latency_ms": None,
            "last_checked": datetime.now().isoformat(),
            "error": "URL not configured"
        }

    # Health check endpoints by model type
    health_endpoints = {"vllm": "/health", "tgi": "/health", "ollama": "/api/tags", "triton": "/v2/health/ready"}

    if model_type in ["azure_openai", "openai", "mistralai"]:
        check_url = url.rstrip("/")
        if "/openai/deployments/" in check_url:
            check_url = check_url.split("/openai/deployments/")[0]
    elif model_type in health_endpoints:
        base_url = url.rstrip("/").rsplit("/v1", 1)[0] if "/v1" in url else url.rstrip("/")
        check_url = f"{base_url}{health_endpoints[model_type]}"
    else:
        check_url = url.rstrip("/")

    try:
        start = datetime.now()
        async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
            resp = await client.get(check_url)
            latency = (datetime.now() - start).total_seconds() * 1000
            # 401/403/404/405 means server is up (just needs auth or wrong path)
            is_up = resp.status_code in [200, 401, 403, 404, 405]
            return {
                "status": "online" if is_up else "error",
                "status_code": resp.status_code,
                "latency_ms": round(latency, 2),
                "last_checked": datetime.now().isoformat(),
                "error": None if is_up else f"HTTP {resp.status_code}"
            }
    except httpx.TimeoutException:
        return {"status": "timeout", "status_code": 408, "latency_ms": None, "last_checked": datetime.now().isoformat(), "error": "Timeout"}
    except httpx.ConnectError:
        return {"status": "offline", "status_code": None, "latency_ms": None, "last_checked": datetime.now().isoformat(), "error": "Connection refused"}
    except Exception as e:
        return {"status": "error", "status_code": 500, "latency_ms": None, "last_checked": datetime.now().isoformat(), "error": str(e)[:50]}


def _load_env_vars():
    """Load environment variables from .env files."""
    global _env_vars

    # Load from project .env files (studio/api.py -> studio/ -> project_root/)
    project_root = Path(__file__).parent.parent
    env_files = [
        project_root / ".env",  # Project root .env (e.g., /path/to/GraSP/.env)
        Path.cwd() / ".env",  # Current working directory .env
        Path.home() / ".env",  # User home .env
        _ENV_FILE,  # Local UI-managed env file
    ]

    for env_file in env_files:
        if env_file.exists():
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, _, value = line.partition('=')
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if key:
                                _env_vars[key] = value
            except Exception as e:
                print(f"Warning: Failed to load {env_file}: {e}")


def _save_env_vars():
    """Save UI-managed environment variables to local file."""
    try:
        with open(_ENV_FILE, 'w') as f:
            f.write("# SyGra Studio managed environment variables\n")
            f.write(f"# Last updated: {datetime.now().isoformat()}\n\n")
            for key, value in sorted(_env_vars.items()):
                # Escape values with special characters
                if ' ' in value or '"' in value or "'" in value:
                    value = f'"{value}"'
                f.write(f"{key}={value}\n")
    except Exception as e:
        print(f"Warning: Failed to save env vars: {e}")


class CodeExecutionRequest(BaseModel):
    """Request model for code execution."""
    file_path: str  # Path to the Python file to execute
    function_name: Optional[str] = None  # Specific function to run
    args: Optional[List[str]] = None  # Command line arguments
    workflow_id: Optional[str] = None  # Associated workflow
    debug: bool = False  # Whether to run in debug mode
    breakpoints: Optional[List[int]] = None  # Line numbers for breakpoints


class DebugAction(BaseModel):
    """Request model for debug actions."""
    action: str  # 'continue', 'step_over', 'step_into', 'step_out', 'stop'
    session_id: str


def _save_executions():
    """
    Save executions to persistent storage using the new scalable storage.

    Also cleans up completed executions from in-memory dict to prevent memory leaks.
    """
    try:
        storage = _get_execution_storage()
        to_remove = []

        # Save completed/failed/cancelled executions to scalable storage
        for exec_id, execution in _executions.items():
            if execution.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
                storage.save_execution(execution)
                to_remove.append(exec_id)

        # Clean up from in-memory dict after saving to storage
        for exec_id in to_remove:
            del _executions[exec_id]

    except Exception as e:
        print(f"Warning: Failed to save executions: {e}")


_executions_loaded = False

def _load_executions():
    """
    Initialize execution storage (will automatically migrate from legacy format if needed).

    This function now delegates to the scalable ExecutionStorage class which:
    - Uses per-run files instead of a monolithic JSON
    - Maintains a lightweight index for fast listing
    - Supports pagination and lazy loading
    - Automatically migrates from legacy .executions_history.json
    """
    global _executions_loaded

    # Prevent duplicate loading
    if _executions_loaded:
        return
    _executions_loaded = True

    # Initialize storage (handles migration from legacy format automatically)
    storage = _get_execution_storage()

    # Note: We no longer load all executions into memory.
    # Executions are loaded on-demand via storage.get_execution()
    # and listed via storage.list_executions() with pagination.


async def _process_execution_queue():
    """Process executions from the queue one at a time."""
    global _current_running_execution, _execution_queue

    while True:
        try:
            # Wait for next job in queue
            job = await _execution_queue.get()
            execution_id, workflow, request = job

            # Skip if already cancelled while waiting in queue
            if execution_id in _cancelled_executions:
                execution = _executions.get(execution_id)
                if execution and execution.status == ExecutionStatus.PENDING:
                    execution.status = ExecutionStatus.CANCELLED
                    execution.completed_at = datetime.now()
                    _save_executions()
                _cancelled_executions.discard(execution_id)
                _execution_queue.task_done()
                continue

            # Set current running execution
            _current_running_execution = execution_id

            try:
                # Run the workflow
                await _run_workflow(execution_id, workflow, request)
            finally:
                _current_running_execution = None
                _execution_queue.task_done()

        except Exception as e:
            print(f"Error processing execution queue: {e}")
            import traceback
            traceback.print_exc()


def _ensure_queue_initialized():
    """Ensure the execution queue and processor are initialized."""
    global _execution_queue, _queue_processor_task

    if _execution_queue is None:
        _execution_queue = asyncio_module.Queue()

    # Start queue processor if not running
    if _queue_processor_task is None or _queue_processor_task.done():
        try:
            loop = asyncio_module.get_running_loop()
            _queue_processor_task = loop.create_task(_process_execution_queue())
        except RuntimeError:
            # No running loop yet, will be started when first execution is queued
            pass


def create_app(
    tasks_dir: Optional[str] = None,
    cors_origins: Optional[List[str]] = None,
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        tasks_dir: Directory containing SyGra task workflows.
        cors_origins: List of allowed CORS origins.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="SyGra Workflow API",
        description="API for visualizing and executing SyGra workflows",
        version="1.0.0",
    )

    # Configure CORS
    if cors_origins is None:
        cors_origins = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8080"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Set tasks directory
    if tasks_dir is None:
        tasks_dir = os.environ.get(
            "SYGRA_TASKS_DIR",
            str(Path(__file__).parent.parent / "tasks" / "examples")  # studio -> project root
        )

    app.state.tasks_dir = tasks_dir

    # Load persisted executions on startup
    _load_executions()

    # Load environment variables from .env files
    _load_env_vars()

    app.state.graph_builder = SygraGraphBuilder()
    app.state.converter = SygraToStudioConverter()

    # Register routes
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all API routes."""

    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok", "service": "SyGra Workflow API"}

    @app.get("/api/config")
    async def get_config():
        """Get server configuration including tasks directory."""
        tasks_path = Path(app.state.tasks_dir)
        tasks_dir = str(tasks_path.resolve()) if tasks_path.exists() else str(tasks_path)

        # Get list of subdirectories for directory picker
        subdirs = []
        if tasks_path.exists():
            subdirs = [str(tasks_path / d.name) for d in tasks_path.iterdir() if d.is_dir()]

        return {
            "tasks_dir": tasks_dir,
            "subdirectories": sorted(subdirs),
            "version": "1.0.0"
        }

    # ==================== Environment Variables API ====================

    @app.get("/api/settings/env")
    async def get_env_vars():
        """Get all environment variables."""
        # Return vars with masked sensitive values
        SENSITIVE_PATTERNS = ['key', 'secret', 'token', 'password', 'api_key', 'apikey', 'auth', 'credential']

        result = []
        for key, value in sorted(_env_vars.items()):
            is_sensitive = any(pattern in key.lower() for pattern in SENSITIVE_PATTERNS)
            result.append({
                "key": key,
                "value": value,
                "masked_value": "*" * min(len(value), 20) if is_sensitive else value,
                "is_sensitive": is_sensitive
            })

        return {
            "variables": result,
            "count": len(result),
            "env_file": str(_ENV_FILE)
        }

    @app.post("/api/settings/env")
    async def set_env_var(data: dict):
        """Add or update an environment variable."""
        key = data.get("key", "").strip()
        value = data.get("value", "")

        if not key:
            raise HTTPException(status_code=400, detail="Key is required")

        # Validate key format (alphanumeric + underscore)
        if not key.replace("_", "").isalnum():
            raise HTTPException(status_code=400, detail="Key must be alphanumeric with underscores only")

        _env_vars[key] = value
        _save_env_vars()

        # Also set in os.environ for immediate use
        os.environ[key] = value

        return {"success": True, "key": key, "message": f"Variable '{key}' saved"}

    @app.delete("/api/settings/env/{key}")
    async def delete_env_var(key: str):
        """Delete an environment variable."""
        if key not in _env_vars:
            raise HTTPException(status_code=404, detail=f"Variable '{key}' not found")

        del _env_vars[key]
        _save_env_vars()

        # Also remove from os.environ
        if key in os.environ:
            del os.environ[key]

        return {"success": True, "key": key, "message": f"Variable '{key}' deleted"}

    @app.post("/api/settings/env/reload")
    async def reload_env_vars():
        """Reload environment variables from .env files."""
        global _env_vars
        _env_vars = {}
        _load_env_vars()

        # Update os.environ with loaded vars
        for key, value in _env_vars.items():
            os.environ[key] = value

        return {"success": True, "count": len(_env_vars), "message": "Environment variables reloaded"}

    # ==================== Models API (using module-level functions) ====================

    @app.get("/api/models/types")
    async def get_model_types():
        """Get all supported model types."""
        return {"types": _MODEL_TYPES, "count": len(_MODEL_TYPES)}

    @app.get("/api/models")
    async def list_models():
        """List all configured models (fast, no pinging)."""
        config = _load_models_config_sync()
        builtin_names = _get_builtin_model_names()
        models = []

        for name, model_config in config.items():
            model_type = model_config.get("model_type", "unknown")
            creds = _get_model_credentials_fast(name, model_config)
            status_info = _models_status.get(name, {"status": "unknown", "last_checked": None})

            type_info = _MODEL_TYPES.get(model_type, {"env_vars": ["URL", "TOKEN"]})
            all_creds_configured = all(
                creds.get(f"{ev.lower()}_configured", False)
                for ev in type_info.get("env_vars", [])
            )

            models.append({
                "name": name,
                "model_type": model_type,
                "model_type_label": type_info.get("label", model_type),
                "model": model_config.get("model", name),
                "description": type_info.get("description", ""),
                "parameters": model_config.get("parameters", {}),
                "api_version": model_config.get("api_version"),
                "credentials": creds,
                "credentials_configured": all_creds_configured,
                "status": status_info.get("status", "unknown"),
                "status_code": status_info.get("status_code"),
                "latency_ms": status_info.get("latency_ms"),
                "last_checked": status_info.get("last_checked"),
                "error": status_info.get("error"),
                "is_builtin": name in builtin_names,  # Flag for SyGra core models (read-only)
            })

        return {"models": models, "count": len(models), "config_path": str(_MODELS_CONFIG_PATH)}

    @app.get("/api/models/{model_name}")
    async def get_model(model_name: str):
        """Get a specific model's configuration."""
        config = _load_models_config_sync()
        if model_name not in config:
            raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

        model_config = config[model_name]
        model_type = model_config.get("model_type", "unknown")

        return {
            "name": model_name,
            "model_type": model_type,
            "model_type_info": _MODEL_TYPES.get(model_type, {}),
            "config": model_config,
            "credentials": _get_model_credentials_fast(model_name, model_config),
            "status": _models_status.get(model_name, {"status": "unknown"}),
        }

    @app.post("/api/models/{model_name}/ping")
    async def ping_model(model_name: str):
        """Ping a single model (lightweight HTTP check)."""
        config = _load_models_config_sync()
        if model_name not in config:
            raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

        result = await _ping_model_http(model_name, config[model_name])
        _models_status[model_name] = result
        return {"model": model_name, **result}

    @app.post("/api/models/ping-all")
    async def ping_all_models():
        """Ping all models in parallel (lightweight HTTP checks)."""
        config = _load_models_config_sync()
        if not config:
            return {"results": {}, "total": 0, "online": 0, "offline": 0}

        # Run all pings concurrently
        tasks = [_ping_model_http(name, cfg) for name, cfg in config.items()]
        names = list(config.keys())

        try:
            results_list = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=20)
        except asyncio.TimeoutError:
            results_list = [{"status": "timeout", "error": "Overall timeout"} for _ in names]

        results = {}
        for name, res in zip(names, results_list):
            if isinstance(res, Exception):
                res = {"status": "error", "error": str(res)[:50]}
            results[name] = res
            _models_status[name] = res

        online = sum(1 for r in results.values() if r.get("status") == "online")
        return {"results": results, "total": len(results), "online": online, "offline": len(results) - online}

    @app.post("/api/models")
    async def create_or_update_model(data: dict):
        """Create or update a model configuration (custom models only)."""
        name = data.get("name", "").strip()
        model_type = data.get("model_type", "").strip()

        if not name:
            raise HTTPException(status_code=400, detail="Model name is required")
        if not model_type or model_type not in _MODEL_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid model type: {model_type}")

        # Check if trying to edit a builtin model
        builtin_names = _get_builtin_model_names()
        if name in builtin_names:
            raise HTTPException(
                status_code=403,
                detail=f"Cannot modify builtin SyGra model '{name}'. Create a custom model with a different name instead."
            )

        # Load custom models config (not builtin)
        custom_config = _load_custom_models_config()
        is_new = name not in custom_config and name not in _load_models_config_sync()

        model_config = {"model_type": model_type}
        if data.get("model"): model_config["model"] = data["model"]
        if data.get("api_version"): model_config["api_version"] = data["api_version"]
        if data.get("parameters"): model_config["parameters"] = data["parameters"]

        # Add additional optional fields
        for field in ["hf_chat_template_model_id", "model_serving_name", "post_process", "input_type", "output_type"]:
            if data.get(field): model_config[field] = data[field]

        custom_config[name] = model_config

        # Save to custom models config (NOT the builtin SyGra models.yaml)
        try:
            _save_custom_models_config(custom_config)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save: {e}")

        # Save credentials if provided
        credentials = data.get("credentials", {})
        if credentials:
            prefix = f"SYGRA_{name.upper()}"
            for key, value in credentials.items():
                if value:
                    env_key = f"{prefix}_{key.upper()}"
                    _env_vars[env_key] = value
                    os.environ[env_key] = value

        return {"success": True, "model": name, "is_new": is_new, "is_builtin": False}

    @app.delete("/api/models/{model_name}")
    async def delete_model(model_name: str):
        """Delete a model configuration (custom models only)."""
        # Check if it's a builtin model
        builtin_names = _get_builtin_model_names()
        if model_name in builtin_names:
            raise HTTPException(
                status_code=403,
                detail=f"Cannot delete builtin SyGra model '{model_name}'. Only custom models can be deleted."
            )

        # Check if model exists in custom config
        custom_config = _load_custom_models_config()
        if model_name not in custom_config:
            raise HTTPException(status_code=404, detail=f"Custom model '{model_name}' not found")

        del custom_config[model_name]

        try:
            _save_custom_models_config(custom_config)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save: {e}")

        _models_status.pop(model_name, None)
        return {"success": True, "model": model_name}

    # ==================================================================

    @app.get("/api/workflows", response_model=List[WorkflowListItem])
    async def list_workflows():
        """
        List all available SyGra workflows.

        Recursively scans the tasks directory for graph_config.yaml files,
        supporting nested folder structures.
        """
        workflows = []
        tasks_dir = Path(app.state.tasks_dir)

        if not tasks_dir.exists():
            return workflows

        # Recursively find all graph_config.yaml files
        for config_path in tasks_dir.rglob("graph_config.yaml"):
            if not config_path.is_file():
                continue

            try:
                graph = app.state.graph_builder.build_from_yaml(str(config_path))
                _workflows[graph.id] = graph

                workflows.append(WorkflowListItem(
                    id=graph.id,
                    name=graph.name,
                    description=graph.description,
                    source_path=str(config_path),
                    node_count=len(graph.nodes),
                    edge_count=len(graph.edges),
                    last_modified=graph.last_modified,
                ))
            except Exception as e:
                # Skip invalid workflows
                print(f"Error loading workflow from {config_path}: {e}")
                continue

        return workflows

    @app.get("/api/workflows/{workflow_id}", response_model=WorkflowGraph)
    async def get_workflow(workflow_id: str):
        """
        Get detailed workflow graph for visualization.

        Args:
            workflow_id: The workflow ID to retrieve.
        """
        # Check cache first
        if workflow_id in _workflows:
            return _workflows[workflow_id]

        # Try to find by scanning
        await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        return _workflows[workflow_id]

    @app.get("/api/workflows/{workflow_id}/openflow")
    async def get_workflow_openflow(workflow_id: str):
        """
        Get workflow in Studio OpenFlow format.

        Args:
            workflow_id: The workflow ID to convert.
        """
        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        workflow = _workflows[workflow_id]
        openflow = app.state.converter.convert_workflow(workflow)

        return openflow

    @app.get("/api/workflows/{workflow_id}/sample-data")
    async def get_workflow_sample_data(workflow_id: str, limit: int = 3, source_index: int = 0):
        """
        Get sample data records from a workflow's data source.

        Args:
            workflow_id: The workflow ID.
            limit: Maximum number of records to return (default: 3).
            source_index: Index of the source to preview (default: 0, first source).

        Returns:
            Sample data records and metadata.
        """
        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        workflow = _workflows[workflow_id]
        data_config = workflow.data_config

        if not data_config or not data_config.get("source"):
            return {
                "records": [],
                "total": 0,
                "message": "No data source configured for this workflow"
            }

        source = data_config.get("source", {})
        # Handle array or single source
        if isinstance(source, list):
            if source_index < 0 or source_index >= len(source):
                return {
                    "records": [],
                    "total": 0,
                    "message": f"Invalid source index {source_index}. Available: 0-{len(source)-1}" if source else "No sources configured"
                }
            source = source[source_index] if source else {}
        elif source_index > 0:
            return {
                "records": [],
                "total": 0,
                "message": f"Only one source configured (index 0)"
            }

        source_type = (source.get("type") or "").lower()

        try:
            records = []
            total_count = None

            if source_type in ("disk", "local_file", "local", "json", "jsonl", "csv"):
                # Local file source
                file_path = source.get("file_path") or source.get("path")
                file_format = source.get("file_format") or source.get("format") or "json"

                if file_path and os.path.exists(file_path):
                    import json as json_lib
                    if file_format in ("json",):
                        with open(file_path, 'r') as f:
                            data = json_lib.load(f)
                            if isinstance(data, list):
                                total_count = len(data)
                                records = data[:limit]
                            else:
                                records = [data]
                                total_count = 1
                    elif file_format in ("jsonl",):
                        with open(file_path, 'r') as f:
                            lines = f.readlines()
                            total_count = len(lines)
                            for line in lines[:limit]:
                                if line.strip():
                                    records.append(json_lib.loads(line))
                    elif file_format in ("csv",):
                        import csv
                        with open(file_path, 'r') as f:
                            reader = csv.DictReader(f)
                            all_rows = list(reader)
                            total_count = len(all_rows)
                            records = all_rows[:limit]
                else:
                    return {
                        "records": [],
                        "total": 0,
                        "message": f"File not found: {file_path}"
                    }

            elif source_type in ("hf", "huggingface"):
                # HuggingFace source - use HF Hub API directly (much faster than datasets library)
                repo_id = source.get("repo_id")
                config_name = source.get("config_name") or "default"
                split = source.get("split", "train")

                if not repo_id:
                    return {
                        "records": [],
                        "total": 0,
                        "message": "No repo_id specified for HuggingFace dataset"
                    }

                try:
                    import httpx
                    # Use HuggingFace datasets-server API for fast row access
                    url = f"https://datasets-server.huggingface.co/first-rows?dataset={repo_id}&config={config_name}&split={split}"

                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.get(url)

                        if response.status_code == 200:
                            data = response.json()
                            rows = data.get("rows", [])
                            records = [row.get("row", row) for row in rows[:limit]]
                            total_count = data.get("num_rows_total", "unknown")
                        else:
                            # Fallback: return info without records
                            return {
                                "records": [],
                                "total": "unknown",
                                "source_type": "huggingface",
                                "message": f"Could not fetch preview (API returned {response.status_code}). View dataset at HuggingFace.",
                                "dataset_info": {"repo_id": repo_id, "config_name": config_name, "split": split}
                            }
                except Exception as hf_err:
                    return {
                        "records": [],
                        "total": 0,
                        "source_type": "huggingface",
                        "message": f"Failed to fetch preview: {str(hf_err)[:150]}",
                        "dataset_info": {"repo_id": repo_id, "config_name": config_name, "split": split}
                    }

            elif source_type in ("servicenow", "snow"):
                # ServiceNow - would need actual connection
                return {
                    "records": [],
                    "total": 0,
                    "message": "ServiceNow preview requires authentication. Configure SNOW credentials to preview data."
                }
            else:
                return {
                    "records": [],
                    "total": 0,
                    "message": f"Preview not supported for source type: {source_type}"
                }

            return {
                "records": records,
                "total": total_count,
                "source_type": source_type,
                "message": None
            }

        except Exception as e:
            return {
                "records": [],
                "total": 0,
                "message": f"Error loading sample data: {str(e)}"
            }

    @app.get("/api/workflows/{workflow_id}/data-columns")
    async def get_workflow_data_columns(workflow_id: str, source_index: int = 0):
        """
        Get column names from a workflow's data source.

        This endpoint fetches a sample record and extracts column names.
        Supports all data source types: HuggingFace, local files, memory, etc.

        Args:
            workflow_id: The workflow ID.
            source_index: Index of the source to get columns from (default: 0).

        Returns:
            List of column names and source metadata.
        """
        # Use existing sample data logic to get columns
        sample_result = await get_workflow_sample_data(workflow_id, limit=1, source_index=source_index)

        columns = []
        if sample_result.get("records") and len(sample_result["records"]) > 0:
            # Extract column names from first record
            first_record = sample_result["records"][0]
            if isinstance(first_record, dict):
                columns = list(first_record.keys())

        return {
            "columns": columns,
            "source_type": sample_result.get("source_type"),
            "source_index": source_index,
            "message": sample_result.get("message") if not columns else None
        }

    @app.post("/api/preview-source")
    async def preview_source_data(request: Request, limit: int = 5):
        """
        Preview data from a source configuration directly (without requiring a saved workflow).

        Accepts source configuration in the POST body and returns sample data.
        This allows previewing data before saving a workflow.

        Args:
            request: Request containing source configuration in body.
            limit: Maximum number of records to return (default: 5).

        Returns:
            Sample data records and metadata.
        """
        try:
            source = await request.json()
        except Exception as e:
            return {
                "records": [],
                "total": 0,
                "message": f"Invalid JSON body: {str(e)}"
            }

        if not source:
            return {
                "records": [],
                "total": 0,
                "message": "No source configuration provided"
            }

        source_type = (source.get("type") or "").lower()

        try:
            records = []
            total_count = None

            if source_type in ("disk", "local_file", "local", "json", "jsonl", "csv"):
                # Local file source
                file_path = source.get("file_path") or source.get("path")
                file_format = source.get("file_format") or source.get("format") or "json"

                if not file_path:
                    return {
                        "records": [],
                        "total": 0,
                        "message": "No file_path specified for local file source"
                    }

                if file_path and os.path.exists(file_path):
                    import json as json_lib
                    if file_format in ("json",):
                        with open(file_path, 'r') as f:
                            data = json_lib.load(f)
                            if isinstance(data, list):
                                total_count = len(data)
                                records = data[:limit]
                            else:
                                records = [data]
                                total_count = 1
                    elif file_format in ("jsonl",):
                        with open(file_path, 'r') as f:
                            lines = f.readlines()
                            total_count = len(lines)
                            for line in lines[:limit]:
                                if line.strip():
                                    records.append(json_lib.loads(line))
                    elif file_format in ("csv",):
                        import csv
                        with open(file_path, 'r') as f:
                            reader = csv.DictReader(f)
                            all_rows = list(reader)
                            total_count = len(all_rows)
                            records = all_rows[:limit]
                    elif file_format in ("parquet",):
                        try:
                            import pandas as pd
                            df = pd.read_parquet(file_path)
                            total_count = len(df)
                            records = df.head(limit).to_dict('records')
                        except ImportError:
                            return {
                                "records": [],
                                "total": 0,
                                "message": "pandas and pyarrow required for parquet files"
                            }
                else:
                    return {
                        "records": [],
                        "total": 0,
                        "message": f"File not found: {file_path}"
                    }

            elif source_type in ("hf", "huggingface"):
                # HuggingFace source - use HF Hub API directly
                repo_id = source.get("repo_id")
                config_name = source.get("config_name")  # Don't default - auto-detect if needed
                split = source.get("split", "train")

                if not repo_id:
                    return {
                        "records": [],
                        "total": 0,
                        "message": "No repo_id specified for HuggingFace dataset"
                    }

                try:
                    import requests as hf_requests

                    # If no config specified, try to auto-detect from available configs
                    if not config_name:
                        # Get available configs from the dataset info API
                        info_url = f"https://datasets-server.huggingface.co/info?dataset={repo_id}"
                        info_response = hf_requests.get(info_url, timeout=10)
                        if info_response.status_code == 200:
                            info_data = info_response.json()
                            available_configs = list(info_data.get("dataset_info", {}).keys())
                            if available_configs:
                                # Use "default" if available, otherwise use the first config
                                config_name = "default" if "default" in available_configs else available_configs[0]
                            else:
                                config_name = "default"
                        else:
                            config_name = "default"

                    # Try the dataset viewer API first (much faster)
                    viewer_url = f"https://datasets-server.huggingface.co/rows?dataset={repo_id}&config={config_name}&split={split}&offset=0&length={limit}"
                    response = hf_requests.get(viewer_url, timeout=10)

                    if response.status_code == 200:
                        data = response.json()
                        records = [row.get("row", row) for row in data.get("rows", [])]
                        total_count = data.get("num_rows_total", len(records))
                    else:
                        # Fall back to datasets library
                        from datasets import load_dataset
                        ds = load_dataset(repo_id, config_name, split=split, streaming=True)
                        records = list(ds.take(limit))
                        total_count = "streaming"
                except Exception as hf_error:
                    return {
                        "records": [],
                        "total": 0,
                        "message": f"HuggingFace error: {str(hf_error)}"
                    }

            elif source_type == "servicenow":
                # ServiceNow source - would need credentials
                return {
                    "records": [],
                    "total": 0,
                    "message": "ServiceNow preview requires saved workflow with credentials"
                }

            else:
                return {
                    "records": [],
                    "total": 0,
                    "message": f"Unknown source type: {source_type}"
                }

            return {
                "records": records,
                "total": total_count,
                "source_type": source_type
            }

        except Exception as e:
            return {
                "records": [],
                "total": 0,
                "message": f"Error loading sample data: {str(e)}"
            }

    @app.post("/api/workflows/{workflow_id}/execute", response_model=ExecutionResponse)
    async def execute_workflow(
        workflow_id: str,
        request: ExecutionRequest,
    ):
        """
        Start workflow execution.

        Jobs are queued and executed one at a time in order.

        Args:
            workflow_id: The workflow ID to execute.
            request: Execution request with input data.
        """
        global _execution_queue, _queue_processor_task

        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        workflow = _workflows[workflow_id]

        # Normalize input_data - if it's a list, use first element for single run
        input_data = request.input_data
        if isinstance(input_data, list):
            input_data = input_data[0] if input_data else {}

        # Create execution record
        execution_id = str(uuid.uuid4())
        execution = WorkflowExecution(
            id=execution_id,
            workflow_id=workflow_id,
            workflow_name=workflow.name,
            status=ExecutionStatus.PENDING,
            input_data=input_data,
            started_at=datetime.now(),
        )

        # Initialize node states
        for node in workflow.nodes:
            execution.node_states[node.id] = NodeExecutionState(
                node_id=node.id,
                status=ExecutionStatus.PENDING,
            )

        _executions[execution_id] = execution

        # Initialize queue if needed
        if _execution_queue is None:
            _execution_queue = asyncio_module.Queue()

        # Start queue processor if not running
        if _queue_processor_task is None or _queue_processor_task.done():
            _queue_processor_task = asyncio_module.create_task(_process_execution_queue())

        # Add to execution queue
        await _execution_queue.put((execution_id, workflow, request))

        # Determine position in queue
        queue_position = _execution_queue.qsize()
        is_running = _current_running_execution is not None

        if is_running:
            message = f"Workflow execution queued: {execution_id} (position {queue_position} in queue)"
        else:
            message = f"Workflow execution started: {execution_id}"

        return ExecutionResponse(
            execution_id=execution_id,
            status=ExecutionStatus.PENDING,
            message=message,
        )

    @app.get("/api/executions/queue/status")
    async def get_queue_status():
        """
        Get the current execution queue status.

        Returns:
            Queue status including running execution and queue size.
        """
        return {
            "current_running": _current_running_execution,
            "queue_size": _execution_queue.qsize() if _execution_queue else 0,
            "is_processing": _queue_processor_task is not None and not _queue_processor_task.done()
        }

    @app.get("/api/executions/{execution_id}", response_model=WorkflowExecution)
    async def get_execution(execution_id: str):
        """
        Get execution status and details.

        First checks in-memory cache (for running executions), then storage (for completed).

        Args:
            execution_id: The execution ID to retrieve.
        """
        # First check in-memory cache (for running/pending executions)
        if execution_id in _executions:
            return _executions[execution_id]

        # Then check scalable storage (for completed/failed/cancelled)
        storage = _get_execution_storage()
        execution = storage.get_execution(execution_id)
        if execution:
            return execution

        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")

    @app.post("/api/executions/{execution_id}/cancel")
    async def cancel_execution(execution_id: str):
        """
        Cancel a running execution.

        Args:
            execution_id: The execution ID to cancel.
        """
        if execution_id not in _executions:
            raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")

        execution = _executions[execution_id]

        if execution.status not in (ExecutionStatus.PENDING, ExecutionStatus.RUNNING):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel execution in {execution.status} state"
            )

        # Signal the background task to stop
        _cancelled_executions.add(execution_id)

        # Actually terminate the running process if it exists
        if execution_id in _running_processes:
            process = _running_processes[execution_id]
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)  # Wait up to 5 seconds for graceful termination
                if process.is_alive():
                    process.kill()  # Force kill if still running
            del _running_processes[execution_id]

        execution.status = ExecutionStatus.CANCELLED
        execution.completed_at = datetime.now()

        # Save to persistence immediately
        _save_executions()

        return {"status": "cancelled", "execution_id": execution_id}

    @app.get("/api/executions")
    async def list_executions(
        workflow_id: Optional[str] = None,
        status: Optional[ExecutionStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        """
        List workflow executions with optional filtering and pagination.

        Uses scalable storage with per-run files for efficient handling of large datasets.

        Args:
            workflow_id: Filter by workflow ID.
            status: Filter by execution status.
            limit: Maximum number of results (default 50).
            offset: Number of results to skip for pagination (default 0).

        Returns:
            Dict with executions list, total count, pagination info.
        """
        storage = _get_execution_storage()
        status_str = status.value if status else None

        # Get paginated executions from storage
        executions, total = storage.list_executions_full(
            workflow_id=workflow_id,
            status=status_str,
            limit=limit,
            offset=offset,
        )

        # Also include currently running executions from in-memory cache
        # (they may not be persisted to storage yet)
        running_executions = []
        for exec_id, exec in _executions.items():
            if exec.status in (ExecutionStatus.RUNNING, ExecutionStatus.PENDING):
                # Apply filters
                if workflow_id and exec.workflow_id != workflow_id:
                    continue
                if status_str and exec.status.value != status_str:
                    continue
                # Check if not already in list (avoid duplicates)
                if not any(e.id == exec_id for e in executions):
                    running_executions.append(exec)

        # Merge running executions at the top if on first page
        if offset == 0 and running_executions:
            # Sort running executions by start time
            running_executions.sort(key=lambda e: e.started_at or datetime.min, reverse=True)
            executions = running_executions + executions
            total += len(running_executions)

        return {
            "executions": executions,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(executions)) < total,
        }

    @app.post("/api/executions/storage/refresh")
    async def refresh_execution_storage():
        """
        Refresh the execution storage index.

        Detects files deleted or added externally and updates the index.
        Call this after manually modifying files on disk.

        Returns:
            Number of changes detected.
        """
        storage = _get_execution_storage()
        changes = storage.refresh_index()

        return {
            "status": "refreshed",
            "changes_detected": changes,
            "total_executions": len(storage._index_cache)
        }

    @app.get("/api/executions/storage/stats")
    async def get_execution_storage_stats():
        """
        Get execution storage statistics.

        Useful for monitoring and debugging storage health.
        """
        storage = _get_execution_storage()
        stats = storage.get_stats()

        # Add info about in-memory executions
        stats["in_memory_executions"] = len(_executions)
        stats["in_memory_running"] = sum(
            1 for e in _executions.values()
            if e.status in (ExecutionStatus.RUNNING, ExecutionStatus.PENDING)
        )

        return stats

    @app.delete("/api/executions/{execution_id}")
    async def delete_execution(execution_id: str):
        """
        Delete an execution from storage.

        Removes both the per-run file and index entry.

        Args:
            execution_id: The execution ID to delete.

        Returns:
            Success status and message.
        """
        # Remove from in-memory cache if present
        if execution_id in _executions:
            del _executions[execution_id]

        # Remove from storage
        storage = _get_execution_storage()
        success = storage.delete_execution(execution_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")

        return {"status": "deleted", "execution_id": execution_id}

    @app.delete("/api/executions")
    async def delete_multiple_executions(execution_ids: List[str]):
        """
        Delete multiple executions from storage.

        Args:
            execution_ids: List of execution IDs to delete.

        Returns:
            Success status with count of deleted executions.
        """
        storage = _get_execution_storage()
        deleted_count = 0
        failed_ids = []

        for exec_id in execution_ids:
            # Remove from in-memory cache if present
            if exec_id in _executions:
                del _executions[exec_id]

            # Remove from storage
            if storage.delete_execution(exec_id):
                deleted_count += 1
            else:
                failed_ids.append(exec_id)

        return {
            "status": "deleted",
            "deleted_count": deleted_count,
            "total_requested": len(execution_ids),
            "failed_ids": failed_ids
        }

    @app.get("/api/tasks")
    async def list_task_directories():
        """
        List available task directories for workflow discovery.

        Recursively scans the tasks directory for folders containing
        graph_config.yaml files, supporting nested folder structures.
        """
        tasks_dir = Path(app.state.tasks_dir)

        if not tasks_dir.exists():
            return []

        tasks = []
        # Recursively find all graph_config.yaml files and get their parent directories
        for config_path in tasks_dir.rglob("graph_config.yaml"):
            if not config_path.is_file():
                continue

            task_dir = config_path.parent
            # Create a relative name from the tasks_dir for better display
            relative_path = task_dir.relative_to(tasks_dir)

            tasks.append({
                "name": str(relative_path),  # e.g., "structured_output_with_multi_llm/dpo_samples"
                "path": str(task_dir),
                "has_workflow": True,  # We only include dirs with graph_config.yaml
            })

        return tasks

    # NOTE: The /api/models endpoint is defined earlier in the file (around line 589)
    # with full status checking and is_builtin flag support. Do not duplicate here.

    def _extract_class_or_function(content: str, name: str) -> Optional[str]:
        """
        Extract a specific class or function definition from Python source code.

        Args:
            content: Full Python file content
            name: Name of the class or function to extract

        Returns:
            The extracted code block or None if not found
        """
        import ast

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return None

        lines = content.splitlines(keepends=True)

        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == name:
                    # Get the start line (1-indexed in AST)
                    start_line = node.lineno - 1

                    # Find the end line by looking at the last line of the node
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') and node.end_lineno else start_line + 1

                    # Extract the code block
                    extracted_lines = lines[start_line:end_line]

                    # Also extract any decorators above the class/function
                    decorator_lines = []
                    for decorator in getattr(node, 'decorator_list', []):
                        dec_start = decorator.lineno - 1
                        dec_end = decorator.end_lineno if hasattr(decorator, 'end_lineno') else dec_start + 1
                        # Only include if it's above the function/class definition
                        if dec_start < start_line:
                            decorator_lines.extend(lines[dec_start:dec_end])

                    # Combine decorators and the main code
                    result = ''.join(decorator_lines + extracted_lines)
                    return result.rstrip() + '\n'

        return None

    @app.get("/api/file-content")
    async def get_file_content(file_path: str, workflow_id: Optional[str] = None, extract_only: bool = True):
        """
        Get the content of a Python file referenced by a node.

        Args:
            file_path: Module path (e.g., 'tasks.examples.image_to_qna.task_executor.QuestionExtractProcessor')
                       or relative/absolute file path
            workflow_id: Optional workflow ID to resolve relative paths
            extract_only: If True, extract only the specific class/function. If False, return full file.
        """
        try:
            # If it looks like a module path (contains dots but no slashes)
            if '.' in file_path and '/' not in file_path and '\\' not in file_path:
                parts = file_path.split('.')
                class_or_func_name = parts[-1] if len(parts) >= 2 else None

                # Get workflow directory if available
                workflow_dir = None
                if workflow_id and workflow_id in _workflows:
                    workflow = _workflows[workflow_id]
                    workflow_dir = Path(workflow.source_path).parent

                possible_paths = []

                # Strategy 1: Check if it's a simple local module (e.g., 'task_executor.ClassName')
                if len(parts) == 2:
                    module_name = parts[0]
                    if workflow_dir:
                        possible_paths.extend([
                            workflow_dir / f"{module_name}.py",
                            workflow_dir / "functions" / f"{module_name}.py",
                            workflow_dir / "processors" / f"{module_name}.py",
                        ])

                # Strategy 2: Full module path (e.g., 'tasks.examples.image_to_qna.task_executor.ClassName')
                # The last part is likely the class name, second-to-last is the module file
                if len(parts) >= 3:
                    # Try treating last part as class name
                    module_parts = parts[:-1]  # Everything except the class name
                    module_file = '/'.join(module_parts) + '.py'

                    # Try relative to tasks_dir root
                    tasks_root = Path(app.state.tasks_dir).parent  # Go up from tasks_dir
                    possible_paths.append(tasks_root / module_file)

                    # Try relative to current working directory
                    possible_paths.append(Path(module_file))

                    # Try relative to workflow directory
                    if workflow_dir:
                        possible_paths.append(workflow_dir / module_file)
                        # Also try just the last module file name in workflow dir
                        possible_paths.append(workflow_dir / f"{module_parts[-1]}.py")

                # Strategy 3: Check workflow directory for common names like task_executor.py
                if workflow_dir:
                    possible_paths.extend([
                        workflow_dir / "task_executor.py",
                        workflow_dir / "processors.py",
                        workflow_dir / "functions.py",
                    ])

                # Try all possible paths
                for possible_path in possible_paths:
                    if possible_path.exists():
                        with open(possible_path, 'r') as f:
                            full_content = f.read()

                        # Try to extract just the specific class or function
                        extracted_content = None
                        if extract_only and class_or_func_name:
                            extracted_content = _extract_class_or_function(full_content, class_or_func_name)

                        # If extraction was requested but failed, return empty string (not the full file)
                        # This prevents showing the entire file when a specific class doesn't exist
                        if extract_only and class_or_func_name and not extracted_content:
                            return {
                                "content": "",  # Class/function not found - return empty
                                "full_content": full_content,
                                "path": str(possible_path.resolve()),
                                "module_path": file_path,
                                "class_name": class_or_func_name,
                                "extracted": False,
                                "not_found": True
                            }

                        return {
                            "content": extracted_content if extracted_content else full_content,
                            "full_content": full_content,
                            "path": str(possible_path.resolve()),
                            "module_path": file_path,
                            "class_name": class_or_func_name,
                            "extracted": extracted_content is not None
                        }

                return {
                    "error": f"Could not find module file for {file_path}. Tried: {[str(p) for p in possible_paths[:5]]}",
                    "content": None
                }
            else:
                # It's a file path
                full_path = Path(file_path)

                # If relative, try to resolve against workflow directory
                if not full_path.is_absolute() and workflow_id and workflow_id in _workflows:
                    workflow = _workflows[workflow_id]
                    workflow_dir = Path(workflow.source_path).parent
                    full_path = workflow_dir / file_path

                if full_path.exists():
                    with open(full_path, 'r') as f:
                        content = f.read()
                    return {"content": content, "path": str(full_path)}
                else:
                    return {"error": f"File not found: {full_path}", "content": None}

        except Exception as e:
            return {"error": str(e), "content": None}

    @app.get("/api/media/file")
    async def serve_media_file(path: str, workflow_id: Optional[str] = None):
        """
        Serve a media file (audio, image, etc.) from the filesystem.

        This endpoint allows the frontend to access media files generated by workflows,
        such as audio outputs stored in workflow output directories.

        Args:
            path: Absolute path to the media file
            workflow_id: Optional workflow ID for validation

        Returns:
            FileResponse with the media file content
        """
        import mimetypes

        try:
            file_path = Path(path)

            # Security: Only allow serving files from allowed directories
            # 1. Files in tasks/ directory (workflow outputs)
            # 2. Files in output/ directory
            allowed_prefixes = [
                str(Path.cwd() / "tasks"),
                str(Path.cwd() / "output"),
                "/tmp",
            ]

            # Also allow paths that are under a workflow's directory
            if workflow_id and workflow_id in _workflows:
                workflow = _workflows[workflow_id]
                workflow_dir = str(Path(workflow.source_path).parent)
                allowed_prefixes.append(workflow_dir)

            # Check if path is allowed
            abs_path = str(file_path.resolve())
            is_allowed = any(abs_path.startswith(prefix) for prefix in allowed_prefixes)

            if not is_allowed:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: Path not in allowed directories"
                )

            if not file_path.exists():
                raise HTTPException(status_code=404, detail=f"File not found: {path}")

            if not file_path.is_file():
                raise HTTPException(status_code=400, detail=f"Not a file: {path}")

            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type is None:
                mime_type = "application/octet-stream"

            return FileResponse(
                path=str(file_path),
                media_type=mime_type,
                filename=file_path.name
            )

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/workflows/{workflow_id}/yaml")
    async def get_workflow_yaml(workflow_id: str):
        """
        Get the raw YAML content for a workflow.

        Returns the full graph_config.yaml file content.
        """
        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow = _workflows[workflow_id]
        yaml_path = Path(workflow.source_path)

        if not yaml_path.exists():
            return {"error": "YAML file not found", "content": None, "path": None}

        try:
            with open(yaml_path, 'r') as f:
                content = f.read()
            return {
                "content": content,
                "path": str(yaml_path.resolve()),
                "filename": yaml_path.name
            }
        except Exception as e:
            return {"error": str(e), "content": None, "path": None}

    @app.get("/api/workflows/{workflow_id}/code")
    async def get_workflow_code(workflow_id: str):
        """
        Get the task_executor.py content for a workflow.

        Looks for task_executor.py in the workflow's directory.
        Also returns a list of all Python files in the directory.
        """
        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow = _workflows[workflow_id]
        workflow_dir = Path(workflow.source_path).parent

        # Look for common Python files
        python_files = []
        code_files = {}

        common_names = ['task_executor.py', 'processors.py', 'functions.py', 'utils.py']

        # First add common named files if they exist
        for name in common_names:
            py_path = workflow_dir / name
            if py_path.exists():
                try:
                    with open(py_path, 'r') as f:
                        content = f.read()
                    code_files[name] = {
                        "content": content,
                        "path": str(py_path.resolve()),
                        "filename": name
                    }
                    python_files.append(name)
                except Exception:
                    pass

        # Then add any other .py files
        for py_path in workflow_dir.glob('*.py'):
            if py_path.name not in python_files and not py_path.name.startswith('__'):
                try:
                    with open(py_path, 'r') as f:
                        content = f.read()
                    code_files[py_path.name] = {
                        "content": content,
                        "path": str(py_path.resolve()),
                        "filename": py_path.name
                    }
                    python_files.append(py_path.name)
                except Exception:
                    pass

        # Return primary task_executor.py content plus list of all files
        primary_file = code_files.get('task_executor.py')

        return {
            "primary": primary_file,
            "files": code_files,
            "file_list": python_files,
            "workflow_dir": str(workflow_dir.resolve())
        }

    @app.get("/api/workflows/{workflow_id}/node/{node_id}/code/{code_type}")
    async def get_node_code(workflow_id: str, node_id: str, code_type: str):
        """
        Get the code for a specific node from task_executor.py.

        Uses AST-based detection to find code blocks by checking base class inheritance.
        This is the single source of truth - no markers or metadata copies.

        Args:
            workflow_id: The workflow ID
            node_id: The node ID
            code_type: Type of code ('pre_process', 'post_process', 'lambda', 'branch_condition', 'output_generator', 'data_transform')

        Returns:
            { "code": "...", "found": true/false }
        """
        import ast

        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        workflow = _workflows[workflow_id]
        workflow_dir = Path(workflow.source_path).parent
        task_executor_path = workflow_dir / "task_executor.py"

        valid_types = {'pre_process', 'post_process', 'lambda', 'branch_condition', 'output_generator', 'data_transform'}
        if code_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Invalid code_type: {code_type}")

        if not task_executor_path.exists():
            return {"code": "", "found": False, "path": None}

        try:
            with open(task_executor_path, 'r') as f:
                content = f.read()
        except Exception as e:
            return {"code": "", "found": False, "error": str(e)}

        # Find the code block using AST
        code = _get_node_code_from_file(content, node_id, code_type)

        return {
            "code": code if code else "",
            "found": code is not None,
            "path": str(task_executor_path.resolve())
        }

    @app.put("/api/workflows/{workflow_id}/yaml")
    async def save_workflow_yaml(workflow_id: str, data: Dict[str, Any]):
        """
        Save edited YAML content to the workflow's graph_config.yaml file.

        Body: { "content": "yaml content string" }
        """
        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        workflow = _workflows[workflow_id]
        config_path = Path(workflow.source_path)

        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Workflow config file not found")

        content = data.get("content", "")

        # Empty content is allowed - save an empty file
        if not content or not content.strip():
            with open(config_path, 'w') as f:
                f.write("")
            return {"status": "saved", "path": str(config_path), "message": "Empty file saved"}

        try:
            # Validate YAML syntax
            import yaml
            yaml.safe_load(content)

            # Write to file
            with open(config_path, 'w') as f:
                f.write(content)

            # Reload the workflow from disk to update in-memory cache
            try:
                graph = app.state.graph_builder.build_from_yaml(str(config_path))
                _workflows[workflow_id] = graph
            except Exception as reload_error:
                print(f"Warning: Could not reload workflow after YAML save: {reload_error}")
                # Still return success since file was saved

            return {"status": "saved", "path": str(config_path)}
        except yaml.YAMLError as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")

    @app.put("/api/workflows/{workflow_id}/code/{filename}")
    async def save_workflow_code(workflow_id: str, filename: str, data: Dict[str, Any]):
        """
        Save edited Python code to a file in the workflow directory.

        Body: { "content": "python code string" }
        """
        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        workflow = _workflows[workflow_id]
        workflow_dir = Path(workflow.source_path).parent

        # Security: only allow .py files in the workflow directory
        if not filename.endswith('.py'):
            raise HTTPException(status_code=400, detail="Only Python files can be saved")

        # Prevent path traversal
        safe_filename = Path(filename).name
        file_path = workflow_dir / safe_filename

        content = data.get("content", "")

        # Empty content is allowed - just save an empty file
        if not content or not content.strip():
            with open(file_path, 'w') as f:
                f.write("")
            return {"status": "saved", "path": str(file_path), "message": "Empty file saved"}

        try:
            # Basic Python syntax check
            compile(content, safe_filename, 'exec')

            # Write to file
            with open(file_path, 'w') as f:
                f.write(content)

            return {"status": "saved", "path": str(file_path)}
        except SyntaxError as e:
            raise HTTPException(status_code=400, detail=f"Python syntax error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")

    @app.post("/api/workflows", response_model=WorkflowSaveResponse)
    async def create_workflow(request: WorkflowCreateRequest):
        """
        Create a new workflow in the tasks directory.

        Creates:
        - A new directory with the workflow name (sanitized)
        - graph_config.yaml with the workflow configuration
        - task_executor.py with any custom processors
        """
        return await _save_workflow_to_disk(app, request, is_new=True)

    @app.put("/api/workflows/{workflow_id}", response_model=WorkflowSaveResponse)
    async def update_workflow(workflow_id: str, request: WorkflowCreateRequest):
        """
        Update an existing workflow.

        Updates:
        - graph_config.yaml with the workflow configuration
        - task_executor.py with any custom processors
        """
        request.id = workflow_id
        return await _save_workflow_to_disk(app, request, is_new=False)

    @app.delete("/api/workflows/{workflow_id}")
    async def delete_workflow(workflow_id: str):
        """
        Delete a workflow.

        If the workflow has a source_path (file-based), deletes the entire workflow directory.
        Also removes the workflow from the cache.
        """
        import shutil

        # Check if workflow exists
        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

        workflow = _workflows[workflow_id]

        # If workflow has a source path, delete the directory
        if workflow.source_path:
            workflow_dir = Path(workflow.source_path).parent
            if workflow_dir.exists():
                try:
                    shutil.rmtree(workflow_dir)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to delete workflow directory: {str(e)}")

        # Remove from cache
        del _workflows[workflow_id]

        return {"success": True, "message": f"Workflow '{workflow_id}' deleted successfully"}

    @app.patch("/api/workflows/{workflow_id}/rename")
    async def rename_workflow(workflow_id: str, data: Dict[str, Any]):
        """
        Rename a workflow.

        Updates the name in the graph_config.yaml file.
        """
        import yaml

        new_name = data.get("name", "").strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="Name is required")

        # Check if workflow exists
        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

        workflow = _workflows[workflow_id]

        # Update the YAML file if it exists
        if workflow.source_path:
            yaml_path = Path(workflow.source_path)
            if yaml_path.exists():
                try:
                    with open(yaml_path, 'r') as f:
                        config = yaml.safe_load(f)

                    config['name'] = new_name

                    with open(yaml_path, 'w') as f:
                        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to update workflow file: {str(e)}")

        # Update in cache
        workflow.name = new_name

        return {"success": True, "name": new_name, "message": f"Workflow renamed to '{new_name}'"}

    @app.put("/api/workflows/{workflow_id}/nodes/{node_id}")
    async def update_node(workflow_id: str, node_id: str, node_data: Dict[str, Any]):
        """
        Update a node's configuration in the workflow.

        Args:
            workflow_id: The workflow ID.
            node_id: The node ID to update.
            node_data: The updated node data.
        """
        import yaml

        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        workflow = _workflows[workflow_id]

        # Find the node
        node = next((n for n in workflow.nodes if n.id == node_id), None)

        # UPSERT: If node doesn't exist, create it first
        if not node:
            # Create a new node based on node_data
            from studio.models import WorkflowNode, ModelConfig as StudioModelConfig

            node_type = node_data.get('node_type', 'output')  # Default to output since that's common case

            # Create the node object
            node = WorkflowNode(
                id=node_id,
                node_type=node_type,
                summary=node_data.get('summary', node_data.get('node_name', node_id)),
                description=node_data.get('description', ''),
            )

            # Set type-specific attributes
            if node_type == 'output':
                node.output_config = node_data.get('output_config', {})
            elif node_type == 'data':
                node.data_config = node_data.get('data_config', {})
            elif node_type == 'llm':
                if 'model' in node_data:
                    node.model = StudioModelConfig(**node_data['model']) if isinstance(node_data['model'], dict) else node_data['model']
                if 'prompt' in node_data:
                    node.prompt = node_data['prompt']

            # Add to workflow
            workflow.nodes.append(node)

        # Update in-memory node fields
        if "summary" in node_data:
            node.summary = node_data["summary"]
        if "description" in node_data:
            node.description = node_data["description"]
        if "prompt" in node_data:
            node.prompt = node_data["prompt"]
        if "model" in node_data:
            if node.model:
                node.model.name = node_data["model"].get("name", node.model.name)
                node.model.parameters = node_data["model"].get("parameters", node.model.parameters)
                # Handle structured_output - can be set, updated, or removed (None)
                if "structured_output" in node_data["model"]:
                    node.model.structured_output = node_data["model"]["structured_output"]
            else:
                from studio.models import ModelConfig
                node.model = ModelConfig(**node_data["model"])
        if "pre_process" in node_data:
            node.pre_process = node_data["pre_process"]
        if "post_process" in node_data:
            node.post_process = node_data["post_process"]
        if "function_path" in node_data:
            node.function_path = node_data["function_path"]
        if "output_config" in node_data:
            node.output_config = node_data["output_config"]
        if "data_config" in node_data:
            node.data_config = node_data["data_config"]
        if "output_keys" in node_data:
            node.output_keys = node_data["output_keys"]
        if "metadata" in node_data:
            node.metadata.update(node_data["metadata"])

        # Handle inline code fields - save directly to task_executor.py (single source of truth)
        # Empty string signals deletion of existing code
        workflow_dir = Path(workflow.source_path).parent if workflow.source_path else None

        if workflow_dir:
            # Pre-processor code (empty string = delete)
            if "_pre_process_code" in node_data:
                code_content = node_data["_pre_process_code"]
                # Write to task_executor.py (single source of truth - no metadata copy)
                _update_task_executor_code(
                    workflow_dir=workflow_dir,
                    node_id=node_id,
                    code_type='pre_process',
                    code_content=code_content,
                    node_summary=node.summary
                )
                # Auto-generate path only if code is not a stub
                clean_code = _extract_class_or_function_body(code_content) if code_content else ""
                is_stub = _is_stub_code(clean_code, 'pre_process') if clean_code else True
                if code_content and code_content.strip() and not is_stub:
                    task_name = _get_task_name_from_path(workflow_dir)
                    safe_node_id = re.sub(r'[^a-zA-Z0-9_]', '', node_id.replace('-', '_').replace(' ', '_'))
                    node.pre_process = f"tasks.{task_name}.task_executor.{safe_node_id}PreProcessor"
                else:
                    node.pre_process = None

            # Post-processor code (empty string = delete)
            if "_post_process_code" in node_data:
                code_content = node_data["_post_process_code"]
                _update_task_executor_code(
                    workflow_dir=workflow_dir,
                    node_id=node_id,
                    code_type='post_process',
                    code_content=code_content,
                    node_summary=node.summary
                )
                # Auto-generate path only if code is not a stub
                clean_code = _extract_class_or_function_body(code_content) if code_content else ""
                is_stub = _is_stub_code(clean_code, 'post_process') if clean_code else True
                if code_content and code_content.strip() and not is_stub:
                    task_name = _get_task_name_from_path(workflow_dir)
                    safe_node_id = re.sub(r'[^a-zA-Z0-9_]', '', node_id.replace('-', '_').replace(' ', '_'))
                    node.post_process = f"tasks.{task_name}.task_executor.{safe_node_id}PostProcessor"
                else:
                    node.post_process = None

            # Lambda function code (empty string = delete)
            if "_lambda_code" in node_data:
                code_content = node_data["_lambda_code"]
                _update_task_executor_code(
                    workflow_dir=workflow_dir,
                    node_id=node_id,
                    code_type='lambda',
                    code_content=code_content,
                    node_summary=node.summary
                )
                # Auto-generate path only if code is not a stub
                clean_code = _extract_class_or_function_body(code_content) if code_content else ""
                is_stub = _is_stub_code(clean_code, 'lambda') if clean_code else True
                if code_content and code_content.strip() and not is_stub:
                    task_name = _get_task_name_from_path(workflow_dir)
                    safe_node_id = re.sub(r'[^a-zA-Z0-9_]', '', node_id.replace('-', '_').replace(' ', '_'))
                    # Use class-based pattern (LambdaFunction) for new code
                    node.function_path = f"tasks.{task_name}.task_executor.{safe_node_id}Lambda"
                else:
                    node.function_path = None

            # Branch condition code (empty string = delete)
            if "_branch_condition_code" in node_data:
                code_content = node_data["_branch_condition_code"]
                _update_task_executor_code(
                    workflow_dir=workflow_dir,
                    node_id=node_id,
                    code_type='branch_condition',
                    code_content=code_content,
                    node_summary=node.summary
                )

            # Output generator code (from top-level _output_generator_code or output_config._generator_code)
            # Empty string signals deletion
            generator_code = node_data.get("_output_generator_code")
            if generator_code is None and "output_config" in node_data:
                generator_code = node_data["output_config"].get("_generator_code")
            if generator_code is not None:  # Process if key exists (even if empty)
                _update_task_executor_code(
                    workflow_dir=workflow_dir,
                    node_id=node_id,
                    code_type='output_generator',
                    code_content=generator_code,
                    node_summary=node.summary
                )
                # Auto-generate the generator path only if code is not a stub
                # (stubs are not actually saved to task_executor.py)
                clean_code = _extract_class_or_function_body(generator_code) if generator_code else ""
                is_stub = _is_stub_code(clean_code, 'output_generator') if clean_code else True

                if generator_code and generator_code.strip() and not is_stub:
                    task_name = _get_task_name_from_path(workflow_dir)
                    safe_node_id = re.sub(r'[^a-zA-Z0-9_]', '', node_id.replace('-', '_').replace(' ', '_'))
                    generator_path = f"tasks.{task_name}.task_executor.{safe_node_id}Generator"
                    # Update output_config with the generator path
                    if not hasattr(node, 'output_config') or node.output_config is None:
                        node.output_config = {}
                    node.output_config['generator'] = generator_path
                else:
                    # Clear generator path when code is deleted or is just a stub
                    if hasattr(node, 'output_config') and node.output_config:
                        node.output_config['generator'] = None

            # For OUTPUT nodes: Check if task_executor.py already has a generator
            # This handles the case when OUTPUT node is added via UI and task_executor.py already has code
            if node.node_type == 'output' and generator_code is None:
                task_executor_path = workflow_dir / "task_executor.py"
                if task_executor_path.exists():
                    try:
                        existing_content = task_executor_path.read_text()
                        safe_node_id = re.sub(r'[^a-zA-Z0-9_]', '', node_id.replace('-', '_').replace(' ', '_'))
                        # Check if there's a generator class for this node
                        existing_generator = _find_code_block_by_ast(existing_content, node_id, 'output_generator')
                        if existing_generator and not _is_stub_code(existing_generator, 'output_generator'):
                            task_name = _get_task_name_from_path(workflow_dir)
                            generator_path = f"tasks.{task_name}.task_executor.{safe_node_id}Generator"
                            if not hasattr(node, 'output_config') or node.output_config is None:
                                node.output_config = {}
                            node.output_config['generator'] = generator_path
                    except Exception as e:
                        print(f"Warning: Could not check existing generator code: {e}")

            # Data transform code (from top-level _data_transform_code or data_config._transform_code)
            # Empty string signals deletion
            transform_code = node_data.get("_data_transform_code")
            if transform_code is None and "data_config" in node_data:
                transform_code = node_data["data_config"].get("_transform_code")
            if transform_code is not None:  # Process if key exists (even if empty)
                _update_task_executor_code(
                    workflow_dir=workflow_dir,
                    node_id=node_id,
                    code_type='data_transform',
                    code_content=transform_code,
                    node_summary=node.summary
                )
                # Auto-generate the transform path only if code is not a stub
                clean_code = _extract_class_or_function_body(transform_code) if transform_code else ""
                is_stub = _is_stub_code(clean_code, 'data_transform') if clean_code else True
                if transform_code and transform_code.strip() and not is_stub:
                    task_name = _get_task_name_from_path(workflow_dir)
                    safe_node_id = re.sub(r'[^a-zA-Z0-9_]', '', node_id.replace('-', '_').replace(' ', '_'))
                    transform_path = f"tasks.{task_name}.task_executor.{safe_node_id}Transform"
                    # Update data_config with the transform path
                    if not hasattr(node, 'data_config') or node.data_config is None:
                        node.data_config = {}
                    if 'source' not in node.data_config:
                        node.data_config['source'] = {}
                    # Set transform class on the source (or first source if array)
                    source = node.data_config['source']
                    if isinstance(source, list) and len(source) > 0:
                        source[0]['transform_class'] = transform_path
                    elif isinstance(source, dict):
                        source['transform_class'] = transform_path
                else:
                    # Clear transform class when code is deleted or is just a stub
                    if hasattr(node, 'data_config') and node.data_config and 'source' in node.data_config:
                        source = node.data_config['source']
                        if isinstance(source, list) and len(source) > 0:
                            source[0].pop('transform_class', None)
                        elif isinstance(source, dict):
                            source.pop('transform_class', None)

        # Persist changes to the YAML file
        if workflow.source_path:
            yaml_path = Path(workflow.source_path)
            if yaml_path.exists():
                try:
                    with open(yaml_path, 'r') as f:
                        config = yaml.safe_load(f)

                    # Handle output nodes specially - they store config at workflow level
                    if node.node_type == 'output':
                        # Build output_config from node.output_config (which has generator path)
                        # and merge with any output_config from node_data
                        output_config = {}

                        # Start with node.output_config (has generator path set above)
                        if hasattr(node, 'output_config') and node.output_config:
                            output_config.update(node.output_config)

                        # Merge in output_config from node_data (has output_map, etc.)
                        if "output_config" in node_data:
                            output_config.update(node_data["output_config"])

                        # Clean output_config - remove internal fields starting with '_'
                        clean_output_config = {k: v for k, v in output_config.items() if not k.startswith('_') and v is not None}

                        # REPLACE entire output_config (not merge) so removed fields are deleted
                        if clean_output_config:
                            config['output_config'] = clean_output_config
                        elif 'output_config' in config:
                            del config['output_config']
                    elif node.node_type == 'data':
                        # Handle data nodes - they store config at workflow level
                        if "data_config" in node_data:
                            # Clean data_config - remove internal fields starting with '_'
                            clean_data_config = {k: v for k, v in node_data["data_config"].items() if not k.startswith('_')}
                            config['data_config'] = clean_data_config
                    else:
                        # Update regular nodes in graph_config.nodes
                        if 'graph_config' not in config:
                            config['graph_config'] = {}
                        if 'nodes' not in config['graph_config']:
                            config['graph_config']['nodes'] = {}

                        yaml_node = config['graph_config']['nodes'].get(node_id)

                        # Create node if it doesn't exist (upsert)
                        if yaml_node is None:
                            yaml_node = {
                                'node_type': node.node_type or 'llm',
                            }
                            config['graph_config']['nodes'][node_id] = yaml_node

                        # Update fields that were changed
                        if "summary" in node_data:
                            yaml_node['node_name'] = node_data["summary"]
                        if "description" in node_data:
                            yaml_node['description'] = node_data["description"]
                        if "prompt" in node_data:
                            yaml_node['prompt'] = _convert_prompts_to_yaml_format(node_data["prompt"])
                        if "model" in node_data:
                            yaml_node['model'] = {
                                'name': node_data["model"].get("name"),
                                'parameters': node_data["model"].get("parameters", {})
                            }
                            # Remove empty parameters
                            if not yaml_node['model']['parameters']:
                                del yaml_node['model']['parameters']
                            # Include structured_output if present and enabled
                            so = node_data["model"].get("structured_output")
                            if so and so.get("enabled", True):
                                # Convert to YAML format (without 'enabled' field)
                                yaml_so = {}
                                if so.get("schema"):
                                    yaml_so["schema"] = so["schema"]
                                # Only include non-default options
                                if so.get("fallback_strategy") and so["fallback_strategy"] != "instruction":
                                    yaml_so["fallback_strategy"] = so["fallback_strategy"]
                                if so.get("retry_on_parse_error") is False:
                                    yaml_so["retry_on_parse_error"] = False
                                if so.get("max_parse_retries") and so["max_parse_retries"] != 2:
                                    yaml_so["max_parse_retries"] = so["max_parse_retries"]
                                if yaml_so:
                                    yaml_node['model']['structured_output'] = yaml_so
                            elif 'structured_output' in yaml_node.get('model', {}):
                                # Remove structured_output if it was disabled
                                del yaml_node['model']['structured_output']
                        # Use node.pre_process/post_process which are auto-generated from code
                        # (not node_data which only has explicit path overrides)
                        if node.pre_process:
                            yaml_node['pre_process'] = node.pre_process
                        elif 'pre_process' in yaml_node:
                            del yaml_node['pre_process']
                        if node.post_process:
                            yaml_node['post_process'] = node.post_process
                        elif 'post_process' in yaml_node:
                            del yaml_node['post_process']
                        if node.function_path:
                            yaml_node['function_path'] = node.function_path
                        elif 'function_path' in yaml_node:
                            del yaml_node['function_path']
                        if "output_keys" in node_data:
                            if node_data["output_keys"]:
                                yaml_node['output_keys'] = node_data["output_keys"]
                            elif 'output_keys' in yaml_node:
                                del yaml_node['output_keys']

                    with open(yaml_path, 'w') as f:
                        yaml.dump(config, f, Dumper=_get_yaml_dumper(), default_flow_style=False, sort_keys=False, allow_unicode=True)

                    # Reload workflow from disk to ensure in-memory cache is consistent
                    try:
                        graph = app.state.graph_builder.build_from_yaml(str(yaml_path))
                        _workflows[workflow_id] = graph
                        # Update node reference to the reloaded node
                        node = next((n for n in graph.nodes if n.id == node_id), node)
                    except Exception as reload_error:
                        print(f"Warning: Could not reload workflow after node update: {reload_error}")
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to persist node update to file: {str(e)}")

        # Return updated node data for frontend sync
        model_data = None
        if node.model:
            model_data = {
                "name": node.model.name,
                "parameters": node.model.parameters
            }
            if node.model.structured_output:
                model_data["structured_output"] = node.model.structured_output

        # Build response with all node data including output/data config
        response_node = {
            "id": node.id,
            "summary": node.summary,
            "description": node.description,
            "model": model_data,
            "prompt": node.prompt,
            "pre_process": node.pre_process,
            "post_process": node.post_process,
            "function_path": node.function_path,
        }

        # Include output_config for output nodes
        if node.node_type == 'output' and node.output_config:
            response_node["output_config"] = node.output_config

        # Include data_config for data nodes
        if node.node_type == 'data' and node.data_config:
            response_node["data_config"] = node.data_config

        return {
            "status": "updated",
            "node_id": node_id,
            "node": response_node
        }

    @app.delete("/api/workflows/{workflow_id}/nodes/{node_id}")
    async def delete_node(workflow_id: str, node_id: str):
        """
        Delete a node from the workflow.

        Args:
            workflow_id: The workflow ID.
            node_id: The node ID to delete.
        """
        import yaml

        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        workflow = _workflows[workflow_id]

        # Find the node
        node = next((n for n in workflow.nodes if n.id == node_id), None)
        if not node:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found in workflow")

        # Persist changes to the YAML file
        if workflow.source_path:
            yaml_path = Path(workflow.source_path)
            workflow_dir = yaml_path.parent
            if yaml_path.exists():
                try:
                    with open(yaml_path, 'r') as f:
                        config = yaml.safe_load(f)

                    # ========================================
                    # STEP 1: Clean up ALL code in task_executor.py for this node
                    # This handles all node types comprehensively
                    # ========================================
                    task_executor_path = workflow_dir / "task_executor.py"
                    if task_executor_path.exists():
                        try:
                            existing_content = task_executor_path.read_text()
                            updated_content = existing_content

                            # Remove ALL possible code types for this node
                            # This covers: LLM nodes (pre/post), Lambda nodes, Branch nodes,
                            # OUTPUT nodes (generator), DATA nodes (transform)
                            all_code_types = [
                                'pre_process',
                                'post_process',
                                'lambda',
                                'branch_condition',
                                'output_generator',
                                'data_transform'
                            ]
                            for code_type in all_code_types:
                                updated_content = _remove_code_block_from_file(updated_content, node_id, code_type)

                            # Write updated content or delete file if empty
                            if updated_content != existing_content:
                                if updated_content.strip():
                                    with open(task_executor_path, 'w') as f:
                                        f.write(updated_content)
                                else:
                                    task_executor_path.unlink()
                        except Exception as e:
                            print(f"Warning: Could not clean up node code from task_executor.py: {e}")

                    # ========================================
                    # STEP 2: Clean up YAML config based on node type
                    # ========================================

                    # OUTPUT nodes: Remove output_config from YAML
                    if node.node_type == 'output':
                        if 'output_config' in config:
                            del config['output_config']

                    # DATA nodes: Remove data_config from YAML
                    elif node.node_type == 'data':
                        if 'data_config' in config:
                            del config['data_config']

                    # Regular nodes (LLM, Lambda, Branch, etc.): Remove from graph_config.nodes
                    # Also remove any YAML references like pre_process, post_process paths
                    if 'graph_config' in config and 'nodes' in config['graph_config']:
                        if node_id in config['graph_config']['nodes']:
                            del config['graph_config']['nodes'][node_id]

                    # ========================================
                    # STEP 3: Clean up edges connected to this node
                    # Also clean up condition references in edges
                    # ========================================
                    if 'graph_config' in config and 'edges' in config['graph_config']:
                        # Remove edges that connect to/from this node
                        config['graph_config']['edges'] = [
                            e for e in config['graph_config']['edges']
                            if e.get('from') != node_id and e.get('to') != node_id
                        ]

                    # ========================================
                    # STEP 4: Save YAML and reload workflow
                    # ========================================
                    with open(yaml_path, 'w') as f:
                        yaml.dump(config, f, Dumper=_get_yaml_dumper(), default_flow_style=False, sort_keys=False, allow_unicode=True)

                    # Reload workflow from disk to update cache
                    try:
                        graph = app.state.graph_builder.build_from_yaml(str(yaml_path))
                        _workflows[workflow_id] = graph
                    except Exception as reload_error:
                        print(f"Warning: Could not reload workflow after node delete: {reload_error}")

                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to delete node from file: {str(e)}")

        return {"status": "deleted", "node_id": node_id}

    @app.post("/api/workflows/{workflow_id}/nodes")
    async def add_node(workflow_id: str, node_data: Dict[str, Any]):
        """
        Add a new node to the workflow.

        Args:
            workflow_id: The workflow ID.
            node_data: The node configuration including id, node_type, etc.
        """
        import yaml

        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        workflow = _workflows[workflow_id]

        node_id = node_data.get("id")
        if not node_id:
            raise HTTPException(status_code=400, detail="Node ID is required")

        # Check if node already exists
        existing = next((n for n in workflow.nodes if n.id == node_id), None)
        if existing:
            raise HTTPException(status_code=400, detail=f"Node {node_id} already exists")

        # Persist changes to the YAML file
        if workflow.source_path:
            yaml_path = Path(workflow.source_path)
            if yaml_path.exists():
                try:
                    with open(yaml_path, 'r') as f:
                        config = yaml.safe_load(f)

                    # Initialize graph_config.nodes if not present
                    if 'graph_config' not in config:
                        config['graph_config'] = {}
                    if 'nodes' not in config['graph_config']:
                        config['graph_config']['nodes'] = {}

                    node_type = node_data.get('node_type', 'llm')
                    workflow_dir = yaml_path.parent

                    # Handle output nodes specially - store config at workflow level
                    if node_type == 'output':
                        output_config = {}

                        # Check if task_executor.py has existing generator code for this node
                        task_executor_path = workflow_dir / "task_executor.py"
                        if task_executor_path.exists():
                            try:
                                existing_content = task_executor_path.read_text()
                                safe_node_id = re.sub(r'[^a-zA-Z0-9_]', '', node_id.replace('-', '_').replace(' ', '_'))
                                existing_generator = _find_code_block_by_ast(existing_content, node_id, 'output_generator')
                                if existing_generator and not _is_stub_code(existing_generator, 'output_generator'):
                                    task_name = _get_task_name_from_path(workflow_dir)
                                    generator_path = f"tasks.{task_name}.task_executor.{safe_node_id}Generator"
                                    output_config['generator'] = generator_path
                            except Exception as e:
                                print(f"Warning: Could not check existing generator code: {e}")

                        # Merge in output_config from node_data
                        if 'output_config' in node_data:
                            output_config.update(node_data['output_config'])

                        # Clean output_config - remove internal fields starting with '_'
                        clean_output_config = {k: v for k, v in output_config.items() if not k.startswith('_') and v is not None}
                        if clean_output_config:
                            config['output_config'] = clean_output_config
                        # Output nodes are not added to graph_config.nodes
                    elif node_type == 'data':
                        # Data nodes store config at workflow level as data_config
                        if 'data_config' in node_data:
                            # Clean data_config - remove internal fields starting with '_'
                            clean_data_config = {k: v for k, v in node_data['data_config'].items() if not k.startswith('_')}
                            config['data_config'] = clean_data_config
                        # Data nodes are not added to graph_config.nodes
                    else:
                        # Create the node config for regular nodes
                        yaml_node = {
                            'node_type': node_type,
                        }
                        if 'summary' in node_data:
                            yaml_node['node_name'] = node_data['summary']
                        if 'description' in node_data:
                            yaml_node['description'] = node_data['description']
                        if 'model' in node_data and node_data['model']:
                            yaml_node['model'] = {
                                'name': node_data['model'].get('name'),
                            }
                            if node_data['model'].get('parameters'):
                                yaml_node['model']['parameters'] = node_data['model']['parameters']
                        if 'prompt' in node_data:
                            yaml_node['prompt'] = _convert_prompts_to_yaml_format(node_data['prompt'])
                        if 'pre_process' in node_data:
                            yaml_node['pre_process'] = node_data['pre_process']
                        if 'post_process' in node_data:
                            yaml_node['post_process'] = node_data['post_process']
                        if 'function_path' in node_data:
                            yaml_node['function_path'] = node_data['function_path']
                        if 'output_keys' in node_data:
                            yaml_node['output_keys'] = node_data['output_keys']
                        if 'tools' in node_data:
                            yaml_node['tools'] = node_data['tools']
                        if 'tool_choice' in node_data:
                            yaml_node['tool_choice'] = node_data['tool_choice']

                        config['graph_config']['nodes'][node_id] = yaml_node

                    with open(yaml_path, 'w') as f:
                        yaml.dump(config, f, Dumper=_get_yaml_dumper(), default_flow_style=False, sort_keys=False, allow_unicode=True)

                    # Reload workflow from disk to update cache
                    try:
                        graph = app.state.graph_builder.build_from_yaml(str(yaml_path))
                        _workflows[workflow_id] = graph
                    except Exception as reload_error:
                        print(f"Warning: Could not reload workflow after node add: {reload_error}")

                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to add node to file: {str(e)}")

        return {"status": "added", "node_id": node_id}

    @app.post("/api/workflows/{workflow_id}/edges")
    async def add_edge(workflow_id: str, edge_data: Dict[str, Any]):
        """
        Add a new edge to the workflow.

        Args:
            workflow_id: The workflow ID.
            edge_data: The edge configuration including source, target, etc.
        """
        import yaml

        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        workflow = _workflows[workflow_id]

        source = edge_data.get("source") or edge_data.get("from")
        target = edge_data.get("target") or edge_data.get("to")
        if not source or not target:
            raise HTTPException(status_code=400, detail="Source and target are required")

        # Persist changes to the YAML file
        if workflow.source_path:
            yaml_path = Path(workflow.source_path)
            if yaml_path.exists():
                try:
                    with open(yaml_path, 'r') as f:
                        config = yaml.safe_load(f)

                    # Initialize graph_config.edges if not present
                    if 'graph_config' not in config:
                        config['graph_config'] = {}
                    if 'edges' not in config['graph_config']:
                        config['graph_config']['edges'] = []

                    # Create the edge config
                    yaml_edge = {
                        'from': source,
                        'to': target,
                    }
                    if 'label' in edge_data:
                        yaml_edge['label'] = edge_data['label']
                    if edge_data.get('is_conditional') or edge_data.get('condition'):
                        if 'condition' in edge_data:
                            yaml_edge['condition'] = edge_data['condition'].get('condition_path')
                        if 'path_map' in edge_data.get('condition', {}):
                            yaml_edge['path_map'] = edge_data['condition']['path_map']

                    config['graph_config']['edges'].append(yaml_edge)

                    with open(yaml_path, 'w') as f:
                        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

                    # Reload workflow from disk to update cache
                    try:
                        graph = app.state.graph_builder.build_from_yaml(str(yaml_path))
                        _workflows[workflow_id] = graph
                    except Exception as reload_error:
                        print(f"Warning: Could not reload workflow after edge add: {reload_error}")

                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to add edge to file: {str(e)}")

        return {"status": "added", "source": source, "target": target}

    @app.delete("/api/workflows/{workflow_id}/edges/{edge_id}")
    async def delete_edge(workflow_id: str, edge_id: str):
        """
        Delete an edge from the workflow.

        Args:
            workflow_id: The workflow ID.
            edge_id: The edge ID to delete (format: source-target or the edge's id).
        """
        import yaml

        if workflow_id not in _workflows:
            await list_workflows()

        if workflow_id not in _workflows:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        workflow = _workflows[workflow_id]

        # Persist changes to the YAML file
        if workflow.source_path:
            yaml_path = Path(workflow.source_path)
            if yaml_path.exists():
                try:
                    with open(yaml_path, 'r') as f:
                        config = yaml.safe_load(f)

                    # Delete matching edges
                    if 'graph_config' in config and 'edges' in config['graph_config']:
                        original_count = len(config['graph_config']['edges'])
                        # Try to match by edge_id (source-target pattern) or exact id
                        config['graph_config']['edges'] = [
                            e for e in config['graph_config']['edges']
                            if not (
                                f"{e.get('from')}-{e.get('to')}" == edge_id or
                                e.get('id') == edge_id
                            )
                        ]
                        deleted_count = original_count - len(config['graph_config']['edges'])

                        if deleted_count == 0:
                            raise HTTPException(status_code=404, detail=f"Edge {edge_id} not found")

                    with open(yaml_path, 'w') as f:
                        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

                    # Reload workflow from disk to update cache
                    try:
                        graph = app.state.graph_builder.build_from_yaml(str(yaml_path))
                        _workflows[workflow_id] = graph
                    except Exception as reload_error:
                        print(f"Warning: Could not reload workflow after edge delete: {reload_error}")

                except HTTPException:
                    raise
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to delete edge from file: {str(e)}")

        return {"status": "deleted", "edge_id": edge_id}

    # ==================== Code Execution & Debug Endpoints ====================

    @app.post("/api/code/execute")
    async def execute_code(request: CodeExecutionRequest):
        """
        Execute a Python file or function.

        Returns an execution ID for tracking. Use the WebSocket endpoint
        /ws/code/{execution_id} to stream output in real-time.
        """
        execution_id = str(uuid.uuid4())[:8]

        # Resolve file path
        file_path = Path(request.file_path)
        if not file_path.is_absolute():
            # Try to resolve relative to workflow directory
            if request.workflow_id and request.workflow_id in _workflows:
                workflow = _workflows[request.workflow_id]
                workflow_dir = Path(workflow.source_path).parent
                file_path = workflow_dir / request.file_path
            else:
                file_path = Path(app.state.tasks_dir) / request.file_path

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        # Prepare execution
        _code_executions[execution_id] = {
            "id": execution_id,
            "file_path": str(file_path),
            "function_name": request.function_name,
            "args": request.args or [],
            "workflow_id": request.workflow_id,
            "debug": request.debug,
            "breakpoints": request.breakpoints or [],
            "status": "pending",
            "output": [],
            "error": None,
            "started_at": None,
            "completed_at": None,
            "process": None,
            "debug_port": None
        }

        # Start execution in background
        asyncio.create_task(_run_code_execution(execution_id, file_path, request))

        return {
            "execution_id": execution_id,
            "status": "started",
            "websocket_url": f"/ws/code/{execution_id}"
        }

    @app.get("/api/code/executions/{execution_id}")
    async def get_code_execution(execution_id: str):
        """Get the status and output of a code execution."""
        if execution_id not in _code_executions:
            raise HTTPException(status_code=404, detail="Execution not found")

        execution = _code_executions[execution_id]
        return {
            "id": execution["id"],
            "status": execution["status"],
            "output": execution["output"],
            "error": execution["error"],
            "debug": execution["debug"],
            "debug_port": execution.get("debug_port"),
            "started_at": execution["started_at"],
            "completed_at": execution["completed_at"]
        }

    @app.post("/api/code/executions/{execution_id}/stop")
    async def stop_code_execution(execution_id: str):
        """Stop a running code execution."""
        if execution_id not in _code_executions:
            raise HTTPException(status_code=404, detail="Execution not found")

        execution = _code_executions[execution_id]
        if execution["status"] != "running":
            return {"status": execution["status"], "message": "Execution not running"}

        # Kill the process
        if execution.get("process"):
            try:
                execution["process"].terminate()
                execution["process"].wait(timeout=5)
            except Exception:
                execution["process"].kill()

        execution["status"] = "cancelled"
        execution["completed_at"] = datetime.now().isoformat()

        return {"status": "cancelled"}

    @app.post("/api/debug/action")
    async def debug_action(action: DebugAction):
        """
        Send a debug action to a running debug session.

        Actions: continue, step_over, step_into, step_out, stop
        """
        if action.session_id not in _code_executions:
            raise HTTPException(status_code=404, detail="Debug session not found")

        execution = _code_executions[action.session_id]
        if not execution.get("debug"):
            raise HTTPException(status_code=400, detail="Not a debug session")

        # Handle stop action
        if action.action == "stop":
            if execution.get("process"):
                execution["process"].terminate()
            execution["status"] = "cancelled"
            return {"status": "stopped"}

        # Get the DAP send function stored during connection
        dap_send = execution.get("dap_send_command")
        if not dap_send:
            raise HTTPException(status_code=400, detail="Debug session not ready - DAP not connected")

        # Map actions to DAP commands
        command_map = {
            "continue": "continue",
            "step_over": "next",
            "step_into": "stepIn",
            "step_out": "stepOut",
            "pause": "pause"
        }

        dap_command = command_map.get(action.action)
        if not dap_command:
            raise HTTPException(status_code=400, detail=f"Unknown debug action: {action.action}")

        try:
            # Send the DAP command (fire and forget - response comes via event listener)
            thread_id = execution.get("thread_id", 1)
            await dap_send(dap_command, {"threadId": thread_id})

            await _send_to_websocket(action.session_id, {
                "type": "debug",
                "content": f"[DEBUG] Sent {action.action} command"
            })

            return {"status": "sent", "action": action.action}

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Debug action failed: {str(e)}")

    class VariablesRequest(BaseModel):
        session_id: str
        variables_reference: int

    @app.post("/api/debug/variables")
    async def get_debug_variables(request: VariablesRequest):
        """Fetch child variables for a given variablesReference."""
        execution = _code_executions.get(request.session_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        fetch_vars = execution.get("dap_fetch_variables")
        if not fetch_vars:
            raise HTTPException(status_code=400, detail="Debug session not ready")

        try:
            variables = await fetch_vars(request.variables_reference)
            return {"variables": variables}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch variables: {str(e)}")

    @app.websocket("/ws/code/{execution_id}")
    async def websocket_code_output(websocket: WebSocket, execution_id: str):
        """
        WebSocket endpoint for streaming code execution output.

        Sends JSON messages with:
        - type: 'stdout' | 'stderr' | 'status' | 'debug'
        - content: The actual content
        - timestamp: ISO timestamp
        """
        await websocket.accept()
        _websocket_connections[execution_id] = websocket

        try:
            if execution_id not in _code_executions:
                await websocket.send_json({"type": "error", "content": "Execution not found"})
                await websocket.close()
                return

            execution = _code_executions[execution_id]

            # Send any existing output
            for line in execution["output"]:
                await websocket.send_json(line)

            # Keep connection alive until execution completes
            while execution["status"] in ("pending", "running"):
                try:
                    # Check for incoming messages (like breakpoint updates)
                    try:
                        data = await asyncio.wait_for(websocket.receive_json(), timeout=0.5)
                        # Handle incoming debug commands
                        if data.get("type") == "breakpoint":
                            execution["breakpoints"] = data.get("lines", [])
                    except asyncio.TimeoutError:
                        pass

                    # Send heartbeat
                    await websocket.send_json({"type": "heartbeat", "status": execution["status"]})
                    await asyncio.sleep(0.5)
                except WebSocketDisconnect:
                    break

            # Send final status
            await websocket.send_json({
                "type": "status",
                "status": execution["status"],
                "error": execution.get("error")
            })

        except WebSocketDisconnect:
            pass
        finally:
            _websocket_connections.pop(execution_id, None)


def _get_task_name_from_path(workflow_dir: Path) -> str:
    """
    Extract SyGra task name from workflow directory path.

    Examples:
        /path/to/tasks/examples/image_to_qna -> examples.image_to_qna
        /path/to/tasks/my_task -> my_task
    """
    # Find the 'tasks' directory in the path
    parts = workflow_dir.parts
    task_parts = []
    found_tasks = False

    for part in parts:
        if found_tasks:
            task_parts.append(part)
        elif part == "tasks":
            found_tasks = True

    if task_parts:
        return ".".join(task_parts)
    else:
        # Fallback: use just the directory name
        return workflow_dir.name


async def _run_code_execution(execution_id: str, file_path: Path, request: CodeExecutionRequest):
    """Background task to run Python code and stream output."""
    execution = _code_executions[execution_id]

    # Wait a moment for WebSocket to connect
    for _ in range(20):  # Wait up to 2 seconds
        if execution_id in _websocket_connections:
            break
        await asyncio.sleep(0.1)

    execution["status"] = "running"
    execution["started_at"] = datetime.now().isoformat()

    try:
        # Prepare the command
        python_executable = sys.executable

        # Store original file path for debug display
        original_file_path = file_path

        if request.debug and request.breakpoints:
            # Run with debugpy for debugging using DAP protocol
            debug_port = 5678 + hash(execution_id) % 1000  # Generate unique port
            execution["debug_port"] = debug_port
            execution["debug"] = True
            execution["breakpoints"] = request.breakpoints
            execution["target_file"] = str(file_path)  # Store for display

            # Create a wrapper script that sets up debugpy and runs the target
            # Uses wait_for_client() which waits for FULL DAP handshake including configurationDone
            import textwrap

            # Check if this is a SyGra workflow - if so, run via main.py
            workflow_dir = file_path.parent
            graph_config = workflow_dir / "graph_config.yaml"
            project_root = Path(__file__).parent.parent  # studio -> project root
            main_py = project_root / "main.py"

            if graph_config.exists() and main_py.exists():
                # SyGra workflow - run main.py with task argument (same as normal execution)
                task_name = _get_task_name_from_path(workflow_dir)
                run_target = str(main_py)
                run_args = ["--task", task_name, "--num_records", "2", "--batch_size", "1", "--debug", "True"]
            else:
                # Regular Python file - run directly
                run_target = str(file_path)
                run_args = request.args or []

            wrapper_code = textwrap.dedent(f'''
import sys
import os

# Set up paths
project_root = r"{str(project_root)}"
sys.path.insert(0, project_root)
os.chdir(project_root)

import debugpy

# Configure debugpy to listen - this starts the DAP server
debugpy.listen(("127.0.0.1", {debug_port}))

# Signal that we're ready
print("[DEBUGPY_READY]", flush=True)

# Wait for debugger to FULLY attach (including configurationDone)
# This ensures breakpoints are set before code runs
try:
    debugpy.wait_for_client()
    print("[DEBUG] Debugger attached, starting execution...", flush=True)
except Exception as e:
    print(f"[DEBUG] Wait for client failed: {{e}}", flush=True)
    sys.exit(1)

# Run the target script using runpy for proper module execution
import runpy
run_target = r"{run_target}"
sys.argv = [run_target] + {run_args}
runpy.run_path(run_target, run_name="__main__")
            ''').strip()

            cmd = [python_executable, "-c", wrapper_code]

            # Notify client about debug port
            await _send_to_websocket(execution_id, {
                "type": "debug",
                "content": f"[DEBUG] Starting debug session on port {debug_port}...",
                "debug_port": debug_port
            })

            # Start DAP client connection in background
            asyncio.create_task(_connect_dap_client(execution_id, debug_port, str(file_path), request.breakpoints))
        else:
            # Normal execution
            if request.function_name:
                # Run specific function
                cmd = [
                    python_executable, "-c",
                    f"import sys; sys.path.insert(0, '{file_path.parent}'); "
                    f"from {file_path.stem} import {request.function_name}; "
                    f"{request.function_name}()"
                ]
            else:
                # Check if this is a SyGra workflow (has graph_config.yaml in same directory)
                workflow_dir = file_path.parent
                graph_config = workflow_dir / "graph_config.yaml"

                if graph_config.exists():
                    # This is a SyGra workflow - run via main.py
                    # Determine task name from directory path
                    # e.g., /path/to/tasks/examples/image_to_qna -> examples.image_to_qna
                    task_name = _get_task_name_from_path(workflow_dir)

                    # Find main.py in project root
                    project_root = Path(__file__).parent.parent  # studio -> project root
                    main_py = project_root / "main.py"

                    if main_py.exists():
                        # Default args for quick test execution
                        default_args = [
                            "--task", task_name,
                            "--num_records", "2",
                            "--batch_size", "1",
                            "--debug", "True"
                        ]
                        # Allow user to override with custom args
                        user_args = request.args or []
                        cmd = [python_executable, str(main_py)] + default_args + user_args
                        # Set working directory to project root for main.py
                        file_path = main_py
                    else:
                        # Fallback: run the file directly
                        cmd = [python_executable, str(file_path)] + (request.args or [])
                else:
                    # Not a SyGra workflow - run the file directly
                    cmd = [python_executable, str(file_path)] + (request.args or [])

        # Log the command being executed (simplified for debug mode)
        if execution.get("debug"):
            display_cmd = f"[DEBUG MODE] {python_executable} {execution.get('target_file', original_file_path)}"
            # For SyGra workflows, use project root as working dir (same as Run mode)
            workflow_dir = original_file_path.parent
            graph_config = workflow_dir / "graph_config.yaml"
            if graph_config.exists():
                # This is a SyGra workflow - run from project root
                project_root = Path(__file__).parent.parent  # studio -> project root
                working_dir = project_root
            else:
                working_dir = original_file_path.parent
        else:
            display_cmd = ' '.join(cmd)
            working_dir = file_path.parent

        start_msg = {
            "type": "stdout",
            "content": f"$ {display_cmd}",
            "timestamp": datetime.now().isoformat()
        }
        execution["output"].append(start_msg)
        await _send_to_websocket(execution_id, start_msg)

        cwd_msg = {
            "type": "stdout",
            "content": f"Working directory: {working_dir}",
            "timestamp": datetime.now().isoformat()
        }
        execution["output"].append(cwd_msg)
        await _send_to_websocket(execution_id, cwd_msg)

        separator_msg = {
            "type": "stdout",
            "content": "─" * 50,
            "timestamp": datetime.now().isoformat()
        }
        execution["output"].append(separator_msg)
        await _send_to_websocket(execution_id, separator_msg)

        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(working_dir),
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        execution["process"] = process

        # Stream output using threads
        output_queue = queue.Queue()

        def read_stream(stream, stream_type):
            for line in iter(stream.readline, ''):
                if line:
                    output_queue.put((stream_type, line.rstrip('\n')))
            stream.close()

        stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, "stdout"))
        stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, "stderr"))
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        # Process output
        while process.poll() is None or not output_queue.empty():
            try:
                stream_type, line = output_queue.get(timeout=0.1)
                output_entry = {
                    "type": stream_type,
                    "content": line,
                    "timestamp": datetime.now().isoformat()
                }
                execution["output"].append(output_entry)
                await _send_to_websocket(execution_id, output_entry)
            except queue.Empty:
                await asyncio.sleep(0.05)

        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)

        # Set final status
        return_code = process.returncode

        # Send completion separator and status
        end_separator = {
            "type": "stdout",
            "content": "─" * 50,
            "timestamp": datetime.now().isoformat()
        }
        execution["output"].append(end_separator)
        await _send_to_websocket(execution_id, end_separator)

        if return_code == 0:
            execution["status"] = "completed"
            exit_msg = {
                "type": "stdout",
                "content": f"✓ Process completed successfully (exit code: {return_code})",
                "timestamp": datetime.now().isoformat()
            }
        else:
            execution["status"] = "failed"
            execution["error"] = f"Process exited with code {return_code}"
            exit_msg = {
                "type": "stderr",
                "content": f"✗ Process failed (exit code: {return_code})",
                "timestamp": datetime.now().isoformat()
            }

        execution["output"].append(exit_msg)
        await _send_to_websocket(execution_id, exit_msg)

    except Exception as e:
        execution["status"] = "failed"
        execution["error"] = str(e)
        error_msg = {
            "type": "stderr",
            "content": f"Execution error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        execution["output"].append(error_msg)
        await _send_to_websocket(execution_id, error_msg)
    finally:
        execution["completed_at"] = datetime.now().isoformat()
        execution["process"] = None


async def _send_to_websocket(execution_id: str, data: dict):
    """Send data to the WebSocket connection for this execution.

    Also stores messages in execution's output array for polling fallback.
    """
    # Add timestamp if not present
    if "timestamp" not in data:
        data["timestamp"] = datetime.now().isoformat()

    # Store in execution's output array for polling fallback
    execution = _code_executions.get(execution_id)
    if execution and "output" in execution:
        execution["output"].append(data)

    # Try to send via WebSocket
    ws = _websocket_connections.get(execution_id)
    if ws:
        try:
            await ws.send_json(data)
        except Exception:
            pass


async def _connect_dap_client(execution_id: str, debug_port: int, file_path: str, breakpoints: list):
    """
    Connect to debugpy via Debug Adapter Protocol (DAP) and manage debug session.
    """
    import json

    execution = _code_executions.get(execution_id)
    if not execution:
        return

    reader = None
    writer = None
    seq = 1
    buffer = b""  # Shared buffer for reading
    dap_lock = asyncio.Lock()  # Lock for coordinating DAP reads
    reading_in_progress = False  # Flag to track if a read is happening

    async def read_dap_message(timeout: float = 10.0, use_lock: bool = True):
        """Read a single DAP message."""
        nonlocal buffer, reading_in_progress

        # Check if another read is in progress
        if reading_in_progress:
            await asyncio.sleep(0.1)
            return None

        try:
            if use_lock:
                # Try to acquire lock with timeout
                try:
                    await asyncio.wait_for(dap_lock.acquire(), timeout=0.5)
                except asyncio.TimeoutError:
                    return None

            reading_in_progress = True
            deadline = asyncio.get_event_loop().time() + timeout
            read_attempts = 0

            # Read until we have headers
            while b"\r\n\r\n" not in buffer:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    # Don't clear buffer - keep partial data for next read
                    # Only log if there's significant data stuck
                    if len(buffer) > 50:
                        buffer_preview = buffer[:80].decode('utf-8', errors='replace')
                        await _send_to_websocket(execution_id, {
                            "type": "debug",
                            "content": f"[DEBUG] Read timeout with {len(buffer)} bytes in buffer"
                        })
                    return None
                try:
                    read_attempts += 1
                    chunk = await asyncio.wait_for(reader.read(4096), timeout=min(remaining, 2.0))
                    if not chunk:
                        await _send_to_websocket(execution_id, {
                            "type": "debug",
                            "content": f"[DEBUG] Read got empty chunk after {read_attempts} attempts"
                        })
                        return None
                    buffer += chunk
                    await _send_to_websocket(execution_id, {
                        "type": "debug",
                        "content": f"[DEBUG] Read {len(chunk)} bytes, total buffer: {len(buffer)}"
                    })
                except asyncio.TimeoutError:
                    if buffer:
                        continue  # Keep trying if we have partial data
                    return None

            # Split headers from potential body data
            header_end = buffer.index(b"\r\n\r\n") + 4
            header_data = buffer[:header_end].decode()
            buffer = buffer[header_end:]

            # Parse Content-Length
            content_length = 0
            for line in header_data.split("\r\n"):
                if line.lower().startswith("content-length:"):
                    content_length = int(line.split(":", 1)[1].strip())
                    break

            if content_length == 0:
                return None

            # Read body (might already be in buffer)
            while len(buffer) < content_length:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return None
                try:
                    chunk = await asyncio.wait_for(reader.read(content_length - len(buffer)), timeout=min(remaining, 2.0))
                    if not chunk:
                        return None
                    buffer += chunk
                except asyncio.TimeoutError:
                    return None

            # Extract body from buffer
            body_data = buffer[:content_length]
            buffer = buffer[content_length:]

            return json.loads(body_data.decode())

        except Exception as e:
            await _send_to_websocket(execution_id, {
                "type": "debug",
                "content": f"[DEBUG] Read error: {str(e)}"
            })
            return None
        finally:
            reading_in_progress = False
            if use_lock and dap_lock.locked():
                dap_lock.release()

    async def send_request_and_wait(command: str, arguments: dict = None, timeout: float = 10.0) -> dict:
        """Send a DAP request and wait for the response, handling any events in between."""
        nonlocal seq

        request = {
            "seq": seq,
            "type": "request",
            "command": command
        }
        if arguments:
            request["arguments"] = arguments

        request_seq = seq
        seq += 1

        # Send request
        body = json.dumps(request)
        header = f"Content-Length: {len(body)}\r\n\r\n"
        writer.write((header + body).encode())
        await writer.drain()

        # Wait for response, handling events in between
        start_time = asyncio.get_event_loop().time()
        messages_received = 0
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            remaining = timeout - (asyncio.get_event_loop().time() - start_time)
            message = await read_dap_message(timeout=min(3.0, remaining), use_lock=False)  # No lock during init
            if message is None:
                continue

            messages_received += 1
            msg_type = message.get("type")

            # Log what we receive for debugging
            if msg_type == "response":
                resp_cmd = message.get("command", "unknown")
                resp_seq = message.get("request_seq", -1)
                await _send_to_websocket(execution_id, {
                    "type": "debug",
                    "content": f"[DEBUG] Got response for {resp_cmd} (seq={resp_seq}, expecting={request_seq})"
                })
            elif msg_type == "event":
                event_name = message.get("event", "unknown")
                await _send_to_websocket(execution_id, {
                    "type": "debug",
                    "content": f"[DEBUG] Got event: {event_name}"
                })

            if msg_type == "response" and message.get("request_seq") == request_seq:
                return message
            elif msg_type == "event":
                # Handle event asynchronously
                asyncio.create_task(handle_event(message))

        raise asyncio.TimeoutError(f"Timeout waiting for {command} response (received {messages_received} messages)")

    # Message queue for coordinating reads
    pending_responses = {}  # seq -> asyncio.Future

    async def send_command(command: str, arguments: dict = None) -> None:
        """Send a DAP command without waiting for response (fire and forget)."""
        nonlocal seq
        request = {
            "seq": seq,
            "type": "request",
            "command": command
        }
        if arguments:
            request["arguments"] = arguments
        seq += 1

        body = json.dumps(request)
        header = f"Content-Length: {len(body)}\r\n\r\n"
        writer.write((header + body).encode())
        await writer.drain()

    async def handle_event(message: dict):
        """Handle DAP events."""
        event_name = message.get("event")
        body = message.get("body", {})

        # Log all events for debugging
        await _send_to_websocket(execution_id, {
            "type": "debug",
            "content": f"[DEBUG] handle_event: {event_name}"
        })

        if event_name == "stopped":
            reason = body.get("reason", "unknown")
            thread_id = body.get("threadId", 1)
            execution["thread_id"] = thread_id  # Store for debug actions

            await _send_to_websocket(execution_id, {
                "type": "debug_stopped",
                "reason": reason,
                "thread_id": thread_id,
                "content": f"[DEBUG] Paused: {reason}"
            })

            # Queue request for debug state - will be processed by message loop
            execution["pending_debug_state"] = thread_id

        elif event_name == "continued":
            await _send_to_websocket(execution_id, {
                "type": "debug_continued",
                "content": "[DEBUG] Execution continued"
            })

        elif event_name in ("terminated", "exited"):
            await _send_to_websocket(execution_id, {
                "type": "debug_terminated",
                "content": "[DEBUG] Debug session ended"
            })

    async def fetch_debug_state(thread_id: int):
        """Fetch and send debug state (stack trace + variables)."""
        nonlocal seq, buffer
        try:
            await _send_to_websocket(execution_id, {
                "type": "debug",
                "content": f"[DEBUG] fetch_debug_state: sending stackTrace for thread {thread_id}"
            })

            # Send stackTrace request
            await send_command("stackTrace", {
                "threadId": thread_id,
                "startFrame": 0,
                "levels": 20
            })

            # Wait for stackTrace response (read_dap_message handles locking)
            stack_response = None
            for i in range(30):
                msg = await read_dap_message(timeout=0.5)
                if msg:
                    msg_type = msg.get("type")
                    msg_cmd = msg.get("command", "")
                    if msg_type == "response" and msg_cmd == "stackTrace":
                        stack_response = msg
                        break
                    elif msg_type == "event":
                        await handle_event(msg)
                else:
                    await asyncio.sleep(0.05)

            if not stack_response or not stack_response.get("body"):
                await _send_to_websocket(execution_id, {
                    "type": "debug",
                    "content": f"[DEBUG] fetch_debug_state: no stack response received"
                })
                return

            frames = stack_response["body"].get("stackFrames", [])
            if not frames:
                return

            frame = frames[0]
            line_num = frame.get("line", 0)
            file_path = frame.get("source", {}).get("path")
            await _send_to_websocket(execution_id, {
                "type": "debug",
                "content": f"[DEBUG] SENDING debug_location: line={line_num}"
            })
            await _send_to_websocket(execution_id, {
                "type": "debug_location",
                "line": line_num,
                "file": file_path,
                "frame_id": frame.get("id"),
                "frames": frames
            })

            # Get scopes
            await send_command("scopes", {"frameId": frame.get("id")})

            scopes_response = None
            for _ in range(20):
                msg = await read_dap_message(timeout=0.5)
                if msg:
                    if msg.get("type") == "response" and msg.get("command") == "scopes":
                        scopes_response = msg
                        break
                    elif msg.get("type") == "event":
                        await handle_event(msg)
                else:
                    await asyncio.sleep(0.05)

            if not scopes_response or not scopes_response.get("body"):
                await _send_to_websocket(execution_id, {
                    "type": "debug",
                    "content": "[DEBUG] No scopes response"
                })
                return

            # Get variables for each scope
            all_vars = []
            for scope in scopes_response["body"].get("scopes", [])[:2]:
                var_ref = scope.get("variablesReference")
                if not var_ref:
                    continue

                await send_command("variables", {"variablesReference": var_ref})

                vars_response = None
                for _ in range(20):
                    msg = await read_dap_message(timeout=0.5)
                    if msg:
                        if msg.get("type") == "response" and msg.get("command") == "variables":
                            vars_response = msg
                            break
                        elif msg.get("type") == "event":
                            await handle_event(msg)
                    else:
                        await asyncio.sleep(0.05)

                if vars_response and vars_response.get("body"):
                    for v in vars_response["body"].get("variables", [])[:30]:
                        all_vars.append({
                            "scope": scope.get("name"),
                            "name": v.get("name"),
                            "value": str(v.get("value", ""))[:200],
                            "type": v.get("type"),
                            "variablesReference": v.get("variablesReference", 0)
                        })

            if all_vars:
                await _send_to_websocket(execution_id, {
                    "type": "debug",
                    "content": f"[DEBUG] SENDING debug_variables: {len(all_vars)} vars"
                })
                await _send_to_websocket(execution_id, {
                    "type": "debug_variables",
                    "variables": all_vars
                })
            else:
                await _send_to_websocket(execution_id, {
                    "type": "debug",
                    "content": "[DEBUG] No variables found"
                })

        except Exception as e:
            await _send_to_websocket(execution_id, {
                "type": "debug",
                "content": f"[DEBUG] Error getting state: {str(e)}"
            })

    async def message_loop():
        """Main message loop - reads all DAP messages and dispatches them."""
        await _send_to_websocket(execution_id, {
            "type": "debug",
            "content": "[DEBUG] Message loop started"
        })

        loop_count = 0
        while execution.get("status") == "running":
            try:
                loop_count += 1

                # Check if we need to fetch debug state
                pending_thread = execution.pop("pending_debug_state", None)
                if pending_thread:
                    await _send_to_websocket(execution_id, {
                        "type": "debug",
                        "content": f"[DEBUG] Fetching debug state for thread {pending_thread}"
                    })
                    await fetch_debug_state(pending_thread)
                    continue

                # read_dap_message handles locking internally
                message = await read_dap_message(timeout=0.5)
                if message:
                    msg_type = message.get("type")
                    event_name = message.get("event", message.get("command", ""))
                    await _send_to_websocket(execution_id, {
                        "type": "debug",
                        "content": f"[DEBUG] Loop received: {msg_type} - {event_name}"
                    })

                    if msg_type == "event":
                        await handle_event(message)
                    elif msg_type == "response":
                        # Check if anyone is waiting for this response
                        req_seq = message.get("request_seq")
                        if req_seq in pending_responses:
                            pending_responses[req_seq].set_result(message)
            except Exception as e:
                if loop_count < 5:  # Only log first few errors
                    await _send_to_websocket(execution_id, {
                        "type": "debug",
                        "content": f"[DEBUG] Loop error: {str(e)}"
                    })
            await asyncio.sleep(0.05)

    # Wait for debugpy to be ready by checking for [DEBUGPY_READY] in output
    # Give it some time to start
    await asyncio.sleep(2.0)

    # Connect with retries - debugpy might take a moment to start listening
    connected = False
    for attempt in range(15):  # Up to ~15 seconds of retries
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection('127.0.0.1', debug_port),
                timeout=2.0
            )
            connected = True
            await _send_to_websocket(execution_id, {
                "type": "debug",
                "content": "[DEBUG] Connected to debug adapter"
            })
            break
        except (ConnectionRefusedError, asyncio.TimeoutError, OSError) as e:
            if attempt < 14:
                await asyncio.sleep(0.5)
                continue
            else:
                await _send_to_websocket(execution_id, {
                    "type": "debug",
                    "content": f"[DEBUG] Failed to connect to debug server after {attempt+1} attempts"
                })
                return

    if not connected or not reader or not writer:
        return

    event_task = None
    attach_seq = None  # Track attach request seq to get response later

    try:
        # Test if we can read from connection
        await _send_to_websocket(execution_id, {
            "type": "debug",
            "content": "[DEBUG] Testing connection read..."
        })

        # Try to read any initial data (some debuggers send events on connect)
        try:
            test_data = await asyncio.wait_for(reader.read(100), timeout=0.5)
            if test_data:
                buffer = test_data  # Put it in buffer for later processing
                await _send_to_websocket(execution_id, {
                    "type": "debug",
                    "content": f"[DEBUG] Initial data received: {len(test_data)} bytes"
                })
        except asyncio.TimeoutError:
            await _send_to_websocket(execution_id, {
                "type": "debug",
                "content": "[DEBUG] No initial data (normal)"
            })

        # DAP handshake - Step 1: Initialize
        await _send_to_websocket(execution_id, {
            "type": "debug",
            "content": "[DEBUG] Sending initialize..."
        })

        init_resp = await send_request_and_wait("initialize", {
            "clientID": "sygra",
            "adapterID": "debugpy",
            "pathFormat": "path",
            "linesStartAt1": True,
            "columnsStartAt1": True,
            "supportsVariableType": True,
            "supportsRunInTerminalRequest": False,
            "supportsProgressReporting": False
        }, timeout=15.0)

        await _send_to_websocket(execution_id, {
            "type": "debug",
            "content": "[DEBUG] Initialize OK"
        })

        # Step 2: Send attach request (but don't wait for response yet - it comes after configurationDone)
        attach_request = {
            "seq": seq,
            "type": "request",
            "command": "attach",
            "arguments": {
                "justMyCode": False,
                "subProcess": False
            }
        }
        attach_seq = seq
        seq += 1

        body = json.dumps(attach_request)
        header = f"Content-Length: {len(body)}\r\n\r\n"
        writer.write((header + body).encode())
        await writer.drain()

        await _send_to_websocket(execution_id, {
            "type": "debug",
            "content": "[DEBUG] Attach request sent"
        })

        # Step 3: Wait for 'initialized' event before setting breakpoints
        # Read messages until we get initialized event
        got_initialized = False
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < 10.0:
            message = await read_dap_message(timeout=2.0)
            if message:
                if message.get("type") == "event" and message.get("event") == "initialized":
                    got_initialized = True
                    await _send_to_websocket(execution_id, {
                        "type": "debug",
                        "content": "[DEBUG] Got initialized event"
                    })
                    break
                elif message.get("type") == "event":
                    await _send_to_websocket(execution_id, {
                        "type": "debug",
                        "content": f"[DEBUG] Event: {message.get('event')}"
                    })

        if not got_initialized:
            await _send_to_websocket(execution_id, {
                "type": "debug",
                "content": "[DEBUG] Warning: No initialized event received"
            })

        # Step 4: Set breakpoints
        if breakpoints:
            bp_resp = await send_request_and_wait("setBreakpoints", {
                "source": {"path": file_path},
                "breakpoints": [{"line": ln} for ln in breakpoints]
            }, timeout=10.0)
            verified = sum(1 for bp in bp_resp.get("body", {}).get("breakpoints", []) if bp.get("verified"))
            await _send_to_websocket(execution_id, {
                "type": "debug",
                "content": f"[DEBUG] Breakpoints: {verified}/{len(breakpoints)} at {breakpoints}"
            })

        # Step 5: Send configurationDone - this triggers attach response
        await send_request_and_wait("configurationDone", timeout=10.0)
        await _send_to_websocket(execution_id, {
            "type": "debug",
            "content": "[DEBUG] Configuration done"
        })

        # Step 6: Now wait for attach response
        start_time = asyncio.get_event_loop().time()
        attach_resp = None
        while (asyncio.get_event_loop().time() - start_time) < 10.0:
            message = await read_dap_message(timeout=2.0)
            if message:
                if message.get("type") == "response" and message.get("request_seq") == attach_seq:
                    attach_resp = message
                    break
                elif message.get("type") == "event":
                    asyncio.create_task(handle_event(message))

        if attach_resp:
            if attach_resp.get("success", True):
                await _send_to_websocket(execution_id, {
                    "type": "debug",
                    "content": "[DEBUG] Debugger attached - session active!"
                })
            else:
                await _send_to_websocket(execution_id, {
                    "type": "debug",
                    "content": f"[DEBUG] Attach failed: {attach_resp.get('message')}"
                })
                return
        else:
            await _send_to_websocket(execution_id, {
                "type": "debug",
                "content": "[DEBUG] No attach response, but continuing..."
            })

        # Function to fetch variables with proper coordination
        async def fetch_variables(variables_reference: int) -> list:
            """Fetch child variables for a given reference."""
            nonlocal seq
            await send_command("variables", {"variablesReference": variables_reference})

            # Read responses until we get our variables response (read_dap_message handles locking)
            for _ in range(20):
                msg = await read_dap_message(timeout=0.5)
                if msg:
                    if msg.get("type") == "response" and msg.get("command") == "variables":
                        if msg.get("body"):
                            return [
                                {
                                    "name": v.get("name"),
                                    "value": str(v.get("value", ""))[:200],
                                    "type": v.get("type"),
                                    "variablesReference": v.get("variablesReference", 0)
                                }
                                for v in msg["body"].get("variables", [])
                            ]
                    elif msg.get("type") == "event":
                        await handle_event(msg)
                else:
                    await asyncio.sleep(0.05)
            return []

        # Store functions for debug actions API
        execution["dap_send_command"] = send_command
        execution["dap_read_message"] = read_dap_message
        execution["dap_fetch_variables"] = fetch_variables
        execution["dap_lock"] = dap_lock

        # Start message loop to handle events and fetch debug state
        event_task = asyncio.create_task(message_loop())

        while execution.get("status") == "running":
            await asyncio.sleep(0.5)

    except asyncio.TimeoutError as e:
        await _send_to_websocket(execution_id, {
            "type": "debug",
            "content": f"[DEBUG] Protocol timeout: {str(e)}"
        })
    except Exception as e:
        await _send_to_websocket(execution_id, {
            "type": "debug",
            "content": f"[DEBUG] Error: {str(e)}"
        })
    finally:
        if event_task:
            event_task.cancel()
        if writer:
            writer.close()


def _represent_multiline_str(dumper, data):
    """Custom YAML representer that uses literal block scalar style for multiline strings."""
    if '\n' in data:
        # Use literal block scalar style (|) for multiline strings
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


def _get_yaml_dumper():
    """Get a custom YAML dumper that properly formats multiline strings."""
    class CustomDumper(yaml.SafeDumper):
        pass
    CustomDumper.add_representer(str, _represent_multiline_str)
    return CustomDumper


async def _save_workflow_to_disk(app: FastAPI, request: WorkflowCreateRequest, is_new: bool) -> WorkflowSaveResponse:
    """
    Save a workflow to disk as graph_config.yaml and task_executor.py.

    Args:
        app: FastAPI application instance
        request: Workflow creation request
        is_new: Whether this is a new workflow or an update

    Returns:
        WorkflowSaveResponse with details about created files
    """
    import re
    import yaml

    tasks_dir = Path(app.state.tasks_dir)

    # Sanitize workflow name for directory
    sanitized_name = re.sub(r'[^\w\-]', '_', request.name.lower().strip())
    sanitized_name = re.sub(r'_+', '_', sanitized_name).strip('_')

    if not sanitized_name:
        raise HTTPException(status_code=400, detail="Invalid workflow name")

    # Determine target directory
    if is_new:
        workflow_dir = tasks_dir / sanitized_name
        # Check if directory already exists
        counter = 1
        original_name = sanitized_name
        while workflow_dir.exists():
            sanitized_name = f"{original_name}_{counter}"
            workflow_dir = tasks_dir / sanitized_name
            counter += 1
    else:
        # For updates, use existing path if available
        if request.source_path:
            config_path = Path(request.source_path)
            if config_path.name == "graph_config.yaml":
                workflow_dir = config_path.parent
            else:
                workflow_dir = config_path
        else:
            workflow_dir = tasks_dir / sanitized_name

    # Create directory if needed
    workflow_dir.mkdir(parents=True, exist_ok=True)

    files_created = []

    # Generate graph_config.yaml
    graph_config = _generate_graph_config(request, sanitized_name)
    config_path = workflow_dir / "graph_config.yaml"

    with open(config_path, 'w') as f:
        yaml.dump(graph_config, f, Dumper=_get_yaml_dumper(), default_flow_style=False, sort_keys=False, allow_unicode=True)
    files_created.append(str(config_path))

    # Generate task_executor.py with code preservation
    # Use the merge function to preserve existing non-stub code while removing
    # code for deleted nodes and adding stubs for new nodes
    executor_code = _generate_task_executor_with_merge(request, sanitized_name, workflow_dir)
    executor_path = workflow_dir / "task_executor.py"
    if executor_code:
        with open(executor_path, 'w') as f:
            f.write(executor_code)
        files_created.append(str(executor_path))
    elif executor_path.exists():
        # No code needed anymore - remove the file if it exists
        # This happens when all nodes that needed code have been removed
        executor_path.unlink()
        print(f"Removed unused task_executor.py")

    # Generate workflow ID
    workflow_id = sanitized_name

    # Update cache
    try:
        graph = app.state.graph_builder.build_from_yaml(str(config_path))
        _workflows[graph.id] = graph
        workflow_id = graph.id
    except Exception as e:
        print(f"Warning: Could not reload workflow after save: {e}")

    return WorkflowSaveResponse(
        success=True,
        workflow_id=workflow_id,
        source_path=str(config_path),
        message=f"Workflow '{request.name}' saved successfully",
        files_created=files_created
    )


# Track used function/class names to ensure uniqueness
_used_names: set = set()


def _generate_readable_name(node, node_type: str, all_nodes: list, suffix: str) -> str:
    """
    Generate a unique readable name for a node's class/function based on summary or position.

    Args:
        node: The node to generate a name for
        node_type: Type of node (lambda, data, output)
        all_nodes: All nodes in the workflow
        suffix: Suffix to add (function, transform, generator)

    Returns:
        A unique readable Python identifier like 'process_data_function' or 'lambda_1_function'
    """
    import re
    global _used_names

    base_name = None

    # Try to use node summary if available and meaningful
    if node.summary and node.summary.strip():
        # Convert summary to valid Python identifier
        name = re.sub(r'[^\w\s]', '', node.summary.lower().strip())
        name = re.sub(r'\s+', '_', name)
        name = re.sub(r'_+', '_', name).strip('_')
        # Skip if summary just equals the node type (not meaningful)
        if name and name != node_type:
            if name[0].isdigit():
                name = f"{node_type}_{name}"
            base_name = name

    # Fall back to numbered name based on position
    if not base_name:
        same_type_nodes = [n for n in all_nodes if n.node_type == node_type]
        try:
            index = same_type_nodes.index(node) + 1
        except ValueError:
            index = 1
        base_name = f"{node_type}_{index}"

    # Ensure uniqueness by adding counter if needed
    full_name = f"{base_name}_{suffix}"
    if full_name in _used_names:
        counter = 2
        while f"{base_name}_{counter}_{suffix}" in _used_names:
            counter += 1
        full_name = f"{base_name}_{counter}_{suffix}"

    _used_names.add(full_name)
    return full_name


def _reset_used_names():
    """Reset the used names set - call at start of each workflow generation."""
    global _used_names
    _used_names = set()


def _serialize_inner_graph(inner_graph) -> dict:
    """
    Recursively serialize an inner_graph structure for YAML storage.

    Args:
        inner_graph: InnerGraph model or dict

    Returns:
        Dictionary ready for YAML serialization
    """
    result = {
        'name': inner_graph.name if hasattr(inner_graph, 'name') else inner_graph.get('name', 'Subgraph'),
        'nodes': {},
        'edges': []
    }

    inner_nodes = inner_graph.nodes if hasattr(inner_graph, 'nodes') else inner_graph.get('nodes', [])
    for inner_node in inner_nodes:
        inner_node_id = inner_node.id if hasattr(inner_node, 'id') else inner_node.get('id')
        inner_node_type = inner_node.node_type if hasattr(inner_node, 'node_type') else inner_node.get('node_type')
        inner_node_config = {
            'node_type': inner_node_type,
            'node_name': inner_node.summary if hasattr(inner_node, 'summary') else inner_node.get('summary'),
        }
        # Save position
        inner_pos = inner_node.position if hasattr(inner_node, 'position') else inner_node.get('position', {})
        if inner_pos:
            inner_node_config['position'] = {
                'x': inner_pos.x if hasattr(inner_pos, 'x') else inner_pos.get('x', 0),
                'y': inner_pos.y if hasattr(inner_pos, 'y') else inner_pos.get('y', 0)
            }
        # Save size
        inner_size = inner_node.size if hasattr(inner_node, 'size') else inner_node.get('size')
        if inner_size:
            inner_node_config['size'] = {
                'width': inner_size.width if hasattr(inner_size, 'width') else inner_size.get('width', 150),
                'height': inner_size.height if hasattr(inner_size, 'height') else inner_size.get('height', 60)
            }
        # Recursively handle nested inner_graph
        nested_inner_graph = inner_node.inner_graph if hasattr(inner_node, 'inner_graph') else inner_node.get('inner_graph')
        if nested_inner_graph:
            inner_node_config['inner_graph'] = _serialize_inner_graph(nested_inner_graph)
        result['nodes'][inner_node_id] = inner_node_config

    inner_edges = inner_graph.edges if hasattr(inner_graph, 'edges') else inner_graph.get('edges', [])
    for inner_edge in inner_edges:
        edge_source = inner_edge.source if hasattr(inner_edge, 'source') else inner_edge.get('source')
        edge_target = inner_edge.target if hasattr(inner_edge, 'target') else inner_edge.get('target')
        result['edges'].append({
            'from': edge_source,
            'to': edge_target
        })

    return result


def _generate_graph_config(request: WorkflowCreateRequest, task_name: str) -> dict:
    """
    Generate graph_config.yaml content from workflow request.

    Args:
        request: Workflow creation request
        task_name: Sanitized task name for paths

    Returns:
        Dictionary ready for YAML serialization
    """
    # Reset used names for this workflow generation
    _reset_used_names()

    config = {}

    # Data config - filter out internal fields (starting with _)
    if request.data_config and request.data_config.get('source'):
        config['data_config'] = {k: v for k, v in request.data_config.items() if not k.startswith('_')}

    # Graph config
    graph_config = {'nodes': {}, 'edges': []}

    for node in request.nodes:
        # Skip START and END nodes - they're implicit
        if node.node_type in ('start', 'end'):
            continue

        node_config: Dict[str, Any] = {
            'node_type': node.node_type
        }

        # Add node-specific config
        if node.node_type == 'llm':
            if node.prompt:
                # Convert prompt messages to YAML format
                prompt_list = []
                for msg in node.prompt:
                    if hasattr(msg, 'role') and hasattr(msg, 'content'):
                        prompt_list.append({msg.role: msg.content})
                    elif isinstance(msg, dict):
                        prompt_list.append({msg.get('role', 'user'): msg.get('content', '')})
                if prompt_list:
                    node_config['prompt'] = prompt_list

            if node.model:
                model_config = {'name': node.model.name if hasattr(node.model, 'name') else node.model.get('name', 'gpt-4o')}
                params = node.model.parameters if hasattr(node.model, 'parameters') else node.model.get('parameters', {})
                if params:
                    model_config['parameters'] = params
                node_config['model'] = model_config

            # Include output_keys for LLM nodes
            if node.output_keys:
                node_config['output_keys'] = node.output_keys

        elif node.node_type == 'multi_llm':
            if node.prompt:
                # Convert prompt messages to YAML format
                prompt_list = []
                for msg in node.prompt:
                    if hasattr(msg, 'role') and hasattr(msg, 'content'):
                        prompt_list.append({msg.role: msg.content})
                    elif isinstance(msg, dict):
                        prompt_list.append({msg.get('role', 'user'): msg.get('content', '')})
                if prompt_list:
                    node_config['prompt'] = prompt_list

            # Include models config for multi_llm nodes
            if node.models:
                node_config['models'] = node.models

            # Include multi_llm_post_process
            if node.multi_llm_post_process:
                node_config['multi_llm_post_process'] = node.multi_llm_post_process

            # Include output_keys for multi_llm nodes
            if node.output_keys:
                node_config['output_keys'] = node.output_keys

        elif node.node_type == 'lambda':
            if node.function_path:
                node_config['function_path'] = node.function_path
            else:
                # Generate a readable function name from node summary or a simple counter
                func_name = _generate_readable_name(node, 'lambda', request.nodes, 'function')
                generated_path = f"tasks.{task_name}.task_executor.{func_name}"
                node_config['function_path'] = generated_path
                # Store back on node for task_executor generation
                node.function_path = generated_path

        elif node.node_type == 'subgraph':
            if node.subgraph_path:
                node_config['subgraph'] = node.subgraph_path
            elif node.inner_graph:
                # Save inline subgraph data for grouped nodes
                inner_graph_data = {
                    'name': node.inner_graph.name if hasattr(node.inner_graph, 'name') else node.inner_graph.get('name', 'Subgraph'),
                    'nodes': {},
                    'edges': []
                }
                # Convert inner nodes
                inner_nodes = node.inner_graph.nodes if hasattr(node.inner_graph, 'nodes') else node.inner_graph.get('nodes', [])
                for inner_node in inner_nodes:
                    inner_node_id = inner_node.id if hasattr(inner_node, 'id') else inner_node.get('id')
                    inner_node_type = inner_node.node_type if hasattr(inner_node, 'node_type') else inner_node.get('node_type')
                    inner_node_config = {
                        'node_type': inner_node_type,
                        'node_name': inner_node.summary if hasattr(inner_node, 'summary') else inner_node.get('summary'),
                    }
                    # Save position for inner nodes
                    inner_pos = inner_node.position if hasattr(inner_node, 'position') else inner_node.get('position', {})
                    if inner_pos:
                        inner_node_config['position'] = {
                            'x': inner_pos.x if hasattr(inner_pos, 'x') else inner_pos.get('x', 0),
                            'y': inner_pos.y if hasattr(inner_pos, 'y') else inner_pos.get('y', 0)
                        }
                    # Save size for inner nodes
                    inner_size = inner_node.size if hasattr(inner_node, 'size') else inner_node.get('size')
                    if inner_size:
                        inner_node_config['size'] = {
                            'width': inner_size.width if hasattr(inner_size, 'width') else inner_size.get('width', 150),
                            'height': inner_size.height if hasattr(inner_size, 'height') else inner_size.get('height', 60)
                        }
                    # Handle nested subgraphs recursively
                    inner_inner_graph = inner_node.inner_graph if hasattr(inner_node, 'inner_graph') else inner_node.get('inner_graph')
                    if inner_inner_graph:
                        # Recursively store nested inner_graph (simplified - just store the raw data)
                        inner_node_config['inner_graph'] = _serialize_inner_graph(inner_inner_graph)
                    inner_graph_data['nodes'][inner_node_id] = inner_node_config
                # Convert inner edges
                inner_edges = node.inner_graph.edges if hasattr(node.inner_graph, 'edges') else node.inner_graph.get('edges', [])
                for inner_edge in inner_edges:
                    edge_source = inner_edge.source if hasattr(inner_edge, 'source') else inner_edge.get('source')
                    edge_target = inner_edge.target if hasattr(inner_edge, 'target') else inner_edge.get('target')
                    inner_graph_data['edges'].append({
                        'from': edge_source,
                        'to': edge_target
                    })
                node_config['inner_graph'] = inner_graph_data

        elif node.node_type == 'connector':
            if node.metadata:
                node_config.update(node.metadata)

        elif node.node_type == 'data':
            # Data nodes are stored in data_config at workflow level, NOT in graph_config.nodes
            if node.data_config:
                # Copy data_config but strip out internal fields
                data_config_clean = {k: v for k, v in node.data_config.items() if not k.startswith('_')}
                if data_config_clean:
                    if 'data_config' not in config:
                        config['data_config'] = {}
                    config['data_config'].update(data_config_clean)
            # Skip adding to graph_config.nodes - data nodes are implicit
            continue

        elif node.node_type == 'output':
            # Output nodes are stored in output_config at workflow level, NOT in graph_config.nodes
            if node.output_config:
                # Copy output_config but strip out internal fields
                output_config_clean = {k: v for k, v in node.output_config.items() if not k.startswith('_')}
                if output_config_clean:
                    if 'output_config' not in config:
                        config['output_config'] = {}
                    config['output_config'].update(output_config_clean)
            # Skip adding to graph_config.nodes - output nodes are implicit
            continue

        elif node.node_type == 'weighted_sampler':
            node_config['node_type'] = 'weighted_sampler'
            if node.sampler_config and node.sampler_config.get('attributes'):
                node_config['attributes'] = node.sampler_config['attributes']

        # Add pre/post processors
        if node.pre_process:
            node_config['pre_process'] = node.pre_process
        if node.post_process:
            node_config['post_process'] = node.post_process

        # Add node_name - displayed in the graph
        if node.summary:
            node_config['node_name'] = node.summary

        # Add description as comment (via metadata)
        if node.description:
            node_config['description'] = node.description

        graph_config['nodes'][node.id] = node_config

    # Build set of data and output node IDs to filter edges
    excluded_node_ids = {node.id for node in request.nodes if node.node_type in ('data', 'output')}

    # Edges - exclude any edges involving data or output nodes
    for edge in request.edges:
        # Skip edges connected to data or output nodes
        if edge.source in excluded_node_ids or edge.target in excluded_node_ids:
            continue

        edge_config: Dict[str, Any] = {
            'from': edge.source if edge.source != 'START' else 'START',
            'to': edge.target if edge.target != 'END' else 'END'
        }

        if edge.is_conditional and edge.condition:
            edge_config['condition_path'] = edge.condition.condition_path
            if edge.condition.path_map:
                edge_config['path_map'] = edge.condition.path_map

        if edge.label:
            edge_config['label'] = edge.label

        graph_config['edges'].append(edge_config)

    config['graph_config'] = graph_config

    # Check if there's an OUTPUT node in the request
    has_output_node = any(n.node_type == 'output' for n in request.nodes)
    has_output_node_with_config = any(
        n.node_type == 'output' and n.output_config
        for n in request.nodes
    )

    # CRITICAL: Handle output_config based on OUTPUT node presence
    # If no OUTPUT node exists, completely remove output_config
    if not has_output_node:
        # No OUTPUT node - remove any output_config entirely
        config.pop('output_config', None)
    elif has_output_node_with_config:
        # OUTPUT node exists and has config - it was already processed in node loop above
        # Just clean up any internal fields (starting with _)
        if 'output_config' in config:
            config['output_config'] = {
                k: v for k, v in config['output_config'].items()
                if not k.startswith('_')
            }
    elif request.output_config:
        # OUTPUT node exists but uses workflow-level output_config
        output_config_clean = {k: v for k, v in request.output_config.items() if not k.startswith('_')}
        if 'output_map' in output_config_clean:
            output_config_clean['output_map'] = {
                k: v for k, v in output_config_clean['output_map'].items()
                if k not in excluded_node_ids
            }
        config['output_config'] = output_config_clean

    # Schema config
    if request.schema_config:
        config['schema_config'] = request.schema_config

    return config


def _generate_task_executor(request: WorkflowCreateRequest, task_name: str) -> Optional[str]:
    """
    Generate task_executor.py content for custom processors.

    Args:
        request: Workflow creation request
        task_name: Sanitized task name for paths

    Returns:
        Python code as string, or None if no custom code needed
    """
    imports = set()
    classes = []
    functions = []

    # Check for custom processors and lambdas
    needs_executor = False

    for node in request.nodes:
        # Check for pre/post processors that reference this task
        if node.pre_process and task_name in node.pre_process:
            needs_executor = True
            imports.add("from sygra.core.graph.functions.node_processor import NodePreProcessorWithState")
            imports.add("from sygra.core.graph.sygra_state import SygraState")

            # Generate placeholder class
            class_name = node.pre_process.split('.')[-1]
            classes.append(f'''
class {class_name}(NodePreProcessorWithState):
    """Pre-processor for {node.id} node."""

    def apply(self, state: SygraState) -> SygraState:
        # TODO: Implement pre-processing logic
        # Access state variables: state["variable_name"]
        # Modify state as needed
        return state
''')

        if node.post_process and task_name in node.post_process:
            needs_executor = True
            imports.add("from sygra.core.graph.functions.node_processor import NodePostProcessorWithState")
            imports.add("from sygra.core.graph.sygra_message import SygraMessage")
            imports.add("from sygra.core.graph.sygra_state import SygraState")

            # Generate placeholder class
            class_name = node.post_process.split('.')[-1]
            classes.append(f'''
class {class_name}(NodePostProcessorWithState):
    """Post-processor for {node.id} node."""

    def apply(self, resp: SygraMessage, state: SygraState) -> SygraState:
        # TODO: Implement post-processing logic
        # Access LLM response: resp.message.content
        # Modify state as needed: state["output_key"] = processed_value
        return state
''')

        # Check for lambda functions - always generate stub if function_path contains this task
        if node.node_type == 'lambda' and node.function_path:
            # Check if function should be defined in this task's executor
            if task_name in node.function_path or 'task_executor' in node.function_path:
                needs_executor = True
                imports.add("from sygra.core.graph.sygra_state import SygraState")
                imports.add("from typing import Any")

                func_name = node.function_path.split('.')[-1]
                # Generate descriptive docstring
                node_desc = node.summary if node.summary else f"Lambda node {node.id}"
                functions.append(f'''
def {func_name}(state: SygraState) -> Any:
    """
    Lambda function: {node_desc}

    This function is executed as part of the workflow pipeline.
    Modify the state and return it, or return a value to be stored.

    Args:
        state: Current workflow state containing all variables

    Returns:
        Modified state or a value to store in state["{node.id}"]
    """
    # TODO: Implement your processing logic here
    #
    # Example - Access input data:
    # input_data = state.get("previous_node_output")
    #
    # Example - Process and return:
    # result = process(input_data)
    # return result
    #
    # Example - Modify state directly:
    # state["my_output"] = computed_value
    # return state

    return state
''')

        # Check for data node transformations
        if node.node_type == 'data' and node.data_config:
            transform_code = node.data_config.get('_transform_code', '')
            if transform_code and transform_code.strip():
                needs_executor = True
                # The transform code already contains imports and class definition
                classes.append(f'''
# === Data Transformation for {node.id} ===
{transform_code}
''')

        # Check for output node generators
        if node.node_type == 'output' and node.output_config:
            generator_code = node.output_config.get('_generator_code', '')
            if generator_code and generator_code.strip():
                needs_executor = True
                # The generator code already contains imports and class definition
                classes.append(f'''
# === Output Generator for {node.id} ===
{generator_code}
''')

    # Check for conditional edges
    for edge in request.edges:
        if edge.is_conditional and edge.condition and edge.condition.condition_path:
            if task_name in edge.condition.condition_path:
                needs_executor = True
                imports.add("from sygra.core.graph.sygra_state import SygraState")

                func_name = edge.condition.condition_path.split('.')[-1]
                path_map_keys = list(edge.condition.path_map.keys()) if edge.condition.path_map else ['default']

                functions.append(f'''
def {func_name}(state: SygraState) -> str:
    """Conditional edge function from {edge.source} to determine next node."""
    # TODO: Implement condition logic
    # Return one of: {path_map_keys}
    # Access state variables: state["variable_name"]
    return "{path_map_keys[0]}"
''')

    # Check if we need DefaultOutputGenerator
    # Only generate if there's an OUTPUT node that needs it
    has_output_node = any(n.node_type == 'output' for n in request.nodes)
    has_llm_nodes = any(n.node_type == 'llm' for n in request.nodes)

    # Generate DefaultOutputGenerator only if:
    # 1. There's an OUTPUT node, OR
    # 2. There's an output_config with generator path pointing to DefaultOutputGenerator
    needs_default_generator = has_output_node and has_llm_nodes

    if needs_default_generator:
        needs_executor = True
        imports.add("from typing import Any")
        imports.add("from sygra.processors.output_record_generator import BaseOutputGenerator")
        imports.add("from sygra.utils import utils")

        classes.append('''
class DefaultOutputGenerator(BaseOutputGenerator):
    """Output generator that converts LangChain messages to chat format."""

    @staticmethod
    def build_response(data: Any, state: dict) -> list:
        """Convert LangChain AIMessage objects to serializable chat format."""
        return utils.convert_messages_from_langchain_to_chat_format(data)
''')

    if not needs_executor:
        return None

    # Build the file content
    code_parts = [
        '"""',
        f'Task executor for {request.name} workflow.',
        '',
        'This file contains custom processors, lambda functions, and conditional edge logic.',
        '"""',
        '',
    ]

    # Add imports
    for imp in sorted(imports):
        code_parts.append(imp)

    code_parts.append('')

    # Add classes
    for cls in classes:
        code_parts.append(cls)

    # Add functions
    for func in functions:
        code_parts.append(func)

    return '\n'.join(code_parts)


def _generate_task_executor_with_merge(
    request: WorkflowCreateRequest,
    task_name: str,
    workflow_dir: Path
) -> Optional[str]:
    """
    Generate task_executor.py content while preserving existing user code.

    This function merges:
    1. Code explicitly included in the request (takes priority)
    2. Existing non-stub code from the current task_executor.py file
    3. New stubs for nodes that need code but don't have any

    Code for deleted nodes (not in request) is NOT preserved.

    Args:
        request: Workflow creation request
        task_name: Sanitized task name for paths
        workflow_dir: Path to the workflow directory

    Returns:
        Python code as string, or None if no custom code needed
    """
    task_executor_path = workflow_dir / "task_executor.py"

    # Get current node IDs from the request (only preserve code for these)
    current_node_ids = {node.id for node in request.nodes}
    current_edge_sources = {edge.source for edge in request.edges if edge.is_conditional}

    # Read existing code blocks from file
    existing_blocks = {}  # {(node_id, code_type): code}
    if task_executor_path.exists():
        try:
            with open(task_executor_path, 'r') as f:
                existing_content = f.read()

            # Extract code blocks using AST-based detection
            ast_blocks = _find_code_blocks_by_ast(existing_content)
            for block in ast_blocks:
                code_type = block['type']
                node_id = block['node_id']
                code = block['code']
                name = block['name']

                # Skip DefaultOutputGenerator - handled separately
                if name == 'DefaultOutputGenerator':
                    continue

                # Skip stub code
                if _is_stub_code(code, code_type):
                    continue

                # Only preserve code for nodes that still exist in the request
                if node_id in current_node_ids or node_id in current_edge_sources:
                    existing_blocks[(node_id, code_type)] = code
        except Exception as e:
            print(f"Warning: Could not read existing task_executor.py: {e}")

    # Now build the merged code
    imports = set()
    classes = []
    functions = []
    needs_executor = False
    has_custom_output_generator = False  # Track if custom generator exists

    for node in request.nodes:
        # Check for pre-processor
        if node.pre_process and task_name in node.pre_process:
            needs_executor = True
            imports.add("from sygra.core.graph.functions.node_processor import NodePreProcessorWithState")
            imports.add("from sygra.core.graph.sygra_state import SygraState")

            class_name = node.pre_process.split('.')[-1]

            # Check if there's existing code in task_executor.py to preserve
            if (node.id, 'pre_process') in existing_blocks:
                # Preserve existing non-stub code
                classes.append(f'''
# === Pre-Processor for {node.id} ===
{existing_blocks[(node.id, 'pre_process')]}
''')
            else:
                # Generate new stub
                classes.append(f'''
# === Pre-Processor for {node.id} ===
class {class_name}(NodePreProcessorWithState):
    """Pre-processor for {node.id} node."""

    def apply(self, state: SygraState) -> SygraState:
        # TODO: Implement pre-processing logic
        # Access state variables: state["variable_name"]
        # Modify state as needed
        return state
''')

        # Check for post-processor
        if node.post_process and task_name in node.post_process:
            needs_executor = True
            imports.add("from sygra.core.graph.functions.node_processor import NodePostProcessorWithState")
            imports.add("from sygra.core.graph.sygra_message import SygraMessage")
            imports.add("from sygra.core.graph.sygra_state import SygraState")

            class_name = node.post_process.split('.')[-1]

            # Check if there's existing code in task_executor.py to preserve
            if (node.id, 'post_process') in existing_blocks:
                # Preserve existing non-stub code
                classes.append(f'''
# === Post-Processor for {node.id} ===
{existing_blocks[(node.id, 'post_process')]}
''')
            else:
                # Generate new stub
                classes.append(f'''
# === Post-Processor for {node.id} ===
class {class_name}(NodePostProcessorWithState):
    """Post-processor for {node.id} node."""

    def apply(self, resp: SygraMessage, state: SygraState) -> SygraState:
        # TODO: Implement post-processing logic
        # Access LLM response: resp.message.content
        # Modify state as needed: state["output_key"] = processed_value
        return state
''')

        # Check for lambda functions
        if node.node_type == 'lambda' and node.function_path:
            if task_name in node.function_path or 'task_executor' in node.function_path:
                needs_executor = True
                imports.add("from sygra.core.graph.sygra_state import SygraState")
                imports.add("from typing import Any")

                func_name = node.function_path.split('.')[-1]

                # Check if request has explicit code
                lambda_code = getattr(node, '_lambda_code', None)
                if lambda_code and lambda_code.strip():
                    functions.append(f'''
# === Lambda Function for {node.id} ===
{lambda_code.strip()}
''')
                elif (node.id, 'lambda') in existing_blocks:
                    # Preserve existing non-stub code
                    functions.append(f'''
# === Lambda Function for {node.id} ===
{existing_blocks[(node.id, 'lambda')]}
''')
                else:
                    # Generate new stub
                    node_desc = node.summary if node.summary else f"Lambda node {node.id}"
                    functions.append(f'''
# === Lambda Function for {node.id} ===
def {func_name}(state: SygraState) -> Any:
    """
    Lambda function: {node_desc}

    This function is executed as part of the workflow pipeline.
    Modify the state and return it, or return a value to be stored.

    Args:
        state: Current workflow state containing all variables

    Returns:
        Modified state or a value to store in state["{node.id}"]
    """
    # TODO: Implement your processing logic here
    return state
''')

        # Check for data node transformations
        if node.node_type == 'data' and node.data_config:
            transform_code = node.data_config.get('_transform_code', '')
            if transform_code and transform_code.strip():
                needs_executor = True
                classes.append(f'''
# === Data Transformation for {node.id} ===
{transform_code}
''')
            elif (node.id, 'data_transform') in existing_blocks:
                needs_executor = True
                classes.append(f'''
# === Data Transformation for {node.id} ===
{existing_blocks[(node.id, 'data_transform')]}
''')

        # Check for output node generators
        # Track if custom generator is added (to avoid adding DefaultOutputGenerator)
        if node.node_type == 'output' and node.output_config:
            generator_code = node.output_config.get('_generator_code', '')
            if generator_code and generator_code.strip():
                needs_executor = True
                has_custom_output_generator = True
                # Add imports needed for output generators
                imports.add("from typing import Any")
                imports.add("from sygra.processors.output_record_generator import BaseOutputGenerator")
                imports.add("from sygra.core.graph.sygra_state import SygraState")
                classes.append(f'''
# === Output Generator for {node.id} ===
{generator_code}
''')
            elif (node.id, 'output_generator') in existing_blocks:
                needs_executor = True
                has_custom_output_generator = True
                # Add imports needed for output generators
                imports.add("from typing import Any")
                imports.add("from sygra.processors.output_record_generator import BaseOutputGenerator")
                imports.add("from sygra.core.graph.sygra_state import SygraState")
                classes.append(f'''
# === Output Generator for {node.id} ===
{existing_blocks[(node.id, 'output_generator')]}
''')

    # Check for conditional edges
    for edge in request.edges:
        if edge.is_conditional and edge.condition and edge.condition.condition_path:
            if task_name in edge.condition.condition_path:
                needs_executor = True
                imports.add("from sygra.core.graph.sygra_state import SygraState")

                func_name = edge.condition.condition_path.split('.')[-1]

                # Check for existing code
                condition_code = getattr(edge.condition, '_code', None)
                if condition_code and condition_code.strip():
                    functions.append(f'''
# === Branch Condition for {edge.source} ===
{condition_code.strip()}
''')
                elif (edge.source, 'branch_condition') in existing_blocks:
                    functions.append(f'''
# === Branch Condition for {edge.source} ===
{existing_blocks[(edge.source, 'branch_condition')]}
''')
                else:
                    path_map_keys = list(edge.condition.path_map.keys()) if edge.condition.path_map else ['default']
                    functions.append(f'''
# === Branch Condition for {edge.source} ===
def {func_name}(state: SygraState) -> str:
    """Conditional edge function from {edge.source} to determine next node."""
    # TODO: Implement condition logic
    # Return one of: {path_map_keys}
    # Access state variables: state["variable_name"]
    return "{path_map_keys[0]}"
''')

    # DefaultOutputGenerator is NOT needed if:
    # 1. There's no OUTPUT node, OR
    # 2. A custom output generator already exists
    # It IS needed only when there's an OUTPUT node with LLM nodes but no custom generator

    if not needs_executor:
        return None

    # Build the file content
    code_parts = [
        '"""',
        f'Task executor for {request.name} workflow.',
        '',
        'This file contains custom processors, lambda functions, and conditional edge logic.',
        '"""',
        '',
    ]

    # Add imports
    for imp in sorted(imports):
        code_parts.append(imp)

    code_parts.append('')

    # Add classes
    for cls in classes:
        code_parts.append(cls)

    # Add functions
    for func in functions:
        code_parts.append(func)

    return '\n'.join(code_parts)


def _extract_class_or_function_body(code_content: str) -> str:
    """
    Extract just the class or function definition from code content,
    removing any inline imports and docstrings that precede it.

    Args:
        code_content: Raw code that may include imports, docstrings, and class/function

    Returns:
        Clean class or function definition without preceding imports
    """
    lines = code_content.strip().split('\n')
    result_lines = []
    in_class_or_func = False
    class_indent = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Skip empty lines before class/function
        if not in_class_or_func and not stripped:
            continue

        # Skip import statements before class/function
        if not in_class_or_func and (stripped.startswith('from ') or stripped.startswith('import ')):
            continue

        # Skip module-level docstrings (before class/function)
        if not in_class_or_func and (stripped.startswith('"""') or stripped.startswith("'''")):
            # Skip until closing quote
            if stripped.count('"""') == 1 or stripped.count("'''") == 1:
                quote = '"""' if '"""' in stripped else "'''"
                for j in range(i + 1, len(lines)):
                    if quote in lines[j]:
                        break
            continue

        # Detect start of class or function
        if stripped.startswith('class ') or stripped.startswith('def '):
            in_class_or_func = True
            class_indent = len(line) - len(line.lstrip())
            result_lines.append(line)
            continue

        # Once in class/function, include everything
        if in_class_or_func:
            result_lines.append(line)

    return '\n'.join(result_lines)


def _detect_code_type_from_ast(code: str) -> Optional[Tuple[str, str, int, int]]:
    """
    Use AST to detect the type of code based on base class inheritance.

    This is more robust than pattern matching on names because it actually
    checks what the class inherits from.

    Args:
        code: Python source code to analyze

    Returns:
        Tuple of (code_type, name, start_line, end_line) or None if not recognized.
        code_type is one of: 'pre_process', 'post_process', 'output_generator',
                            'data_transform', 'lambda', 'branch_condition'
    """
    import ast

    # Base class mappings - check these against actual inheritance
    BASE_CLASS_TO_TYPE = {
        # Pre-processors
        'NodePreProcessor': 'pre_process',
        # Post-processors
        'NodePostProcessor': 'post_process',
        'NodePostProcessorWithState': 'post_process',
        # Output generators
        'BaseOutputGenerator': 'output_generator',
        # Data transforms
        'DataTransform': 'data_transform',
        # Edge conditions (branch)
        'EdgeCondition': 'branch_condition',
        # Lambda functions
        'LambdaFunction': 'lambda',
    }

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        # Check class definitions
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                # Handle simple base class names: class Foo(BaseClass)
                if isinstance(base, ast.Name):
                    base_name = base.id
                    if base_name in BASE_CLASS_TO_TYPE:
                        end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                        return (BASE_CLASS_TO_TYPE[base_name], node.name, node.lineno, end_line)

                # Handle attribute access: class Foo(module.BaseClass)
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                    if base_name in BASE_CLASS_TO_TYPE:
                        end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                        return (BASE_CLASS_TO_TYPE[base_name], node.name, node.lineno, end_line)

        # Check function definitions (for lambda and branch_condition functions)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Lambda functions: typically named {node_id}_function
            if node.name.endswith('_function'):
                end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                # Extract node_id from function name
                node_id = node.name[:-9]  # Remove '_function' suffix
                return ('lambda', node.name, node.lineno, end_line)

            # Branch conditions: typically named {node_id}_condition
            elif node.name.endswith('_condition'):
                end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                return ('branch_condition', node.name, node.lineno, end_line)

    return None


def _find_code_blocks_by_ast(content: str) -> List[Dict[str, Any]]:
    """
    Parse file content using AST to find all code blocks and their types.

    Returns a list of dicts with:
        - type: code type ('pre_process', 'post_process', etc.)
        - name: class/function name
        - node_id: extracted node ID from the name
        - start_line: 1-indexed start line
        - end_line: 1-indexed end line
        - code: the extracted code string
    """
    import ast

    BASE_CLASS_TO_TYPE = {
        'NodePreProcessor': 'pre_process',
        'NodePostProcessor': 'post_process',
        'NodePostProcessorWithState': 'post_process',
        'BaseOutputGenerator': 'output_generator',
        'DataTransform': 'data_transform',
        'EdgeCondition': 'branch_condition',
        'LambdaFunction': 'lambda',
    }

    # Suffixes for extracting node_id from names
    SUFFIX_PATTERNS = {
        'pre_process': ('PreProcessor',),
        'post_process': ('PostProcessor',),
        'output_generator': ('Generator',),
        'data_transform': ('Transform',),
        'lambda': ('Lambda', '_function'),  # Class-based pattern first, function-based for backwards compat
        'branch_condition': ('Condition', '_condition'),  # Class-based pattern first, function-based for backwards compat
    }

    results = []
    lines = content.splitlines(keepends=True)

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return results

    for node in ast.walk(tree):
        code_type = None
        name = None
        node_id = None

        # Check class definitions
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                base_name = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr

                if base_name and base_name in BASE_CLASS_TO_TYPE:
                    code_type = BASE_CLASS_TO_TYPE[base_name]
                    name = node.name
                    # Extract node_id from class name
                    for suffix in SUFFIX_PATTERNS.get(code_type, ()):
                        if name.endswith(suffix):
                            node_id = name[:-len(suffix)]
                            break
                    if not node_id:
                        node_id = name
                    break

        # Check function definitions
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.endswith('_function'):
                code_type = 'lambda'
                name = node.name
                node_id = name[:-9]  # Remove '_function'
            elif node.name.endswith('_condition'):
                code_type = 'branch_condition'
                name = node.name
                node_id = name[:-10]  # Remove '_condition'

        if code_type and name:
            start_line = node.lineno - 1  # Convert to 0-indexed
            end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 1

            # Extract the code
            code_lines = lines[start_line:end_line]
            code = ''.join(code_lines).rstrip()

            results.append({
                'type': code_type,
                'name': name,
                'node_id': node_id,
                'start_line': start_line,
                'end_line': end_line,
                'code': code
            })

    return results


def _find_code_block_for_node(content: str, node_id: str, code_type: str) -> Optional[Tuple[int, int, str]]:
    """
    Find a specific code block for a node ID and code type using AST.

    Args:
        content: Full file content
        node_id: The node ID to find
        code_type: Type of code ('pre_process', 'post_process', etc.)

    Returns:
        Tuple of (start_pos, end_pos, code) for string replacement, or None if not found
    """
    # First try marker-based detection
    marker_map = {
        'pre_process': 'Pre-Processor',
        'post_process': 'Post-Processor',
        'lambda': 'Lambda Function',
        'branch_condition': 'Branch Condition',
        'output_generator': 'Output Generator',
        'data_transform': 'Data Transformation',
    }

    marker_label = marker_map.get(code_type)
    if marker_label:
        # Pattern allows for blank lines between code blocks using \n\s*
        marker_pattern = rf'# === {re.escape(marker_label)} for {re.escape(node_id)} ===\n.*?(?=\n\s*# ===|\n\s*class DefaultOutputGenerator|\Z)'
        match = re.search(marker_pattern, content, re.DOTALL)
        if match:
            return (match.start(), match.end(), match.group(0))

    # Fall back to AST-based detection
    blocks = _find_code_blocks_by_ast(content)
    lines = content.splitlines(keepends=True)

    # Normalize node_id for comparison
    safe_node_id = re.sub(r'[^a-zA-Z0-9_]', '', node_id.replace('-', '_').replace(' ', '_'))

    for block in blocks:
        if block['type'] != code_type:
            continue

        # Compare normalized node IDs
        block_safe_id = re.sub(r'[^a-zA-Z0-9_]', '', block['node_id'].replace('-', '_').replace(' ', '_'))
        if block_safe_id == safe_node_id:
            # Check if there's a marker comment preceding the class/function
            # Look at the line(s) before the block start
            actual_start_line = block['start_line']
            marker_prefix = f'# === {marker_label} for '

            # Scan backwards to find marker comment (skip blank lines)
            check_line = actual_start_line - 1
            while check_line >= 0:
                line_content = lines[check_line].strip()
                if line_content.startswith(marker_prefix):
                    # Found a marker, include it in the range
                    actual_start_line = check_line
                    break
                elif line_content == '':
                    # Blank line, continue searching backwards
                    check_line -= 1
                else:
                    # Non-blank, non-marker line - stop searching
                    break

            # Calculate character positions from line numbers
            start_pos = sum(len(lines[i]) for i in range(actual_start_line))
            end_pos = sum(len(lines[i]) for i in range(block['end_line']))
            return (start_pos, end_pos, block['code'])

    return None


def _is_stub_code(code: str, code_type: str) -> bool:
    """
    Detect if code is just a stub/template without actual user modifications.

    Stub patterns:
    - Pre-processor: Only has "return state" with comments
    - Post-processor: Only has "return {"response": resp.message.content}" with comments
    - Data transform: Only has "return record" with comments
    - Lambda/Branch: Only has "return" with no real logic

    Args:
        code: The code to check
        code_type: Type of code ('pre_process', 'post_process', 'data_transform', 'lambda', 'branch_condition', 'output_generator')

    Returns:
        True if this is stub code that should not be saved
    """
    if not code or not code.strip():
        return True

    # Extract just the meaningful lines (non-comment, non-empty, non-docstring)
    lines = code.strip().split('\n')
    meaningful_lines = []
    in_docstring = False
    docstring_quote = None

    for line in lines:
        stripped = line.strip()

        # Handle docstrings
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring_quote = '"""' if stripped.startswith('"""') else "'''"
                # Check if docstring ends on same line
                if stripped.count(docstring_quote) >= 2:
                    continue  # Single-line docstring, skip
                in_docstring = True
                continue
        else:
            if docstring_quote in stripped:
                in_docstring = False
            continue

        # Skip empty lines
        if not stripped:
            continue

        # Skip comment lines
        if stripped.startswith('#'):
            continue

        # Skip class/def declarations
        if stripped.startswith('class ') or stripped.startswith('def '):
            continue

        # Skip decorator lines
        if stripped.startswith('@'):
            continue

        # This is a meaningful line
        meaningful_lines.append(stripped)

    # Check for stub patterns based on code type
    if code_type == 'pre_process':
        # Stub pre-processor only has "return state" or assigns self.params
        for line in meaningful_lines:
            if line not in ('return state', 'self.params = params'):
                return False
        return True

    elif code_type == 'post_process':
        # Stub post-processor only has return {"response": resp.message.content}
        for line in meaningful_lines:
            if line not in ('return {"response": resp.message.content}',):
                return False
        return True

    elif code_type == 'data_transform':
        # Stub data transform only has "return data" or "return record" or assigns self.params
        # Also allow the name property return (e.g., return "SomeTransform")
        for line in meaningful_lines:
            # Allow standard stub patterns
            if line in ('return data', 'return record', 'self.params = params'):
                continue
            # Allow name property return (quoted string)
            if line.startswith('return "') and line.endswith('"'):
                continue
            if line.startswith("return '") and line.endswith("'"):
                continue
            # Any other line means it's not a stub
            return False
        return True

    elif code_type == 'lambda':
        # Stub lambda has no meaningful lines or just returns state
        if not meaningful_lines:
            return True
        if len(meaningful_lines) == 1 and meaningful_lines[0].startswith('return'):
            if meaningful_lines[0] in ('return state', 'return None', 'return'):
                return True
        return False

    elif code_type == 'branch_condition':
        # Stub branch condition just returns a default string
        if not meaningful_lines:
            return True
        if len(meaningful_lines) == 1 and meaningful_lines[0].startswith('return'):
            # Check for stub returns like "return state", "return 'default'", etc.
            if meaningful_lines[0] in ('return state', 'return None', 'return', 'return "default"', "return 'default'"):
                return True
        return False

    elif code_type == 'output_generator':
        # Stub output generator only has default return statements
        stub_patterns = (
            'return super()._build_record(state)',
            'return {}',
            'return',
        )
        for line in meaningful_lines:
            if line not in stub_patterns:
                return False
        return True

    return False


def _rebuild_task_executor(workflow_dir: Path) -> bool:
    """
    Rebuild the entire task_executor.py file from stored node metadata.

    This creates a clean, well-organized file with:
    - Consolidated imports at the top
    - Organized sections for each code type
    - No duplicate imports

    Args:
        workflow_dir: Path to the workflow directory

    Returns:
        True if successful, False otherwise
    """
    task_executor_path = workflow_dir / "task_executor.py"
    task_name = workflow_dir.name

    # Collect all imports needed
    imports = set()
    imports.add('from typing import Any, Dict')

    # Code sections
    data_transforms = []
    pre_processors = []
    post_processors = []
    lambda_functions = []
    branch_conditions = []
    output_generators = []

    # Read existing file to extract current code blocks
    existing_content = ""
    has_default_generator = False

    if task_executor_path.exists():
        try:
            with open(task_executor_path, 'r') as f:
                existing_content = f.read()
        except Exception:
            pass

    # Parse existing code blocks using AST-based detection (checks base class inheritance)
    if existing_content:
        # Track node_ids we've already extracted to avoid duplicates
        extracted_ids = {
            'data_transform': set(),
            'pre_process': set(),
            'post_process': set(),
            'lambda': set(),
            'branch_condition': set(),
            'output_generator': set(),
        }

        # First, extract marker-based blocks (these take precedence)
        # Note: The lookahead allows for blank lines between code blocks using \n\s*
        marker_patterns = {
            'data_transform': r'# === Data Transformation for ([^\n]+) ===\n(.*?)(?=\n\s*# ===|\n\s*class DefaultOutputGenerator|\Z)',
            'pre_process': r'# === Pre-Processor for ([^\n]+) ===\n(.*?)(?=\n\s*# ===|\n\s*class DefaultOutputGenerator|\Z)',
            'post_process': r'# === Post-Processor for ([^\n]+) ===\n(.*?)(?=\n\s*# ===|\n\s*class DefaultOutputGenerator|\Z)',
            'lambda': r'# === Lambda Function for ([^\n]+) ===\n(.*?)(?=\n\s*# ===|\n\s*class DefaultOutputGenerator|\Z)',
            'branch_condition': r'# === Branch Condition for ([^\n]+) ===\n(.*?)(?=\n\s*# ===|\n\s*class DefaultOutputGenerator|\Z)',
            'output_generator': r'# === Output Generator for ([^\n]+) ===\n(.*?)(?=\n\s*# ===|\n\s*class DefaultOutputGenerator|\Z)',
        }

        code_lists = {
            'data_transform': data_transforms,
            'pre_process': pre_processors,
            'post_process': post_processors,
            'lambda': lambda_functions,
            'branch_condition': branch_conditions,
            'output_generator': output_generators,
        }

        # Extract marker-based blocks first
        for code_type, pattern in marker_patterns.items():
            for match in re.finditer(pattern, existing_content, re.DOTALL):
                node_id = match.group(1).strip()
                code = match.group(2).strip()
                if code and node_id not in extracted_ids[code_type]:
                    clean_code = _extract_class_or_function_body(code)
                    if clean_code and not _is_stub_code(clean_code, code_type):
                        code_lists[code_type].append((node_id, clean_code))
                        extracted_ids[code_type].add(node_id)

        # Now use AST-based detection for code without markers
        # This checks actual base class inheritance for robust detection
        ast_blocks = _find_code_blocks_by_ast(existing_content)

        for block in ast_blocks:
            code_type = block['type']
            node_id = block['node_id']
            code = block['code']

            # Skip if already extracted via marker
            if node_id in extracted_ids.get(code_type, set()):
                continue

            # Skip DefaultOutputGenerator
            if block['name'] == 'DefaultOutputGenerator':
                continue

            # Skip stub code
            if _is_stub_code(code, code_type):
                continue

            # Add to appropriate list
            if code_type in code_lists:
                code_lists[code_type].append((node_id, code))
                extracted_ids[code_type].add(node_id)

        # Add required imports based on what was found
        if pre_processors:
            imports.add('from sygra.core.graph.functions.node_processor import NodePreProcessor')
            imports.add('from sygra.core.graph.sygra_state import SygraState')
        if post_processors:
            imports.add('from sygra.core.graph.functions.node_processor import NodePostProcessor')
            imports.add('from sygra.core.graph.functions.node_processor import NodePostProcessorWithState')
            imports.add('from sygra.core.graph.sygra_message import SygraMessage')
            imports.add('from sygra.core.graph.sygra_state import SygraState')
        if lambda_functions:
            imports.add('from sygra.core.graph.functions.lambda_function import LambdaFunction')
            imports.add('from sygra.core.graph.sygra_state import SygraState')
        if branch_conditions:
            imports.add('from sygra.core.graph.functions.edge_condition import EdgeCondition')
            imports.add('from sygra.core.graph.sygra_state import SygraState')
        if output_generators:
            imports.add('from sygra.processors.output_record_generator import BaseOutputGenerator')
        if data_transforms:
            imports.add('from sygra.processors.data_transform import DataTransform')

        # Check for DefaultOutputGenerator - only keep if explicitly present
        has_default_generator = 'class DefaultOutputGenerator' in existing_content and not output_generators

    # Build the clean file content
    content_parts = [
        '"""',
        f'Task executor for {task_name} workflow.',
        '',
        'This file contains custom processors, lambda functions, and conditional edge logic.',
        '"""',
        '',
    ]

    # Add utility imports if needed for DefaultOutputGenerator
    # Only add these imports if we're actually including the DefaultOutputGenerator
    if has_default_generator:
        imports.add('from sygra.processors.output_record_generator import BaseOutputGenerator')
        imports.add('from sygra.utils import utils')

    # Add sorted imports (deduplicated via set)
    sorted_imports = sorted(imports)
    for imp in sorted_imports:
        content_parts.append(imp)

    content_parts.append('')
    content_parts.append('')

    # Add Data Transformations section
    if data_transforms:
        for node_id, code in data_transforms:
            content_parts.append(f'# === Data Transformation for {node_id} ===')
            content_parts.append(code)
            content_parts.append('')
            content_parts.append('')

    # Add Pre-Processors section
    if pre_processors:
        for node_id, code in pre_processors:
            content_parts.append(f'# === Pre-Processor for {node_id} ===')
            content_parts.append(code)
            content_parts.append('')
            content_parts.append('')

    # Add Post-Processors section
    if post_processors:
        for node_id, code in post_processors:
            content_parts.append(f'# === Post-Processor for {node_id} ===')
            content_parts.append(code)
            content_parts.append('')
            content_parts.append('')

    # Add Lambda Functions section
    if lambda_functions:
        for node_id, code in lambda_functions:
            content_parts.append(f'# === Lambda Function for {node_id} ===')
            content_parts.append(code)
            content_parts.append('')
            content_parts.append('')

    # Add Branch Conditions section
    if branch_conditions:
        for node_id, code in branch_conditions:
            content_parts.append(f'# === Branch Condition for {node_id} ===')
            content_parts.append(code)
            content_parts.append('')
            content_parts.append('')

    # Add Output Generators section
    if output_generators:
        for node_id, code in output_generators:
            content_parts.append(f'# === Output Generator for {node_id} ===')
            content_parts.append(code)
            content_parts.append('')
            content_parts.append('')
    elif has_default_generator:
        # Only add DefaultOutputGenerator if it was explicitly in the file before
        # Don't add it automatically - user must explicitly want it
        content_parts.append('class DefaultOutputGenerator(BaseOutputGenerator):')
        content_parts.append('    """Output generator that converts LangChain messages to chat format."""')
        content_parts.append('')
        content_parts.append('    @staticmethod')
        content_parts.append('    def build_response(data: Any, state: dict) -> list:')
        content_parts.append('        """Convert LangChain AIMessage objects to serializable chat format."""')
        content_parts.append('        return utils.convert_messages_from_langchain_to_chat_format(data)')
        content_parts.append('')

    try:
        with open(task_executor_path, 'w') as f:
            f.write('\n'.join(content_parts))
        return True
    except Exception as e:
        print(f"Error writing task_executor.py: {e}")
        return False


def _update_task_executor_code(
    workflow_dir: Path,
    node_id: str,
    code_type: str,  # 'pre_process', 'post_process', 'lambda', 'branch_condition', 'output_generator', 'data_transform'
    code_content: str,
    node_summary: Optional[str] = None
) -> bool:
    """
    Update the task_executor.py file with new processor/function code.

    Uses AST-based detection to find and replace code blocks by checking
    base class inheritance. No markers needed - single source of truth.

    Args:
        workflow_dir: Path to the workflow directory
        node_id: The node ID (used to generate class/function names)
        code_type: Type of code ('pre_process', 'post_process', 'lambda', 'branch_condition', 'output_generator', 'data_transform')
        code_content: The Python code content to save (can be empty to delete)
        node_summary: Optional node summary for docstrings

    Returns:
        True if successful, False otherwise
    """
    import ast

    task_executor_path = workflow_dir / "task_executor.py"

    valid_types = {'pre_process', 'post_process', 'lambda', 'branch_condition', 'output_generator', 'data_transform'}
    if code_type not in valid_types:
        print(f"Unknown code_type: {code_type}")
        return False

    # Read existing content
    existing_content = ""
    if task_executor_path.exists():
        try:
            with open(task_executor_path, 'r') as f:
                existing_content = f.read()
        except Exception as e:
            print(f"Error reading task_executor.py: {e}")
            return False

    # Extract just the class/function body from the code content
    clean_code = _extract_class_or_function_body(code_content) if code_content else ""

    # Skip saving if this is stub code (user hasn't added real logic)
    if clean_code and _is_stub_code(clean_code, code_type):
        # Don't save stub code - return success but don't write
        return True

    # If file doesn't exist or is empty, create it with the code
    if not existing_content.strip():
        if not clean_code:
            return True  # Nothing to write

        task_name = workflow_dir.name
        content = _create_task_executor_file(task_name, code_type, clean_code)
        try:
            with open(task_executor_path, 'w') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error writing task_executor.py: {e}")
            return False

    # File exists - find the code block using AST
    found_block = _find_code_block_by_ast(existing_content, node_id, code_type)

    if clean_code:
        # Ensure required imports exist
        updated_content = _ensure_imports(existing_content, code_type)

        if found_block:
            # Replace existing block
            start_pos, end_pos = found_block
            # Recalculate positions if imports were added
            if updated_content != existing_content:
                # Re-find the block in updated content
                found_block = _find_code_block_by_ast(updated_content, node_id, code_type)
                if found_block:
                    start_pos, end_pos = found_block
                else:
                    # Block no longer found after import changes, add at end
                    updated_content = updated_content.rstrip() + '\n\n\n' + clean_code + '\n'
                    try:
                        with open(task_executor_path, 'w') as f:
                            f.write(updated_content)
                        return True
                    except Exception as e:
                        print(f"Error writing task_executor.py: {e}")
                        return False

            updated_content = updated_content[:start_pos] + clean_code + '\n' + updated_content[end_pos:]
        else:
            # Add new code at the end
            updated_content = updated_content.rstrip() + '\n\n\n' + clean_code + '\n'

        # Clean up excessive newlines
        updated_content = re.sub(r'\n{4,}', '\n\n\n', updated_content)
    else:
        # Delete the code block (empty code_content)
        if found_block:
            start_pos, end_pos = found_block
            updated_content = existing_content[:start_pos] + existing_content[end_pos:]
            updated_content = re.sub(r'\n{3,}', '\n\n', updated_content)
        else:
            updated_content = existing_content

    # Write the updated content
    try:
        with open(task_executor_path, 'w') as f:
            f.write(updated_content)
        return True
    except Exception as e:
        print(f"Error writing task_executor.py: {e}")
        return False


def _create_task_executor_file(task_name: str, code_type: str, code: str) -> str:
    """Create a new task_executor.py file with initial code."""
    imports = _get_imports_for_code_type(code_type)

    content_parts = [
        '"""',
        f'Task executor for {task_name} workflow.',
        '',
        'This file contains custom processors, lambda functions, and conditional edge logic.',
        '"""',
        '',
        'from typing import Any, Dict',
    ]
    content_parts.extend(imports)
    content_parts.extend(['', '', code, ''])

    return '\n'.join(content_parts)


def _get_imports_for_code_type(code_type: str) -> List[str]:
    """Get the required imports for a code type."""
    imports = []
    if code_type == 'pre_process':
        imports.append('from sygra.core.graph.functions.node_processor import NodePreProcessor')
        imports.append('from sygra.core.graph.sygra_state import SygraState')
    elif code_type == 'post_process':
        imports.append('from sygra.core.graph.functions.node_processor import NodePostProcessor')
        imports.append('from sygra.core.graph.sygra_message import SygraMessage')
        imports.append('from sygra.core.graph.sygra_state import SygraState')
    elif code_type == 'lambda':
        imports.append('from sygra.core.graph.functions.lambda_function import LambdaFunction')
        imports.append('from sygra.core.graph.sygra_state import SygraState')
    elif code_type == 'branch_condition':
        imports.append('from sygra.core.graph.functions.edge_condition import EdgeCondition')
        imports.append('from sygra.core.graph.sygra_state import SygraState')
    elif code_type == 'output_generator':
        imports.append('from sygra.processors.output_record_generator import BaseOutputGenerator')
        imports.append('from sygra.core.graph.sygra_state import SygraState')
    elif code_type == 'data_transform':
        imports.append('from sygra.processors.data_transform import DataTransform')
    return imports


def _ensure_imports(content: str, code_type: str) -> str:
    """Ensure the required imports for a code type exist in the file."""
    required_imports = _get_imports_for_code_type(code_type)

    # Find where imports end (look for first class or function definition)
    lines = content.split('\n')
    import_end_idx = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('from ') or stripped.startswith('import '):
            import_end_idx = i + 1
        elif stripped.startswith('class ') or stripped.startswith('def ') or stripped.startswith('@'):
            break

    # Check which imports are missing
    missing_imports = []
    for imp in required_imports:
        if imp not in content:
            missing_imports.append(imp)

    if not missing_imports:
        return content

    # Insert missing imports
    new_lines = lines[:import_end_idx] + missing_imports + lines[import_end_idx:]
    return '\n'.join(new_lines)


def _find_code_block_by_ast(content: str, node_id: str, code_type: str) -> Optional[Tuple[int, int]]:
    """
    Find a code block for a node using AST-based detection.

    Returns (start_pos, end_pos) character positions for replacement, or None if not found.
    """
    import ast

    # Base class to code type mapping
    BASE_CLASS_TO_TYPE = {
        'NodePreProcessor': 'pre_process',
        'NodePostProcessor': 'post_process',
        'NodePostProcessorWithState': 'post_process',
        'BaseOutputGenerator': 'output_generator',
        'DataTransform': 'data_transform',
        'EdgeCondition': 'branch_condition',
        'LambdaFunction': 'lambda',
    }

    # Expected class name suffixes
    SUFFIX_MAP = {
        'pre_process': 'PreProcessor',
        'post_process': 'PostProcessor',
        'output_generator': 'Generator',
        'data_transform': 'Transform',
        'lambda': 'Lambda',
        'branch_condition': 'Condition',
    }

    # Normalize node_id for comparison
    safe_node_id = re.sub(r'[^a-zA-Z0-9_]', '', node_id.replace('-', '_').replace(' ', '_'))
    expected_suffix = SUFFIX_MAP.get(code_type, '')
    expected_name = f"{safe_node_id}{expected_suffix}"

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    lines = content.splitlines(keepends=True)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if class name matches expected pattern
            class_name = node.name
            class_safe_id = class_name[:-len(expected_suffix)] if class_name.endswith(expected_suffix) else class_name

            # Check base class inheritance
            detected_type = None
            for base in node.bases:
                base_name = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr

                if base_name and base_name in BASE_CLASS_TO_TYPE:
                    detected_type = BASE_CLASS_TO_TYPE[base_name]
                    break

            # Match if type and node_id match
            if detected_type == code_type:
                # Check if the class name contains the node_id
                normalized_class_id = re.sub(r'[^a-zA-Z0-9_]', '', class_safe_id.replace('-', '_'))
                if normalized_class_id == safe_node_id or class_name == expected_name:
                    start_line = node.lineno - 1  # 0-indexed
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 1

                    start_pos = sum(len(lines[i]) for i in range(start_line))
                    end_pos = sum(len(lines[i]) for i in range(end_line))
                    return (start_pos, end_pos)

    return None


def _remove_code_block_from_file(content: str, node_id: str, code_type: str) -> str:
    """
    Remove a code block for a specific node from file content.

    Uses AST-based detection to find and remove the code block.
    Also removes associated marker comments.

    Args:
        content: The file content
        node_id: The node ID to remove code for
        code_type: Type of code ('pre_process', 'post_process', 'output_generator', etc.)

    Returns:
        Updated content with the code block removed
    """
    import ast

    if not content or not content.strip():
        return content

    # Base class to code type mapping
    BASE_CLASS_TO_TYPE = {
        'NodePreProcessor': 'pre_process',
        'NodePreProcessorWithState': 'pre_process',
        'NodePostProcessor': 'post_process',
        'NodePostProcessorWithState': 'post_process',
        'BaseOutputGenerator': 'output_generator',
        'DataTransform': 'data_transform',
        'EdgeCondition': 'branch_condition',
        'LambdaFunction': 'lambda',
    }

    # Expected class name suffixes
    SUFFIX_MAP = {
        'pre_process': 'PreProcessor',
        'post_process': 'PostProcessor',
        'output_generator': 'Generator',
        'data_transform': 'Transform',
        'lambda': 'Lambda',
        'branch_condition': 'Condition',
    }

    # Marker patterns for each code type
    MARKER_PATTERNS = {
        'pre_process': r'# === Pre-?[Pp]rocessor for ',
        'post_process': r'# === Post-?[Pp]rocessor for ',
        'output_generator': r'# === Output Generator for ',
        'data_transform': r'# === Data Transform for ',
        'lambda': r'# === Lambda for ',
        'branch_condition': r'# === Branch Condition for ',
    }

    # Normalize node_id for comparison
    safe_node_id = re.sub(r'[^a-zA-Z0-9_]', '', node_id.replace('-', '_').replace(' ', '_'))
    expected_suffix = SUFFIX_MAP.get(code_type, '')
    expected_name = f"{safe_node_id}{expected_suffix}"

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return content

    lines = content.splitlines(keepends=True)
    lines_to_remove = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            class_safe_id = class_name[:-len(expected_suffix)] if class_name.endswith(expected_suffix) else class_name

            # Check base class inheritance
            detected_type = None
            for base in node.bases:
                base_name = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr

                if base_name and base_name in BASE_CLASS_TO_TYPE:
                    detected_type = BASE_CLASS_TO_TYPE[base_name]
                    break

            # Match if type and node_id match
            if detected_type == code_type:
                normalized_class_id = re.sub(r'[^a-zA-Z0-9_]', '', class_safe_id.replace('-', '_'))
                if normalized_class_id == safe_node_id or class_name == expected_name:
                    start_line = node.lineno - 1  # 0-indexed
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 1

                    # Mark class lines for removal
                    for i in range(start_line, end_line):
                        lines_to_remove.add(i)

                    # Also look for marker comment and docstrings before the class
                    marker_pattern = MARKER_PATTERNS.get(code_type)
                    if marker_pattern:
                        # Search backwards for marker and associated content
                        search_start = max(0, start_line - 20)  # Look up to 20 lines back
                        for i in range(start_line - 1, search_start - 1, -1):
                            if i < 0:
                                break
                            line = lines[i].strip()
                            # Check for marker
                            if re.match(marker_pattern + re.escape(node_id), lines[i]):
                                lines_to_remove.add(i)
                                # Also remove empty line before marker if present
                                if i > 0 and not lines[i-1].strip():
                                    lines_to_remove.add(i - 1)
                                break
                            # Remove docstrings, import statements, and empty lines between marker and class
                            elif line.startswith('"""') or line.startswith("'''") or line.startswith('from ') or line.startswith('import ') or not line:
                                # Check if this is part of a docstring block
                                if line.startswith('"""') or line.startswith("'''"):
                                    lines_to_remove.add(i)
                                elif not line:
                                    lines_to_remove.add(i)
                                # Stop at imports (they might be shared)
                            else:
                                # Hit something else, stop searching
                                break

    if not lines_to_remove:
        return content

    # Rebuild content without removed lines
    new_lines = [lines[i] for i in range(len(lines)) if i not in lines_to_remove]

    # Clean up multiple consecutive empty lines
    result = ''.join(new_lines)

    # Remove excessive blank lines (more than 2 consecutive)
    result = re.sub(r'\n{4,}', '\n\n\n', result)

    # Ensure file ends with single newline
    result = result.rstrip() + '\n' if result.strip() else ''

    return result


def _get_node_code_from_file(content: str, node_id: str, code_type: str) -> Optional[str]:
    """
    Extract the code for a specific node from file content using AST.

    Returns the code string if found, None otherwise.
    """
    import ast

    # Base class to code type mapping
    BASE_CLASS_TO_TYPE = {
        'NodePreProcessor': 'pre_process',
        'NodePostProcessor': 'post_process',
        'NodePostProcessorWithState': 'post_process',
        'BaseOutputGenerator': 'output_generator',
        'DataTransform': 'data_transform',
        'EdgeCondition': 'branch_condition',
        'LambdaFunction': 'lambda',
    }

    # Expected class name suffixes
    SUFFIX_MAP = {
        'pre_process': 'PreProcessor',
        'post_process': 'PostProcessor',
        'output_generator': 'Generator',
        'data_transform': 'Transform',
        'lambda': 'Lambda',
        'branch_condition': 'Condition',
    }

    # Normalize node_id for comparison
    safe_node_id = re.sub(r'[^a-zA-Z0-9_]', '', node_id.replace('-', '_').replace(' ', '_'))
    expected_suffix = SUFFIX_MAP.get(code_type, '')
    expected_name = f"{safe_node_id}{expected_suffix}"

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    lines = content.splitlines(keepends=True)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            class_safe_id = class_name[:-len(expected_suffix)] if class_name.endswith(expected_suffix) else class_name

            # Check base class inheritance
            detected_type = None
            for base in node.bases:
                base_name = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr

                if base_name and base_name in BASE_CLASS_TO_TYPE:
                    detected_type = BASE_CLASS_TO_TYPE[base_name]
                    break

            # Match if type and node_id match
            if detected_type == code_type:
                normalized_class_id = re.sub(r'[^a-zA-Z0-9_]', '', class_safe_id.replace('-', '_'))
                if normalized_class_id == safe_node_id or class_name == expected_name:
                    start_line = node.lineno - 1  # 0-indexed
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 1

                    # Extract the code
                    code_lines = lines[start_line:end_line]
                    return ''.join(code_lines).rstrip()

    return None


def _execute_workflow_subprocess(
    task_name: str,
    args_dict: dict,
    result_queue: multiprocessing.Queue,
    log_queue: multiprocessing.Queue,
    node_queue: multiprocessing.Queue = None,
):
    """
    Function that runs in a subprocess to execute the workflow.

    This allows us to terminate the process mid-execution to save LLM costs.
    Logs are sent back to the main process via log_queue.
    Node execution events are sent via node_queue for real-time UI updates.
    """
    try:
        from sygra.core.base_task_executor import DefaultTaskExecutor
        from sygra.core.execution_callbacks import ExecutionCallbacks
        from sygra.utils import utils
        from sygra.logger.logger_config import set_external_logger
        from argparse import Namespace
        from datetime import datetime

        # Create a logger that sends logs to the queue
        class QueueLogger:
            def __init__(self, queue):
                self.queue = queue

            def _send(self, level: str, msg: str):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
                self.queue.put(f"{timestamp} - {level} - {msg}")

            def debug(self, msg: str): self._send("DEBUG", msg)
            def info(self, msg: str): self._send("INFO", msg)
            def warn(self, msg: str): self._send("WARNING", msg)
            def warning(self, msg: str): self._send("WARNING", msg)
            def error(self, msg: str): self._send("ERROR", msg)
            def exception(self, msg: str): self._send("ERROR", msg)

        # Set up log capture
        queue_logger = QueueLogger(log_queue)
        set_external_logger(queue_logger)

        # Reconstruct args namespace
        args = Namespace(**args_dict)

        # Set current task for SyGra utils
        utils.current_task = task_name

        # Create execution callbacks for real-time node tracking
        execution_callbacks = None
        if node_queue is not None:
            def on_node_start(node_name: str, input_data: dict):
                node_queue.put({
                    "event": "node_start",
                    "node_name": node_name,
                    "timestamp": datetime.now().isoformat(),
                })

            def on_node_complete(node_name: str, output_data: dict, duration_ms: int):
                node_queue.put({
                    "event": "node_complete",
                    "node_name": node_name,
                    "duration_ms": duration_ms,
                    "timestamp": datetime.now().isoformat(),
                })

            def on_node_error(node_name: str, error_msg: str, context: dict):
                node_queue.put({
                    "event": "node_error",
                    "node_name": node_name,
                    "error": error_msg,
                    "timestamp": datetime.now().isoformat(),
                })

            execution_callbacks = ExecutionCallbacks(
                on_node_start=on_node_start,
                on_node_complete=on_node_complete,
                on_node_error=on_node_error,
            )

        # Create and run task executor
        executor = DefaultTaskExecutor(args)
        executor.execute(execution_callbacks=execution_callbacks)

        result_queue.put({"status": "completed"})
    except Exception as e:
        import traceback
        from datetime import datetime as dt
        log_queue.put(f"{dt.now().strftime('%Y-%m-%d %H:%M:%S')} - ERROR - {type(e).__name__}: {str(e)}")
        result_queue.put({
            "status": "failed",
            "error": f"{type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc()
        })


class ExecutionLogCapture:
    """
    Logger that captures SyGra logs to an execution's logs list.

    Implements SyGra's ExternalLoggerProtocol to intercept all SyGra logs.
    """

    def __init__(self, execution: WorkflowExecution):
        self.execution = execution

    def _format_msg(self, level: str, msg: str) -> str:
        """Format log message with timestamp like SyGra's default format."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        return f"{timestamp} - {level} - {msg}"

    def debug(self, msg: str) -> None:
        self.execution.logs.append(self._format_msg("DEBUG", msg))

    def info(self, msg: str) -> None:
        self.execution.logs.append(self._format_msg("INFO", msg))

    def warn(self, msg: str) -> None:
        self.execution.logs.append(self._format_msg("WARNING", msg))

    def error(self, msg: str) -> None:
        self.execution.logs.append(self._format_msg("ERROR", msg))

    def exception(self, msg: str) -> None:
        self.execution.logs.append(self._format_msg("ERROR", msg))


async def _run_workflow(
    execution_id: str,
    workflow: WorkflowGraph,
    request: ExecutionRequest,
) -> None:
    """
    Background task to run a SyGra workflow in a subprocess.

    Using multiprocessing allows us to terminate the execution mid-flight
    when cancellation is requested, saving LLM costs.

    Args:
        execution_id: The execution ID.
        workflow: The workflow graph to execute.
        request: The execution request.
    """
    import os
    import glob
    import json

    execution = _executions[execution_id]

    # Check if already cancelled before starting
    if execution_id in _cancelled_executions:
        execution.status = ExecutionStatus.CANCELLED
        execution.completed_at = datetime.now()
        _cancelled_executions.discard(execution_id)
        return

    execution.status = ExecutionStatus.RUNNING

    try:
        # Load the workflow configuration
        if not workflow.source_path:
            raise ValueError("Workflow source path not available")

        # Extract task name from source path
        source_path = workflow.source_path
        if source_path.endswith("/graph_config.yaml"):
            task_dir = os.path.dirname(source_path)
        else:
            task_dir = source_path

        # Convert path to task module format
        task_name = task_dir.replace("/", ".").replace("\\", ".")
        if not task_name.startswith("tasks."):
            task_name = f"tasks.{task_name}" if not task_name.startswith("tasks") else task_name

        # Determine output directory and run name
        effective_output_dir = request.output_dir if request.output_dir else task_dir
        effective_run_name = request.run_name if request.run_name else f"studio_{execution_id[:8]}"

        # Create args dict for subprocess (must be picklable)
        args_dict = {
            "task": task_name,
            "start_index": request.start_index,
            "num_records": request.num_records,
            "batch_size": request.batch_size,
            "checkpoint_interval": request.checkpoint_interval,
            "debug": request.debug,
            "clear_logs": False,
            "output_with_ts": request.output_with_ts,
            "run_name": effective_run_name,
            "run_args": request.run_args or {},
            "resume": request.resume,
            "output_dir": effective_output_dir,
            "oasst": False,
            "quality": request.quality,
            "disable_metadata": request.disable_metadata,
        }

        # Update node states
        execution.current_node = "START"
        if "START" in execution.node_states:
            execution.node_states["START"].status = ExecutionStatus.COMPLETED
            execution.node_states["START"].completed_at = datetime.now()

        # Create queues for subprocess communication
        result_queue = multiprocessing.Queue()
        log_queue = multiprocessing.Queue()
        node_queue = multiprocessing.Queue()

        process = multiprocessing.Process(
            target=_execute_workflow_subprocess,
            args=(task_name, args_dict, result_queue, log_queue, node_queue)
        )

        # Store process for potential cancellation
        _running_processes[execution_id] = process

        execution.logs.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - Starting workflow execution in subprocess...")
        process.start()

        # Helper to drain logs from queue
        def drain_logs():
            while True:
                try:
                    log_msg = log_queue.get_nowait()
                    execution.logs.append(log_msg)
                except:
                    break

        # Helper to drain node events and update node states
        def drain_node_events():
            while True:
                try:
                    event = node_queue.get_nowait()
                    node_name = event.get("node_name")
                    event_type = event.get("event")

                    if node_name and node_name in execution.node_states:
                        node_state = execution.node_states[node_name]

                        if event_type == "node_start":
                            node_state.status = ExecutionStatus.RUNNING
                            node_state.started_at = datetime.fromisoformat(event.get("timestamp"))
                            execution.current_node = node_name

                        elif event_type == "node_complete":
                            node_state.status = ExecutionStatus.COMPLETED
                            node_state.completed_at = datetime.fromisoformat(event.get("timestamp"))
                            node_state.duration_ms = event.get("duration_ms", 0)

                        elif event_type == "node_error":
                            node_state.status = ExecutionStatus.FAILED
                            node_state.error = event.get("error")
                            node_state.completed_at = datetime.fromisoformat(event.get("timestamp"))
                except:
                    break

        # Poll for completion while checking for cancellation and collecting logs
        while process.is_alive():
            # Collect any pending logs and node events
            drain_logs()
            drain_node_events()

            if execution_id in _cancelled_executions:
                execution.logs.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - Cancellation requested, terminating execution...")
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                drain_logs()  # Get any final logs
                drain_node_events()  # Get any final node events
                execution.status = ExecutionStatus.CANCELLED
                execution.completed_at = datetime.now()
                _cancelled_executions.discard(execution_id)
                if execution_id in _running_processes:
                    del _running_processes[execution_id]
                # Close queues to prevent resource leaks
                try:
                    log_queue.close()
                    result_queue.close()
                    node_queue.close()
                except:
                    pass
                # Persist execution history
                _save_executions()
                return
            await asyncio.sleep(0.3)  # Check every 300ms for more responsive log updates

        process.join()

        # Drain any remaining logs and node events
        drain_logs()
        drain_node_events()

        # Clean up process reference
        if execution_id in _running_processes:
            del _running_processes[execution_id]

        # Check if cancelled externally (e.g., via cancel endpoint terminating process)
        # This handles the race condition where the process was killed externally
        if execution_id in _cancelled_executions or execution.status == ExecutionStatus.CANCELLED:
            execution.status = ExecutionStatus.CANCELLED
            execution.completed_at = datetime.now()
            _cancelled_executions.discard(execution_id)
            # Close queues
            try:
                log_queue.close()
                result_queue.close()
                node_queue.close()
            except:
                pass
            _save_executions()
            return

        # Get result from queue
        result = None
        try:
            result = result_queue.get_nowait()
        except:
            pass

        # Close queues to prevent resource leaks
        try:
            log_queue.close()
            log_queue.join_thread()
            result_queue.close()
            result_queue.join_thread()
            node_queue.close()
            node_queue.join_thread()
        except:
            pass

        if result and result.get("status") == "failed":
            raise Exception(result.get("error", "Unknown error"))

        # Final check: if cancelled during execution, don't mark as completed
        if execution_id in _cancelled_executions or execution.status == ExecutionStatus.CANCELLED:
            execution.status = ExecutionStatus.CANCELLED
            if not execution.completed_at:
                execution.completed_at = datetime.now()
            _cancelled_executions.discard(execution_id)
            _save_executions()
            return

        execution.logs.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - Workflow execution completed")

        # Mark all nodes as completed
        for node_id, node_state in execution.node_states.items():
            if node_state.status == ExecutionStatus.PENDING:
                node_state.status = ExecutionStatus.COMPLETED
                node_state.completed_at = datetime.now()

        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = datetime.now()

        # Find the output file and read its contents
        import glob
        import json
        output_pattern = f"{effective_output_dir}/{effective_run_name}_output_*.json"
        output_files = glob.glob(output_pattern)
        if output_files:
            # Get the most recent file
            execution.output_file = max(output_files, key=os.path.getmtime)

            # Read and parse the output data
            try:
                with open(execution.output_file, 'r') as f:
                    output_content = f.read().strip()
                    if not output_content:
                        execution.output_data = None
                    else:
                        # Try parsing as JSON first (handles arrays and objects)
                        try:
                            execution.output_data = json.loads(output_content)
                        except json.JSONDecodeError:
                            # Fallback to JSONL format (one JSON object per line)
                            execution.output_data = [json.loads(line) for line in output_content.split('\n') if line.strip()]
            except Exception as read_err:
                execution.output_data = result  # Fallback to executor result
        else:
            execution.output_data = result

        # Find and load metadata file
        metadata_dir = f"{effective_output_dir}/metadata"
        if os.path.exists(metadata_dir):
            metadata_pattern = f"{metadata_dir}/metadata_*.json"
            metadata_files = glob.glob(metadata_pattern)
            if metadata_files:
                # Get the most recent metadata file
                execution.metadata_file = max(metadata_files, key=os.path.getmtime)
                try:
                    with open(execution.metadata_file, 'r') as f:
                        execution.metadata = json.load(f)
                except Exception as meta_err:
                    execution.logs.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - WARNING - Failed to load metadata: {meta_err}")

        if execution.started_at:
            duration = (execution.completed_at - execution.started_at).total_seconds()
            execution.duration_ms = int(duration * 1000)

        # Persist execution history
        _save_executions()

    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}"
        execution.logs.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ERROR - Workflow execution failed: {error_msg}")
        execution.logs.append(traceback.format_exc())

        execution.status = ExecutionStatus.FAILED
        execution.error = error_msg
        execution.completed_at = datetime.now()

        # Mark current node as failed, and all pending nodes as cancelled
        for node_id, node_state in execution.node_states.items():
            if node_id == execution.current_node:
                # The node that failed
                node_state.status = ExecutionStatus.FAILED
                node_state.error = error_msg
                node_state.completed_at = datetime.now()
            elif node_state.status == ExecutionStatus.PENDING:
                # Nodes that never ran due to the failure - mark as cancelled
                node_state.status = ExecutionStatus.CANCELLED
            elif node_state.status == ExecutionStatus.RUNNING:
                # Any running node should also be marked as failed
                node_state.status = ExecutionStatus.FAILED
                node_state.error = "Execution aborted due to failure"
                node_state.completed_at = datetime.now()

        # Clean up process if it exists
        if execution_id in _running_processes:
            del _running_processes[execution_id]

        # Persist execution history
        _save_executions()

    finally:
        # Clean up cancellation tracking
        _cancelled_executions.discard(execution_id)


# Create default app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
