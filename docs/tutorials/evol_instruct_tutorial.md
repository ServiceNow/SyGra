# Evolution of Prompts with Evol-Instruct

This tutorial demonstrates how to use the [Evol-Instruct](https://arxiv.org/pdf/2304.12244) in the GraSP framework to automatically evolve prompts into more complex and nuanced instructions.

> **Key Features You’ll Learn**  
> `prompt evolution`, `subgraphs`, `automated prompt engineering`, `depth/breadth techniques`, `prompt transformation`

---

## Prerequisites

- GraSP framework installed (see [Installation Guide](../installation.md))
- Basic Python and YAML knowledge

---

## What You’ll Build

You’ll create a system that:
- **Loads simple prompts** from a dataset
- **Applies evolution techniques** to make them more complex
- **Uses a subgraph to transform prompts**

---

## Step 1: Project Structure

```
evol_instruct/
├── task_executor.py     # Outputs evolved text
├── graph_config.yaml    # Workflow graph
├── test.json            # Sample prompts
```

## Step 2: Data Loading

- Loads prompts from `test.json`, e.g.:

```json
[
  { "text": "tell me a story about a jungle and river." }
]
```

## Step 3: Pipeline Implementation

### Parent Graph (`graph_config.yaml`)

The main pipeline is defined in `evol_instruct/graph_config.yaml`:

- **Data Source**: Loads prompts from `test.json` (a list of simple instructions or questions).
- **Nodes**:
  - `evol_text`: A subgraph node that references the Evol-Instruct recipe in `grasp/recipes/evol_instruct`. This node applies random evolution techniques to the prompt (e.g., adding constraints, requiring reasoning, or generating rare/specialized prompts).
  - `query_llm`: An LLM node that receives the evolved prompt and generates a response. The prompt simply passes the evolved text to the model.
- **Edges**: The workflow is linear: prompt → evolution subgraph → LLM response → END.
- **Output Config**: Maps the original prompt, evolved prompt, and LLM response to the final output structure.

**Reference:** [evol_instruct/graph_config.yaml](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/evol_instruct/graph_config.yaml)

### Evol-Instruct Subgraph (Internal) (`grasp/recipes/evol_instruct/graph_config.yaml`)

The subgraph, referenced by the parent graph, is defined in `grasp/recipes/evol_instruct/graph_config.yaml`:

- **build_text_node**: A lambda node that applies the `EvolInstructPromptGenerator` to transform the original prompt using a random evolution technique.
- **evol_text_node**: An LLM node that receives the evolved instruction and outputs the evolved text.
- **Edges**: The flow is: build_text_node → evol_text_node → END.

**Reference:** [grasp/recipes/evol_instruct/graph_config.yaml](https://github.com/ServiceNow/GraSP/blob/main/grasp/recipes/evol_instruct/graph_config.yaml)

## Step 4: Output Collection

- Results are structured as:

```json
[
  {
    "id": 1,
    "text": "tell me a story about a jungle and river.",
    "evolved_text": "Compose a story set in a jungle with a river, incorporating a mythical creature or legend as a key element.",
    "llm_response": "In the heart of the lush Amazon jungle ..."
  }
]
```

## Step 5: Running the Pipeline

From your GraSP project root, run:

```bash
python main.py --task path/to/your/evol_instruct
```

Or use the CLI:

```bash
grasp run path/to/your/evol_instruct
```

---

## Try It Yourself

- Add new prompts to `test.json`
- Experiment with custom evolution techniques

---

## Next Steps

- Explore [custom subgraphs](custom_subgraphs_tutorial.md) for modular workflows
- Learn about [structured output](structured_output_tutorial.md) for standardized results