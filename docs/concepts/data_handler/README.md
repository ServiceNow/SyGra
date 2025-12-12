# Data Handlers

Data handler is used for reading and writing the data. Currently, it supports following handlers:

 - File handler with various file types like JSON, JSONL, CSV, Parquet, Folder with supported type.
 - Huggingface handler: When reading data from huggingface, it can read the whole dataset and process, or it can stream chunk of data.
 - ServiceNow Handler to connect a ServiceNow instance : Currently it reads or writes into a single table per dataset configuration.

<kbd> ![DataHandler](https://raw.githubusercontent.com/ServiceNow/SyGra/refs/heads/main/docs/resources/images/component_data_handler.png) </kbd>

## Components

### Base Interface (`DataHandler`)

The abstract base class that defines the core interface for all data handlers:

- `read()`: Read data from a source
- `write()`: Write data to a destination
- `get_files()`: List available files in the data source


## Configuration

The YAML data configuration consists of the following:
- `data_config`: Defines data source and sink configurations with `source` and `sink` keys.
- The `source` key specifies the input data config, and the `sink` key specifies the output data config.

### Basic Structure
```yaml
data_config:
  source:
    type: "hf"  # or "disk" or "servicenow"
    # source-specific configurations
  sink:
    type: "hf"  # or or "disk" or "servicenow"
    # sink-specific configurations
```
