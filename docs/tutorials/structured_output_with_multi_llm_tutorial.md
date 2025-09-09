# Structured Output with Multi-LLM

This tutorial demonstrates how to use multiple LLMs in parallel for response generation and evaluation, with structured output and quality rating, using the GraSP framework. The example is based on the DPO (Direct Preference Optimization) Samples task.

> **Key Features You’ll Learn**  
> `multi-LLM processing`, `response evaluation`, `parallel model inference`, `quality rating`, `structured output schemas`

---

## Prerequisites

- GraSP framework installed (see [Installation Guide](../installation.md))
- Access to multiple LLMs (e.g., gpt4, gpt-4o, gpt-4o-mini)
- Familiarity with YAML and Python

---

## What You’ll Build

You’ll create a system that:
- **Sends prompts to multiple LLMs in parallel**
- **Collects and structures responses from each model**
- **Uses a judge model to rate each response**
- **Sorts and formats output by rating**

---

## Step 1: Project Structure

```
structured_output_with_multi_llm/
└── dpo_samples/
    ├── data_transform.py        # Data transforms for prompt extraction
    ├── graph_config.yaml        # Main workflow graph
    ├── task_executor.py         # Task logic and output formatting
    └── README.md                # Example documentation
```

---

## Step 2: Pipeline Implementation

### Parent Graph (`dpo_samples/graph_config.yaml`)

The main pipeline is defined in `structured_output_with_multi_llm/dpo_samples/graph_config.yaml`:

- **Data Source**: Loads conversation data from a JSON file, applying transformations to extract the user prompt, baseline response, and initialize state variables.
- **Nodes**:
  - `generate_samples`: A `multi_llm` node that sends the user prompt to multiple LLMs (gpt4, gpt-4o, gpt-4o-mini) with different structured output schemas. Pre-processing prepares the state for response collection.
  - `rate_samples`: An LLM node that acts as a judge, rating each model's response on a scale of 1-10 and providing explanations.
- **Edges**: The graph cycles between generating and rating samples, continuing until all quality buckets are covered or the maximum number of iterations is reached.
- **Output Config**: Custom output formatting is handled by the output generator in `task_executor.py`.

**Reference:** [dpo_samples/graph_config.yaml](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/structured_output_with_multi_llm/dpo_samples/graph_config.yaml)

### Task Executor (`task_executor.py`)

This file implements custom logic for the pipeline:
- **GenerateSamplesPreProcessor**: Initializes state variables and prepares for model response collection.
- **Output formatting**: Compiles and sorts all rated responses, structuring the final output.

**Reference:** [task_executor.py](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/structured_output_with_multi_llm/dpo_samples/task_executor.py)

## Step 3: Running the Pipeline

From your GraSP project root, run:

```bash
python main.py --task examples.structured_output_with_multi_llm.dpo_samples --num_records 1
```

---

## Example Output

```json
{
  "id": "test_id",
  "taxonomy": ["test_taxonomy"],
  "annotation_type": ["scale", "gpt4", "gpt-4o", "gpt-4o-mini"],
  "language": "en",
  "tags": ["dpo_samples_rating"],
  "conversation": [
    {
      "role": "user",
      "content": "What are the key considerations when designing a sustainable urban transportation system?"
    },
    {
      "role": "assistant",
      "content": [
        {
          "generation": { "message": "Designing a sustainable urban transportation system requires...", "success": true },
          "model": "gpt-4o",
          "judge_rating": 9,
          "judge_explanation": "This response provides comprehensive coverage of sustainability factors..."
        },
        {
          "generation": { "message": "When designing a sustainable urban transportation system...", "success": true },
          "model": "gpt4",
          "judge_rating": 8,
          "judge_explanation": "The response covers most key considerations..."
        },
        {
          "generation": "A sustainable urban transportation system should focus on...",
          "model": "gpt-4o-mini",
          "judge_rating": 6,
          "judge_explanation": "The response covers basic aspects but lacks depth..."
        }
      ]
    }
  ]
}
```

---

## Try It Yourself

- Add more models or change schemas for advanced evaluation
- Use your own dataset and rating criteria

---

## Next Steps

- Explore [agent simulation](agent_simulation_tutorial.md) for multi-agent conversations
- Explore [self-improving code generation](glaive_code_assistant_tutorial.md) with iterative refinement
