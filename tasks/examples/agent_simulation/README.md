# Agent Simulation

This example demonstrates how to create structured AI agent dialogues with opposing viewpoints using the GraSP framework. It showcases a directed graph implementation that orchestrates a realistic, multi-turn conversation between two dynamically generated personas discussing a specific topic using agentic nodes.

## Overview

The agent simulation is designed to:

- **Generate realistic debates**: Create authentic dialogue with contrasting perspectives on specific topics
- **Guide conversational arcs**: Manage a complete conversation from greeting to conclusion
- **Illustrate system interventions**: Use strategic message injection to guide conversation depth and structure

## Directory Contents

- `task_executor.py`: Core functionality for the agent simulation
- `graph_config.yaml`: Configuration file defining the workflow graph
- `categories.json`: Sample categories/topics for agent conversations

## How It Works

1. **Topic Selection**: The system loads a category and subcategory from `categories.json` (e.g., Health/Yoga)

2. **Persona Generation**: The `persona_assignor` node creates two distinct personas relevant to the topic:
   - Assigns roles (one-word names) for each agent
   - Generates detailed prompts that define each agent's background, communication style, and stance

3. **Conversation Initialization**: 
   - A random agent is selected to start the conversation
   - The agent begins with a greeting that establishes their character and introduces the topic

4. **Turn-Based Discussion**:
   - Agents respond to each other's messages in turns
   - After turn 3, system messages encourage deeper discussion
   - After turn 5, system messages guide the agents to begin wrapping up

5. **Conversation Conclusion**:
   - The conversation ends when an agent includes "FINAL ANSWER" in their response
   - The system generates structured output including the conversation history and taxonomy

## Usage

To modify the topics for discussion, edit the `categories.json` file with new categories and subcategories.

To customize the agent behaviors:
- Adjust the prompt templates in `graph_config.yaml`
- Modify the system messages injected at specific turns
- Change the model parameters like temperature to control response variability

