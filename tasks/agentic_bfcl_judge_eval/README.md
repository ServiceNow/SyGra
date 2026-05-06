# AgentJudgeBench

**AgentJudgeBench: A Multi-Difficulty Benchmark for Evaluating LLM Judges on Agentic Tool-Calling**

SyGra pipeline for reproducing the experiments in the paper. Measures how well LLM judges align with a deterministic programmatic judge when scoring agentic tool-calling plans across 3 difficulty tiers, 6 DAG topologies, 5 generators, 6 judges, and with/without ground truth.

- **Dataset**: [ServiceNow-AI/AgentJudgeBench](https://huggingface.co/datasets/ServiceNow-AI/AgentJudgeBench) on HuggingFace
- **Scale**: 3,808 records × 3 difficulties × 5 generators × 6 judges × 2 conditions = 321,648 evaluations
- **Generators evaluated**: SmolLM3-3B, Llama-3.1-8B-Instruct, Qwen3-32B, Llama-3.3-70B-Instruct, GPT-5.4
- **Judges evaluated**: GPT-OSS-20B, QwQ-32B, GPT-OSS-120B, Claude Sonnet 4.5, Gemini 2.5 Pro, GPT-5.4

---

## Directory contents

```
agentic_bfcl_judge_eval/
├── task_executor.py                 # Programmatic judge + LLM-judge pre/post processors
├── run_generate.py                  # CLI: produce tool-call predictions from a generator
├── run_judge.py                     # CLI: run LLM + programmatic judges on predictions
├── prepare_difficulty_inputs.py     # Splits HF dataset (columns: query/query_medium/query_hard) into 3 JSONLs
├── prepare_corrupted_gt.py          # Builds C3 corrupted-GT input by deranging expected_responses within each dag_type
├── analyze_results.py               # Aggregates per-record JSONLs into per-cell mean alignment (Fig 3 / Tables 1, 3)
│
├── graph_config_generate_only.yaml  # Pipeline: generator inference only
├── graph_config.yaml                # Pipeline: judge with-GT + without-GT (1.0 default) — main results
├── graph_config_nogt_05.yaml        # Pipeline: C2 ablation — without-GT with 0.5 default
├── graph_config_corrupted_gt.yaml   # Pipeline: C3 control — judge sees corrupted GT
└── graph_config_freeform.yaml       # Pipeline: RQ6 ablation — minimal free-form prompt
```

### Per-file purpose

| File | Purpose |
|---|---|
| `task_executor.py` | Implements `ProgrammaticJudge` (Eqs 1–3 in the paper), `ComputeLLMVsProgrammaticAccuracy*` (Eq 4), and the pre/post processors that serialize state and parse judge responses. |
| `run_generate.py` | Loads `graph_config_generate_only.yaml`, patches in the generator model name and the per-difficulty input file, runs SyGra to produce `<generator>/<difficulty>.jsonl`. |
| `run_judge.py` | Loads a judge config (defaults to `graph_config.yaml`, override with `--config`), patches in the judge model and input path, runs SyGra to produce `<generator>/judged_by_<judge>/<difficulty>.jsonl`. |
| `prepare_difficulty_inputs.py` | One-time data prep. Reads the HF record (which has `user_message`, `query_medium`, `query_hard` columns) and emits `input_easy.jsonl` / `input_medium.jsonl` / `input_hard.jsonl` with `user_message` set to the per-difficulty query. |
| `prepare_corrupted_gt.py` | One-time prep for C3. For each generator-output JSONL, replaces each record's `expected_responses` with the GT from a different record of the same `dag_type` (random derangement). Original GT is preserved as `true_expected_responses` so the programmatic judge still has the real reference. |
| `analyze_results.py` | Walks the run output directories, computes mean alignment per `(generator, judge, difficulty, condition)` cell, and writes a CSV that maps directly to the paper's Fig 3 / Table 1 / Table 3 / Fig 7 cell values. |
| `graph_config.yaml` | Main judge graph: `judge_tool_calls` (with-GT) → `judge_tool_calls_answer_only` (without-GT) → `judge_programmatic` → two alignment lambdas. Default for all main-table results in the paper. |
| `graph_config_generate_only.yaml` | Single-node generator graph used by `run_generate.py`. |
| `graph_config_nogt_05.yaml` | Same graph as `graph_config.yaml`, but the without-GT prompt uses 0.5-default rubric. C2 ablation (Table 3). |
| `graph_config_corrupted_gt.yaml` | Same graph as `graph_config.yaml`, but the with-GT prompt receives `corrupted_expected_responses` instead of `expected_responses`. C3 anchoring control. |
| `graph_config_freeform.yaml` | Same graph as `graph_config.yaml`, but uses minimal free-form judge prompts instead of the structured rubric. RQ6 ablation (Fig 7). |

---

## Pipeline

```
generate_tool_calls          (run_generate.py)
    ↓
judge_tool_calls             (LLM judge, with GT)
judge_tool_calls_answer_only (LLM judge, without GT)
judge_programmatic           (deterministic reference, Eqs 1–3)
calculate_judge_accuracy             (alignment, with-GT)
calculate_answer_only_judge_accuracy (alignment, without-GT)
```

### Metrics (4 scores, each in {0, 0.5, 1})

| Metric | What it measures |
|---|---|
| `tool_selection_accuracy` | Are the right tool names selected? |
| `parameter_structure_accuracy` | Are parameter *names* and dict structure correct? (values are not checked) |
| `sequence_accuracy` | Are tools called in the right order? |
| `query_coverage_accuracy` | Does the plan address all parts of the user request? |

Alignment per metric: `1 − |programmatic − llm|`. Aggregated to `overall_llm_alignment_percentage` per record, then averaged across records to produce the cell values in Fig 3 and Table 1.

### Experimental conditions

| Label | Graph config | Paper section |
|---|---|---|
| with-GT, 1.0-default | `graph_config.yaml` (`judge_tool_calls` node) | Main results, Fig 3 |
| without-GT, 1.0-default | `graph_config.yaml` (`judge_tool_calls_answer_only` node) | Main results, Fig 3 |
| C2: without-GT, 0.5-default | `graph_config_nogt_05.yaml` | §4.2 C2 ablation, Table 3 |
| C3: corrupted-GT | `graph_config_corrupted_gt.yaml` | §4.2 C3 control, Table 1 |
| RQ6: free-form prompt | `graph_config_freeform.yaml` | RQ6, Fig 7 |

Temperature (RQ4), judge scale (RQ5), CoT (RQ7), and small-judge (H1) sweeps reuse `graph_config.yaml` with different `--judge_model` values or model parameters; no separate config is needed.

---

## Configure models (required before any run)

Every model used by these pipelines (5 generators + 6 judges, plus any judge variants for RQ4–RQ7 / H1) must be defined as an entry in `sygra/config/models.yaml`. Each entry expects matching `SYGRA_<MODEL_NAME>_URL` and `SYGRA_<MODEL_NAME>_TOKEN` values in `.env`.

All `model.name` fields in the graph configs are set to a single placeholder `smollm3`. Either replace this with your own entry key in each YAML, or rely on the runtime overrides — `run_generate.py --model <key>` and `run_judge.py --judge_model <key>` overwrite the YAML default at runtime, so for sweep-style reproduction you only need each `<key>` you pass on the CLI to exist in `models.yaml`.

---

## Reproduction order

All commands run from the SyGra repo root.

**Keep conditions separate.** `run_judge.py` writes to `<generator>/judged_by_<judge>/` regardless of which graph config you use, so C1, C2, C3, and free-form runs for the same `(generator, judge, difficulty)` will land in the same directory (distinguished only by run timestamps). For each invocation in Steps 4–6 below, pass `--run_name c2_<judge>_<difficulty>` (or `c3_…`, `freeform_…`) — or set `--output_dir` to a per-condition directory — so the JSONLs from different conditions don't get conflated during analysis.

### Step 1: Prepare per-difficulty inputs

Download the HF dataset to a local JSONL (each row carries `user_message`, `query_medium`, `query_hard`), then split:

```bash
python tasks/agentic_bfcl_judge_eval/prepare_difficulty_inputs.py \
    --source <path_to_hf_jsonl>
# produces:
#   tasks/agentic_bfcl_judge_eval/input_easy.jsonl
#   tasks/agentic_bfcl_judge_eval/input_medium.jsonl
#   tasks/agentic_bfcl_judge_eval/input_hard.jsonl
```

### Step 2: Run generators

For each (generator, difficulty) cell. Five generators in the paper: `smollm3_3b`, `llama_3_1_8b_instruct`, `qwen3_32b`, `llama_3_3_70b_instruct`, `gpt_5_4`.

```bash
python tasks/agentic_bfcl_judge_eval/run_generate.py \
    --model <generator> --difficulty <easy|medium|hard>
# produces tasks/agentic_bfcl_judge_eval/<generator>/<difficulty>.jsonl
```

### Step 3: Run the main judge pipeline (Fig 3 / main results)

For each (generator, judge, difficulty) cell. Six judges: `gpt_oss_20b`, `qwq_32b`, `gpt_oss_120b`, `claude_sonnet_45`, `gemini_2_5_pro`, `gpt_5_4`.

```bash
python tasks/agentic_bfcl_judge_eval/run_judge.py \
    --generator <generator> --judge_model <judge> --difficulty <easy|medium|hard>
# produces tasks/agentic_bfcl_judge_eval/<generator>/judged_by_<judge>/<difficulty>.jsonl
```

This single invocation produces both with-GT and without-GT alignments per record (`overall_llm_alignment_percentage` and `overall_llm_alignment_percentage_no_gt`).

### Step 4 (C2 ablation, Table 3): without-GT 0.5-default

Same grid as Step 3, but with the recalibrated prompt:

```bash
python tasks/agentic_bfcl_judge_eval/run_judge.py \
    --generator <generator> --judge_model <judge> --difficulty <easy|medium|hard> \
    --config graph_config_nogt_05.yaml
```

### Step 5 (C3 control, Table 1): corrupted GT

First, derange GT within each `dag_type` for the chosen generator:

```bash
python tasks/agentic_bfcl_judge_eval/prepare_corrupted_gt.py \
    --generator <generator>
# produces tasks/agentic_bfcl_judge_eval/<generator>/<difficulty>_corrupted_gt.jsonl
```

Then judge with the corrupted-GT graph:

```bash
python tasks/agentic_bfcl_judge_eval/run_judge.py \
    --generator <generator> --judge_model <judge> --difficulty <easy|medium|hard> \
    --config graph_config_corrupted_gt.yaml \
    --input tasks/agentic_bfcl_judge_eval/<generator>/<difficulty>_corrupted_gt.jsonl
```

### Step 6 (RQ6, Fig 7): free-form prompt

```bash
python tasks/agentic_bfcl_judge_eval/run_judge.py \
    --generator <generator> --judge_model <judge> --difficulty <easy|medium|hard> \
    --config graph_config_freeform.yaml
```

### Step 7 (RQ4, RQ5, RQ7, H1): model/parameter sweeps

These reuse `graph_config.yaml` (Step 3) with no new graph config. Each variant is a separate **`models.yaml` entry** that you pass via `--judge_model`:

- **RQ4 (temperature, Fig 5)**: define three entries (e.g. `qwen3_32b_t0.3`, `qwen3_32b_t0.7`, `qwen3_32b_t1.0`) — each one identical except for the `temperature` field — then run Step 3 once per entry.
- **RQ5 (judge scale, Fig 6)**: simply vary `--judge_model` across the existing six judge entries.
- **RQ7 (CoT, Fig 8)**: define a thinking-off variant entry (e.g. `qwq_32b_no_thinking`) alongside the standard `qwq_32b`, run Step 3 with each.
- **H1 (small judge)**: add a small-model entry (e.g. `qwen3_1_7b`) and run Step 3 with it.

### Step 8: Aggregate to per-cell numbers

Once Steps 3–7 are done, aggregate the per-record JSONLs into the cell values reported in Fig 3, Table 1, Table 3, and Fig 7:

```bash
python tasks/agentic_bfcl_judge_eval/analyze_results.py --output results.csv
```

The script walks `<generator>/judged_by_<judge>/<run_name>/*.jsonl`, infers `condition` from the `--run_name` prefix you used (`c1_…`, `c2_…`, `c3_…`, `freeform_…`), and writes one row per `(generator, judge, difficulty, condition)` cell with `mean_alignment_with_gt` and `mean_alignment_without_gt`. Filter the CSV to reproduce specific paper figures:

- **Fig 3 / main results**: `condition == c1_main`
- **Table 1 cGT column**: `condition == c3_corrupted_gt`, `mean_alignment_with_gt`
- **Table 3 0.5-default**: `condition == c2_nogt_05`, `mean_alignment_without_gt`
- **Fig 7 free-form vs structured**: compare `c1_main` (`mean_alignment_with_gt`) with `rq6_freeform` for the same `(generator, judge, difficulty)`

Bootstrap CIs (Appendix E) and inter-judge κ (Table 2) are not included; both operate on the same per-record JSONLs and can be computed with standard `scipy`.

---

## Output fields per record

| Field | Description |
|---|---|
| `id` | Record identifier |
| `dag_type` | DAG topology (linear, fan-out, fan-in, diamond, optional-enrichment, loop-like) |
| `user_message` | Natural-language user query (per difficulty) |
| `generated_tool_calls` | Tool calls produced by the generator |
| `judge_response` | LLM judge scores, with-GT condition |
| `judge_response_no_gt` | LLM judge scores, without-GT condition |
| `programmatic_judge_response` | Deterministic reference scores (Eqs 1–3) |
| `per_metric_comparison` | Per-metric alignment vs programmatic (with-GT) |
| `overall_llm_alignment_percentage` | Aggregate alignment % (with-GT) |
| `per_metric_comparison_no_gt` | Per-metric alignment vs programmatic (without-GT) |
| `overall_llm_alignment_percentage_no_gt` | Aggregate alignment % (without-GT) |
