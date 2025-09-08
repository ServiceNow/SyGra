# Glaive Code Assistant Tutorial

This tutorial shows how to build a self-improving code assistant using the GraSP framework. You’ll implement a feedback loop where an LLM generates code, critiques its own answers, and refines them iteratively.

> **Key Features You’ll Learn**  
> `self-critique`, `iterative refinement`, `code generation`, `feedback loop`, `stopping conditions`

---

## Prerequisites

- GraSP framework installed (see [Installation Guide](../installation.md))
- Familiarity with Python and coding problems

---

## What You’ll Build

You’ll create a system that:
- **Loads coding problems** from a dataset
- **Generates code solutions** using an LLM
- **Evaluates solutions against references**
- **Refines answers based on critique**

---

## Step 1: Project Structure

```
glaive_code_assistant/
├── task_executor.py     # Critique cycle logic
├── graph_config.yaml    # Workflow graph
```


## Step 2: Pipeline Implementation

### Parent Graph (`graph_config.yaml`)

The main pipeline is defined in `glaive_code_assistant/graph_config.yaml`:

- **Data Source**: Loads coding problems from the `glaiveai/glaive-code-assistant-v2` HuggingFace dataset, renaming `task_id` to `id`.
- **Nodes**:
  - `generate_answer`: An LLM node that generates a code solution based on the question. The prompt instructs the model to respond only with code and revise based on critique.
  - `critique_answer`: An LLM node with custom pre- and post-processors. It acts as a teacher, using the reference solution to critique the generated answer and recommend improvements. If the answer is correct, it responds with 'NO MORE FEEDBACK'.
- **Edges**: The graph cycles between answer generation and critique, controlled by a custom edge condition (`ShouldContinueCondition`). The loop ends if the solution is correct or after a maximum number of rounds.
- **Output Config**: Custom output formatting is handled by the output generator in `task_executor.py`.

**Reference:** [glaive_code_assistant/graph_config.yaml](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/glaive_code_assistant/graph_config.yaml)

### Task Executor (`task_executor.py`)

This file implements custom logic for the pipeline:
- **CritiqueAnsNodePreProcessor**: Prepares conversation state for grading by the critique node.
- **CritiqueAnsNodePostProcessor**: Updates the state after critique.
- **ShouldContinueCondition**: Custom edge condition to control the critique/answer loop, ending when the solution is correct or after 8 rounds.
- **CodeGenOutputGenerator**: Formats the output to include all conversation turns, critiques, and improvements.

**Reference:** [task_executor.py](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/glaive_code_assistant/task_executor.py)

## Step 3: Output Collection

- Collects all turns, critiques, and improvements in a structured format


## Step 4: Running the Pipeline

From your GraSP project root, run:

```bash
python main.py --task path/to/your/glaive_code_assistant
```

Or use the CLI:

```bash
grasp run path/to/your/glaive_code_assistant
```

---

## Example Output

```json
[
  {
    "id": "299392dcbd6a991853554c2869deeff6f97b13db6a3a4c7f6e25fb41778dafc2",
    "conversation": [
      { "role": "user", "content": "I want to create a function in Python that checks whether a given substring is present in a given string. How can I do that?" },
      { "role": "assistant", "content": "def is_substring_present(main_string, substring): return substring in main_string" },
      { "role": "user", "content": "NO MORE FEEDBACK" }
    ],
    "taxonomy": [ { "category": "Coding" } ],
    "tags": [ "glaiveai/glaive-code-assistant-v2", "reannotate", "self-critique" ]
  }
]
```

---

## Try It Yourself

- Add new coding problems
- Adjust critique logic for stricter or more lenient feedback

---

## Next Steps

- Explore [custom subgraphs](custom_subgraphs_tutorial.md) for modular workflows
- Learn about [structured output](structured_output_tutorial.md) for standardized results
