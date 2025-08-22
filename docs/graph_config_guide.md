# GraSP Graph Configuration Guide

## Table of Contents

- [Structure Overview](#structure-overview)
- [Data Configuration](#data-configuration)
- [Graph Configuration](#graph-configuration)
  - [Nodes](#nodes)
  - [Edges](#edges)
    - [Simple Edges](#simple-edges)
    - [Conditional Edges](#conditional-edges)
- [Output Configuration](#output-configuration)
- [Full Example](#full-example)
- [Schema_Validator](#schema-validator)

## Structure Overview

A GraSP configuration file is a YAML document with these main sections:

```yaml
data_config:
  # Source data configuration

graph_config:
  nodes:
    # Node definitions
  edges:
    # Edge definitions

output_config:
  # Output generation configuration

schema_config:
  # Output schema validation 


```

Let's look at each section in detail. The sections below document all the available options and properties for each part of the configuration.

## Data Configuration

The `data_config` section defines your input data sources, output destinations (sinks), and any transformations to apply.

```yaml
data_config:
  source:
    # Example 1: HuggingFace dataset source
    type: "hf"                               # HuggingFace dataset
    repo_id: "google-research-datasets/mbpp" # HuggingFace repository ID
    config_name: "sanitized"                 # Dataset configuration name
    split: ["train", "validation", "prompt"] # Dataset splits to use

    # OR

    # Example 2: Local file source
    type: "disk"                             # Local file source
    file_path: "/path/to/data.json"          # Path to input file
    file_format: "json"                      # Format (json, jsonl, csv, parquet)
    encoding: "utf-8"                        # File encoding

    # Optional transformations to apply to the input data
    transformations:
      - transform: grasp.processors.data_transform.RenameFieldsTransform  # Path to transformation class
        params:                                                     # Parameters for the transformation
          mapping:
            task_id: id                     # Rename 'task_id' field to 'id'
          overwrite: false                  # Don't overwrite existing fields
          
  # Optional sink configuration for where to store output data
  sink:
    # Example 1: HuggingFace dataset sink
    type: "hf"                               # HuggingFace dataset
    repo_id: "output-dataset/synthetic-mbpp" # Where to upload the data
    split: "train"                           # Split to write to
    private: true                            # Create a private dataset
    
    # OR
    
    # Example 2: Local file sink
    type: "json"                             # File format (json, jsonl, csv, parquet)
    file_path: "/path/to/output/file.json"   # Path to save the file
    encoding: "utf-8"                        # File encoding
```

### Data Source Options

The `source` subsection of `data_config` configures where the input data will come from.

#### HuggingFace Source

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `type` | string | Source type: "hf" | Required |
| `repo_id` | string | HuggingFace dataset repository ID | Required |
| `config_name` | string | Dataset configuration name | None |
| `split` | string or list | Dataset split(s) to use | "train" |
| `token` | string | HuggingFace API token | None |
| `streaming` | boolean | Whether to stream the dataset | false |
| `shard` | object | Configuration for sharded processing | None |

#### Local File Source

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `type` | string | Source type: "disk" | Required |
| `file_path` | string | Path to local file | Required |
| `file_format` | string | File format (json, jsonl, csv, parquet) | Required |
| `encoding` | string | Character encoding | "utf-8" |

### Transformations

Transformations allow you to modify the input data before processing.

| Parameter | Type | Description |
|-----------|------|-------------|
| `transform` | string | Fully qualified path to a transformation class |
| `params` | object | Parameters for the transformation |

#### Some of the available transformations are: 
#### RenameFieldsTransform
It renames the fields in the dataset, so the prompt variables used are meaningful and reusable.
The Below example shows how the `page` is renamed to `id`, `llm_extract` is renamed to `text` and `type` is renamed to `text_format`.
```yaml
      - transform: grasp.processors.data_transform.RenameFieldsTransform
        params:
          mapping:
            page: id
            llm_extract: text
            type: text_format
```
#### CombineRecords
When you want to combine records to form a new dataset, you can use this transformation.
Below example shows how we can skip 10 records from beginning and from end, and combine 2 records by shifting 1.
For example record `11` and `12` will be combined to form `page`=`11-12`, in this example, `pdf_reader` and `llm_extract` columns are combined with two new lines. 
And `type`, `model`, `metadata` is just picking data from first record. `$1` denotes first record, `$2` denotes second record and so on. 
Once `11` and `12` is combined to form `11-12`, it shift by 1 and combines `12` with `13` to form `12-13`.
```yaml
      - transform: grasp.processors.data_transform.CombineRecords
        params:
          skip:
            from_beginning: 10
            from_end: 10
          combine: 2
          shift: 1
          join_column:
            page: "$1-$2"
            pdf_reader: "$1\n\n$2"
            llm_extract: "$1\n\n$2"
            type: "$1"
            model: "$1"
            metadata: "$1"
```
#### SkipRecords
When we want to skip records for a dataset, we can use this transform.
Below example shows how to skip first 10 and last 10 records using count.
```yaml
      - transform: grasp.processors.data_transform.SkipRecords
        params:
          skip_type: "count"
          count:
            from_start: 10
            from_end: 10
```
Below example shows how to skip first 10 and last 10 records using range.
```yaml
      - transform: grasp.processors.data_transform.SkipRecords
        params:
          skip_type: "range"
          range: "[:10],[-10:]"
```

### Data Sink Options

The `sink` subsection of `data_config` configures where the output data will be stored.

#### HuggingFace Sink

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `type` | string | Sink type: "hf" | Required |
| `repo_id` | string | HuggingFace dataset repository ID | Required |
| `config_name` | string | Dataset configuration name | None |
| `split` | string | Dataset split to write to | "train" |
| `token` | string | HuggingFace API token | None |
| `private` | boolean | Whether to create a private dataset | true |

#### File Sink

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `type` | string | File format: "json", "jsonl", "csv", "parquet" | Required |
| `file_path` | string | Path to output file | Required |
| `encoding` | string | Character encoding | "utf-8" |


### Data Less Configuration

GraSP supports generating data without requiring an input data source. This is useful for knowledge distillation from models, creating purely synthetic datasets, or any scenario where you want to generate content from scratch.

To generate data without a source:

1. Simply omit the `source` configuration in the `data_config` section
2. Keep the `sink` configuration to specify where to store the generated data

```yaml
data_config:
  # No source configuration
  
  # Only sink configuration
  sink:
    type: "json"
    file_path: "output/synthetic_data.jsonl"
```


## Graph Configuration

The `graph_config` section defines the nodes and edges of your computational graph.

```yaml
graph_config:
  nodes:
    # Node definitions
  edges:
    # Edge definitions
```

This section is where you define the processing steps (nodes) and the flow between them (edges) that make up your data generation pipeline.

### Graph Properties
This defines the graph level properties, it can be a common properties but controlled from the task.
```yaml
  graph_properties:
    chat_conversation: singleturn   #singleturn or multiturn
    chat_history_window_size: 5
```

### Nodes

Nodes represent the processing steps in your pipeline. GraSP supports multiple types of nodes, such as LLM, multi_llm, weighted_sampler, lambda, agent, subgraph, and more.

All node types support these common parameters:

| Parameter   | Type   | Description                                           | Default   |
|-------------|--------|------------------------------------------------------|-----------|
| `node_type` | string | Type of node ("llm", "multi_llm", "weighted_sampler", "lambda", etc.) | Required  |
| `node_state`| string | Node state ("active" or "idle") to enable/disable the node | "active" |

**For detailed documentation and configuration options for each node type, see [nodes/](nodes/).**

### Edges

Edges define the flow of execution between nodes.

#### Special Nodes: START and END

GraSP graphs automatically include two special nodes:

- **START**: The entry point of the graph. Every graph must have at least one edge from START to another node.
- **END**: The exit point of the graph. When execution reaches the END node, the graph processing is complete.

These special nodes are handled automatically by the framework and don't need to be defined in the `nodes` section. They are only referenced in edge definitions.

#### Simple Edges

Simple edges define a direct path from one node to another.

```yaml
edges:
  - from: START              # Source START node (entry point)
    to: persona_sampler      # Target node
  - from: persona_sampler    # Source node
    to: paraphrase_question  # Target node
  - from: final_node         # Last processing node
    to: END                  # Exit point of the graph
```

#### Conditional Edges

Conditional edges define different paths based on a condition. Conditions can direct flow to the END node to terminate processing.

```yaml
- from: critique_answer
  condition: grasp.tasks.mbpp.code_generation_with_graph_builder.task_executor.ShouldContinueCondition
  path_map:
    END: END                          # Path to END when condition returns "END" (terminates processing)
    generate_answer: generate_answer  # Path to generate_answer when condition returns "generate_answer"
```

In condition functions, you can return `constants.GRASP_END` to direct flow to the END node:

```python
class ShouldContinueCondition(EdgeCondition):
    def apply(self, state: GraspState) -> str:
        # End after 4 iterations or the last feedback response contains "NO MORE FEEDBACK"
        messages = state["messages"]
        if len(messages) > 8 or (
                len(messages) > 1 and "no more feedback" in messages[-1].content.lower()
        ):
            return constants.GRASP_END  # This will direct flow to the END node
        return "generate_answer"
```

**Edge Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `from` | string | Source node name (can be a regular node or START) | 
| `to` | string | Target node name (can be a regular node or END) |
| `condition` | string | Fully qualified path to a condition class or function (for conditional edges) |
| `path_map` | object | Map of condition results to target node names (for conditional edges) |

## Output Configuration

The `output_config` section defines how to generate the final output records. This component translates the final state of the graph into the desired output format for each processed record.

### Overview

There are two approaches to generating output records:

1. **YAML-driven** with the `output_map` configuration (recommended)
2. **Custom Python implementation** by overriding the `generate()` method

### YAML-Driven Output Configuration

This approach uses declarative configuration to map state variables to output fields. The `output_map` section defines how to construct your final output records by specifying what goes into each field:

```yaml
output_config:
  # Path to a class that inherits from BaseOutputGenerator
  generator: grasp.tasks.mbpp.code_generation_with_graph_builder.task_executor.CodeGenOutputGenerator

  # Map of output fields and how to populate them
  output_map:
    id:                       # Output field name
      from: "id"              # Get value from this state variable
    conversation:
      from: "messages"        # Get value from this state variable
      transform: "build_conversation"  # Apply this method from the generator class to transform the value
    taxonomy:
      value:                  # Use this static value (not from state)
        - category: "Coding"
          subcategory: ""
    annotation_type:
      value: ["mistral-large"]
    language:
      value: "en"
    tags:
      value: ["mbpp", "self-critique"]
```

#### How `output_map` works

The `output_map` is a dictionary where:
1. Each **key** becomes a field name in your output record
2. Each **value** is a configuration object that defines how to populate that field

For each field, you have two main ways to populate it:

1. **Dynamic values from state** (using `from`):
   ```yaml
   id:
     from: "id"  # Takes the value from state["id"]
   ```
   This retrieves the value with the key "id" from the graph state and puts it in the output record's "id" field.

2. **Static values** (using `value`):
   ```yaml
   language:
     value: "en"  # Hardcoded value "en"
   ```
   This puts the literal value "en" in the output record's "language" field.

3. **Transformed values** (using `from` + `transform`):
   ```yaml
   conversation:
     from: "messages"  # Takes the value from state["messages"]
     transform: "build_conversation"  # Passes it through a transformation method
   ```
   This takes the value from state["messages"], passes it through the `build_conversation` method defined in your generator class, and puts the result in the output record's "conversation" field.

#### Example output record

With the configuration above, your final output record would look like:

```json
{
  "id": "mbpp-125",  // Value from state["id"]
  "conversation": [  // Result of build_conversation(state["messages"])
    {"role": "user", "content": "Write a function to check if a number is prime"},
    {"role": "assistant", "content": "Here's a function..."}
  ],
  "taxonomy": [  // Static value from configuration
    {
      "category": "Coding",
      "subcategory": ""
    }
  ],
  "annotation_type": ["mistral-large"],  // Static value
  "language": "en",  // Static value
  "tags": ["mbpp", "self-critique"]  // Static value
}
```

**Output Configuration Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `generator` | string | Fully qualified path to a class that inherits from `BaseOutputGenerator` |
| `output_map` | object | Map of output field names to mappings |
| `output_map.<field>.from` | string | State variable to get value from (mutually exclusive with `value`) |
| `output_map.<field>.value` | any | Static value for the field (mutually exclusive with `from`) |
| `output_map.<field>.transform` | string | Method name in the generator class to transform the value |

**Metadata in Output Map**

Metadata can be any supported data for the record, sometimes we want to put datasource as metadata.
However, datasource is already mentioned in the current YAML file. output_map value supports \$ variables which points to a node in the YAML.
\$ variables are only supported under `value` key.

Below example shows how a dictionary value can have \$ variables as dictionary values,
list values and direct string value. 
It can read the path with dot format, also supports list with subscript operator.

```yaml
output_config:
  output_map:
    id:
      from: "id"
    content:
      from: "text"
    metadata:
      value:
        source:
          - type: [$data_config.source.type, $data_config.source.config_name]
            location: $data_config.source.repo_id
          - type: $graph_config.nodes.extract_question.node_type
            location: $graph_config.nodes.extract_question.model.name
        start_node: $graph_config.edges[0].from
        author: john doe

```

### Custom Transformations

When using `transform` in the `output_map`, you must implement the corresponding method in your generator class:

```python
class CodeGenOutputGenerator(BaseOutputGenerator):
    """
    Example output generator with custom transformations
    """
    def build_conversation(self, data: Any, state: dict[str, Any]) -> Any:
        """
        Transform messages into a conversation format
        
        Args:
            data: The value from the state (from the 'from' field)
            state: The entire graph state
            
        Returns:
            The transformed value
        """
        chat_format_messages = utils.convert_messages_from_langchain_to_chat_format(data)
        
        # Example transformation logic:
        if chat_format_messages and "no more feedback" in chat_format_messages[-1]["content"].lower():
            # Remove the last message with "no more feedback"
            chat_format_messages = chat_format_messages[:-1]
            
        # Add additional messages or modify existing ones
        if "rephrased_text" in state and state["rephrased_text"]:
            # output keys can be directly accessed from state
            question = state["rephrased_text"].replace("PARAPHRASED QUESTION: ", "")
            chat_format_messages.insert(0, {"role": "user", "content": question})
            
        return chat_format_messages
```

### Fully Custom Output Generation

For more complex output generation logic, you can override the `generate()` method:

```python
class CustomOutputGenerator(BaseOutputGenerator):
    def generate(self, state: GraspState) -> dict[str, Any]:
        """
        Create a custom output record from the graph state
        
        Args:
            state: The final graph state
            
        Returns:
            The output record as a dictionary
        """
        # Custom logic to build the output record
        if "messages" not in state:
            return None  # Skip records that don't have messages
            
        # Build your output record with custom logic
        record = {
            "id": state.get("id", ""),
            "conversation": self._process_conversation(state["messages"]),
            "metadata": self._build_metadata(state),
            # Other fields...
        }
        
        return record
        
    def _process_conversation(self, messages):
        # Helper method for processing messages
        # ...
        
    def _build_metadata(self, state):
        # Helper method for building metadata
        # ...
```

The output generator is the final step in the pipeline and determines what data gets saved as the result of your synthetic data generation process.

## Full Example

Here's a complete example based on the code generation task:

```yaml
data_config:
  source:
    type: "hf"
    repo_id: "google-research-datasets/mbpp"
    config_name: "sanitized"
    split: ["train", "validation", "prompt"]

    transformations:
      - transform: grasp.processors.data_transform.RenameFieldsTransform
        params:
          mapping:
            task_id: id
          overwrite: false

graph_config:
  nodes:
    persona_sampler:
      node_type: weighted_sampler
      attributes:
        num_turns:
          values: [2, 3, 4, 5]
        tone1:
          values: [professional, casual, friendly, inquisitive, formal]
        persona1:
          values: [high school teacher, college professor, software engineer]

    paraphrase_question:
      node_type: llm        
      output_keys: rephrased_text
      prompt:
        - system: |
            Assume you are {persona1} persona.
            You are an assistant tasked with paraphrasing a user question.
        - user: |
            QUESTION: {prompt}. Write the program in python.      
      model:      
        name: mistralai      
        parameters:          
          temperature: 1.0

    generate_answer:  
      node_type: llm        
      prompt:
        - system: |
            You are an assistant tasked with solving python coding problems.
        - user: |
            {prompt}      
      model:      
        name: gpt-4o            # Must match a model defined in config/models.yaml
        parameters:             # Override default parameters from models.yaml
          temperature: 0.1
        
    critique_answer:  
      pre_process: grasp.tasks.mbpp.code_generation_with_graph_builder.task_executor.CritiqueAnsNodePreProcessor
      node_type: llm 
      output_role: user 
      prompt:        
        - system: |              
            You are a teacher grading a solution to a python coding problem.
          
            QUESTION: {prompt}            
            TEST CASES: {test_list}
      model:      
        name: gpt-4o
        parameters:          
          temperature: 1.0

  edges:
    - from: START
      to: persona_sampler
    - from: persona_sampler
      to: paraphrase_question
    - from: paraphrase_question
      to: generate_answer
    - from: generate_answer
      to: critique_answer
    - from: critique_answer
      condition: grasp.tasks.mbpp.code_generation_with_graph_builder.task_executor.ShouldContinueCondition
      path_map:
        END: END
        generate_answer: generate_answer

output_config:
  generator: grasp.tasks.mbpp.code_generation_with_graph_builder.task_executor.CodeGenOutputGenerator

  output_map:
    id:
      from: "id"
    conversation:
      from: "messages"
      transform: "build_conversation"
    taxonomy:
      value:
        - category: "Coding"
          subcategory: ""
    annotation_type:
      value: ["mistral-large"]
    language:
      value: "en"
    tags:
      value: ["mbpp", "reannotate", "self-critique"]
```

## Schema Validator

### Introduction

Schema validator enables users to ensure correctness of generated data before uploading to HF or File System.


Key features supported for schema validation are as follows: 

1. **YAML based schema check:** Users can define their schema using YAML config files in the following ways:-
   - Define a custom schema class inside `custom_schemas.py` and add it's path in `schema` key inside `schema_config`.
   - Add expected schema config in a list of dict format inside `fields` key inside `schema_config`.
   
2. **Rule based validation support:** Aside from adding validator rules inside custom class, users can choose from validation methods supported(details in additional validation rules section) and add it as a key for a particular field's dict.
   
### Usage Illustration

Let's assume we have the following record generated which we want to validate: 

```json
{
        "id": 130426,
        "conversation": [
            {
                "role": "user",
                "content": "I am trying to get the CPU cycles at a specific point in my code."
            },
            {
                "role": "assistant",
                "content": "The `rdtsc` function you're using gives you the number of cycles since the CPU was last reset, which is not what you want in this case."
            }
        ],
        "taxonomy": [
            {
                "category": "Coding",
                "subcategory": ""
            }
        ],
        "annotation_type": [
            "mistral-large"
        ],
        "language": [
            "en"
        ],
        "tags": [
            "glaiveai/glaive-code-assistant-v2",
            "reannotate",
            "self-critique"
        ]
}
```
For the above record, user can have the following class defined inside `custom_schemas.py` defining the 
expected keys and values along with additional validation rules if any. 

```python
class CustomUserSchema(BaseModel):
    '''
    This demonstrates an example of a customizable user schema that can be modified or redefined by the end user.
    Below is a sample schema with associated validator methods.
    '''
    id: int
    conversation: list[dict[str,Any]]
    taxonomy: list[dict[str, Any]]
    annotation_type: list[str]
    language: list[str]
    tags: list[str]

    @root_validator(pre=True)
    def check_non_empty_lists(cls, values):
        if not values.get('id'):
            raise ValueError('id cannot be empty')
        return values
```
#### Sample YAML configuration to use custom schema defined in `custom_schemas.py`

```yaml
schema_config:
  schema: grasp.validators.custom_schemas.CustomUserSchema
```
#### Sample YAML configuration to define schema in YAML: 

```yaml
schema_config:
  fields:
    - name: id
      type: int
      is_greater_than: 99999
    - name: conversation
      type: list[dict[str, any]]
    - name: taxonomy
      type: list[dict[str, any]]
    - name: annotation_type
      type: list[str]
    - name: language
      type: list[str]
    - name: tags
      type: list[str]
```
Note that `fields` is expected to be a list of dicts with `name` and `type` present in each dict with additional option
of providing validation key. In the above example `is_greater_than` is a validation key shown for demonstration purpose 
to ensure `id` key in each record has a value with 6 digits or more. 


## Post Generation Tasks
Post generation tasks are tasks that are executed after the graph has been executed. These tasks can be used to perform additional processing on the generated data, such as **OASST Mapper** and **Data Quality** tagging. 

### `Data mapper` or `oasst_mapper`

OASST Mapper enables users to transform data coming from output record generator into SFT/DPO format depending upon user's choice in the [OASST2 fomat](https://huggingface.co/datasets/OpenAssistant/oasst2).

By default, the Data Mapper is **disabled**. To enable it, add the following runtime argument:

```
--oasst True
```

You can refer to the data mapper [README](data_mapper/README.md) for more details on how to configure the OASST Mapper.

### `Data Quality` tagging

Data Quality tagging is a feature that allows users to tag the generated data with quality metrics which can be useful for evaluation of the generated data and act as a filtering mechanism during training.

By default, the Data Quality tagging is **disabled**. To enable it, add the following runtime argument:

```
--quality True
```
You can refer to the data quality tagging [README](data_quality/README.md) for more details on how to configure the Data Quality tagging.