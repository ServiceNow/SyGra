# HuggingFace Handler

Specializes in interacting with HuggingFace datasets, supporting:

- Reading from public/private datasets
- Streaming large datasets
- Sharded dataset handling
- Dataset card (README) management
- Multiple data splits

## Reading from HuggingFace Public Datasets

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
from sygra.core.dataset.huggingface_handler import HuggingFaceHandler
from sygra.core.dataset.dataset_config import DataSourceConfig

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

## Writing to your private dataset

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
from sygra.core.dataset.dataset_config import OutputConfig
from sygra.core.dataset.huggingface_handler import HuggingFaceHandler

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

## Working with sharded datasets

YAML:
```yaml
data_config:
  source:
    type: "hf"
    repo_id: "large-dataset"
    shard:
      regex: "-.*\\.parquet$"
      index: [0, 1, 2]
```

Python:
```python
from sygra.core.dataset.dataset_config import DataSourceConfig
from sygra.core.dataset.huggingface_handler import HuggingFaceHandler

config = DataSourceConfig(
    repo_id="large-dataset",
    shard={"regex": "-.*\\.parquet$", "index": [0, 1, 2]}
)

handler = HuggingFaceHandler(source_config=config)
shard_files = handler.get_files()

for shard_path in shard_files:
    shard_data = handler.read(path=shard_path)
    # Process shard data
```

## Field Transformations

YAML:
```yaml
data_config:
  source:
    type: "hf"
    repo_id: "dataset/name"
    transformations:
      - transform: sygra.processors.data_transform.RenameFieldsTransform
        params:
          mapping:
            old_field: new_field
          overwrite: false
```

Python:
```python
from sygra.processors.data_transform import RenameFieldsTransform
from sygra.core.dataset.dataset_config import DataSourceConfig
from sygra.core.dataset.huggingface_handler import HuggingFaceHandler

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
