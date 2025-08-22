## Agent Node

GraSP supports creating and executing agents using the ReAct (Reasoning and Acting) framework. Agent nodes extend LLM nodes with additional capabilities for tool usage, reasoning, and autonomous decision-making.

To use it, include the following configuration in your `graph_config.yaml` file:

### Example Configuration:

```yaml
research_agent:
  node_type: agent
  prompt:
    - system: |
        You are a research assistant that helps users find information. Use the provided tools to search for information and answer the user's question.
        Always think step by step and explain your reasoning.
    - user: |
        Please help me research {topic}. I'm particularly interested in {specific_aspect}.
  tools:
    - grasp.tasks.agent_tool_simulation.tools.search_tool.search
    - grasp.tasks.agent_tool_simulation.tools.calculator_tool.calculate
  inject_system_messages:
    2: "Remember to cite your sources when providing information."
    4: "If you're unsure about something, acknowledge the uncertainty rather than making up information."
  output_keys:
    - agent_response
  model:
    name: vllm_model
    parameters:
      temperature: 0.2
      max_tokens: 1024
```

### Configuration Fields:

- `node_type`: This should be set to `agent`.

- `prompt`: This is the prompt that will be sent to the agent. The prompt implementation is same as any other node with system, user and assistant turn, however system turn must be added to define agent behavior.

- `tools`: A list of tools that the agent can use. Tools are provided to the agent through the `create_react_agent` function from LangGraph.
  The following tools are currently supported:
  - `grasp.tasks.examples.agent_tool_simulation.tools_from_module` All valid tools from a module.
  - `grasp.tasks.examples.agent_tool_simulation.tools_from_class` All valid tools from a class.
  
  Make sure all the necessary tools are decorated with `@tool` from `langchain_core.tools`

- `inject_system_messages`: Optional dictionary where keys are conversation turn indices and values are additional system messages to inject at those turns. This allows for dynamic guidance of the agent based on conversation length.

- `post_process`: This is the function class of `type NodePostProcessor`, used to post-process the output from the agent.
  The class needs to define an `apply()` method with parameter `GraspMessage`. This allows for extracting specific information from the agent's response.

- `output_keys`: These are the variables used to store the output from the agent. This can be a list or a single variable.
  If a postprocessor is defined, `output_keys` can include multiple variables.

- `model`: This defines the model to be used for the agent. The model must be compatible with the BaseChatModel interface for proper agent functionality.
  - The ModelFactory will automatically select the appropriate model implementation based on the model type.
  - **NOTE**: 
    - The model extending from BaseChatModel should be implemented in models/langgraph folder. Refer to `CustomVLLMChatModel` in `models/langgraph/vllm_chat_model.py`
    - `backend: langgraph` Needs be set in models.yaml against the model being used in agent node.
    - **Supported model types:** `vllm, openai`

- `pre_process`: This is an optional functional class of type `NodePreProcessor`, used to preprocess the input before sending it to the agent.

- `input_key`: This is an optional field to specify the input key for the agent node. If not defined, the default input
  key (`messages`) will be used.

- `chat_history`: Boolean flag to enable or disable chat history for multi-turn conversations. When enabled, the agent can reference previous interactions.

### Inherited Features from LLM Node:

Agent nodes inherit all the features of LLM nodes, including:

- Support for chat history
- Input/output key configuration
- Pre/post processing capabilities
- Output role specification

### Key Differences from LLM Node:

1. **Tool Usage**: Agent nodes can use tools to interact with external systems or perform specific functions.

2. **ReAct Framework**: Agent nodes use the ReAct framework from LangGraph, which enables reasoning and acting cycles.

3. **Model Requirements**: Agent nodes require models that implement the BaseChatModel interface.

4. **System Message Injection**: Agent nodes support dynamic injection of system messages based on conversation turn.

### Implementation Details:

The agent node uses LangGraph's `create_react_agent` function to create a ReAct agent with the specified model and tools. The agent's system prompt is composed of the base prompt and any injected system messages based on the conversation turn.

When executed, the agent goes through reasoning and acting cycles until it reaches a final answer, which is then post-processed and returned as specified in the `output_keys`.
