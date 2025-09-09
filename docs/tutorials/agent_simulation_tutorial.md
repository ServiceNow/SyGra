# Agent Simulation Tutorial

This tutorial walks you through creating structured AI agent dialogues with opposing viewpoints using the GraSP framework. By the end, you’ll have built a system that orchestrates realistic, multi-turn conversations between dynamically generated personas on specific topics.

> **Key Features You’ll Learn**  
> `agent nodes`, `chat history`, `system message intervention`, `multi-turn dialogue`, `multi-agent`

---

## Prerequisites

Before you begin, make sure you have:

- GraSP framework installed and configured (see [Installation Guide](../installation.md))  
- A basic understanding of YAML configuration files  
- Access to an LLM API or local model for generating agent responses  

---

## What You’ll Build

In this tutorial, you’ll create a system that:

- **Generates realistic debates**: Builds authentic dialogues with contrasting perspectives  
- **Guides conversation arcs**: Manages full conversations from greeting to conclusion  
- **Uses system interventions**: Injects strategic system messages to guide the flow  

---

## Step 1: Project Structure

Your project directory in this tutorial looks like this:

```
agent_simulation/
├── task_executor.py     # Core functionality 
├── graph_config.yaml    # Workflow graph configuration
└── categories.json      # Topics for agent conversations
```

## Step 2: Defining Conversation Topics

The `categories.json` file lists potential conversation topics. Start with a simple example:

```json
[
  {
    "category": "Health",
    "subcategory": "Yoga"
  }
]
```

You can expand this list with more categories and subcategories as needed.


## Step 3: Understanding the Conversation Flow

The simulation follows this workflow:

1. **Topic selection** – The system loads a category/subcategory (e.g., Health/Yoga)  
2. **Persona generation** – Two distinct personas with opposing viewpoints are created  
3. **Conversation initialization** – A random agent begins with a greeting  
4. **Turn-based discussion** – Agents respond to one another, guided by system interventions  
5. **Conversation conclusion** – Ends when an agent outputs `"FINAL ANSWER"`  


## Step 4: Pipeline Implementation

### Graph Configuration (`graph_config.yaml`)

Defines the conversation structure and flow, including:

- **Persona generation**: A node that creates two distinct personas with different viewpoints  
- **Agent nodes**: Separate nodes for each conversational agent  
- **System interventions**: Strategic system messages injected at specific turns (e.g., turns 3 and 5)  
- **Edge conditions**: Rules that control conversation flow and termination  

### Task Executor (`task_executor.py`)

Implements the processing logic for your nodes:

- **Post-processors** – Extract and format agent personas  
- **Pre-processors** – Prepare agents before each turn  
- **Edge conditions** – Manage turn switching and when to end the conversation  
- **Output formatting** – Structure the final conversation output  

### Reference Implementation

See the GraSP repository for complete examples:

- Graph configuration: [`graph_config.yaml`](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/agent_simulation/graph_config.yaml)  
- Task executor: [`task_executor.py`](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/agent_simulation/task_executor.py)  


## Step 5: Creating Your Own Implementation

To build your own simulation:

1. **Define agent personas** – Generate distinct personas with opposing viewpoints  
2. **Set up turn taking** – Implement sequential agent responses  
3. **Add system interventions** – Configure strategic message injections (e.g., to deepen debate or wrap up)  
4. **Define conversation flow** – Create edge conditions to control agent switching and termination  
5. **Format output** – Generate structured conversation history and taxonomy  


## Step 6: Running the Simulation

From your GraSP project root, run:

```bash
python main.py --task path/to/your/agent_simulation
```

Or use the CLI:

```bash
grasp run path/to/your/agent_simulation
```

---

## Try It Yourself

Extend this tutorial by:

1. **Adding more topics** – Expand `categories.json` with new categories and subcategories  
2. **Creating personality modifiers** – Add debate styles to your persona generator  
3. **Adding emotional trajectories** – Guide the emotional tone of the conversation  

---

## Example Output

Here’s a sample output (your results will vary based on LLM responses):

```json
[
  {
    "id": "<conversation_id>",
    "conversation": [
      {
        "user": "Open the dialogue with respectful greetings. Remain in character and begin discussing the assigned topic."
      },
      {
        "agent_2": "Hello. Let's dive into the subject of yoga. I'm interested in its physical benefits, but I’m skeptical about the spiritual claims. What evidence supports these?"
      },
      {
        "agent_1": "Greetings. Yoga’s physical benefits are well-documented, but its mental and spiritual aspects are harder to quantify. Still, studies link yoga to reduced anxiety and improved mindfulness, which many practitioners interpret as spiritual growth. How does that align with your perspective?"
      }
      // Additional turns omitted for brevity
    ],
    "taxonomy": [
      {
        "category": "Health",
        "subcategory": "Yoga"
      }
    ]
  }
]
```

---

## Next Steps

- Learn how to [use tool interventions](agent_tool_simulation_tutorial.md) for more grounded conversations  
- Explore [structured output](structured_output_tutorial.md) to format results  
