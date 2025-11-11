"""
Utility functions for AgentLab-SyGra integration.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sygra.logger.logger_config import logger

try:
    from agentlab.agents.agent_args import AgentArgs  # type: ignore

    AGENTLAB_AVAILABLE = True
except ImportError:
    AGENTLAB_AVAILABLE = False


def convert_trajectory_to_training_format(
    trajectory: List[Dict[str, Any]], format: str = "instruction_following"
) -> Dict[str, Any]:
    """
    Convert agent trajectory to training data format.

    Args:
        trajectory: Agent execution trajectory
        format: Output format (instruction_following, conversation, qa)

    Returns:
        Formatted training example
    """
    if format == "instruction_following":
        # Format: instruction → reasoning → actions → outcome
        return {
            "instruction": trajectory[0].get("observation", {}).get("goal", ""),
            "reasoning": [step.get("thought", "") for step in trajectory],
            "actions": [step.get("action", "") for step in trajectory],
            "outcome": trajectory[-1].get("observation", {}).get("success", False),
        }

    elif format == "conversation":
        # Format: multi-turn conversation
        messages = []
        for step in trajectory:
            if step.get("thought"):
                messages.append({"role": "assistant", "content": step["thought"]})
            if step.get("action"):
                messages.append({"role": "action", "content": step["action"]})
        return {"messages": messages}

    elif format == "qa":
        # Format: question-answer pairs
        return {
            "question": trajectory[0].get("observation", {}).get("goal", ""),
            "answer": " ".join([step.get("action", "") for step in trajectory]),
        }

    else:
        raise ValueError(f"Unknown format: {format}")


def extract_successful_trajectories(
    results: List[Dict[str, Any]], min_steps: int = 1, max_steps: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Filter and extract successful trajectories from results.

    Args:
        results: List of agent execution results
        min_steps: Minimum steps required
        max_steps: Maximum steps allowed

    Returns:
        List of successful trajectories
    """
    successful = []

    for result in results:
        if not result.get("success", False):
            continue

        trajectory = result.get("trajectory", [])
        num_steps = len(trajectory)

        if num_steps < min_steps:
            continue

        if max_steps and num_steps > max_steps:
            continue

        successful.append(result)

    return successful


def compute_trajectory_statistics(trajectories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute statistics from trajectories.

    Args:
        trajectories: List of trajectories

    Returns:
        Statistics dictionary
    """
    if not trajectories:
        return {}

    total_steps = [len(t.get("trajectory", [])) for t in trajectories]
    success_count = sum(1 for t in trajectories if t.get("success", False))

    stats = {
        "total_trajectories": len(trajectories),
        "successful_trajectories": success_count,
        "success_rate": success_count / len(trajectories) if trajectories else 0,
        "avg_steps": sum(total_steps) / len(total_steps) if total_steps else 0,
        "min_steps": min(total_steps) if total_steps else 0,
        "max_steps": max(total_steps) if total_steps else 0,
    }

    # Compute cost if available
    total_cost = sum(t.get("total_cost", 0) for t in trajectories)
    if total_cost > 0:
        stats["total_cost"] = total_cost
        stats["avg_cost_per_trajectory"] = total_cost / len(trajectories)

    return stats


def merge_sygra_agentlab_configs(
    sygra_config: Dict[str, Any], agentlab_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge SyGra and AgentLab configurations.

    Args:
        sygra_config: SyGra workflow configuration
        agentlab_config: AgentLab agent/experiment configuration

    Returns:
        Merged configuration
    """
    merged = {
        "sygra": sygra_config,
        "agentlab": agentlab_config,
        "integration": {
            "version": "1.0",
            "framework": "sygra-agentlab-hybrid",
        },
    }

    return merged


def validate_integration_config(config: Dict[str, Any]) -> bool:
    """
    Validate integration configuration.

    Args:
        config: Configuration to validate

    Returns:
        True if valid, raises ValueError otherwise
    """
    required_keys = ["node_type"]

    if config.get("node_type") == "agentlab_agent":
        required_keys.extend(["agent_args"])

    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required key: {key}")

    return True


def create_agentlab_agent_from_dict(config: Dict[str, Any]) -> Optional["AgentArgs"]:
    """
    Create AgentLab agent from dictionary configuration.

    Args:
        config: Agent configuration dictionary

    Returns:
        AgentArgs instance or None
    """
    if not AGENTLAB_AVAILABLE:
        logger.warning("AgentLab not available")
        return None

    # This is a simplified version - extend based on needs
    agent_type = config.get("agent_type", "generic")

    if agent_type == "generic":
        from agentlab.agents.generic_agent import GenericAgentArgs  # type: ignore[import-untyped]
        from agentlab.llm.llm_configs import CHAT_MODEL_ARGS_DICT  # type: ignore[import-untyped]

        model_name = config.get("model_name", "openai/gpt-4o-mini")
        chat_model_args = CHAT_MODEL_ARGS_DICT.get(model_name)

        return GenericAgentArgs(
            chat_model_args=chat_model_args,
            flags=config.get("flags"),
            max_retry=config.get("max_retry", 4),
        )

    return None


def export_trajectories_to_dataset(
    trajectories: List[Dict[str, Any]],
    output_file: str,
    format: str = "instruction_following",
    filter_successful: bool = True,
):
    """
    Export trajectories to training dataset file.

    Args:
        trajectories: List of trajectories
        output_file: Output file path
        format: Training data format
        filter_successful: Only include successful trajectories
    """
    if filter_successful:
        trajectories = extract_successful_trajectories(trajectories)

    dataset = []
    for traj in trajectories:
        if "trajectory" in traj:
            example = convert_trajectory_to_training_format(traj["trajectory"], format)
            dataset.append(example)

    # Save to file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix == ".jsonl":
        with open(output_path, "w") as f:
            for example in dataset:
                f.write(json.dumps(example) + "\n")
    elif output_path.suffix == ".json":
        with open(output_path, "w") as f:
            json.dump(dataset, f, indent=2)
    else:
        raise ValueError(f"Unsupported file format: {output_path.suffix}")

    logger.info(f"Exported {len(dataset)} examples to {output_file}")


def compare_agent_performance(
    results_1: List[Dict[str, Any]],
    results_2: List[Dict[str, Any]],
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Compare performance between two sets of agent results.

    Args:
        results_1: First set of results
        results_2: Second set of results
        labels: Labels for the two sets

    Returns:
        Comparison statistics
    """
    if labels is None:
        labels = ["Agent 1", "Agent 2"]

    stats_1 = compute_trajectory_statistics(results_1)
    stats_2 = compute_trajectory_statistics(results_2)

    comparison = {
        labels[0]: stats_1,
        labels[1]: stats_2,
        "difference": {
            "success_rate": stats_2.get("success_rate", 0) - stats_1.get("success_rate", 0),
            "avg_steps": stats_2.get("avg_steps", 0) - stats_1.get("avg_steps", 0),
        },
    }

    return comparison
