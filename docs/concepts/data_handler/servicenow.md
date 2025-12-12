# ServiceNow Handler

The ServiceNow Handler enables seamless integration with ServiceNow as both a data source (read) and data sink (write) in SyGra workflows, using the [PySNC](https://github.com/ServiceNow/PySNC) library.

## Features

- Read Operations: Query any ServiceNow table with filters, field selection, ordering, and pagination
- Write Operations: Insert new records, update existing records, or upsert (insert or update)
- Auto-Table Creation: Automatically creates custom tables (prefixed with `u_`) if they don't exist
- Multiple Auth Methods: Basic authentication, OAuth2 password grant flow, environment variables
- Flexible Querying: Dict-based filters or ServiceNow encoded query strings
- Batch Processing: Configurable batch sizes with automatic pagination
- Field Mapping: Automatic handling of custom table field prefixes (`u_`)

## Authentication

The handler supports three authentication methods (checked in order):

### 1. Environment Variables (Recommended)

```bash
export SNOW_INSTANCE="dev00000"
export SNOW_USERNAME="admin"
export SNOW_PASSWORD="your_password"
```

```python
import os
import sygra

SNOW_INSTANCE = os.getenv("SNOW_INSTANCE")

source = sygra.data.from_servicenow(
    instance=SNOW_INSTANCE,
    table="incident",
    limit=10
)
```

### 2. Basic Authentication

```python
import sygra

source = sygra.data.from_servicenow(
    instance="dev000000",
    username="admin",
    password="your_password",
    table="incident"
)
```

### 3. OAuth2 Password Grant Flow

```python
import sygra

source = sygra.data.from_servicenow(
    instance="dev000000",
    username="admin",
    password="your_password",
    oauth_client_id="your_client_id",
    oauth_client_secret="your_client_secret",
    table="incident"
)
```

Environment Variables for OAuth:
```bash
export SNOW_OAUTH_CLIENT_ID="your_client_id"
export SNOW_OAUTH_CLIENT_SECRET="your_client_secret"
```

## Source Configuration

### YAML Configuration

```yaml
data_config:
  source:
    type: servicenow

    # Connection (optional if using environment variables)
    instance: dev000000
    username: admin
    password: your_password

    # Table Query
    table: incident

    # Filters (optional)
    filters:
      active: "true"
      priority: ["1", "2"]
      state:
        operator: ">="
        value: "2"

    # OR use encoded query
    query: "active=true^priorityIN1,2^stateNOTIN6,7"

    # Field Selection
    fields:
      - sys_id
      - number
      - short_description
      - description
      - priority
      - state

    # Pagination & Ordering
    limit: 100
    batch_size: 100
    order_by: sys_created_on
    order_desc: true

    # Advanced Options
    display_value: "all"
    exclude_reference_link: true
    streaming: false

    # Connection Options
    proxy: null
    verify_ssl: true
    cert: null
    auto_retry: true
```

### Python Configuration

```python
from sygra.core.dataset.servicenow_handler import ServiceNowHandler
from sygra.core.dataset.dataset_config import DataSourceConfig

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

handler = ServiceNowHandler(source_config=config)
data = handler.read()
```

## Sink Configuration

### YAML Configuration

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

### Python Configuration

```python
from sygra.core.dataset.dataset_config import OutputConfig
from sygra.core.dataset.servicenow_handler import ServiceNowHandler

output_config = OutputConfig(
    type="servicenow",
    instance="dev000000",
    username="admin",
    password="your_password",
    table="u_ai_incident_analysis",
    operation="insert",
    key_field="sys_id"
)

handler = ServiceNowHandler(output_config=output_config)
handler.write(data)
```

## Usage Examples

### Example 1: Read and Export to File

```python
import sygra

source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    filters={"active": "true", "priority": ["1", "2"]},
    fields=["sys_id", "number", "short_description", "priority"],
    limit=100
)

workflow = (
    sygra.Workflow("export_incidents")
    .source(source)
    .sink("output/incidents.jsonl")
)

result = workflow.run()
```

### Example 2: Read → AI Analysis → Write to Custom Table

```python
import sygra

source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    filters={"active": "true", "priority": ["1", "2"]},
    fields=["sys_id", "number", "short_description", "priority", "state"],
    limit=10
)

sink = sygra.data.to_servicenow(
    instance="dev000000",
    table="u_ai_incident_analysis",
    operation="insert"
)

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

### Example 3: Read → Update Existing Records

```python
import sygra

source = sygra.data.from_servicenow(
    instance="dev000000",
    table="u_ai_incident_analysis",
    fields=["sys_id", "u_short_description", "u_description"],
    limit=5
)

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

### Example 4: ServiceNow to HuggingFace

```python
import sygra

snow_source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    filters={"priority": ["1", "2", "3"]},
    fields=["number", "short_description", "description", "priority"],
    limit=1000
)

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

### Query Patterns

Simple Equality:
```python
filters = {
    "active": "true",
    "priority": "1",
    "state": "2"
}
```

Multiple Values (OR Logic):
```python
filters = {
    "priority": ["1", "2", "3"]
}
```

Complex Operators:
```python
filters = {
    "priority": {"operator": ">=", "value": "2"},
    "sys_created_on": {"operator": ">", "value": "2024-01-01"}
}
```

Supported Operators: `=`, `!=`, `>`, `>=`, `<`, `<=`, `IN`, `NOT IN`, `LIKE`, `STARTSWITH`, `ENDSWITH`

Encoded Queries:
```python
source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    query="active=true^priorityIN1,2,3^assigned_toISNOTEMPTY"
)
```

## Write Operations

| Operation | Description | Requires key_field | Auto-creates tables |
|-----------|-------------|-------------------|---------------------|
| insert | Create new records | No | Yes (u_* tables) |
| update | Modify existing records | Yes | No |
| upsert | Insert or update based on key | Yes | Yes (u_* tables) |

Insert (with Auto-Table Creation):
```python
sink = sygra.data.to_servicenow(
    instance="dev000000",
    table="u_ai_analysis",
    operation="insert"
)
```

Update:
```python
sink = sygra.data.to_servicenow(
    instance="dev000000",
    table="incident",
    operation="update",
    key_field="sys_id"
)
```

Upsert:
```python
sink = sygra.data.to_servicenow(
    instance="dev000000",
    table="u_ai_analysis",
    operation="upsert",
    key_field="incident_number"
)
```

## Advanced Features

### 1. Custom Table Field Prefixing

```python
data = {
    "incident_number": "INC0001",
    "severity_score": 8
}

# Becomes in ServiceNow
{
    "u_incident_number": "INC0001",
    "u_severity_score": 8
}
```

### 2. Field Value Format

ServiceNow fields have both `value` and `display_value`.

### 3. Batch Processing

```python
source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    limit=10000,
    batch_size=500
)
```

### 4. Streaming Mode

```python
source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    streaming=True,
    batch_size=100
)
```

### 5. Connection Options

```python
source = sygra.data.from_servicenow(
    instance="dev000000",
    table="incident",
    proxy="http://proxy.company.com:8080",
    verify_ssl=True,
    cert="/path/to/client/cert.pem",
    auto_retry=True
)
```

## References

- PySNC Documentation: https://servicenow.github.io/PySNC/
