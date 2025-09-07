## Weighted Sampler Node

GraSP supports random selection of values for attributes in your workflow using the **weighted_sampler** node. This node enables you to sample configuration values—optionally with custom weights—or pull data directly from external sources.

Weighted sampler nodes are useful for randomized data generation, prompt diversity, scenario coverage, and more.

### Example Configuration

```yaml
persona_sampler:
  node_type: weighted_sampler
  attributes:
    num_turns:                # Attribute name
      values: [2, 3, 4, 5]    # Possible values
    tone:
      values: [professional, casual, friendly, formal]
      weights: [2, 1, 1, 1]   # Optional weights (default: equal weights)
    question_role:
      values:
        column: "persona"
        source:
          type: "hf"
          repo_id: "nvidia/Nemotron-Personas"
          config_name: "default"
          split: "train"
```

### Configuration Fields

- **`node_type`**:  
  Set to `weighted_sampler` to indicate this node type.

- **`attributes`**:  
  Map of attribute names to their sampling configuration.

  - **`values`**:  
    List of possible values to sample from, or configuration for external data sources.  
    - If a static list is provided, one value is sampled per run.
    - If pointing to a data source (like Huggingface or Disk), values are read sequentially from the source. If the source has fewer records than needed, it loops back to the beginning (non-stream sources only).
    - The `column` can be a single column name or a list of columns (for column-wise sampling).

  - **`weights`** (optional):  
    List of weights (same length as `values`) for weighted random sampling. If not specified, all values are sampled with equal probability.

### Advanced Data Source Sampling

- **Static List**:  
  ```yaml
  num_turns:
    values: [2, 3, 4, 5]
  ```
- **Data Source (e.g. Huggingface)**:  
  ```yaml
  question_role:
    values:
      column: "persona"
      source:
        type: "hf"
        repo_id: "nvidia/Nemotron-Personas"
        config_name: "default"
        split: "train"
  ```
- **Multiple Columns**:  
  If `column` is a list, one column is picked at random for each record.

### Notes

- Attribute values can be sampled randomly or sequentially from lists, data files, or Huggingface datasets.
- When using a non-stream data source and records run out, sampling loops back to the beginning.
- For best performance, avoid using stream data sources with samplers. Also make sure the dataset is not too large, as it downloads and pick sample in local process.
- The sampled values are stored as state variables, ready for use by subsequent nodes.

---

**Tip:** Use weighted samplers to inject diversity and controlled randomness into your pipeline, or to generate data for experiments and training.

---