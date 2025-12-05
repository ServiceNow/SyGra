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
from sygra.core.dataset.dataset_config import DataSourceConfig

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
from sygra.core.dataset.dataset_config import OutputConfig

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
      - transform: sygra.processors.data_transform.RenameFieldsTransform
        params:
          mapping:
            old_field: new_field
          overwrite: false
```

Python:

```python
from sygra.processors.data_transform import RenameFieldsTransform

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

---

## ServiceNow Handler

The ServiceNow Handler enables seamless integration with ServiceNow as both a data source (read) and data sink (write) in SyGra workflows, using the [PySNC](https://github.com/ServiceNow/PySNC) library.

### Features

- **Read Operations**: Query any ServiceNow table with filters, field selection, ordering, and pagination
- **Write Operations**: Insert new records, update existing records, or upsert (insert or update)
- **Auto-Table Creation**: Automatically creates custom tables (prefixed with `u_`) if they don't exist
- **Multiple Auth Methods**: Basic authentication, OAuth2 password grant flow, environment variables
- **Flexible Querying**: Dict-based filters or ServiceNow encoded query strings
- **Batch Processing**: Configurable batch sizes with automatic pagination
- **Field Mapping**: Automatic handling of custom table field prefixes (`u_`)


### Authentication

The handler supports three authentication methods (checked in order):

#### 1. Environment Variables (Recommended)

```bash
export SNOW_INSTANCE="dev00000"
export SNOW_USERNAME="admin"
export SNOW_PASSWORD="your_password"
```

```python
import os

# Instance from environment, credentials auto-loaded
SNOW_INSTANCE = os.getenv("SNOW_INSTANCE")

source = sygra.data.from_servicenow(
    instance=SNOW_INSTANCE,
    table="incident",
    limit=10
)
```

#### 2. Basic Authentication

```python
source = sygra.data.from_servicenow(
    instance="dev000000",
    username="admin",
    password="your_password",
    table="incident"
)
```

#### 3. OAuth2 Password Grant Flow

```python
source = sygra.data.from_servicenow(
    instance="dev000000",
    username="admin",
    password="your_password",
    oauth_client_id="your_client_id",
    oauth_client_secret="your_client_secret",
    table="incident"
)
```

**Environment Variables for OAuth**:
```bash
export SNOW_OAUTH_CLIENT_ID="your_client_id"
export SNOW_OAUTH_CLIENT_SECRET="your_client_secret"
```

### Source Configuration

#### YAML Configuration

```yaml
data_config:
  source:
    type: servicenow

    # Connection (optional if using environment variables)
    instance: dev000000              # ServiceNow instance name
    username: admin                  # Optional (env: SNOW_USERNAME)
    password: your_password          # Optional (env: SNOW_PASSWORD)

    # Table Query
    table: incident                  # Required: table to query

    # Filters (optional)
    filters:
      active: "true"                 # Simple equality
      priority: ["1", "2"]           # Multiple values (OR)
      state:                         # Complex operator
        operator: ">="
        value: "2"

    # OR use encoded query
    query: "active=true^priorityIN1,2^stateNOTIN6,7"

    # Field Selection (optional, recommended for performance)
    fields:
      - sys_id
      - number
      - short_description
      - description
      - priority
      - state

    # Pagination & Ordering
    limit: 100                       # Max records to retrieve
    batch_size: 100                  # Records per API call (default: 100)
    order_by: sys_created_on         # Sort field
    order_desc: true                 # Sort descending (default: false)

    # Advanced Options
    display_value: "all"             # "all", "true", "false" (default: "all")
    exclude_reference_link: true     # Exclude reference links (default: true)
    streaming: false                 # Use iterator vs list (default: false)

    # Connection Options
    proxy: null                      # HTTP proxy (optional)
    verify_ssl: true                 # SSL verification (optional)
    cert: null                       # Client certificate path (optional)
    auto_retry: true                 # Auto-retry on 429 errors (default: true)
```

#### Python Configuration

```python
from sygra.core.dataset.servicenow_handler import ServiceNowHandler
from sygra.core.dataset.dataset_config import DataSourceConfig

# Configure source
config = DataSourceConfig(
    type="servicenow",
    instance="dev000000",
    username="admin",
    password="your_password",
    table="incident",
    filters={"active": "true", "priority": ["1", "2"]},
    fields=["sys_id", "number", "short_description", "priority"],
    limit=100,
    batch_size=100,
    order_by="sys_created_on",
    order_desc=True
)

# Initialize handler
handler = ServiceNowHandler(source_config=config)

# Read data
data = handler.read()
```

### Sink Configuration

#### YAML Configuration

```yaml
data_config:
  sink:
    type: servicenow

    # Connection (optional if using environment variables)
    instance: dev000000
    username: admin
    password: your_password

    # Table & Operation
    table: u_ai_incident_analysis    # Target table (auto-created if starts with u_)
    operation: insert                # insert, update, or upsert (default: "insert")
    key_field: sys_id                # Field to match for update/upsert (default: "sys_id")

    # Connection Options
    proxy: null
    verify_ssl: true
    cert: null
    auto_retry: true
```

#### Python Configuration

```python
from sygra.core.dataset.dataset_config import OutputConfig

# Configure output
output_config = OutputConfig(
    type="servicenow",
    instance="dev000000",
    username="admin",
    password="your_password",
    table="u_ai_incident_analysis",
    operation="insert",
    key_field="sys_id"
)

# Initialize handler
handler = ServiceNowHandler(output_config=output_config)

# Write data
handler.write(data)
```

### Usage Examples

#### Example 1: Read and Export to File

```python
import sygra

# Read from ServiceNow
source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    filters={"active": "true", "priority": ["1", "2"]},
    fields=["sys_id", "number", "short_description", "priority"],
    limit=100
)

# Export to file
workflow = (
    sygra.Workflow("export_incidents")
    .source(source)
    .sink("output/incidents.jsonl")
)

result = workflow.run()
```

#### Example 2: Read → AI Analysis → Write to Custom Table

```python
import sygra

# Read from incident table
source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    filters={"active": "true", "priority": ["1", "2"]},
    fields=["sys_id", "number", "short_description", "priority", "state"],
    limit=10
)

# Write to custom table (auto-created if doesn't exist)
sink = sygra.data.to_servicenow(
    instance="dev000000",
    table="u_ai_incident_analysis",
    operation="insert"
)

# Build workflow
workflow = (
    sygra.Workflow("incident_analyzer")
    .source(source)
    .llm(
        model="gpt-4o-mini",
        prompt="""Analyze this ServiceNow incident:

Number: {number}
Description: {short_description}
Priority: {priority}

Provide JSON with:
- severity_score (1-10)
- predicted_resolution_time (hours)
- recommended_action (text)
- root_cause_category (technical/user/process/other)""",
        output="ai_analysis"
    )
    .sink(sink)
)

result = workflow.run()
```

#### Example 3: Read → Update Existing Records

```python
import sygra

# Read from custom table
source = sygra.data.from_servicenow(
    instance="dev000000",
    table="u_ai_incident_analysis",
    fields=["sys_id", "u_short_description", "u_description"],
    limit=5
)

# Update same table
sink = sygra.data.to_servicenow(
    instance="dev000000",
    table="u_ai_incident_analysis",
    operation="update",
    key_field="sys_id"
)

workflow = (
    sygra.Workflow("paraphrase_updater")
    .source(source)
    .llm(
        model="gpt-4o-mini",
        temperature=0.7,
        prompt="Create detailed paraphrase: {u_short_description}",
        output="paraphrase"
    )
    .sink(sink)
)

result = workflow.run()
```

#### Example 4: ServiceNow to HuggingFace

```python
import sygra

# Read from ServiceNow
snow_source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    filters={"priority": ["1", "2", "3"]},
    fields=["number", "short_description", "description", "priority"],
    limit=1000
)

# Write to HuggingFace
hf_sink = sygra.data.to_huggingface(
    repo_id="your-org/servicenow-incidents",
    private=True
)

workflow = (
    sygra.Workflow("snow_to_hf_sync")
    .source(snow_source)
    .llm(
        model="gpt-4o-mini",
        prompt="Anonymize and clean: {short_description}",
        output="cleaned_description"
    )
    .sink(hf_sink)
)

result = workflow.run()
```

#### Example 5: Complete YAML Workflow

**graph_config.yaml**:
```yaml
data_config:
  source:
    type: servicenow
    table: incident
    filters:
      active: "true"
      priority: ["1", "2"]
    fields:
      - sys_id
      - number
      - short_description
      - description
      - priority
      - state
      - urgency
      - impact
    limit: 10
    order_by: sys_created_on
    order_desc: true

  sink:
    type: servicenow
    table: u_ai_incident_analysis
    operation: insert

graph_config:
  nodes:
    analyzer:
      node_type: llm
      model:
        provider: openai
        name: gpt-4o-mini
        temperature: 0.1
        max_tokens: 1024
      output_keys: ai_analysis
      prompt:
        - system: |
            You are an expert IT incident analyst.
        - user: |
            Analyze this incident:
            Number: {number}
            Description: {short_description}
            Priority: {priority}

  edges:
    - from: START
      to: analyzer
    - from: analyzer
      to: END
```

**Run**:
```bash
uv run python main.py -t examples.servicenow_ai_analysis_insert -n 10
```

### Query Patterns

#### Simple Equality

```python
filters = {
    "active": "true",
    "priority": "1",
    "state": "2"
}
```

#### Multiple Values (OR Logic)

```python
filters = {
    "priority": ["1", "2", "3"]  # priority=1 OR priority=2 OR priority=3
}
```

#### Complex Operators

```python
filters = {
    "priority": {"operator": ">=", "value": "2"},
    "sys_created_on": {"operator": ">", "value": "2024-01-01"}
}
```

**Supported Operators**: `=`, `!=`, `>`, `>=`, `<`, `<=`, `IN`, `NOT IN`, `LIKE`, `STARTSWITH`, `ENDSWITH`

#### Encoded Queries

```python
# Use ServiceNow query syntax directly
source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    query="active=true^priorityIN1,2,3^assigned_toISNOTEMPTY"
)
```

### Write Operations

| Operation | Description | Requires key_field | Auto-creates tables |
|-----------|-------------|-------------------|---------------------|
| **insert** | Create new records | No | Yes (u_* tables) |
| **update** | Modify existing records | Yes | No |
| **upsert** | Insert or update based on key | Yes | Yes (u_* tables) |

#### Insert (with Auto-Table Creation)

```python
sink = sygra.data.to_servicenow(
    instance="dev000000",
    table="u_ai_analysis",  # Created automatically if doesn't exist
    operation="insert"
)
```

**What Happens**:
1. Checks if table exists
2. If table doesn't exist and starts with `u_`, creates it automatically
3. Infers field types from data:
   - `str` → String (255 or 4000 chars)
   - `int` → Integer
   - `bool` → Boolean
   - `dict`/`list` → String (4000 chars, stored as JSON)
4. Inserts all records

#### Update

```python
sink = sygra.data.to_servicenow(
    instance="dev000000",
    table="incident",
    operation="update",
    key_field="sys_id"  # Match records by sys_id (default)
)
```

**Requirements**:
- Source data must include the `key_field` (e.g., `sys_id`)
- Records must exist in ServiceNow

#### Upsert

```python
sink = sygra.data.to_servicenow(
    instance="dev000000",
    table="u_ai_analysis",
    operation="upsert",
    key_field="incident_number"  # Match on incident_number
)
```

**Behavior**:
- If record with `key_field` value exists → update
- If record doesn't exist → insert

### Advanced Features

#### 1. Custom Table Field Prefixing

For custom tables (starting with `u_`), field names are automatically prefixed with `u_`:

```python
# Your data
data = {
    "incident_number": "INC0001",
    "severity_score": 8
}

# Automatically becomes in ServiceNow
{
    "u_incident_number": "INC0001",
    "u_severity_score": 8
}
```

**You don't need to add the `u_` prefix manually** - the handler does it automatically.

#### 2. Field Value Format

ServiceNow fields have both `value` and `display_value`:

```python
# Read from ServiceNow
record = {
    "priority": {
        "value": "1",                    # Database value
        "display_value": "Critical"      # Human-readable label
    },
    "assigned_to": {
        "value": "user_sys_id_123",      # sys_id reference
        "display_value": "John Doe"      # User's name
    }
}
```

#### 3. Batch Processing

```python
source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    limit=10000,            # Total records
    batch_size=500          # 500 records per API call (default: 100)
)
```

#### 4. Streaming Mode

For very large datasets:

```python
source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    streaming=True,         # Returns iterator instead of list
    batch_size=100
)
```

#### 5. Connection Options

```python
source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",

    # Proxy settings
    proxy="http://proxy.company.com:8080",

    # SSL settings
    verify_ssl=True,                    # Verify SSL certificates
    cert="/path/to/client/cert.pem",    # Client certificate

    # Auto-retry on rate limits
    auto_retry=True                     # Retry on 429 errors (default: True)
)
```

### Configuration Reference

**Complete Source Configuration**:
```python
{
    "type": "servicenow",

    # Connection
    "instance": str,                        # Required (or env: SNOW_INSTANCE)
    "username": str | None,                 # Optional (env: SNOW_USERNAME)
    "password": str | None,                 # Optional (env: SNOW_PASSWORD)
    "oauth_client_id": str | None,          # Optional (env: SNOW_OAUTH_CLIENT_ID)
    "oauth_client_secret": str | None,      # Optional (env: SNOW_OAUTH_CLIENT_SECRET)

    # Query
    "table": str,                           # Required
    "query": str | None,                    # Encoded query string
    "filters": dict[str, Any] | None,       # Dict-based filters
    "fields": list[str] | None,             # Field selection
    "limit": int | None,                    # Max records
    "batch_size": int = 100,                # Records per API call (default: 100)
    "order_by": str | None,                 # Sort field
    "order_desc": bool = False,             # Sort direction (default: False)

    # Advanced
    "display_value": str = "all",           # "all", "true", "false" (default: "all")
    "exclude_reference_link": bool = True,  # Default: True
    "streaming": bool = False,              # Default: False

    # Connection
    "proxy": str | None,
    "verify_ssl": bool | None,
    "cert": str | None,
    "auto_retry": bool = True               # Default: True
}
```

**Complete Sink Configuration**:
```python
{
    "type": "servicenow",

    # Connection
    "instance": str,                        # Required (or env: SNOW_INSTANCE)
    "username": str | None,                 # Optional (env: SNOW_USERNAME)
    "password": str | None,                 # Optional (env: SNOW_PASSWORD)
    "oauth_client_id": str | None,          # Optional (env: SNOW_OAUTH_CLIENT_ID)
    "oauth_client_secret": str | None,      # Optional (env: SNOW_OAUTH_CLIENT_SECRET)

    # Operation
    "table": str,                           # Required
    "operation": str = "insert",            # "insert", "update", "upsert" (default: "insert")
    "key_field": str = "sys_id",            # Field to match for update/upsert (default: "sys_id")

    # Connection
    "proxy": str | None,
    "verify_ssl": bool | None,
    "cert": str | None,
    "auto_retry": bool = True               # Default: True
}
```

### Example Tasks

**Working Examples**:
- `/tasks/examples/servicenow_ai_analysis_insert/` - Read incidents → AI analysis → Insert to custom table
- `/tasks/examples/servicenow_ai_analysis_update/` - Read custom table → Generate paraphrase → Update records

**Run Examples**:
```bash
# Insert example
uv run python main.py -t examples.servicenow_ai_analysis_insert -n 10

# Update example
uv run python main.py -t examples.servicenow_ai_analysis_update -n 5
```

### References

- **PySNC Documentation**: https://servicenow.github.io/PySNC/
