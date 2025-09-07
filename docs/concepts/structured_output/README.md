# Structured Output Generation 

## 📌 Introduction

This module introduces a flexible and extensible framework to generate and validate **structured outputs** from LLMs. It
is designed to work **natively with Azure OpenAI, VLLM and Ollama**, leveraging their structured output capabilities, while
providing **fallback support for any other LLM or custom model wrapper** through JSON schema-based validation.
### 🔧 Why This is Helpful

- Ensures consistent and reliable response formats from LLMs during data generation to reduce the post processing effort.
- Eliminates the need for brittle regex or manual parsing of raw LLM outputs.
- Allows easy plug-and-play validation via **Pydantic classes** or **YAML-based schema configs**.

---

## 🚀 Key Features


- **Structured Output Modes**:
  - **Class-based schema**: Define a Python class for validating output (e.g., using Pydantic).
  - **YAML-defined schema**: Use simple YAML to define structure and field-level validation rules.
- **Dynamic Type-Fetching**:
  - User simply needs to point their schema correctly to either of the above two choices. The type of schema desired and required processing for it is handled dynamically. 
- **Flexible Integration**:
  - Plug structured output validation into any LLM pipeline with minimal code changes.
  - Easily extend by defining your own schemas or rules.

---

## ⚙️ Architecture Overview

Each node in a task graph can be defined with:
- Model name (e.g., `gpt-4o`, `llama3-8b`)
- Parameters (e.g., `temperature`)
- Structured output config:
  - Class-based (`type: class`)
  - Schema-based (`type: schema`)

```yaml
nodes:
  node1:
    node_type: llm
    model:
      name: gpt-4o
      parameters:
        temperature: 0.1
    structured_output:
      enabled: true
      schema: "grasp.core.models.structured_output.schemas_factory.CustomUserSchema"

  node2:
    node_type: llm
    model:
      name: llama3-8b
      parameters:
        temperature: 0.2
    structured_output:
      enabled: true
      schema:
        fields:
          answer:
            type: str
            description: "The main answer"
          confidence:
            type: float
            description: "Confidence score"
```

## ✍️ How to Define a Schema

Structured output schema can be defined in two ways depending on your use case:

---

### ✅ Option 1: Using Python Class (Pydantic)

This is the preferred approach if you want to write custom validation logic or reuse complex types.

1. Define your schema class in `<your_local_path>`:

```python
from pydantic import BaseModel, root_validator, model_validator, Field
from typing import Any


class SimpleResponse(BaseModel):
    """Simple response with just text and status"""
    message: str = Field(description="Response message")
    success: bool = Field(default=True, description="Operation success status")

   @model_validator(pre=True)
   def check_non_empty_messages(cls, values):
      if not values.get('message'):
         raise ValueError('message cannot be empty')
      return values
```

2. Then point to it in your YAML config:

```yaml
structured_output:
    enabled: true
    schema: "<your_local_path>.SimpleResponse"
```
### ✅ Option 2: Using YAML (No Code Schema Definition)

This is ideal for quick prototyping or use cases where no custom Python logic is needed.
```yaml
 structured_output:
   enabled: true
   schema:
     fields:
       answer:
         type: str
         description: "The main answer"
       confidence:
         type: float
         description: "Confidence score"
```
## 📏 Rules for Using Schema Validation

To ensure the structured output validation runs smoothly, follow these rules:

---

### 🔹 General Rules

**1. Structured Output Generation is triggered only when `structured_output` is defined**:
   - `schema` key must be present and must point to a valid pydantic class path or contain a dict defining desired output schema. Additional rules for class based schema definition or YAML based schema definition are described below. 

**2. `enabled` is optional**:
   - If the `structured_output` key is **present** in the node’s YAML config, `enabled` is set to **true** by default.
   - Use this when you want to turn off `structured_output_generation` but want to preserve schema config make in `YAML`.
---

### 🔹 For Class-Based Schemas

- Must inherit from `pydantic.BaseModel`.
- Can use `@model_validator` or `@validator` for custom rules.
- The class path provided must be **fully qualified**, e.g. `<your_local_path>>.CustomUserSchema`.

---

### 🔹 For YAML-Based Schemas

- Must be defined inside `fields` key inside `schema` key.
- Type for each field must be valid Python type.
---

## 📝 Limitations

- Native structured output generation is currently supported exclusively for `vllm`, `azure_openai`, `tgi` and `ollama` ModelTypes.
- For OpenAI ModelType, structured output functionality requires API versions `2024-08-01-preview` or later.
- For VLLM ModelType, structured output functionality requires version `0.8.4` or later.
- For all other ModelTypes, structured output generation is supported through fallback JSON schema validation.

