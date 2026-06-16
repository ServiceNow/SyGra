"""
WoW State Prediction Benchmark Runner — SyGra Discovery Agent

Runs the wow_state_predictor SyGra graph step-by-step over WoW trajectory files,
producing prediction files that are 100% compatible with WoW's evaluate_workflows.py.

Key design:
  - Steps within a trajectory are run SEQUENTIALLY (each step's prediction feeds
    into the next step's context, exactly like WoW's autoregressive loop).
  - Multiple trajectories can be run concurrently (--concurrency N).
  - Static context (table schemas, tool specs) is filtered per trajectory,
    using the exact same logic as WoW's WorldModelAgent._build_state_prediction_prompt.

Usage:
  cd /path/to/GraSP
  uv run python tasks/examples/wow_state_predictor/runner.py \\
    --trajectories-dir /path/to/wow/src/wow/data_files/trajectories \\
    --output-dir /path/to/state_pred/sygra-discovery \\
    --model bedrock_model \\
    --max-k 5 \\
    --subfolder manual

Then evaluate with WoW's evaluator (no changes needed):
  cd /path/to/world-of-workflows
  uv run python -m wow.environment.sampling.evaluate_workflows \\
    --state-preds-dir /path/to/state_pred/sygra-discovery/bedrock_model/manual \\
    --trajectories-dir src/wow/data_files/trajectories \\
    --k 5 \\
    --output-dir evaluation_results/sygra-discovery
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TASK_DIR = Path(__file__).parent
GRAPH_CONFIG_PATH = TASK_DIR / "graph_config.yaml"

# WoW prompts directory — adjust if WoW is installed elsewhere
# Can also be overridden via --wow-prompts-dir CLI arg.
_DEFAULT_WOW_PROMPTS = (
    Path(__file__).parent.parent.parent.parent.parent
    / "world-of-workflows"
    / "src"
    / "wow"
    / "environment"
    / "prompts"
)


# ---------------------------------------------------------------------------
# Graph building
# ---------------------------------------------------------------------------


_MODELS_YAML_PATH = Path(__file__).parent.parent.parent.parent / "sygra" / "config" / "models.yaml"


def _load_model_params(model_name: str) -> dict:
    """Load parameters for a model from models.yaml.

    Returns the model's native parameters dict (e.g. max_completion_tokens,
    temperature, reasoning_effort) so the graph config can use them correctly.
    Always:
      - Sets reasoning_effort to 'low' for benchmark efficiency
      - Sets max_tokens / max_completion_tokens to 16000
    """
    if not _MODELS_YAML_PATH.exists():
        return {}
    with open(_MODELS_YAML_PATH) as f:
        models = yaml.safe_load(f)
    params = dict(models.get(model_name, {}).get("parameters", {}))
    if "reasoning_effort" in params:
        params["reasoning_effort"] = "low"
    # Normalise token limit to 16000 regardless of which key the model uses
    if "max_completion_tokens" in params:
        params["max_completion_tokens"] = 16000
    else:
        params["max_tokens"] = 16000
    return params


def build_compiled_graph(model_name: str):
    """Build and compile the SyGra discovery-agent graph.

    Loads graph_config.yaml, overrides the agent model name and parameters
    (using the model's own parameters from models.yaml so that e.g.
    gpt-5/gpt-5-mini get max_completion_tokens rather than max_tokens),
    then builds the LangGraph StateGraph via SyGra's GraphConfig + LangGraphBuilder.
    Returns a compiled LangGraph that can be invoked with ainvoke(state).
    """
    from sygra.core.graph.graph_config import GraphConfig
    from sygra.core.graph.langgraph.graph_builder import LangGraphBuilder

    with open(GRAPH_CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    agent_model_cfg = config["graph_config"]["nodes"]["discovery_agent"]["model"]

    # Override model name
    agent_model_cfg["name"] = model_name

    # Merge model's native parameters from models.yaml, replacing graph_config defaults.
    # This ensures max_completion_tokens is used for o-series/gpt-5 models instead of max_tokens.
    native_params = _load_model_params(model_name)
    if native_params:
        agent_model_cfg["parameters"] = native_params

    graph_config = GraphConfig(config, dataset=None, output_transform_args={})
    graph = LangGraphBuilder(graph_config).build()
    return graph.compile()


# ---------------------------------------------------------------------------
# Static context loading (same files WoW uses)
# ---------------------------------------------------------------------------


def load_static_context(wow_prompts_dir: Path) -> tuple[dict, list, dict]:
    """Load WoW's compressed_schemas, compressed_tool_specs, tool_request_mapping.

    Returns:
        (table_schemas, tool_specs, tool_mapping)
    """
    with open(wow_prompts_dir / "compressed_schemas.json") as f:
        table_schemas: dict = json.load(f)

    with open(wow_prompts_dir / "compressed_tool_specs.json") as f:
        raw = json.load(f)
        tool_specs: list = raw.get("tools", raw)

    with open(wow_prompts_dir / "tool_request_mapping.json") as f:
        tool_mapping: dict = json.load(f)

    _log.info(
        "Loaded static context: %d tables, %d tool specs, %d tool mappings",
        len(table_schemas),
        len(tool_specs),
        len(tool_mapping),
    )
    return table_schemas, tool_specs, tool_mapping


# ---------------------------------------------------------------------------
# Context filtering (exact same logic as WoW's agent.py)
# ---------------------------------------------------------------------------


def _extract_workflow_tables(trajectory: list[dict]) -> set[str]:
    """Extract table names from trajectory step audits — mirrors WoW's _extract_tables."""
    tables: set[str] = set()
    for step in trajectory:
        for audit in step.get("audits", []):
            t = audit.get("tablename", "")
            if t:
                tables.add(t)
    return tables


def _extract_workflow_tools(trajectory: list[dict]) -> set[str]:
    """Extract tool names from trajectory steps — mirrors WoW's _extract_tools."""
    tools: set[str] = set()
    for step in trajectory:
        # Current format: tool_name at top level
        t = step.get("tool_name", "")
        if t:
            tools.add(t)
        # Old format: nested under "action"
        action = step.get("action", {})
        if isinstance(action, dict):
            t = action.get("tool_name", "")
            if t:
                tools.add(t)
    return tools


def filter_context(
    trajectory: list[dict],
    table_schemas: dict,
    tool_specs: list,
    tool_mapping: dict,
) -> tuple[dict, list]:
    """Filter schemas and tool specs to only what's relevant for this trajectory.

    Mirrors the filtering in WoW's agent.py:_build_state_prediction_prompt:
      - filtered_schemas: only tables seen in trajectory audits
      - inc_tools_specs:  only GET tools that appear in the trajectory
    """
    workflow_tables = _extract_workflow_tables(trajectory)
    workflow_tools = _extract_workflow_tools(trajectory)

    # Filter table schemas to trajectory tables only
    filtered_schemas = {k: v for k, v in table_schemas.items() if k in workflow_tables}

    # GET tools that appear in this trajectory (same filter as WoW state prediction)
    get_tool_names = {
        tool_name
        for tool_name, ops in tool_mapping.items()
        if "get" in ops
    }
    inc_tool_names = get_tool_names & workflow_tools

    inc_tools_specs = [t for t in tool_specs if t.get("name") in inc_tool_names]

    _log.debug(
        "Filtered context: %d tables (from %d), %d tool specs (from %d)",
        len(filtered_schemas),
        len(table_schemas),
        len(inc_tools_specs),
        len(tool_specs),
    )
    return filtered_schemas, inc_tools_specs


# ---------------------------------------------------------------------------
# Per-trajectory sequential prediction
# ---------------------------------------------------------------------------


async def predict_trajectory(
    compiled_graph: Any,
    trajectory: list[dict],
    trajectory_path: Path,
    filtered_schemas: dict,
    inc_tools_specs: list,
    max_k: Optional[int],
) -> list[dict]:
    """Run the discovery agent sequentially over all steps in a trajectory.

    Each step's predicted state is appended to `predicted_states` and passed
    as context to the next step — exactly matching WoW's autoregressive loop.

    Returns:
        List of predicted state dicts (each: {"audits": [...]})
    """
    steps = trajectory[:max_k] if max_k else trajectory
    predicted_states: list[dict] = []

    for i, step in enumerate(steps):
        # Extract action fields (same as WoW's generate_state_predictions)
        action = {k: v for k, v in step.items() if k in ("tool_name", "parameters")}
        # Handle old trajectory format: action nested under "action" key
        if not action.get("tool_name") and isinstance(step.get("action"), dict):
            action = step["action"]

        _log.info(
            "  Step %d/%d: %s", i + 1, len(steps), action.get("tool_name", "?")
        )

        state: dict[str, Any] = {
            "action_json": json.dumps(action),
            "previous_states_json": json.dumps(predicted_states),
            "table_schemas_json": json.dumps(filtered_schemas),
            "tool_specs_json": json.dumps(inc_tools_specs),
            "step_index": i,
        }

        try:
            result = await compiled_graph.ainvoke(state)
            pred_json: str = result.get("predicted_state_json", '{"audits": []}')
            predicted_state: dict = json.loads(pred_json)
        except Exception as exc:
            _log.error(
                "  Step %d failed (%s). Storing empty prediction.", i + 1, exc
            )
            predicted_state = {"audits": []}

        n = len(predicted_state.get("audits", []))
        _log.info("  Step %d done: %d audit records predicted", i + 1, n)
        predicted_states.append(predicted_state)

    return predicted_states


# ---------------------------------------------------------------------------
# WoW-format output writer
# ---------------------------------------------------------------------------


def write_wow_output(
    trajectory_path: Path,
    trajectory: list[dict],
    predicted_states: list[dict],
    output_dir: Path,
    model_name: str,
    max_k: Optional[int],
) -> Path:
    """Write a WoW-compatible prediction file.

    The file structure exactly matches what WorldModelAgent.generate_state_predictions
    produces, so evaluate_workflows.py can consume it without any changes.
    """
    k = min(len(predicted_states), max_k or len(predicted_states))

    # action_calls: same format as WoW
    actions = []
    for step in trajectory[:k]:
        if step.get("tool_name"):
            actions.append(
                {k_: v for k_, v in step.items() if k_ in ("tool_name", "parameters")}
            )
        elif isinstance(step.get("action"), dict):
            actions.append(step["action"])

    results = {
        "prediction_info": {
            "model": model_name,
            # WoW evaluator uses this field's basename to find the GT trajectory
            "trajectory_file": str(trajectory_path),
            "k": k,
            "total_actions_predicted": k,
            "total_states_generated": len(predicted_states),
        },
        "action_calls": actions,
        "predicted_states": predicted_states[:k],
    }

    output_file = output_dir / trajectory_path.name
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    _log.info("  Written: %s", output_file)
    return output_file


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def run_all(
    trajectories_dir: Path,
    output_dir: Path,
    model_name: str,
    max_k: Optional[int],
    subfolder: Optional[str],
    skip_existing: bool,
    concurrency: int,
    wow_prompts_dir: Path,
) -> None:
    """Orchestrate prediction across all trajectory files."""
    # Build graph once (model baked in)
    _log.info("Building SyGra compiled graph with model=%s ...", model_name)
    compiled_graph = build_compiled_graph(model_name)
    _log.info("Graph built successfully.")

    # Load static context once
    table_schemas, tool_specs, tool_mapping = load_static_context(wow_prompts_dir)

    # Collect trajectory files
    search_root = trajectories_dir / subfolder if subfolder else trajectories_dir
    traj_files = sorted(search_root.rglob("*.json"))
    if not traj_files:
        _log.error("No trajectory JSON files found under %s", search_root)
        return

    _log.info("Found %d trajectory files to process", len(traj_files))

    # Output base: output_dir / model_name / subfolder (or flat)
    out_base = output_dir / model_name
    if subfolder:
        out_base = out_base / subfolder

    async def process_one(traj_path: Path) -> None:
        out_file = out_base / traj_path.name
        if skip_existing and out_file.exists():
            _log.info("Skipping (already exists): %s", traj_path.name)
            return

        _log.info("Processing: %s", traj_path.name)
        try:
            with open(traj_path) as f:
                trajectory = json.load(f)
        except Exception as exc:
            _log.error("Failed to load %s: %s", traj_path, exc)
            return

        if not trajectory:
            _log.warning("Empty trajectory: %s", traj_path.name)
            return

        filtered_schemas, inc_tools_specs = filter_context(
            trajectory, table_schemas, tool_specs, tool_mapping
        )

        predicted_states = await predict_trajectory(
            compiled_graph,
            trajectory,
            traj_path,
            filtered_schemas,
            inc_tools_specs,
            max_k,
        )

        write_wow_output(
            traj_path, trajectory, predicted_states, out_base, model_name, max_k
        )

    # Run with concurrency limit (semaphore).
    # NOTE: steps within each trajectory are always sequential.
    # Concurrency > 1 runs multiple TRAJECTORIES in parallel.
    semaphore = asyncio.Semaphore(concurrency)

    async def guarded(traj_path: Path) -> None:
        async with semaphore:
            await process_one(traj_path)

    await asyncio.gather(*[guarded(p) for p in traj_files])
    _log.info("All trajectories processed. Output dir: %s", out_base)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WoW State Prediction via SyGra Discovery Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--trajectories-dir",
        required=True,
        type=Path,
        help="Path to WoW trajectories directory (e.g., .../src/wow/data_files/trajectories)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help=(
            "Base output directory. Predictions are written to "
            "<output-dir>/<model>/<subfolder>/<traj>.json"
        ),
    )
    parser.add_argument(
        "--model",
        default="bedrock_model",
        help=(
            "SyGra model name as registered in models.yaml "
            "(e.g., bedrock_model, gpt-4o-mini, gpt-4o). "
            "Must have a langgraph-compatible backend."
        ),
    )
    parser.add_argument(
        "--max-k",
        type=int,
        default=None,
        help="Maximum number of steps to predict per trajectory (default: all steps)",
    )
    parser.add_argument(
        "--subfolder",
        default=None,
        help=(
            "Process only trajectories under this subfolder "
            "(e.g., 'manual', 'dep_graph', 'constraint'). "
            "Default: all subfolders."
        ),
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip trajectories whose prediction file already exists",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help=(
            "Number of trajectories to process in parallel (default 1). "
            "Steps within each trajectory are always sequential. "
            "Use 1 to avoid hammering the SN dev instance."
        ),
    )
    parser.add_argument(
        "--wow-prompts-dir",
        type=Path,
        default=None,
        help=(
            "Path to WoW's prompts/ directory containing compressed_schemas.json, "
            "compressed_tool_specs.json, and tool_request_mapping.json. "
            f"Default: {_DEFAULT_WOW_PROMPTS}"
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG logging",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    wow_prompts_dir = args.wow_prompts_dir or _DEFAULT_WOW_PROMPTS
    if not wow_prompts_dir.exists():
        _log.error(
            "WoW prompts directory not found: %s\n"
            "Set --wow-prompts-dir to the correct path.",
            wow_prompts_dir,
        )
        sys.exit(1)

    if not args.trajectories_dir.exists():
        _log.error("Trajectories directory not found: %s", args.trajectories_dir)
        sys.exit(1)

    # Load dotenv if present (SyGra convention)
    try:
        from sygra.utils.dotenv import load_dotenv
        load_dotenv(dotenv_path=".env", override=True)
    except ImportError:
        pass

    asyncio.run(
        run_all(
            trajectories_dir=args.trajectories_dir,
            output_dir=args.output_dir,
            model_name=args.model,
            max_k=args.max_k,
            subfolder=args.subfolder,
            skip_existing=args.skip_existing,
            concurrency=args.concurrency,
            wow_prompts_dir=wow_prompts_dir,
        )
    )


if __name__ == "__main__":
    main()
