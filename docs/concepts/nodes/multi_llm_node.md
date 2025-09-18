## Multi-LLM Node

SyGra supports the ability to run multiple large language models in parallel using the **multi_llm** node. This is useful for benchmarking, model comparison, or workflows where you want to generate multiple outputs for the same prompt and aggregate or rate the results.

A multi-llm node sends the same prompt to several configured models and collects all responses together in the state.

### Example Configuration

```yaml
generate_samples:  
  node_type: multi_llm
  pre_process: tasks.dpo_samples.task_executor.generate_samples_pre_process
  output_keys: model_responses    # Optional: key to store all model responses in state
  prompt:        
    - user: "{user_prompt}"
  models:      
    mistral_large:               # Model identifier
      name: mistralai            # Model name (must be defined in models.yaml)
      parameters:          
        max_tokens: 2000
        temperature: 0.7            
    mixtral_instruct_8x22b:         # Model identifier
      name: mixtral_instruct_8x22b  # Model name (must be defined in models.yaml)
      parameters:
        temperature: 0.7
        max_tokens: 2000
  multi_llm_post_process: tasks.dpo_samples.task_executor.post_process_responses  # Optional
```

### Configuration Fields

- **`node_type`**:  
  Set to `multi_llm` for this node type.

- **`prompt`**:  
  The prompt/messages to send to each model. Supports templated variables (e.g., `{user_prompt}`).

- **`models`**:  
  Map of model identifiers to their configuration. Each entry must specify:
  - `name`: The model name as defined in your `models.yaml`.
  - `parameters`: Model-specific parameters (such as `temperature`, `max_tokens`, etc).
  - Each model receives the same prompt, but you can specify different parameters for each.

- **`output_keys`**:  
  The key in the state where the multi-model responses are stored (default: `"messages"`).

- **`pre_process`**:  
  Optional. Path to a function or class (with an `apply()` method) to transform the input before calling the models.

- **`multi_llm_post_process`**:  
  Optional. Path to a function or class (with an `apply()` method) to process the collected responses after calling all models. By default, responses are stored as a dictionary with model names as keys.

- **`input_key`**:  
  Optional. State key to read input messages from. Defaults to `"messages"`.

- **`node_state`**:  
  Optional. Node-specific state key.

### Output

The output from a multi-llm node will contain a mapping of model names to their respective responses, for example:

```json
{
  "model_responses": {
    "gpt4": { "message": "...", "success": true },
    "gpt-4o": { "message": "...", "success": true },
    "gpt4o-mini": "A sustainable urban transportation system should focus on..."
  }
}
```

### Reference Example: DPO Samples Task

For a full workflow demonstrating the use of the multi-llm node—including advanced structured output, post-processing, and integration with judge models—see the [DPO Samples Task example](#example-configuration) in this documentation.

### Notes

- **Model Responses**: All configured models are called in parallel with the same prompt, and their outputs are collected together.
- **Custom Processing**: Use `pre_process` and `multi_llm_post_process` to customize how inputs and outputs are handled.
- **Flexible Output**: Each model’s structured output can be configured independently using YAML schema or class-based definitions. See the referenced DPO example for details.
- **Use Cases**: Useful for data generation, preference optimization, or any scenario where model comparison or diversity is required.

---

**Tip:** Combine multi-llm nodes with judge models and edge conditions for advanced workflows such as DPO (Direct Preference Optimization), rating, or filtering.

---