## Lambda Node

GraSP supports custom logic in your workflow using the **lambda** node. Lambda nodes allow you to execute arbitrary Python functions or classes, making them ideal for custom data processing, state manipulation, or integration of unique logic that doesn't fit standard node types.

### Example Configuration

```yaml
lambda_function_node:
  node_type: lambda
  lambda: path.to.module.function_name or path.to.module.LambdaFunctionImplementationClass
  output_keys: 
    - return_key1
    - return_key2 
```

### Configuration Fields

- **`node_type`**:  
  Set to `lambda` to indicate this node type.

- **`lambda`**:  
  Fully qualified path to the function or class to execute.  
  - Can be a direct function (e.g., `tasks.my_task.task_executor.lambda_function`)
  - Or a class that implements the `LambdaFunction` interface (e.g., `tasks.my_task.task_executor.TestLambda`)

- **`output_keys`**:  
  List of keys from the return dictionary or state that will be made available to subsequent nodes.

- **`node_state`**:  
  Optional. Node-specific state key.

### Example Lambda Implementation

You can implement a lambda either as a class or a function:

```python
# Example in yaml: lambda: tasks.my_task.task_executor.TestLambda
from grasp.core.graph.functions.lambda_function import LambdaFunction
from grasp.core.graph.grasp_state import GraspState

class TestLambda(LambdaFunction):
    def apply(lambda_node_dict: dict, state: GraspState):
        state["return_key1"] = "hello world"
        state["return_key2"] = "dummy world"
        return state

# Or as a direct function:
def lambda_function(lambda_node_dict: dict, state: GraspState):
    state["return_key1"] = "hello world"
    state["return_key2"] = "dummy world"
    return state
```

### Notes

- Lambda nodes give you full control over data transformation, allowing you to bridge, preprocess, or postprocess state as needed.
- All keys you want accessible in the next node should be listed in `output_keys`.
- Use lambda nodes for any custom task, especially when built-in nodes do not cover your use case.

---

**Tip:** Keep your lambda logic modular and reusable across tasks for maximum flexibility.

---