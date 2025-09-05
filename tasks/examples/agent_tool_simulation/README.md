# Agent Tool Simulation

This example demonstrates how to integrate external tools with AI agents using the GraSP framework. It showcases how to structure and use function calling with agents to perform tasks requiring specific capabilities, in this case mathematical operations.

> **Key Features**:
> `function calling`, `tool integration`, `mathematical operations`, `class-based tools`, `module-based tools`

## Overview

The agent tool simulation is designed to:

- **Demonstrate tool integration**: Show how to connect external functions as tools to agents
- **Showcase multiple tool sources**: Illustrate different approaches to defining and importing tools
- **Implement tool-based reasoning**: Enable agents to decompose problems and select appropriate tools

## Directory Contents

- `task_executor.py`: Contains post-processing logic for the tool-using agent
- `graph_config.yaml`: Configuration file defining the workflow graph and tool imports
- `tools.py`: Basic tools defined as standalone functions
- `tools_from_class.py`: Tools defined as methods within a class
- `tools_from_module.py`: Module-level tools that can be imported as a group
- `user_queries.json`: Sample mathematical queries to test the agent with tools

## How It Works

1. **Query Loading**: The system loads math questions from `user_queries.json`

2. **Tool Configuration**: The agent is configured with access to multiple math operation tools:
   - Addition function from standalone module
   - Subtraction and division methods from a class
   - Multiplication function from another module

3. **Agent Processing**:
   - The agent receives a mathematical query
   - It analyzes which tools are needed to solve the problem
   - It calls the appropriate tools with the correct parameters
   - The agent combines tool outputs to produce a final answer

4. **Result Capture**:
   - The `MathAgentPostProcessor` extracts the calculated result
   - The system stores this in the state for structured output
