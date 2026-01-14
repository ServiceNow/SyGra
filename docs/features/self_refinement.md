# Self Refinement

> **Iterative candidate improvement with judge scores and a reflection trajectory (as a reusable subgraph)**

## Overview

Self Refinement is a workflow pattern where SyGra:

- Generates a candidate output for a given input prompt
- Uses a separate *judge* step to score and critique the candidate
- Optionally refines the candidate using the critique
- Repeats until the candidate is accepted (meets a score threshold) or a maximum number of iterations is reached

This feature is implemented as a reusable **subgraph recipe**: `sygra.recipes.self_refinement`.

---

## What you get

When used in a task, the self-refinement subgraph produces:

- `candidate`: the final accepted (or last) candidate
- `self_refine_judge`: judge output containing score, pass/fail, critique, and raw parsed output
- `reflection_trajectory`: an ordered list capturing each iteration’s candidate + judge result (useful for training / analysis)

### Example output shape

```json
{
  "candidate": "...final candidate...",
  "self_refine_judge": {
    "score": 4,
    "is_good": true,
    "critique": "...",
    "raw": {"score": 4, "is_good": true, "critique": "..."}
  },
  "reflection_trajectory": [
    {
      "iteration": 0,
      "candidate_key": "candidate",
      "candidate": "...candidate at iteration 0...",
      "judge": {"score": 2, "is_good": false, "critique": "...", "raw": {"...": "..."}}
    },
    {
      "iteration": 1,
      "candidate_key": "candidate",
      "candidate": "...candidate at iteration 1...",
      "judge": {"score": 4, "is_good": true, "critique": "...", "raw": {"...": "..."}}
    }
  ]
}
```

---

## How it works (recipe)

The recipe lives at:

- `sygra/recipes/self_refinement/graph_config.yaml`
- `sygra/recipes/self_refinement/task_executor.py`

### Nodes

- `init_self_refine` (lambda)
  - Initializes internal loop state and `reflection_trajectory`
  - Uses internal state keys prefixed with `_self_refine_*` to minimize collision risk in host graphs
- `generate_candidate` (llm)
  - Creates the initial candidate from `{prompt}`
- `judge_candidate` (llm + post-process)
  - Returns JSON with `{score, is_good, critique}`
  - Post-processor normalizes and writes:
    - `self_refine_judge`
    - `self_refine_is_good`
    - `self_refine_critique`
- `update_trajectory` (lambda)
  - Appends `{candidate, judge, iteration}` to `reflection_trajectory`
- `refine_candidate` (llm)
  - Produces an improved candidate using `{self_refine_critique}`

### Looping behavior

A conditional edge (`SelfRefinementLoopCondition`) ends the subgraph when either:

- The judge accepts (`self_refine_is_good == True`), or
- The maximum number of refinement iterations is reached

---

## Using self refinement as a subgraph in a task

A typical pattern is to add a `subgraph` node in your task and point it at the recipe.

The example task is located at:

- `tasks/examples/self_refinement/graph_config.yaml`
- `tasks/examples/self_refinement/input.json`

### Example task config (high level)

In `tasks/examples/self_refinement/graph_config.yaml`, the task defines a single node:

- `self_refine`:
  - `node_type: subgraph`
  - `subgraph: sygra.recipes.self_refinement`
  - Overrides recipe node config via `node_config_map` (e.g., model selection, temperatures, and loop parameters)

It also maps the key outputs into the final dataset using `output_config.output_map`:

- `candidate` from `candidate`
- `self_refine_judge` from `self_refine_judge`
- `reflection_trajectory` from `reflection_trajectory`

---

## Running the example

From the repo root:

```bash
python main.py --task examples.self_refinement --num_records 2
```

Artifacts:

- Output records are written under `tasks/examples/self_refinement/` (typically `output_<timestamp>.json`)
- Metadata is written under `tasks/examples/self_refinement/metadata/` (typically `metadata_tasks_examples_self_refinement_<timestamp>.json`)

The metadata file includes per-node execution statistics (e.g., `self_refine.generate_candidate`, `self_refine.judge_candidate`) and aggregate token/cost summaries.

---

## Customization

You can tune behavior either in the recipe or (recommended) from the task via `node_config_map`:

- `init_self_refine.params.max_iterations`
- `init_self_refine.params.score_threshold`
- `judge_candidate.model.parameters.temperature` (usually `0` for consistent scoring)
- Prompts for `generate_candidate`, `judge_candidate`, and `refine_candidate`

If you need the recipe to write outputs under different keys (to avoid collisions in a larger host graph), you can override:

- `update_trajectory.params.candidate_key`
- `update_trajectory.params.judge_key`
