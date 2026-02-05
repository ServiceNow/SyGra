# Flight Booking Scenario Generator (with Semantic Dedup)

This example task generates a diverse `scenarios_generated.json` for:

- `tasks/examples/flight_booking_conversations/scenarios.json`

It also runs **semantic deduplication** to remove near-duplicate scenarios.

## What it does

- Generates **one scenario per record** (set by `--num_records`).
- Each scenario includes:
  - `scenario_id`, `name`, `description`, `goal`, `outcome`, `failure_reason`
  - knowledge-article style `policy` (list of strings)
  - `coverage_tags`
  - `category`, `subcategory`, `weight`
  - `dedup_text` (used only for semantic dedup)
- Runs graph post-processing:
  1. `SemanticDedupPostProcessor` over `dedup_text`
  2. `ExportFlightBookingScenariosJsonPostProcessor` which writes the final list to the target `scenarios.json`

## How to run

From repo root:

```bash
python main.py --task tasks.examples.flight_booking_scenarios_generator --num_records 200 --batch_size 25 --checkpoint_interval 100
```

## Outputs

- Raw generation output (per-record):
  - `tasks/examples/flight_booking_scenarios_generator/output_<timestamp>.json`
- Semantic dedup report:
  - `tasks/examples/flight_booking_scenarios_generator/semantic_dedup_report_<timestamp>.json`
- Deduped output file:
  - `tasks/examples/flight_booking_scenarios_generator/SemanticDedupPostProcessor_<timestamp>.json`
- Exported target file:
  - `tasks/examples/flight_booking_conversations/scenarios_generated.json`

## Notes / Tuning

- Dedup threshold is controlled in `graph_config.yaml` under `graph_post_process`.
  - `similarity_threshold: 0.90` is a good starting point.
  - Lower it (e.g. `0.86`) to remove more near-duplicates.
  - Raise it (e.g. `0.94`) to keep more variants.
- If you want "capture all variations", increase `--num_records`.
  - Dedup will keep only distinct ones.
