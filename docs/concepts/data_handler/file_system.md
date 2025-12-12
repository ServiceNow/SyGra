# File System Handler

Manages local file operations with support for:

- JSON, JSONL (JSON Lines), Parquet files
- Special data type handling (datetime, numpy arrays)

## Working with Local Files

1. Reading from JSON/Parquet/JSONL files:

YAML:
```yaml
data_config:
  source:
    type: "disk"
    file_path: "data/input.json"   # also supports Parquet, JSONL
```

Python:
```python
from data_handlers import FileHandler
from sygra.core.dataset.dataset_config import DataSourceConfig

config = DataSourceConfig(file_path="/data/input.parquet")
handler = FileHandler(source_config=config)
data = handler.read()
```

2. Writing to JSONL with custom encoding:

YAML:
```yaml
data_config:
  sink:
    type: "disk"
    file_path: "data/output.jsonl"
    encoding: "utf-16"
```

Python:
```python
from sygra.core.dataset.dataset_config import OutputConfig
from data_handlers import FileHandler

output_config = OutputConfig(encoding="utf-16")
handler = FileHandler(output_config=output_config)
handler.write(data, path="/data/output.jsonl")
```
