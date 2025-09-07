# Data Mapper

## Introduction

**Data Mapper** enables users to transform data from an output record generator into **SFT** or **DPO** format, based on configuration preferences.

### Key Features

1. **YAML-Based Transformation Control**  
   Users can select the transformation format (SFT/DPO) by modifying the `required` and `type` keys under the `oasst_mapper` section in the configuration file.

2. **Automated Output Validation**  
   Once a transformation type is chosen, the output is automatically schema-validated—no manual validation required.

---

## Default Behavior

By default, the Data Mapper is **disabled**. To enable it, add the following runtime argument:

```
--oasst True
```

The default configuration is specified in the `configuration.yaml` file:

```yaml
oasst_mapper:
  required: "yes"
  type: "sft"
  intermediate_writing: "no"
```

- `required`: Indicates whether transformation is mandatory (`"yes"`).
- `type`: Defines the transformation format (`"sft"` or `"dpo"`).
- `intermediate_writing`: Enables saving intermediate files for debugging (`"yes"` or `"no"`).

---

## Usage Illustration

Given an input record like the following:

```json
{
  "id": 602,
  "conversation": [
    {
      "role": "user",
      "content": "How would you draft a Python function that identifies the initial recurring character in a specified string?"
    },
    {
      "role": "assistant",
      "content": "def first_repeated_char(s):\n    seen = set()\n    for char in s:\n        if char in seen:\n            return char\n        seen.add(char)\n    return None"
    }
  ],
  "taxonomy": [{"category": "Coding", "subcategory": ""}],
  "annotation_type": ["mistral-large"],
  "language": "en",
  "tags": ["mbpp", "reannotate", "self-critique"]
}
```

### To Transform

You can run the Data Mapper in two modes:

#### 1. Default Mode

Run with:

```
--oasst True
```

This uses the configuration specified in `configuration.yaml`:

```yaml
oasst_mapper:
  required: "yes"
  type: "sft"
  intermediate_writing: "no"
```

#### 2. Overridden Mode

To override the default behavior, modify the `output_config` section in your `graph_config.yaml` file like so:

```yaml
output_config:
  oasst_mapper:
    required: "yes"
    type: "sft"
    intermediate_writing: "yes"
```

> 💡 Set `intermediate_writing` to `"yes"` to store intermediate files before transformation (useful for debugging). If not provided or set to any other value, it defaults to `"no"`.
### Output Example

The transformed output will follow the selected format (e.g., SFT), like this:

```json
[
  {
    "conversation_id": "conv_8513aa73",
    "message_id": "msg_1_59a96096",
    "parent_id": null,
    "root_message_id": "msg_1_59a96096",
    "message_level": 1,
    "role": "user",
    "content": "...",
    ...
  },
  {
    "conversation_id": "conv_8513aa73",
    "message_id": "msg_2_e8b221e8",
    "parent_id": "msg_1_59a96096",
    "root_message_id": "msg_1_59a96096",
    "message_level": 2,
    "role": "assistant",
    "content": "...",
    ...
  }
]
```

---

## Rules for Using Data Mapping

1. To run in default mode, simply use the runtime flag `--oasst True`.
2. If you want to override defaults, define `oasst_mapper` inside `output_config` in the config file.
3. If `oasst_mapper` is defined, its keys must be:
   - `required`: must be `"yes"` or `"no"`
   - `type`: must be `"sft"` or `"dpo"`
   - `intermediate_writing`: optional, defaults to `"no"` if not `"yes"`
4. If keys are missing or values are invalid, exceptions will be raised.

---

## Additional Features

Support for **custom transformation types** and **custom validation schemas** is planned in a future release.