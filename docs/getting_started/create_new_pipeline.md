## Steps to Create a Synthetic Data Pipeline

With the graph node and edge YAML configuration, it's easy to set up a flow.  
Example: [glaive code assistant](https://github.com/ServiceNow/SyGra/tree/main/tasks/examples/glaive_code_assistant).

**Basic steps:**
- Create a sub-directory under `tasks` for your use case.
- Create a `graph_config.yaml` for your pipeline (nodes, edges, models, etc).
- Create a `task_executor.py` for any custom logic or processing.
- Execute with `python main.py --task <your_task> ...`
- Results are stored in `output.json` in your sub-directory.

#### Resumable Execution: 

In the event of a failure, the process can gracefully shut down and later resume execution from the point of interruption. To activate resumable execution, set the flag `--resume True` when running your command. For instance: `python main.py --task <your_task> ... --resume True`. 

> See the [Graph Configuration Guide](https://github.com/ServiceNow/SyGra/blob/main/docs/getting_started/graph_config_guide.md) for detailed schema, examples, and best practices for defining graphs, tasks, and processors.

---