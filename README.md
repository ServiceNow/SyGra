<div align="center">
  <img width=30% src="https://raw.githubusercontent.com/ServiceNow/GraSP/refs/heads/main/docs/resources/images/grasp_logo.png">

  <h1>GRASP: GRAph-oriented Synthetic data generation Pipeline</h1>
</div>


Framework to easily generate complex synthetic data pipelines by visualizing and configuring the pipeline as a
computational graph. [langgraph](https://python.langchain.com/docs/langgraph/) is used as the underlying graph
configuration/execution library. Refer
to [langraph examples](https://github.com/langchain-ai/langgraph/tree/main/examples) to get a sense of the different
kinds of computational graph which can be configured.
<br>
<be>

## Introduction

GraSP Framework is created to generate synthetic data. As it is a complex process to define the flow, this design simplifies the synthetic data generation process. GraSP platform will support the following:
- Defining the seed data configuration
- Define a task, which involves graph node configuration, flow between nodes and conditions between the node
- Define the output location to dump the generated data

Seed data can be pulled from either Huggingface or file system. Once the seed data is loaded, GraSP platform allows datagen users to write any data processing using the data transformation module. When the data is ready, users can define the data flow with various types of nodes. A node can also be a subgraph defined in another yaml file.

Each node can be defined with preprocessing, post processing, and LLM prompt with model parameters. Prompts can use seed data as python template keys.  
Edges define the flow between nodes, which can be conditional or non-conditional, with support for parallel and one-to-many flows.

At the end, generated data is collected in the graph state for a specific record, processed further to generate the final dictionary to be written to the configured data sink.

![GraspFramework](https://raw.githubusercontent.com/ServiceNow/GraSP/refs/heads/main/docs/resources/images/grasp_architecture.png)

---

## Components

GraSP supports extendability and ease of implementation—most tasks are defined as graph configuration YAML files. Each task consists of two major components: a graph configuration and Python code to define conditions and processors.

A node is defined by the node module, supporting types like LLM call, multiple LLM call, lambda node, and sampler node.  
LLM-based nodes require a model configured in `models.yaml` and runtime parameters. Sampler nodes pick random samples from static YAML lists. For custom node types, you can implement new nodes in the platform.

You can also define connections (edges) between nodes, which control conditional or parallel data flow.

As of now, LLM inference is supported for TGI, vLLM, Azure, Azure OpenAI, Ollama and Triton compatible servers. Model deployment is external and configured in `models.yaml`.

![GraspComponents](https://raw.githubusercontent.com/ServiceNow/GraSP/refs/heads/main/docs/resources/images/grasp_usecase2framework.png)

---


## Documentation

For a **complete reference** of all YAML configuration options, node/edge types, data sources and sinks, output mapping, schema validation, and advanced features:

👉 **[Documentation](https://github.com/ServiceNow/GraSP/blob/main/docs/installation.md)**

👉 **[Getting Started](https://github.com/ServiceNow/GraSP/tree/main/docs/getting_started)**

👉 **[Concepts](https://github.com/ServiceNow/GraSP/tree/main/docs/concepts)**

👉 **[GraSP Library](https://github.com/ServiceNow/GraSP/blob/main/docs/grasp_library.md)**

👉 **[Contribute](https://github.com/ServiceNow/GraSP/blob/main/docs/contributing.md)**

---

## License

[Your license here]

---

**Questions?**  
Open an issue or discussion! Contributions are welcome.
