
![ModelConfig](https://raw.githubusercontent.com/ServiceNow/SyGra/refs/heads/main/docs/resources/images/sygra_model_config.png)

SyGra requires model configuration as the first step. It supports various clients like HTTP, MistralAzure, AsyncOpenAI, AsyncAzureOpenAI, Ollama to connect to inference servers (Text Generation Inference (TGI), vLLM server, Azure Cloud Service, Ollama, Triton etc.).

The `config` folder contains the main configuration file: `models.yaml`. You can add your model alias as a key and define its properties as shown below.

> **Note:**  
> For Triton, the pre-processing and post-processing configuration (`payload_json` & `response_key`) can be defined in the [`payload_cfg.json`](https://github.com/ServiceNow/SyGra/blob/main/sygra/config/payload_cfg.json) file. `payload_key` in the `payload_cfg.json` file should be added to the `models.yaml` file for the corresponding Triton model. If the payload key is not defined in `models.yaml`, the default payload format will be used.

### Environment Variables for Credentials and Chat Templates

All sensitive connection information such as model URL and tokens **must be set via environment variables** and not stored in the config file.

For each model defined in your `models.yaml`, set environment variables as follows:
- `SYGRA_<MODEL_NAME>_URL` (for the model endpoint)
- `SYGRA_<MODEL_NAME>_TOKEN` (for API keys or tokens)
- If `modify_tokenizer: true` is set for a model, provide a chat template string via:
  - `SYGRA_<MODEL_NAME>_CHAT_TEMPLATE`

**Naming Convention:**  
`<MODEL_NAME>` is the model’s key from your `models.yaml`, with all spaces replaced by underscores, and all letters uppercased (e.g., `mixtral 8x7b` → `MIXTRAL_8X7B`).

**Example:**  
For `mixtral_8x7b` and `gpt4`, set:
- `SYGRA_MIXTRAL_8X7B_URL`, `SYGRA_MIXTRAL_8X7B_TOKEN`
- `SYGRA_GPT4_URL`, `SYGRA_GPT4_TOKEN`
- If `mixtral_8x7b` has `modify_tokenizer: true`, set:  
  - `SYGRA_MIXTRAL_8X7B_CHAT_TEMPLATE` to your custom Jinja2 chat template string

You should use a `.env` file at the project root or set these in your shell environment.

**Note:**
If you want to define a list of URLs for any model, you can use pipe (`|`) as a separator. For example, if you have a model called `mixtral_8x7b` with URLs `https://myserver/models/mixtral-8x7b` and `https://myserver/models/mixtral-8x7b-2`, you can set the following environment variables as shown in examples below.

### Example `.env`:

```bash
SYGRA_MIXTRAL_8X7B_URL=https://myserver/models/mixtral-8x7b|https://myserver/models/mixtral-8x7b-2
SYGRA_MIXTRAL_8X7B_TOKEN=sk-abc123
SYGRA_MIXTRAL_8X7B_CHAT_TEMPLATE={% for m in messages %} ... {% endfor %}
```


### Configuration Properties


| Key                         | Description                                                                                                                |
|-----------------------------|----------------------------------------------------------------------------------------------------------------------------|
| `model_type`                | Type of backend server (`tgi`, `vllm`, `openai`, `azure_openai`, `azure`, `mistralai`, `ollama`, `triton`)                 |
| `model_name`                | Model name for your deployments (for Azure/Azure OpenAI)                                                                   |
| `api_version`               | API version for Azure or Azure OpenAI                                                                                      |
| `hf_chat_template_model_id` | Hugging Face model ID                                                                                                      |
| `multi_modal`               | *(Optional)* Boolean: Set this to false if the model is not multi-modal (default: true)                                    |
| `completions_api`           | *(Optional)* Boolean: use completions API instead of chat completions API (default: false)                                 |
| `modify_tokenizer`          | *(Optional)* Boolean: apply custom chat template and modify the base model tokenizer (default: false)                      |
| `special_tokens`            | *(Optional)* List of special stop tokens used in generation                                                                |
| `post_process`              | *(Optional)* Post processor after model inference (e.g. `models.model_postprocessor.RemoveThinkData`)                      |
| `parameters`                | *(Optional)* Generation parameters (see below)                                                                             |
| `chat_template_params`      | *(Optional)* Chat template parameters (e.g. `reasoning_effort` for `gpt-oss-120b`) <br/> when `completions_api` is enabled |
| `ssl_verify`                | *(Optional)* Verify SSL certificate (default: true)                                                                        |
| `ssl_cert`                  | *(Optional)* Path to SSL certificate file                                                                                  |
| `json_payload`              | *(Optional)* Boolean: use JSON payload instead of JSON string for `http client` based models (default: false)              |
| `headers`                   | *(Optional)* Dictionary of headers to be sent with the request for `http client` based models                              |
![Note](https://img.shields.io/badge/Note-important-yellow)  
> - Do **not** include `url`, `auth_token`, or `api_key` in your YAML config. These are sourced from environment variables as described above.<br>
> - If you want to set **ssl_verify** to **false** globally, you can set `ssl_verify:false` under `model_config` section in config/configuration.yaml

#### Customizable Model Parameters

- `temperature`: Sampling randomness (0.0–2.0; lower is more deterministic)
- `top_p`: Nucleus sampling (0.0–1.0)
- `max_tokens` / `max_new_tokens`: Maximum number of tokens to generate
- `stop`: List of stop strings to end generation
- `repetition_penalty`: Penalizes repeated tokens (1.0 = no penalty)
- `presence_penalty`: (OpenAI only) Encourages novel tokens
- `frequency_penalty`: (OpenAI only) Penalizes frequently occurring tokens

The model alias set as a key in the configuration is referenced in your graph YAML files (for node types such as `llm` or `multi_llm`). You can override these model `parameters`, `chat_template_params` in the graph YAML for specific scenarios.

---

### Understanding `openai` vs `azure_openai` vs `azure` Model Types

SyGra supports multiple ways of connecting to OpenAI and OpenAI-compatible models. The following clarifies the difference between **`openai`**, **`azure_openai`**, and **`azure`** model types:

| Model Type     | Description | Typical Use Case | Required Config Keys                                                  |
|----------------|-------------|------------------|-----------------------------------------------------------------------|
| **`openai`** | Connects directly to the **public OpenAI API** (`https://api.openai.com/v1`). | Use this for hosted OpenAI models like `gpt-4o`, `gpt-3.5-turbo`, etc. | `model_type: openai`                                                  |
| **`azure_openai`** | Connects to **OpenAI models hosted on Azure** (Azure Cognitive Services → OpenAI deployment). Requires `model_name` and `api_version`. | Use when your organization deploys *OpenAI models* via Azure. | `model_type: azure_openai`, `model_name`, `api_version`               |
| **`azure`** | Generic **HTTP client wrapper** for *non-OpenAI* Azure models (e.g., **Anthropic Claude**, **Mistral**, **Custom inference endpoints**) using Azure API Gateway / Managed Endpoints. | Use when Azure acts simply as a proxy HTTP endpoint to another model. | `model_type: azure`, plus any extra headers in `.env` and models.yaml |

---

#### Environment Variables

| Client | Required Environment Variables |
|--------|-------------------------------|
| `openai` | `SYGRA_<MODEL>_URL=https://api.openai.com/v1`<br>`SYGRA_<MODEL>_TOKEN=sk-...` |
| `azure_openai` | `SYGRA_<MODEL>_URL=https://<resource>.openai.azure.com`<br>`SYGRA_<MODEL>_TOKEN=<azure-key>` |
| `azure` | `SYGRA_<MODEL>_URL=https://<your-azure-endpoint>`<br>`SYGRA_<MODEL>_TOKEN=<auth-if-required>` |

---

### Example Configuration (`models.yaml`)

```yaml
gpt4_openai:
  model_type: openai
  parameters:
    temperature: 0.7
    max_tokens: 512

gpt4_azure:
  model_type: azure_openai
  model_name: gpt-4-32k
  api_version: 2024-05-01-preview
  parameters:
    temperature: 0.7
    max_tokens: 512

llama_3_1_405b_instruct:
  model_type: azure
  load_balancing: round_robin
  parameters:
    max_tokens: 4096
    temperature: 0.8
  hf_chat_template_model_id: meta-llama/Meta-Llama-3.1-405B-Instruct

qwen_2.5_32b_vl:
  model_type: vllm
  completions_api: true
  hf_chat_template_model_id: Qwen/Qwen2.5-VL-32B-Instruct
  parameters:
    temperature: 0.15
    max_tokens: 10000
    stop: ["<|endoftext|>", "<|im_end|>", "<|eod_id|>"]

qwen3_1.7b:
  hf_chat_template_model_id: Qwen/Qwen3-1.7B
  post_process: sygra.core.models.model_postprocessor.RemoveThinkData
  model_type: ollama
  parameters:
    max_tokens: 2048
    temperature: 0.8

qwen3-32b-triton:
  hf_chat_template_model_id: Qwen/Qwen3-32B
  post_process: sygra.core.models.model_postprocessor.RemoveThinkData
  model_type: triton
  payload_key: default
  # Uses default payload format defined in config/payload_cfg.json.
  # Add/Update the payload_cfg.json if you need to use a different payload format with new key.
  parameters:
    temperature: 0.7

```

> **Important:**
If you set modify_tokenizer: true for a model, you must provide the corresponding chat template in your environment as SYGRA_<MODEL_NAME>_CHAT_TEMPLATE.
Otherwise, exception will be raised during the model initialization.
---
