# AgentJudgeBench

**AgentJudgeBench: A Multi-Difficulty Benchmark for Evaluating LLM Judges on Agentic Tool-Calling**

This directory contains the SyGra pipeline implementation for AgentJudgeBench — a benchmark that measures how well LLM judges align with a deterministic programmatic judge when scoring agentic tool-calling plans across 3 difficulty tiers.

- **Dataset**: [ServiceNow-AI/AgentJudgeBench](https://huggingface.co/datasets/ServiceNow-AI/AgentJudgeBench) on HuggingFace
- **Paper**: See `AgentJudgeBench__A_Multi_Difficulty_Benchmark_for_Evaluating_LLM_Judges_on_Agentic_Tool_Calling/`
- **Scale**: 3,808 records × 3 difficulties × 5 generators × 6 judges × 2 conditions = 321,648 evaluations

---

## Directory structure

```
agentic_bfcl_judge_eval/
├── task_executor.py              # All processors and judges (pre/post/lambda)
├── run_judge.py                  # CLI: run LLM judge sweep over a generator's outputs
├── run_generate.py               # CLI: run generator inference to produce tool calls
├── prepare_difficulty_inputs.py  # Splits HF dataset into easy/medium/hard JSONL files
├── prepare_corrupted_gt.py       # Builds corrupted-GT inputs for C3 control condition
├── audit_and_launch.py           # Checks sweep completeness, launches missing runs
├── rerun_nulls.py                # Re-runs records that returned null judge responses
├── zero_cost_analysis.py         # Computes alignment stats without new API calls
├── rai_patch.py                  # Patches records that hit RAI refusals during judging
│
├── graph_config.yaml             # Main pipeline: generate + judge (with-GT & no-GT)
├── graph_config_nogt_05.yaml     # C2 ablation: no-GT with 0.5 default scoring
├── graph_config_freeform.yaml    # C3 ablation: minimal freeform prompt
├── graph_config_corrupted_gt.yaml# C3 control: judge sees corrupted ground truth
├── graph_config_generate_only.yaml  # Generation-only (no judging)
├── graph_config_judge_only.yaml     # Judging-only (pre-generated tool calls)
│
├── prompts/                      # Standalone prompt files (extracted from configs)
│   ├── judge_with_gt.txt         # C1 with-GT prompt
│   ├── judge_no_gt.txt           # C1 no-GT prompt (1.0 default)
│   ├── judge_no_gt_0.5default.txt# C2 no-GT prompt (0.5 default)
│   ├── judge_freeform.txt        # Freeform minimal prompt
│   └── README.md                 # Prompt variable reference
│
├── run_judge_sweep.sh            # Sweep: all judges × all difficulties for one generator
├── run_judge_sweep_parallel.sh   # Parallelized version of above
├── run_c1_judge_sweep.sh         # C1 (standard) sweep
├── run_c2_nogt05_sweep.sh        # C2 ablation sweep
├── run_ablations.sh              # Full ablation suite (C1 + C2 + freeform)
├── run_h1_qwen3_1_7b_sweep.sh    # H1: small-judge sweep (Qwen3-1.7B)
├── run_judge_for_one.sh          # Single-judge single-difficulty run
├── run_judge_rerun_sweep.sh      # Re-run sweep for failed/null records
├── run_judge_rerun_worker.sh     # Worker script for rerun sweep
├── watch_sweep.sh                # Monitor live sweep progress
├── seed_data_hf.ipynb            # Notebook: download + prepare data from HuggingFace
│
└── AgentJudgeBench__A_Multi_Difficulty_Benchmark.../
    └── [paper LaTeX source]
```

---

## Evaluation pipeline

For each record the graph executes five steps:

```
(optional) generate_tool_calls
    → judge_tool_calls          (LLM judge WITH ground truth)
    → judge_tool_calls_answer_only  (LLM judge WITHOUT ground truth)
    → judge_programmatic        (deterministic reference scorer)
    → calculate_judge_accuracy
    → calculate_answer_only_judge_accuracy
```

### Metrics (4 scores, each ∈ {0, 0.5, 1})

| Metric | What it measures |
|---|---|
| `tool_selection_accuracy` | Are the right tool names selected? |
| `parameter_structure_accuracy` | Are parameter *names* and dict structure correct? (values are NOT checked) |
| `sequence_accuracy` | Are tools called in the right order? |
| `query_coverage_accuracy` | Does the plan address all parts of the user request? |

Alignment is computed as `1 - |programmatic_score - llm_score|` per metric, averaged to yield `overall_llm_alignment_percentage`.

---

## Experimental conditions

| Condition | Config | Description |
|---|---|---|
| C1 with-GT | `graph_config.yaml` (`judge_tool_calls` node) | LLM judge sees ground-truth tool calls |
| C1 no-GT | `graph_config.yaml` (`judge_tool_calls_answer_only` node) | LLM judge sees query + tools only |
| C2 | `graph_config_nogt_05.yaml` | No-GT with 0.5 default score (tests whether optimistic default inflates C1 no-GT) |
| C3 freeform | `graph_config_freeform.yaml` | Minimal prompt ablation |
| C3 corrupted-GT | `graph_config_corrupted_gt.yaml` | Judge receives shuffled/corrupted ground truth |

---

## Setup

### Prerequisites

```bash
# From SyGra root
pip install -e .
cp .env.example .env  # fill in model API keys (see sygra/config/models.yaml for key names)
```

Model keys follow the pattern `SYGRA_<MODEL_NAME>_URL` / `SYGRA_<MODEL_NAME>_TOKEN` in `.env`.
See `sygra/config/models.yaml` for the full list of model entries used in this benchmark.

### Prepare data

```bash
# Download from HuggingFace and split by difficulty
cd tasks/examples/agentic_bfcl_judge_eval
python prepare_difficulty_inputs.py
# → produces input_easy.jsonl, input_medium.jsonl, input_hard.jsonl
```

---

## How to run

### Run the full judge sweep (one generator, all difficulties, all judges)

```bash
bash run_judge_sweep.sh <generator_name>
# e.g. bash run_judge_sweep.sh llama_3_3_70b_instruct
```

### Run a single judge on a single difficulty

```bash
bash run_judge_for_one.sh <generator> <difficulty> <judge_model>
# e.g. bash run_judge_for_one.sh llama_3_3_70b_instruct easy claude_large
```

### Run via SyGra directly

```bash
# From SyGra root
python main.py \
  --config tasks/examples/agentic_bfcl_judge_eval/graph_config.yaml \
  --data_path tasks/examples/agentic_bfcl_judge_eval/llama_3_3_70b_instruct/easy.jsonl \
  --model_name claude_large \
  --batch_size 25 \
  --run_name claude_large_easy
```

### Run C2 ablation

```bash
bash run_c2_nogt05_sweep.sh <generator_name>
```

### Re-run null/failed records

```bash
python rerun_nulls.py --generator llama_3_3_70b_instruct --difficulty easy --judge claude_large
```

---

## Output fields

| Field | Description |
|---|---|
| `id` | Record identifier |
| `dag_type` | DAG topology (linear, fan-out, fan-in, diamond, optional-enrichment, loop-like) |
| `user_message` | Natural language user query |
| `generated_tool_calls` | Tool calls from the candidate generator model |
| `judge_response` | LLM judge scores (with ground truth) |
| `judge_response_no_gt` | LLM judge scores (without ground truth) |
| `programmatic_judge_response` | Deterministic reference scores |
| `per_metric_comparison` | Per-metric alignment vs programmatic (with-GT judge) |
| `overall_llm_alignment_percentage` | Aggregate alignment % (with-GT judge) |
| `per_metric_comparison_no_gt` | Per-metric alignment (no-GT judge) |
| `overall_llm_alignment_percentage_no_gt` | Aggregate alignment % (no-GT judge) |

---

## Generators evaluated

5 generator models (produce the tool-call predictions being judged):

| Config key | Model |
|---|---|
| `llama_3_3_70b_instruct` | Llama-3.3-70B-Instruct |
| `llama_3_1_8b_instruct` | Llama-3.1-8B-Instruct |
| `qwen3_32b` | Qwen3-32B |
| `smollm3_3b` | SmolLM3-3B |
| `gpt_5_4` | GPT-5-4 |

## Judges evaluated

6 LLM judge models (score the generated tool calls):

See `sygra/config/models.yaml` for version strings and endpoint configuration.
Model entries use `claude_large`, `gemini_flash`, `qwq_32b`, etc. as config keys.
