# Dataset Tools Framework

A modular and extensible framework to define, register, and run dataset processing tools via configuration files or CLI commands.

---

## Project Structure

```
tools/
├── base_tool.py           # Abstract base class for all tools
├── config.py              # Pydantic-based config parsing
├── executor.py            # Executes one or more tools as a pipeline
├── registry.py            # Tool registration and dynamic discovery
├── cli.py                 # CLI logic
├── __main__.py            # Entry point for `python -m grasp.tools`
└── toolkits/              # All tools live here
    └── tool_name/
        └── processor.py   # File containing tool logic
```

---

## 🚀 Getting Started

### 1. Tool Structure

Each tool:
- Lives in its own folder inside `tools/toolkits/`
- Has a `processor.py` file
- Contains a class inheriting from `BaseTool`
- Uses the `@register_tool` decorator

Example:

```python
# grasp/tools/toolkits/dummy_processor/processor.py

@register_tool
class DummyProcessor(BaseTool):
    name = "dummy_processor"
    description = "Adds a dummy field to each record"

    def __init__(self, config):
        self.message = config.get("message", "processed")
        self.field_name = config.get("field_name", "processed_by")

    def process(self, input_path, output_path):
        # implement data read/write logic
        return output_path
```

---

### 2. List Available Tools

```bash
./run_tools.sh --list-tools
```

---

### 3. Run Tool(s) via Config File

Prepare a YAML file like:

```yaml
data_config:
  source:
    type: disk
    file_path: data/input.jsonl

  sink:
    type: jsonl
    file_path: grasp/tools/tool_runs/output.jsonl

tools:
  dummy_processor:
    config:
      message: "Processed via CLI"
      field_name: "cli_processed"
```

Then run:

```bash
./run_tools.sh --config grasp/tools/config/my_pipeline.yaml
```

This executes the full pipeline and saves the final output.

---

## ✅ Tool Auto-Discovery

The framework will automatically detect all tools under `grasp/tools/toolkits/*/processor.py`, so you don't need to import them manually.

Each discovered tool must:
- Be in a directory under `toolkits/`
- Have a `processor.py` file
- Contain a class with the `@register_tool` decorator

---

## 🔧 Add Your Own Tool

1. Create a new folder under `grasp/tools/toolkits/your_tool_name/`
2. Add a `processor.py` file
3. Define your tool class:

```python
@register_tool
class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"

    def __init__(self, config):
        ...

    def process(self, input_path, output_path):
        ...
```

4. Run with a YAML config like:

```yaml
tools:
  my_tool:
    config:
      some_param: value
```

## 🧰 Available Tools

### 1. `dummy_processor`
A simple tool that adds a dummy field to each record in the dataset. This tool is primarily for demonstration purposes.
**Config Example**:
```yaml
tools:
  dummy_processor:
    config:
      message: "Processed via CLI"
      field_name: "cli_processed"
```

### 2. `oasst_mapper`
Transforms conversation data using a structured pipeline to fit the OASST-compatible schema. Currently supports two modes: `sft` (Supervised Fine-Tuning) and `dpo` (Direct Preference Optimization).

**Config Example**:
```yaml
tools:
  oasst_mapper:
    config:
      type: "sft" # or dpo
```
For more details, refer to the [OASST Mapper documentation](../../docs/concepts/data_mapper/README.md).

### 3. `data_quality`
Runs a sequence of quality tagging tasks on conversation data. The tasks include:
- conversation_pretokenization
- language_tagging
- metadata_tagging
- data_characteristics
- lexical_diversity
- llm_based_quality
- ppl_score
- reward_score

**Config Example**:
```yaml
tools:
  data_quality:
    config:
      tasks:
        - name: "conversation_pretokenization"
          params:
            hf_chat_template_model_id: "meta-llama/Meta-Llama-3-8B-Instruct"
        - name: "metadata_tagging"
        - name: "llm_based_quality"
```

For more details on data quality config, refer to the [Data Quality documentation](../../docs/concepts/data_quality/README.md).
