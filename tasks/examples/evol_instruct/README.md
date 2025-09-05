# Evol-Instruct

This example demonstrates how to use a subgraph within the GraSP framework. It showcases usage of [Evol-Instruct](https://arxiv.org/pdf/2304.12244) recipe which is a evolution techniques that can transform simple prompts into more complex, nuanced, and challenging instructions through automated prompt engineering.

## Overview

The Evol-Instruct example is designed to:

- **Transform simple prompts**: Evolve basic instructions into more sophisticated variants
- **Apply various evolution techniques**: Implement depth-based (constraints, deepening, concretizing, reasoning) and breadth-based transformations

## Directory Contents

- `task_executor.py`: Core functionality for outputting evolved text
- `graph_config.yaml`: Configuration file defining the workflow graph
- `test.json`: Sample input prompts for evolution

## How It Works

1. **Input Prompts**:
   - The system loads simple prompts from `test.json`
   - Each prompt is a basic instruction or question (e.g., "tell me a story about a jungle and river")

2. **Evolution Process**:
   - The prompt is passed to the `evol_text` subgraph (defined in [recipes/evol_instruct](../../../grasp/recipes/evol_instruct/Readme.md))
   - The `EvolInstructPromptGenerator` lambda function transforms the input prompt
   - A random evolution technique is applied from available methods:
     - **Depth techniques**: Add constraints, increase depth/breadth, concretize concepts, require multi-step reasoning
     - **Breadth technique**: Create a new prompt in the same domain but more rare/specialized

3. **Transformation**:
   - The evolved prompt is processed by the LLM in the subgraph
   - The result is a more complex version of the original prompt
   - The evolved text is passed to the main graph's `query_llm` node

4. **Response Generation**:
   - The LLM responds to the evolved prompt
   - The system captures both the original text, evolved text, and the LLM response

## Usage

This example demonstrates techniques for:
- Creating more challenging and nuanced prompts using a seed data
- Using subgraphs for modular functionality

To customize this example:
- Modify the evolution techniques in the recipe files
- Change the algorithm selection logic (currently random)
- Adjust the model parameters for different response characteristics
- Create new evolution techniques by adding your own subgraphs or extending the recipe
