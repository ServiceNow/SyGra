# Structured Output

This tutorial shows how to implement structured output from LLM responses using the GraSP framework. You’ll learn to extract specific information from LLM outputs in a standardized JSON format.

> **Key Features You’ll Learn**  
> `structured JSON output`, `schema definition`, `post-processing`, `code taxonomy`, `response normalization`

---

## Prerequisites

- GraSP framework installed (see [Installation Guide](../installation.md))
- Familiarity with Python and JSON

---

## What You’ll Build

You’ll create a system that:
- **Loads code snippets** from a dataset
- **Extracts structured data** (category, subcategory) from LLM responses
- **Handles parsing and formatting for downstream use**

---

## Step 1: Project Structure

```
structured_output/
├── task_executor.py     # Structured data extraction
├── graph_config.yaml    # Workflow graph and schema
```


## Step 2: Pipeline Implementation

### Parent Graph (`graph_config.yaml`)

The main pipeline is defined in `structured_output/graph_config.yaml`:

- **Data Source**: Loads code snippets from the `glaiveai/glaive-code-assistant-v2` HuggingFace dataset, renaming `task_id` to `id`.
- **Nodes**:
  - `generate_taxonomy`: An LLM node with a prompt instructing the model to extract the category and subcategory from the code snippet. The node uses a structured output schema for reliable extraction and a post-processor for normalization.
- **Edges**: The workflow is linear: data → taxonomy extraction → END.
- **Output Config**: Maps the question, category, and subcategory from the state to the final output structure.

**Reference:** [structured_output/graph_config.yaml](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/structured_output/graph_config.yaml)

### Task Executor (`task_executor.py`)

This file implements custom logic for the pipeline:
- **GenerateTaxonomyPostProcessor**: Extracts structured data from the LLM output, handling JSON parsing and normalization.

**Reference:** [task_executor.py](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/structured_output/task_executor.py)


## Step 3: Output Formatting

- Formats the final output with:
  - Original question ID and content
  - Extracted category and subcategory


## Step 4: Running the Pipeline

From your GraSP project root, run:

```bash
python main.py --task path/to/your/structured_output
```

---

## Example Output

```json
[
    {
        "id": "20705cc57af2ec0d2ea976de82a4c833f915d6a0bd6b3e3b508c3a4edf213743",
        "question": "I have a field that contains a string of numbers like '2002 2005 2001 2006 2008 2344'...",
        "category": "Database",
        "sub_category": "SQL Query"
    }
]
```

---

## Try It Yourself

- Change the schema to extract different fields
- Use your own dataset for testing

---

## Next Steps

- Explore [structured output with multi-LLM](structured_output_with_multi_llm_tutorial.md) for advanced scenarios
- Learn about [agent simulation](agent_simulation_tutorial.md) for multi-agent conversations
