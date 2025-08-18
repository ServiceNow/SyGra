# Data Handlers


## Components

### Base Interface (`DataHandler`)

The abstract base class that defines the core interface for all data handlers:

- `read()`: Read data from a source
- `write()`: Write data to a destination
- `get_files()`: List available files in the data source

### HuggingFace Handler

Specializes in interacting with HuggingFace datasets, supporting:

- Reading from public/private datasets
- Streaming large datasets
- Sharded dataset handling
- Dataset card (README) management
- Multiple data splits

### File System Handler

Manages local file operations with support for:

- JSON, JSONL (JSON Lines), Parquet files
- Special data type handling (datetime, numpy arrays)

## Configuration

The YAML data configuration consists of the following:
- `data_config`: Defines data source and sink configurations with `source` and `sink` keys. 
- The `source` key specifies the input data config, and the `sink` key specifies the output data config.

### Basic Structure
```yaml
data_config:
  source:
    type: "hf"  # or "disk" for local filesystem
    # source-specific configurations
  sink:
    type: "hf"  # or "disk" for local filesystem
    # sink-specific configurations
```

## Use Cases

### 1. Reading from HuggingFace Public Datasets

```yaml
data_config:
  source:
    type: "hf"
    repo_id: "google-research-datasets/mbpp"
    config_name: "sanitized"
    split: ["train", "validation", "prompt"]
```

### Source Configuration

Configure your data source using `DataSourceConfig`:

```python
from core.dataset.dataset_config import DataSourceConfig

# For HuggingFace datasets
hf_config = DataSourceConfig(
    repo_id="datasets/dataset-name",
    config_name="default",
    split="train",
    token="your_hf_token",  # Optional for private datasets
    streaming=True,  # Optional for large datasets
    shard=None  # Optional for sharded datasets
)

# For local files
file_config = DataSourceConfig(
    file_path="/path/to/data.json",
    encoding="utf-8",  # Optional, defaults to utf-8
)
```

### Output Configuration

Configure your output destination using `OutputConfig`:

```python
from core.dataset.dataset_config import OutputConfig

# For HuggingFace datasets
hf_output = OutputConfig(
    repo_id="your-username/your-dataset",
    config_name="default",
    split="train",
    token="your_hf_token",
    private=True  # Optional, defaults to False
)

# For local files
file_output = OutputConfig(
    encoding="utf-8"  # Optional, defaults to utf-8
)
```

## Usage Examples

### Working with HuggingFace Datasets

1. Reading from a public dataset:

YAML:
```yaml
data_config:
  source:
    type: "hf"
    repo_id: "google-research-datasets/mbpp"
    config_name: "sanitized"
    split: ["train", "validation", "prompt"]
```

Python:

```python
from core.dataset.huggingface_handler import HuggingFaceHandler
from core.dataset.dataset_config import DataSourceConfig

# Configure source
config = DataSourceConfig(
    repo_id="databricks/databricks-dolly-15k",
    config_name="default",
    split="train"
)

# Initialize handler
handler = HuggingFaceHandler(source_config=config)

# Read data
data = handler.read()
```

2. Writing to your private dataset:

YAML:

```yaml
data_config:
  sink:
    type: "hf"
    repo_id: "your-username/your-dataset"
    config_name: "custom_config"
    split: "train"
    push_to_hub: true
    private: true
```

Python:

```python
# Configure output

output_config = OutputConfig(
    repo_id="your-username/your-dataset",
    config_name="default",
    split="train",
    token="your_hf_token",
    private=True
)

handler = HuggingFaceHandler(output_config=output_config)
handler.write(data) 
```

3. Working with sharded datasets:

YAML:

```yaml
data_config:
  source:
    type: "hf"
    repo_id: "large-dataset"
    shard:
      regex: "-.*\\.parquet$"
      index: [0, 1, 2]  # Only process first 3 shards
```

Python: 

```python
config = DataSourceConfig(
    repo_id="large-dataset",
    shard={"regex": "-.*\\.parquet$", "index": [0, 1, 2]}  # Only process first 3 shards
)

handler = HuggingFaceHandler(source_config=config)
shard_files = handler.get_files()

for shard_path in shard_files:
    shard_data = handler.read(path=shard_path)
    # Process shard data
```

### Field Transformations 

YAML: 

```yaml
data_config:
  source:
    type: "hf"
    repo_id: "dataset/name"
    transformations:
      - transform: processors.data_transform.RenameFieldsTransform
        params:
          mapping:
            old_field: new_field
          overwrite: false
```

Python: 

```python
from processors.data_transform import RenameFieldsTransform

config = DataSourceConfig(
    repo_id="dataset/name",
    transformations=[
        {
            "transform": RenameFieldsTransform,
            "params": {
                "mapping": {"old_field": "new_field"},
                "overwrite": False
            }
        }
    ]
)

handler = HuggingFaceHandler(source_config=config)
data = handler.read()
```

### Working with Local Files

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
output_config = OutputConfig(encoding="utf-16")
handler = FileHandler(output_config=output_config)
handler.write(data, path="/data/output.jsonl")
```
