# Evaluation Tasks (`tasks/eval`)

SyGra is a graph-oriented workflow framework for synthetic data generation **and evaluation**. Evaluation tasks are implemented as standard SyGra tasks (a `graph_config.yaml` + optional Python utilities) and produce:

- **Per-record outputs** (including unit metric results)
- **Aggregated evaluation reports** (aggregator metrics computed after the run)

## Quick start

Run an eval task through `main.py`:

```bash
uv run python main.py --task tasks.eval.question_answering.simpleqa --num_records 50
```

You can also omit the `tasks.` prefix:

```bash
uv run python main.py --task eval/classification/simpleqa --num_records 50
```

To control where artifacts are written:

```bash
uv run python main.py \
  --task tasks.eval.question_answering.simpleqa \
  --num_records 50 \
  --output_dir /abs/path/to/my_eval_outputs
```

## Concepts

SyGra evaluation is organized into two metric layers:

- **Unit metrics**
  - Per-record metrics computed *inside the graph*.
  - Stored back into the record/state (e.g., `exact_match_result`).
- **Aggregator metrics**
  - Dataset-level metrics computed *after the run* by aggregating unit metric outputs (e.g., accuracy, precision, recall, F1).
  - Produced by graph-level post-processing.

### Key files and registries

- **Generic eval utilities**: `tasks/eval/utils.py`
  - `UnitMetrics`: reusable `lambda` node implementation that computes unit metrics via `UnitMetricRegistry`.
  - `MetricCollatorPostProcessor`: reusable graph post-processor that computes aggregator metrics via `AggregatorMetricRegistry`.
- **Unit metric registry**: `sygra.core.eval.metrics.unit_metrics.unit_metric_registry.UnitMetricRegistry`
- **Aggregator metric registry**: `sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry.AggregatorMetricRegistry`

## Evaluation lifecycle

At a high level, an eval task runs as follows:

1. **Load task config**
   - Task configs live under `tasks/<task_name>/graph_config.yaml`.

2. **Load dataset**
   - Configured in `data_config.source`.
   - Common sources: HuggingFace (`type: hf`) or local disk.

3. **Execute the graph per record**
   - Nodes (LLM / lambda / sampler / etc.) run and update the `SygraState`.

4. **Compute unit metrics per record (inside the graph)**
   - Typically implemented as a `lambda` node.
   - Example used in eval tasks: `tasks.eval.utils.UnitMetrics`
   - Unit metric outputs are stored back into the record (e.g., `exact_match_result`).

5. **Write the per-record output file**
   - The framework writes a file named like `output_*.json` or `output_*.jsonl`.

6. **Compute aggregator metrics (graph post-processing)**
   - Configured via `graph_post_process` in the task YAML.
   - Framework reads the output file back and runs each configured graph post processor.
   - For eval tasks this is commonly: `tasks.eval.utils.MetricCollatorPostProcessor`.

7. **Write aggregator results file(s)**
   - For each post processor, SyGra writes a new file by replacing the `output` prefix in the filename with the post-processor class name.
   - Example: `output_2026-01-27_12-31-46.json` -> `MetricCollatorPostProcessor_2026-01-27_12-31-46.json`

## Using `tasks/eval/utils.py` in eval graphs

### Unit metrics (generic `UnitMetrics` lambda)

`tasks.eval.utils.UnitMetrics` is a generic lambda node that:

- Reads `golden_key` and `predicted_key` from the graph state.
- Iterates the configured `unit_metrics_map`.
- Instantiates metrics via `UnitMetricRegistry.get_metric(name, **params)`.
- Writes per-record results back into state as `<metric_name>_result`.

This is why most eval graphs:

- Add a `unit_metrics` lambda node.
- Include the corresponding `*_result` field in `output_config.output_map`.

### Aggregator metrics (generic `MetricCollatorPostProcessor`)

`tasks.eval.utils.MetricCollatorPostProcessor` is a generic graph-level post-processor that:

- Loads the run output file (`output_*.json`).
- For each configured entry in `aggregator_metrics_map`:
  - Selects the unit-metric column specified by `unit_metrics_results` (commonly `exact_match_result`).
  - Converts dicts to `UnitMetricResult` objects.
  - Instantiates the aggregator metric via `AggregatorMetricRegistry.get_metric(name, **params)`.
  - Computes the aggregated metric over all rows.

It writes a new JSON file named by replacing `output` in the filename with `MetricCollatorPostProcessor`.

## Outputs and artifacts

An eval run typically produces **two primary artifacts**:

### 1) Per-record output (includes unit metric results)

This is the main run output file written during graph execution (typically named `output_*.json` or `output_*.jsonl`).

You’ll find, per record:

- The original fields you mapped in `output_config.output_map`
- The model outputs (e.g., `predicted_answer`)
- **Unit metric result fields** (e.g., `exact_match_result`)

In the eval examples, `UnitMetrics` stores metric results in the state using:

- `state[unit_metric_name + "_result"] = results[0].to_dict()`

So if you configure `exact_match`, you’ll typically see:

- `exact_match_result`: a dict representing a `UnitMetricResult`

### 2) Aggregated evaluation report (aggregator metrics)

After the run completes, SyGra runs graph post-processors and writes additional JSON files.

For eval tasks using `tasks.eval.utils.MetricCollatorPostProcessor`, the report output is:

- `MetricCollatorPostProcessor_*.json`

This file contains a list with a single “report object”:

- `evaluation_summary`: counts/status
- `results`: a dict keyed by aggregator metric name (e.g., `accuracy`, `f1_score`)

## `MetricCollatorPostProcessor_*.json` file format

The file is a JSON list with a single report object:

```json
[
  {
    "evaluation_summary": {
      "total_records": 1000,
      "status": "success"
    },
    "results": {
      "accuracy": {
        "accuracy": 0.689
      },
      "precision": {
        "average_precision": 0.54,
        "precision_per_class": {
          "Music": 0.91,
          "Politics": 0.92,
          "Other": 0.45
        }
      },
      "recall": {
        "average_recall": 0.72,
        "recall_per_class": {
          "Music": 0.81,
          "Politics": 0.56,
          "Other": 0.72
        }
      },
      "f1_score": {
        "average_f1_score": 0.62,
        "f1_score_per_class": {
          "Music": 0.86,
          "Politics": 0.69,
          "Other": 0.55
        }
      }
    }
  }
]
```

Notes:

- **Top-level** is always a list (currently a single-item list).
- `evaluation_summary.status` is typically:
  - `success`
  - `no_data`
  - `fatal_error` (includes an `error` string)
- `results` keys match the `aggregator_metrics_map[].name` entries from your task config.
- `results` can contain **multiple aggregator metrics** in a single report (e.g., `accuracy`, `precision`, `recall`, `f1_score`, `pass_at_k`, etc.).
- For classification-style metrics, per-class fields (e.g., `precision_per_class`) are keyed by the task’s **label classes** (for example: `Music`, `Politics`, `Other`).
- The exact shape of each metric payload is **metric-dependent**:
  - Example: `accuracy` returns `{ "accuracy": <float> }`.
  - Example: `precision`/`recall`/`f1_score` may return both macro/average values and per-class breakdowns.

## Configuring metrics in `graph_config.yaml`

Eval tasks typically implement **unit metrics** as a lambda node and **aggregator metrics** as a graph post-processor.

### Unit metric example (per record)

From `tasks/eval/question_answering/simpleqa/graph_config.yaml`:

- `lambda: tasks.eval.utils.UnitMetrics`
- `unit_metrics_map`: list of unit metrics to run

Example:

```yaml
unit_metrics:
  node_type: lambda
  lambda: tasks.eval.utils.UnitMetrics
  golden_key: "answer"
  predicted_key: "predicted_answer"
  unit_metrics_map:
    - name: "exact_match"
      params:
        key: "text"
  output_keys:
    - exact_match_result
```

This writes `exact_match_result` into each output record.

### Aggregator metric example (dataset-level)

From `tasks/eval/classification/simpleqa/graph_config.yaml`:

```yaml
graph_post_process:
  - processor: tasks.eval.utils.MetricCollatorPostProcessor
    params:
      aggregator_metrics_map:
        - name: "accuracy"
          params:
            key: "text"
          unit_metrics_results:
            - "exact_match_result"
        - name: "f1_score"
          params:
            predicted_key: "text"
            golden_key: "text"
          unit_metrics_results:
            - "exact_match_result"
```

`MetricCollatorPostProcessor` will:

- Build a DataFrame from the run output (`output_*.json`)
- For each aggregator metric:
  - Pull the configured `unit_metrics_results` column (e.g., `exact_match_result`)
  - Convert dicts to `UnitMetricResult`
  - Instantiate the metric via `AggregatorMetricRegistry.get_metric(name, **params)`
  - Compute `metric.calculate(unit_metrics_results)`

## Programmatic access

- **Unit metric results**
  - Read the per-record output file and inspect fields ending in `_result` (e.g., `exact_match_result`).
  - These fields are dict-serialized `UnitMetricResult` values.
- **Aggregator metric results**
  - Read `MetricCollatorPostProcessor_*.json` and access:
    - `"results"` for metrics
    - `"evaluation_summary"` for counts/status

## Extending evaluation

### Add a new unit metric

- Implement a class under `sygra.core.eval.metrics.unit_metrics.*` inheriting the unit metric base.
- Decorate it with the unit metric decorator so it registers (see `UnitMetricRegistry` in `sygra.core.eval.metrics.unit_metrics.unit_metric_registry`).
- Reference it by name in your task YAML under `unit_metrics_map`.

### Add a new aggregator metric

- Implement a class under `sygra.core.eval.metrics.aggregator_metrics.*` inheriting the aggregator metric base.
- Decorate/register it (see `AggregatorMetricRegistry` in `sygra.core.eval.metrics.aggregator_metrics.aggregator_metric_registry`).
- Reference it by name in `graph_post_process` -> `MetricCollatorPostProcessor` -> `aggregator_metrics_map`.

### Add a new graph-level report

Graph post-processing is generic.

- Implement a `GraphPostProcessor` (`sygra.core.graph.graph_postprocessor.GraphPostProcessor`).
- Add it to `graph_post_process` in the task config.
- SyGra will automatically write a new file by replacing `output` with your post-processor class name.

## Troubleshooting / notes

- **Graph post-processing reads the full output into memory**
  - `GraphPostProcessor` runs after the graph completes and loads the entire output file. This is appropriate for evaluation, but avoid it for very large generations.
- **`MetricCollatorPostProcessor` expects the unit-metric field to exist**
  - If the configured `unit_metrics_results` field is missing (or not included in `output_config.output_map`), metrics will fail with a `KeyError` listing available columns.
- **JSON vs JSONL**
  - Current graph post-processing reads the output with `json.load(...)`, so it expects the run output to be a JSON array (`output_*.json`).
  - If your run produces `output_*.jsonl`, you will need to either:
    - Configure the task to write JSON (preferred for eval), or
    - Implement a custom graph post-processor that can stream/parse JSONL.

---

