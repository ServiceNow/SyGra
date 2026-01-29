<div align="center">
  <img width=30% src="https://raw.githubusercontent.com/ServiceNow/SyGra/refs/heads/main/docs/resources/images/sygra_logo.png">

  <h1>SyGra: Graph-oriented Synthetic data generation Pipeline</h1>

<a href="https://pypi.org/project/sygra/">
    <img src="https://img.shields.io/pypi/v/sygra.svg?logo=pypi&color=orange"/></a>
<a href="https://github.com/ServiceNow/SyGra/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/ServiceNow/SyGra/actions/workflows/ci.yml/badge.svg"/></a>
<a href="https://github.com/ServiceNow/SyGra/releases">
    <img alt="Releases" src="https://img.shields.io/github/v/release/ServiceNow/SyGra?logo=bookstack&logoColor=white"/></a>
<a href="https://servicenow.github.io/SyGra">
    <img alt="Documentation" src="https://img.shields.io/badge/MkDocs-Documentation-green.svg"/></a>
<a href="http://arxiv.org/abs/2508.15432">
    <img src="https://img.shields.io/badge/arXiv-2508.15432-B31B1B.svg" alt="arXiv"></a>
<a href="LICENSE">
    <img alt="Licence" src="https://img.shields.io/badge/License-Apache%202.0-blue.svg"/></a>

<br>
<br>
<br>
</div>


Framework to easily generate complex synthetic data pipelines by visualizing and configuring the pipeline as a
computational graph. [LangGraph](https://python.langchain.com/docs/langgraph/) is used as the underlying graph
configuration/execution library. Refer
to [LangGraph examples](https://github.com/langchain-ai/langgraph/tree/main/examples) to get a sense of the different
kinds of computational graph which can be configured.
<br>
<br>

## Introduction

SyGra Framework is created to generate synthetic data. As it is a complex process to define the flow, this design simplifies the synthetic data generation process. SyGra platform will support the following:
- Defining the seed data configuration
- Define a task, which involves graph node configuration, flow between nodes and conditions between the node
- Define the output location to dump the generated data

Seed data can be pulled from various data source, few examples are Huggingface, File system, ServiceNow Instance. Once the seed data is loaded, SyGra platform allows datagen users to write any data processing using the data transformation module. When the data is ready, users can define the data flow with various types of nodes. A node can also be a subgraph defined in another yaml file.

Each node can be defined with preprocessing, post processing, and LLM prompt with model parameters. Prompts can use seed data as python template keys.  
Edges define the flow between nodes, which can be conditional or non-conditional, with support for parallel and one-to-many flows.

At the end, generated data is collected in the graph state for a specific record, processed further to generate the final dictionary to be written to the configured data sink.

![SygraFramework](https://raw.githubusercontent.com/ServiceNow/SyGra/refs/heads/main/docs/resources/images/sygra_architecture.png)

---

# Quick Start

## Using the Framework

Clone the repo and run a built-in example in **2 commands**:

```bash
# 1. Clone and enter the repo
git clone https://github.com/ServiceNow/SyGra.git && cd SyGra

# 2. Set your model credentials
export SYGRA_GPT_4O_MINI_URL="https://api.openai.com/v1"
export SYGRA_GPT_4O_MINI_TOKEN="sk-..."

# 3. Run an example task
uv run python main.py -t examples.glaive_code_assistant -n 2
```

**Expected Output:**
```
Processing records: 100%|████████████████| 2/2
Output written to: output/glaive_code_assistant.jsonl
```

Check `output/glaive_code_assistant.jsonl` — you'll see generated code solutions with self-critique refinement.

### What Just Happened?

The task `tasks/examples/glaive_code_assistant` loads coding problems from HuggingFace and runs a **self-critique loop**:

**Key concepts:**
- **Data source** pulls from HuggingFace datasets
- **Conditional edges** create loops (critique → regenerate until correct)
- **`{question}`** and **`{answer}`** come from the dataset

Browse all examples here: [`tasks/examples/`](https://github.com/ServiceNow/SyGra/tree/main/tasks/examples)

---

## Using the Library

Install SyGra as a Python package for use in scripts or notebooks:

```bash
pip install sygra
```

Then build pipelines programmatically:

```python
import sygra

workflow = sygra.Workflow("my_workflow")
results = (
    workflow
    .source([
        {"topic": "space exploration"},
        {"topic": "artificial intelligence"},
    ])
    .llm(
        model="gpt-4o-mini",
        prompt="Write a short story about {topic}",
        output="story"
    )
    .sink("output/stories.json")
    .run()
)

print(results)
```

**Expected Output:**
```
[
  {"topic": "space exploration", "story": "In the year 2157, Captain Maya Chen..."},
  {"topic": "artificial intelligence", "story": "The neural network awakened..."}
]
```

Check `output/stories.json` for the full generated content.

---

## SyGra Studio

**SyGra Studio** is a visual workflow builder that replaces manual YAML editing with an interactive drag-and-drop interface. It also allows you to execute a task, monitor during execution and view the result along with metadata like latency, token usage etc.

![SyGraStudio](https://raw.githubusercontent.com/ServiceNow/SyGra/refs/heads/main/docs/resources/videos/studio_create_new_flow.gif)

**Studio Features:**
- **Visual Graph Builder** — Drag-and-drop nodes, connect them visually, configure with forms
- **Real-time Execution** — Watch your workflow run with live node status and streaming logs
- **Rich Analytics** — Track usage, tokens, latency, and success rates across runs
- **Multi-LLM Support** — Azure OpenAI, OpenAI, Ollama, vLLM, Mistral, and more

```bash
# One command to start
make studio
# Then open http://localhost:8000
```

> **[Read the full Studio documentation →](https://servicenow.github.io/SyGra/getting_started/create_task_ui/)**

---

## Task Components

SyGra supports extendability and ease of implementation—most tasks are defined as graph configuration YAML files. Each task consists of two major components: a graph configuration and Python code to define conditions and processors.
YAML contains various parts:

- **Data configuration** : Configure file or huggingface or ServiceNow instance as source and sink for the task.
- **Data transformation** : Configuration to transform the data into the format it can be used in the graph.
- **Node configuration** : Configure nodes and corresponding properties, preprocessor and post processor.
- **Edge configuration** : Connect the nodes configured above with or without conditions.
- **Output configuration** : Configuration for data tranformation before writing the data into sink.

The data configuration supports source and sink configuration, which can be a single configuration or a list. When it is a list of dataset configuration, it allows merging the dataset as column based and row based. Access the dataset keys or columns with alias prefix in the prompt, and finally write into various output dataset in a single flow.

A node is defined by the node module, supporting types like LLM call, multiple LLM call, lambda node, and sampler node.  

LLM-based nodes require a model configured in `models.yaml` and runtime parameters. Sampler nodes pick random samples from static YAML lists. For custom node types, you can implement new nodes in the platform.

As of now, LLM inference is supported for TGI, vLLM, OpenAI, Azure, Azure OpenAI, Ollama and Triton compatible servers. Model deployment is external and configured in `models.yaml`.

<!-- ![SygraComponents](https://raw.githubusercontent.com/ServiceNow/SyGra/refs/heads/main/docs/resources/images/sygra_usecase2framework.png) -->


## Contact

To contact us, please send us an [email](mailto:sygra_team@servicenow.com)!

## License

The package is licensed by ServiceNow, Inc. under the Apache 2.0 license. See [LICENSE](LICENSE) for more details.

## Questions?

Ask SyGra's [DeepWiki](https://deepwiki.com/ServiceNow/SyGra) </br>
Open an [issue](https://github.com/ServiceNow/SyGra/issues) or start a [discussion](https://github.com/ServiceNow/SyGra/discussions)! Contributions are welcome.
