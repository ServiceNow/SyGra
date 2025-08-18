# Image to Text Data Generation

This module introduces support for multimodal data generation pipelines that accept **images** or **image + text** as input and produce **textual outputs** using vision-capable LLMs like `gpt-4o`. It expands traditional text-only pipelines to support visual reasoning tasks like chart judgment, document analysis, and multimodal QA.

## Key Features

- Supports **image-only** and **image+text** prompts.
- Converts image fields into **base64-encoded data URLs** compatible with LLM APIs.
- Compatible with HuggingFace datasets, streaming, and on-disk formats.
- Automatically handles **lists of images** per field.
- Seamless round-tripping between loading, prompting, and output publishing.

---
## Supported Image Input Types

Each image field in a dataset record may be one of the following:

- Local file path (e.g., `"data/img1.png"`)
  - Supported Extensions: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`, `.tif`, `.webp`, `.ico`, `.apng`
- HTTP(S) URL (e.g., `"https://example.com/img.png"`)
- Raw `bytes`
- `PIL.Image` object
- Dictionary: `{ "bytes": <byte_data> }`
- A list of any of the above
- A base64-encoded data URL (e.g., `"data:image/png;base64,..."`)

### Input Source: Local Disk Dataset

Supports `.json`, `.jsonl`, or `.parquet` datasets with local or remote image paths.

#### File Layout

```
project/
├── data/
│   ├── 000001.png
│   ├── 000002.png
│   └── input.json
```

#### `data/input.json`

```json
[
  { "id": "1", "image": "data/000001.png" },
  { "id": "2", "image": "https://example.com/image2.png" }
]
```

#### Configuration

```yaml
data_config:
  source:
    type: "disk"
    file_path: "data/input.json"
```

- Local paths are resolved relative to `file_path`.
- Remote URLs are fetched and encoded to base64 automatically.



### Input Source: HuggingFace Dataset

Supports datasets hosted on the HuggingFace Hub in streaming or download mode.

#### Example Record

```json
{ "id": "1", "image": "PIL.Image object or URL" }
```

#### Configuration

```yaml
data_config:
  source:
    type: "hf"
    repo_id: "myorg/my-dataset"
    config_name: "default"
    split: "train"
    streaming: true
```

- Handles both `datasets.Image` fields and string URLs.
- Images are resolved and encoded to base64.

### Multiple Image Fields

If a record has more than one image field (e.g., `"chart"` and `"legend"`), reference them individually:

```yaml
- type: image_url
  image_url: "{chart}"
- type: image_url
  image_url: "{legend}"
```

## How Image Transformation Works

1. Detects image-like fields from supported types.
2. Converts each to a base64-encoded `data:image/...` string.
3. Expands fields containing list of images internally into multiple prompt entries.
     
    **Input:**
    ```json
    { "image": ["img1.png", "img2.png"] }
    ```
    
    **Prompt config:**
    
    ```yaml
    - type: image_url
      image_url: "{image}"
    ```
    
    **Will expand to:**
    
    ```yaml
    - type: image_url
      image_url: "data:image/png;base64,..."
    - type: image_url
      image_url: "data:image/png;base64,..."
    ```
4. Leaves already-encoded data URLs unchanged.

---

## HuggingFace Sink Round-Tripping

When saving output back to HuggingFace datasets:

```yaml
sink:
  type: "hf"
  repo_id: "<your_repo>"
  config_name: "<your_config>"
  split: "train"
  push_to_hub: true
  private: true
  token: "<hf_token>"
```

Each field that originally contained a `data:image/...` base64 string will be:
- **Decoded back into a PIL Image**.
- **Stored in its native image format** in the output dataset.
- Uploaded to the dataset repo as proper image entries (not strings).

---

## Example Configuration: Graph Quality Judgement

```yaml
data_config:
  source:
    type: "hf"
    repo_id: "<repo_id>"
    config_name: "<config_name>"
    split: "train"
    streaming: true
    transformations:
      - transform: processors.data_transform.AddNewFieldTransform
        params:
          mapping:
            graph_judgement: ""
            graph_judgement_content: ""

graph_config:
  nodes:
    judge_synthetic_graph_quality:
      node_type: llm
      post_process: tasks.image_description.task_executor.GraphJudgementPostProcessor
      prompt:
        - user:
            - type: text
              text: |
                You are given a graph image that represents structured numerical data.
                ...
                Output Format:
                <JUDGEMENT>
                accept/reject
                </JUDGEMENT>
                <JUDGEMENT_EXPLANATION>
                Explanation goes here.
                </JUDGEMENT_EXPLANATION>
            - type: image_url
              image_url: "{image}"
      model:
        name: gpt-4o
        parameters:
          max_tokens: 1000
          temperature: 0.3

  edges:
    - from: START
      to: judge_synthetic_graph_quality
    - from: judge_synthetic_graph_quality
      to: END

output_config:
  output_map:
    id: 
      from: "id"
    image: 
      from: "image"
    graph_judgement: 
      from: "graph_judgement"
    graph_judgement_content: 
      from: "graph_judgement_content"
```
---
## Notes

- **Image generation is not supported** in this module. The `image_url` type is strictly for passing existing image inputs (e.g., loaded from datasets), not for generating new images via model output.
- For a complete working example, see: [`tasks/image_description`](../../tasks/image_description/graph_config.yaml)


