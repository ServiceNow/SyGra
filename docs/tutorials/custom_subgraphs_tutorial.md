# Custom Subgraphs

This tutorial shows how to create and use custom subgraphs in the SyGra framework. You’ll learn to build modular, reusable graph components for complex AI workflows.

> **Key Features You’ll Learn**  
> `custom subgraphs`, `modular design`, `code generation`, `self-critique`, `feedback loops`

---

## Prerequisites

- SyGra framework installed (see [Installation Guide](../installation.md))
- Understanding of YAML workflow configuration
- Python basics

---

## What You’ll Build

You’ll create a system that:
- **Loads programming problems** from a dataset
- **Uses subgraphs** to process, paraphrase, and solve problems
- **Implements feedback loops** for iterative improvement

---

## Step 1: Project Structure

```
custom_subgraphs/
├── task_executor.py                # Orchestrates subgraph execution and feedback
├── graph_config.yaml               # Main workflow graph with subgraph references
├── generate_question_subgraph/
│   └── graph_config.yaml           # Subgraph for question generation
```

## Step 2: Subgraph and Main Graph

- **Subgraph**: Handles persona sampling and question paraphrasing
- **Main graph**: Receives paraphrased question, generates solution, then critiques and refines

## Step 3: Pipeline Implementation

### Parent Graph (`graph_config.yaml`)

The main pipeline is defined in `custom_subgraphs/graph_config.yaml`:

- **Data Source**: Loads programming problems from the MBPP dataset (Google's "sanitized" split), renaming `task_id` to `id` for consistency.
- **Nodes**:
  - `generate_question`: A subgraph node that references the subgraph in `generate_question_subgraph`. It handles persona sampling and question paraphrasing.
  - `generate_answer`: An LLM node that receives the paraphrased question and generates a code solution. The prompt instructs the model to respond only with code and revise based on critique.
  - `critique_answer`: An LLM node with a custom pre-processor. It acts as a teacher, using provided test cases to critique the generated solution and recommend improvements. If the answer is correct, it responds with 'NO MORE FEEDBACK'.
- **Edges**: The graph cycles between answer generation and critique, controlled by a custom edge condition (`ShouldContinue`). The loop ends if the solution is correct or after a maximum number of rounds.
- **Output Config**: Custom output formatting is handled by the output generator in `task_executor.py`.

**Reference:** [custom_subgraphs/graph_config.yaml](https://github.com/ServiceNow/SyGra/blob/main/tasks/examples/custom_subgraphs/graph_config.yaml)

### Subgraph (`generate_question_subgraph/graph_config.yaml`)

The subgraph, referenced by the parent graph, is defined in `generate_question_subgraph/graph_config.yaml`:

- **persona_sampler**: Samples random personas and communication styles for the paraphrasing step.
- **paraphrase_question**: Uses an LLM to paraphrase the user question according to the sampled persona, preserving all relevant details and outputting a clearly marked paraphrased question.
- **Edges**: The workflow is linear: persona sampling → paraphrasing → END.

**Reference:** [generate_question_subgraph/graph_config.yaml](https://github.com/ServiceNow/SyGra/blob/main/tasks/examples/custom_subgraphs/generate_question_subgraph/graph_config.yaml)

### Task Executor (`task_executor.py`)

This file implements custom logic for the pipeline:
- **CritiqueAnswerNodePreProcessor**: Prepares conversation state for grading by the critique node.
- **ShouldContinue**: Custom edge condition to control the critique/answer loop, ending when the solution is correct or after 8 rounds.
- **CustomSubgraphsOutputGenerator**: Formats the output to include all conversation turns, critiques, and improvements.

**Reference:** [task_executor.py](https://github.com/ServiceNow/SyGra/blob/main/tasks/examples/custom_subgraphs/task_executor.py)

## Step 4: Running the Pipeline

From your SyGra project root, run:

```bash
python main.py --task path/to/your/custom_subgraphs
```

---

## Example Output

```json
[
    {
        "id": 602,
        "conversation": [
            { "role": "user", "content": "Could you provide a Python function that identifies the first character that repeats in a specified string?" },
            { "role": "assistant", "content": "def first_repeating_character(s): ..." }
        ],
        "metadata": {
            "original_question": "Write a python function to find the first repeated character in a given string.",
            "rephrased_text": "PARAPHRASED QUESTION: Could you provide a Python function that identifies the first character that repeats in a specified string?",
            "taxonomy": [ { "category": "Coding", "subcategory": "" } ],
            "tags": ["mbpp","reannotate","self-critique"]
        }
    }
]
```

---

## Try It Yourself

- Create new subgraphs for other workflow steps
- Adjust persona or critique logic
- Add more feedback cycles for complex tasks

---

## Next Steps

- Explore [self-improving code generation](glaive_code_assistant_tutorial.md) with iterative refinement
- Learn about [structured output](structured_output_tutorial.md) for standardized results
