## LLM Node

SyGra supports text generation using LLMs. SyGra provides integration with various LLMs hosted on different inference
servers.

To use it, include the following configuration in your `graph_config.yaml` file:

### Example Configuration:

```yaml
paraphrase_question:
  node_type: llm
  prompt:
    - system: |
        You are an assistant tasked with paraphrasing a user query in a {tone} tone acting as a {persona}. Do NOT change/paraphrase the python code and keep it as is. Do NOT generate any conversational text and respond ONLY with the paraphrased query in the following format: "PARAPHRASED QUERY: <query>"
    - user: |
        USER QUERY: Provide a brief description of the problem the code is trying to solve and a brief explanation of the code. Do NOT generate any conversational text and respond ONLY with the problem the code is trying to solve and the explanation of the code.

        {code}
  post_process: tasks.mbpp.code_explanation.task_executor.ParaphraseQuestionNodePostProcessor
  output_keys:
    - rephrased_text
  model:
    name: mistralai
    parameters:
      temperature: 0.3

```

### Configuration Fields:

- `node_type`: This should be set to `llm`.

- `prompt`: This is the prompt that will be sent to the LLM. It should contain the system prompt and the user prompt.
  The system prompt defines the instructions for the LLM, and the user prompt provides the user query.

- `post_process`: This is the function class of `type NodePostProcessor`, used to post-process the output from the LLM. 
  The class need to define `apply()` method with parameter `SygraMessage`. `SygraMessage` is just a wrapper on the actual LangGraph message object(`AIMessage`, `UserMessage`, etc).
  Please note, if the variables returned by the above method are required as state variables, they should be defined in the `output_vars` field for the node.
  This also has backward compatibility, you can set a direct method to `post_process` with the above signature.

- `output_keys`: These are the variables used to store the output from the LLM. This is typically a method defined by
  the user in their `task_executor` file. It can be a list or a single variable.
    - If a postprocessor is not defined, the default postprocessor is invoked, and the output is stored in
      `output_keys`.
    - If a postprocessor is defined, `output_keys` can include multiple variables.
    - *Note*: `output_vars` and `output_key` are deprecated.
    - *Note*:  With this change, access the output_keys directly from state variable.
    - *Note*: By default, the returned message is an assistant message. To change the role of the message, use
      `output_role`.

- `model`: This defines the LLM model to be used. The primary model configuration should be specified in the
  `models.yaml` file under the config folder. Parameters defined in the node override those in `models.yaml`.

- `pre_process`: This is an optional functional class of type `NodePreProcessor`, used to preprocess the input before sending it to the LLM. If not
  provided, the default preprocessor is used. This class need to define `apply` method with `SygraState` as a parameter.
  
  Example code:
  ```python
  class CritiqueAnsNodePreProcessor(NodePreProcessor):
      def apply(self, state:SygraState):
          if not state["messages"]:
              state["messages"] = []
  
          # We need to convert user turns to assistant and vice versa
          cls_map = {"ai": HumanMessage, "human": AIMessage}
          translated = [cls_map[msg.type](content=msg.content) for msg in state["messages"]]
          state.update({"messages": translated})
          return state
   ```
  It also supports backward compatibility, user can set a simple method into `pre_process`.

- `output_key`: The old behavior is still maintained with `output_keys`. But this variable is renamed, this may impact graph_config.yaml file and the output generator code.

- `input_key`: This is an optional field to specify the input key for the LLM node. If not defined, the default input
  key (`messages`) will be used.

- `output_role`: This defines the role of the message returned by the LLM. It can be `system`, `user`, or `assistant`.
  If not specified, the default role (`assistant`) will be used.

  - `tools`: This is an optional field to specify the tools to be used by the LLM. 
    The following tools are currently supported:
      -  `tasks.examples.llm_node_tool_simulation.tools_from_module.tool_method` Single tool method with annotation @tool
      -  `tasks.examples.llm_node_tool_simulation.tools_from_module` All valid tools from a module.
      -  `tasks.examples.llm_node_tool_simulation.tools_from_module.MyToolClass` All valid tools from a class.

    Make sure all the necessary tools are decorated with `@tool` from `langchain_core.tools`
    Refer to the [Example Task](https://github.com/ServiceNow/SyGra/tree/main/tasks/examples/llm_node_tool_simulation) with tools attached to LLM Node.
    
    ![Note](https://img.shields.io/badge/Note-important-yellow)
  >   We currently support `openai`, `azure_openai`, `vllm` model types for tool calls.

