# Semantic Deduplication

> **Remove near-duplicate generated records using embedding-based similarity as a graph post-processor**

## Overview

SyGra supports semantic deduplication as a **graph post-processing** step via:

`sygra.core.graph.graph_postprocessor.SemanticDedupPostProcessor`

It embeds a configured output field (e.g., `answer`, `description`) and removes items whose **cosine similarity** is above a configurable threshold.

This is useful when:

- Your generation workflow tends to repeat the same/very similar answers.
- You are generating multiple records and want to reduce redundant samples.
- You want a report of duplicate pairs to inspect or tune dedup behavior.

## Quick Start

Add the post processor under `graph_post_process` in your task `graph_config.yaml`.

Example (dedup over `answer`, see `tasks/examples/semantic_dedup/graph_config.yaml`):

```yaml
graph_post_process:
  - processor: sygra.core.graph.graph_postprocessor.SemanticDedupPostProcessor
    params:
      field: answer
      similarity_threshold: 0.92
      id_field: id
      embedding_backend: sentence_transformers
      embedding_model: all-MiniLM-L6-v2
      dedup_mode: nearest_neighbor
      vectorstore_k: 20
      keep: first
      max_pairs_in_report: 1000
```

Example (dedup over `description`, see `tasks/examples/semantic_dedup_no_seed/graph_config.yaml`):

```yaml
graph_post_process:
  - processor: sygra.core.graph.graph_postprocessor.SemanticDedupPostProcessor
    params:
      field: description
      similarity_threshold: 0.85
      id_field: id
      embedding_backend: sentence_transformers
      embedding_model: all-MiniLM-L6-v2
      keep: first
      max_pairs_in_report: 1000
```

## Configuration Reference

### Parameters

All parameters are provided under `params:`.

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `field` | string | Field to embed and compare for similarity. If the field value is a list/tuple, values are joined with newlines. | `text` |
| `similarity_threshold` | float | Cosine similarity threshold. Higher values drop fewer items. | `0.9` |
| `id_field` | string | Optional ID field used in the report for readability. If missing, indices are used. | `id` |
| `embedding_backend` | string | Embedding backend. Currently only `sentence_transformers` is supported. | `sentence_transformers` |
| `embedding_model` | string | SentenceTransformers model name to use for embeddings. | `all-MiniLM-L6-v2` |
| `report_filename` | string | Optional report JSON filename. If relative, it is written next to the graph output file. If omitted, the report name is derived from the output file name. | (derived) |
| `keep` | string | Which item to keep when duplicates are found: `first` or `last`. | `first` |
| `max_pairs_in_report` | int | Max number of duplicate pairs written to the report. | `2000` |
| `dedup_mode` | string | Dedup implementation to use: `nearest_neighbor` (default) or `all_pairs`. Any other value is unsupported and will raise an error. `nearest_neighbor` avoids building a full similarity matrix by only comparing against nearest neighbors / kept items. `all_pairs` computes a full similarity matrix (exact, but O(n^2)). | `nearest_neighbor` |
| `vectorstore_k` | int | Number of nearest neighbors to retrieve/consider when `dedup_mode: nearest_neighbor`. | `20` |

### How dedup is applied

- A greedy pass keeps an item if it is not too similar to a previously kept one.
- Similarity is computed via cosine similarity over normalized embeddings.
- `keep: first` keeps the earlier item, `keep: last` prefers the later item.

## Output report

If SyGra provides `metadata["output_file"]` at runtime, the post processor writes a JSON report next to the output file.

### Report naming

- If `report_filename` is provided:
  - absolute paths are used as-is
  - relative paths are resolved relative to the output directory
- Otherwise, the report filename is derived from the output filename:
  - `output_*.json` -> `semantic_dedup_report_*.json`

### Report format (high level)

The report includes:

- `input_count`, `output_count`, `dropped_count`
- configuration (`field`, `similarity_threshold`, `embedding_model`, etc.)
- a bounded list of duplicate pairs under `duplicates`

Each entry in `duplicates` contains:

- `kept_index`, `dropped_index`
- `kept_id`, `dropped_id`
- `similarity`

## Dependencies

When using `embedding_backend: sentence_transformers`, this feature requires the `sentence-transformers` package to be available in your environment.

## Performance considerations

When `dedup_mode: nearest_neighbor` (default), dedup runs incrementally and does not build a full similarity matrix. This is typically faster and uses less memory for larger outputs.

When `dedup_mode: all_pairs`, the implementation computes a full similarity matrix (**O(n^2)** time/memory), so it is intended for **relatively small** output lists.

If you plan to deduplicate very large outputs, consider:

- generating in smaller batches
- using a higher threshold to reduce comparisons
- implementing an approximate/streaming dedup strategy

## Troubleshooting

### Unsupported embedding backend

If you set `embedding_backend` to anything other than `sentence_transformers`, SyGra will raise:

`ValueError: Unsupported embedding_backend: ...`

### No report is written

A report is only written if `metadata["output_file"]` is present. If you are running in a context where SyGra does not set it, the post processor will still deduplicate in-memory but will not persist the report.
