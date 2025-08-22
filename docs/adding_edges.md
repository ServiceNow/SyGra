## Adding Edges in the YAML Configuration

### Edge Configuration
To add an edge to the graph configuration, include it in the edges section of the YAML file. Each edge is represented as a dictionary with specific properties that define its behavior.
Here's an example of an edge configuration:
```yaml 
edges:
  - from: node1
    to: node2
  - from: node2
    condition: grasp.tasks.example.task_executor.ShouldContinueCondition
    path_map:
      result1: node3
      result2: node4
```

Properties  to configure an edge:

### Special Nodes: START and END

GraSP graphs automatically include two special nodes:

- **START**: The entry point of the graph. Every graph must have at least one edge from START to another node.
- **END**: The exit point of the graph. When execution reaches the END node, the graph processing is complete.

These special nodes are handled automatically by the framework and don't need to be defined in the `nodes` section. They are only referenced in edge definitions.

Example:
```yaml
edges:
  - from: START      # Entry point of the graph
    to: first_node   # First node to execute
  - from: last_node  # Last processing node
    to: END          # Exit point of the graph
```

In conditional edges, you can direct flow to the END node to terminate processing:
```yaml
edges:
  - from: some_node
    condition: tasks.example.ShouldContinueCondition
    path_map:
      END: END                # Terminates processing when condition returns "END"
      continue: next_node     # Continues to next_node when condition returns "continue"
```

#### `from` (required)

The from property specifies the source node of the edge. It indicates the node from which the edge originates. The value should be a valid node name defined in the nodes section of the YAML configuration or the special node "START".

Example:
```yaml
from: node1
```

#### `to` (optional)

The to property specifies the target node of the edge. It indicates the node to which the edge leads. The value should be a valid node name defined in the nodes section of the YAML configuration or the special node "END".

Example:
```yaml
to: node2
```

#### `condition` (optional)

The condition property allows to specify a condition functional class of type `EdgeCondition` that determines the path to take based on the result of the `apply` method. 
The value should be a fully qualified path to the class.
Example Code:
```python
class ShouldContinueCondition(EdgeCondition):
    def apply(state: GraspState) -> str:
        # End after 4 iterations or the last feedback response contains "NO MORE FEEDBACK"
        messages = state["messages"]
        if len(messages) > 8 or (
                len(messages) > 1 and "no more feedback" in messages[-1].content.lower()
        ):
            return GRASP_END
        return "generate_answer"
```
```yaml
condition: tasks.example.ShouldContinueCondition
```
The `condition` class should accept the current state of the graph(`GraspState`) and return a value that matches one of the keys in the `path_map` (explained below).

Alternatively, it also supports a direct method like `tasks.example.should_continue` for backward compatibility.
#### `path_map` (optional)

The `path_map` property is used in conjunction with the `condition` property. It defines a mapping between the possible results of the condition function and the corresponding target nodes.

Example:
```yaml
path_map:
  result1: node3
  result2: node4
```
In this example, if the condition function returns result1, the edge will lead to node3. If the condition function returns result2, the edge will lead to node4.

### Edge Validation
When configuring edges in the YAML file, it's important to ensure that the nodes referenced in the edges are valid and exist in the graph configuration. The graph builder will validate the edges and raise errors if any inconsistencies or invalid connections are found.

Key considerations:

- The `from` node must be a valid node defined in the nodes section of the YAML configuration.
- If the `to` property is specified, it must refer to a valid node defined in the nodes section.
- If the `condition` and `path_map` properties are used, the `condition` function must exist, and the keys in the `path_map` must correspond to valid nodes.

If any validation errors are encountered during the graph building process, a detailed error message will be raised, indicating the specific issues found in the edge configurations.

### Examples
Here are a few more examples of edge configurations to illustrate different scenarios:

1. Simple edge:
```yaml
edges:
  - from: node1
    to: node2
```
2. Conditional edge with path mapping:
```yaml
edges:
  - from: START
    to: node1
  - from: node1
    to: node2
  - from: node2
    to: node3
  - from: node3
    condition: tasks.example.MyCondition
    path_map:
      success: node4
      failure: node5
```
