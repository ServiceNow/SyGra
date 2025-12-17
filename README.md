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

# Installation

Pick how you want to use **SyGra**:

<div align="center">

<a href="https://servicenow.github.io/SyGra/installation/">
  <img src="https://img.shields.io/badge/Use%20as-Framework-4F46E5?style=for-the-badge" alt="Install as Framework">
</a>
&nbsp;&nbsp;
<a href="https://servicenow.github.io/SyGra/library/sygra_library/">
  <img src="https://img.shields.io/badge/Use%20as-Library-10B981?style=for-the-badge" alt="Install as Library">
</a>

</div>

### Which one should I choose?
- **Framework** → Run end-to-end pipelines from YAML graphs + CLI tooling and project scaffolding.
  (Start here: **[`Installation`](https://servicenow.github.io/SyGra/installation/)**)

- **Library** → Import SyGra in your own Python app/notebook; call APIs directly.
  (Start here: **[`SyGra Library`](https://servicenow.github.io/SyGra/library/sygra_library/)**)

![Note](https://img.shields.io/badge/Note-important-yellow)  
> Before running the commands below, make sure to add your model configuration in `config/models.yaml` and set environment variables for credentials and chat templates as described in the [Model Configuration](https://servicenow.github.io/SyGra/getting_started/model_configuration/) docs.

<details>
  <summary><strong>TL;DR – Framework Setup</strong></summary>

See full steps in <a href="https://servicenow.github.io/SyGra/installation/">Installation</a>.

```bash
git clone git@github.com:ServiceNow/SyGra.git

cd SyGra
uv run python main.py --task examples.glaive_code_assistant --num_records=1
```
</details>

<details>
  <summary><strong>TL;DR – Library Setup</strong></summary>

See full steps in <a href="https://servicenow.github.io/SyGra/library/sygra_library/">Sygra Library</a>.

```bash
pip install sygra  
```

```python
import sygra

workflow = sygra.Workflow("tasks/examples/glaive_code_assistant")
workflow.run(num_records=1)
```
</details>

### Quick Start
> To get started with SyGra, please refer to some **[Example Tasks](https://github.com/ServiceNow/SyGra/tree/main/tasks/examples)** or **[SyGra Documentation](https://servicenow.github.io/SyGra/)**

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
