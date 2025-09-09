# Agent Tool Simulation Tutorial

This tutorial guides you through integrating external tools with AI agents using the GraSP framework. By the end, you’ll have a system where agents can call mathematical functions implemented as Python modules, classes, or standalone functions.

> **Key Features You’ll Learn**  
> `function calling`, `tool integration`, `mathematical operations`, `class-based tools`, `module-based tools`

---

## Prerequisites

Before you begin, make sure you have:

- GraSP framework installed and configured (see [Installation Guide](../installation.md))
- Basic understanding of Python modules and function/class definitions
- Access to an LLM API or local model for agent reasoning

---

## What You’ll Build

You’ll create an agent that:

- **Receives math queries** (e.g., "Multiply 2 and 3, then subtract 1")
- **Selects and calls appropriate tools** (addition, subtraction, multiplication, division)
- **Combines tool outputs** to produce a final answer

---

## Step 1: Project Structure

Directory structure in this tutorial:

```
agent_tool_simulation/
├── task_executor.py         # Post-processing logic for tool-using agent
├── graph_config.yaml        # Workflow graph and tool imports
├── tools.py                 # Standalone function tools
├── tools_from_class.py      # Tools as class methods
├── tools_from_module.py     # Tools as module-level functions
├── user_queries.json        # Sample math queries
```

## Step 2: Defining Tools and Queries

- `tools.py`: Functions like `add(a, b)`
- `tools_from_class.py`: Class with methods for subtraction/division
- `tools_from_module.py`: Module with multiplication, etc.
- `user_queries.json`: Sample queries, e.g.:

```json
[
  { "user_query": "What is 3/2?" },
  { "user_query": "What is (2+3)*5?" }
]
```

## Step 3: Workflow Overview

1. **Query Loading**: System loads questions from `user_queries.json`
2. **Tool Configuration**: Agent is given access to all relevant tools
3. **Agent Processing**:
   - Receives a query
   - Decides which tools to call and in what order
   - Calls tools via function calling
   - Combines results
4. **Result Capture**: Post-processor extracts the answer for output

## Step 4: Pipeline Implementation

### Graph Configuration (`graph_config.yaml`)

The `graph_config.yaml` file defines the workflow for the agent tool simulation task. Here’s what it does:

- **Data Source**: Specifies that user queries are loaded from `user_queries.json`.
- **Nodes**: Defines a single `math_agent` node of type `agent`. This node is configured with:
  - **Tools**: Lists all available mathematical tools, including standalone functions, class-based methods, and module-level tools. These are imported and made available for function calling by the agent.
  - **Prompt**: Provides the system and user prompts, instructing the agent on how to use the tools for arithmetic operations.
  - **Model**: Sets the LLM to use (e.g., gpt-4o) and its parameters.
- **Edges**: Establishes the flow from `START` to `math_agent` and then to `END`, representing a single-step reasoning process.
- **Output Config**: Maps the output fields (`id`, `user_query`, `math_result`) from the agent’s state to the final output structure.

### Task Executor (`task_executor.py`)

The `task_executor.py` file implements the post-processing logic for the agent node:

- **MathAgentPostProcessor**: This class extracts the agent’s answer from the LLM response and stores it in the state under the key `math_result`. This enables the output mapping defined in the graph config.
- The post-processor ensures that the final output always contains the computed answer in a structured format.

### Reference Implementation

See the GraSP repository for complete examples:

- Graph configuration: [agent_tool_simulation/graph_config.yaml](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/agent_tool_simulation/graph_config.yaml)
- Task Executor: [agent_tool_simulation/task_executor.py](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/agent_tool_simulation/task_executor.py)

## Step 5: Running the Simulation

From your GraSP project root, run:

```bash
python main.py --task path/to/your/agent_tool_simulation
```

Or use the CLI:

```bash
grasp run path/to/your/agent_tool_simulation
```

---

## Example Output

```json
[
    {
        "id": "6b9e75c4fe9b803f0c6f1dd59081750fa100db56874a12b0b83683b7ea9a0c8b",
        "user_query": "Can you give me answer for 3/2?",
        "math_result": "The result of ( 3/2 ) is 1.5."
    },
    {
        "id": "e79908ac2f64bbdf7611c307ba3b73f647a2bbcf06d42e9c16c6321aa9ac3e1d",
        "user_query": "Can you give me answer for (2+3)*5?",
        "math_result": "The answer to ((2+3) × 5) is (25)."
    },
    {
        "id": "6af6cadbfaa3eda3b9eb678dece24dac211c8bd3cd62e8742d8364422cfeecb2",
        "user_query": "Can you give me answer for multiplying 2 and 3 and then subtract 1 from answer?",
        "math_result": "The result of multiplying 2 and 3 and then subtracting 1 is 5."
    }
]
```

---

## Try It Yourself

- Add more mathematical tools (e.g., exponentiation)
- Modify `user_queries.json` with new queries
- Implement more complex reasoning chains

---

## Next Steps

- Explore [agent simulation](agent_simulation_tutorial.md) for multi-agent conversations
- Learn about [structured output](structured_output_tutorial.md) for standardized results
