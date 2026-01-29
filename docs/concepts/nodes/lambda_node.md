## Lambda Node

SyGra supports custom logic in your workflow using the **lambda** node. Lambda nodes allow you to execute arbitrary Python functions or classes, making them ideal for custom data processing, state manipulation, or integration of unique logic that doesn't fit standard node types.

### Example Configuration

```yaml
lambda_function_node:
  node_type: lambda
  function_type: sync
  lambda: path.to.module.function_name or path.to.module.LambdaFunctionImplementationClass
  output_keys: 
    - return_key1
    - return_key2 
```

### Configuration Fields

- **`node_type`**:  
  Set to `lambda` to indicate this node type.

- **`function_type`**:  
  Set to `sync` or `async` to indicate the type of function to execute. Default is `async`.

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
from sygra.core.graph.functions.lambda_function import LambdaFunction
from sygra.core.graph.sygra_state import SygraState

# Lambda function with sync apply(), to use async flow use AsyncLambdaFunction
class TestLambda(LambdaFunction):
    def apply(lambda_node_dict: dict, state: SygraState):
        state["return_key1"] = "hello world"
        state["return_key2"] = "dummy world"
        return state

# Or as a direct function:
def lambda_function(lambda_node_dict: dict, state: SygraState):
    state["return_key1"] = "hello world"
    state["return_key2"] = "dummy world"
    return state
```

### Notes

- Lambda nodes give you full control over data transformation, allowing you to bridge, preprocess, or postprocess state as needed.
- All keys you want accessible in the next node should be listed in `output_keys`.
- Use lambda nodes for any custom task, especially when built-in nodes do not cover your use case.
- If you have async programming in your lambda function, use `AsyncLambdaFunction` instead of `LambdaFunction`. In this case, the `apply` function is async in nature, and you can call async function with `await` keyword.
When you define lambda function, you need to provide `function_type` as `sync` or `async`(default).

----
### Example workflow with sync and async lambda function:

YAML configuration
```yaml
data_config:
  source:
    type: hf
    repo_id: openai/gsm8k
    config_name: main
    split: train
graph_config:
  nodes:
    lambda_1:
      node_type: lambda
      lambda: tasks.examples.lambda_test.task_executor.Lambda1Function
      function_type: sync
      node_name: Sync Node
    lambda_2:
      node_type: lambda
      lambda: tasks.examples.lambda_test.task_executor.Lambda2Function
      function_type: async
      node_name: Async Node
  edges:
  - from: START
    to: lambda_1
  - from: lambda_1
    to: lambda_2
  - from: lambda_2
    to: END
```

Task Executor Code:
```python
"""
Task executor for lambda test workflow having sync and async implementation.
"""
import asyncio
import time
from sygra.core.graph.functions.lambda_function import LambdaFunction, AsyncLambdaFunction
from sygra.core.graph.sygra_state import SygraState
from sygra.logger.logger_config import logger

async def count_async():
    print("One")
    logger.info("One...")
    await asyncio.sleep(1)
    print("Two")
    logger.info("Two...")
    await asyncio.sleep(1)

def count_sync(count:int):
    print("One")
    logger.info("One...")
    time.sleep(1)
    print("Two")
    logger.info("Two...")
    time.sleep(1)
    logger.info("Count..." + str(count))

async def wrapper_count_sync(count:int):
    return count_sync(count)

# sync lambda function
class Lambda1Function(LambdaFunction):
    """Execute custom logic on workflow state."""

    @staticmethod
    def apply(lambda_node_dict: dict, state: SygraState) -> SygraState:
        """Implement this method to apply lambda function.

        Args:
            lambda_node_dict: configuration dictionary
            state: current state of the graph

        Returns:
            SygraState: the updated state object
        """
        logger.info("sync function calling.......class1...")

        count_sync(2)

        logger.info("task done")
        return state

#async lambda function
class Lambda2Function(AsyncLambdaFunction):
    """Execute custom logic on workflow state."""

    @staticmethod
    async def apply(lambda_node_dict: dict, state: SygraState) -> SygraState:
        """Implement this method to apply lambda function.

        Args:
            lambda_node_dict: configuration dictionary
            state: current state of the graph

        Returns:
            SygraState: the updated state object
        """
        logger.info("async function calling.......class2...")
        await count_async()
        return state

```
---

**Tip:** Keep your lambda logic modular and reusable across tasks for maximum flexibility.

---