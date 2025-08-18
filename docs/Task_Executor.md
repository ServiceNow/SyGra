## Task Executor
The Task Executor is responsible for executing tasks and managing their state.

### `BaseGraphState` Class
This class defines the state of the graph. It is the base class for the state variables with some default variables. All the variables including the input data keys, variables defined within curly braces in the node_config,
`output_vars`& `output_key`defined in the node_config are available by default.

The nodes communicate with each other using this class. It is mandatory to have `messages` field for using llm nodes.

### `init_graph` Method
The init_graph method of the Task Executor is responsible for building and compiling the graph. Users need to use the `GraspStateGraph` class to get the `StateGraph` object.

### `init_dataset`Method
The `init_dataset` method is responsible for initializing the dataset. It is called before the graph is built.

### `output_record_generator` Method
The `output_record_generator` method is responsible for generating the output record. It is called after the graph is executed.
