# Audio to Text Data Generation

This module introduces support for multimodal data generation pipelines that accept **audio** or **audio + text** as input and produce **textual outputs** using audio-capable LLMs like `Qwen2-Audio-7B`. It expands traditional text-only pipelines to support audio reasoning tasks like speech recognition, audio classification, and multimodal QA.

## Key Features

- Supports **audio-only** and **audio+text** prompts.
- Converts audio fields into **base64-encoded data URLs** compatible with LLM APIs.
- Compatible with HuggingFace datasets, streaming, and on-disk formats.
- Automatically handles **lists of audio** per field.
- Seamless round-tripping between loading, prompting, and output publishing.

---
## Supported Image Input Types

Each audio field in a dataset record may be one of the following:

- Local file path (e.g., `"data/aud.wav"`)
  - Supported Extensions: `.wav`, `.flac`, `.ogg`, `mp3`, `.m4a`, `.aac`, `.aiff`
- HTTP(S) URL (e.g., `"https://example.com/audio.wav"`)
- Raw `bytes`
- HuggingFace `datasets.Audio` object
- Dictionary: `{ "bytes": <byte_data> }`
- A list of any of the above
- A base64-encoded data URL (e.g., `"data:audio/wav;base64,..."`)

### Input Source: Local Disk Dataset

Supports `.json`, `.jsonl`, or `.parquet` datasets with local or remote audio paths.

#### File Layout

```
project/
├── data/
│   ├── 000001.wav
│   ├── 000002.wav
│   └── input.json
```

#### `data/input.json`

```json
[
  { "id": "1", "audio": "data/000001.wav" },
  { "id": "2", "audio": "https://example.com/audio.wav" }
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
{ "id": "1", "audio": "HuggingFace datasets.Audio object or URL" }
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

- Handles both `datasets.Audio` fields and string URLs.
- Audio is resolved and encoded to base64.

### Multiple Audio Fields

If a record has more than one audio fields (e.g., `"bird_sounds"` and `"animal_sounds"`), reference them individually:

```yaml
- type: audio_url
  audio_url: "{bird_sounds}"
- type: audio_url
  audio_url: "{animal_sounds}"
```

## How Audio Transformation Works

1. Detects audio-like fields from supported types.
2. Converts each to a base64-encoded `data:audio/...` string.
3. Expands fields containing list of audio internally into multiple prompt entries.
     
    **Input:**
    ```json
    { "audio": ["data/000001.wav", "data/000002.wav"] }
    ```
    
    **Prompt config:**
    
    ```yaml
    - type: audio_url
      audio_url: "{audio}"
    ```
    
    **Will expand to:**
    
    ```yaml
    - type: audio_url
      audio_url: "data:audio/wav;base64,..."
    - type: audio_url
      audio_url: "data:audio/wav;base64,..."
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

Each field that originally contained a `data:audio/...` base64 string will be:
- **Decoded back into a HuggingFace datasets.Audio object**.
- **Stored in its native audio format** in the output dataset.
- Uploaded to the dataset repo as proper audio entries (not strings).

---

## Example Configuration: Identify the animal in the audio

```yaml
data_config:
  source:
    type: "hf"
    repo_id: "datasets-examples/doc-audio-1"
    split: "train"
    streaming: true

  sink:
    type: "hf"
    repo_id: ServiceNow-AI/SyGra
    config_name: MM-doc-audio-1
    split: train
    push_to_hub: true
    private: true
    token: "<hf_token>"

graph_config:
  nodes:
    identify_animal:
      output_keys: animal
      node_type: llm
      prompt:
        - user:
            - type: text
              text: |
                Identify the animal in the provided audio.
            - type: audio_url
              audio_url: "{audio}"

      model:
        name: qwen_2_audio_7b
        parameters:
          max_tokens: 1000
          temperature: 0.3
  edges:
    - from: START
      to: identify_animal
    - from: identify_animal
      to: END

output_config:
    output_map:
        id:
          from: "id"
        audio:
          from: "audio"
        animal:
          from: "animal"
```

## Notes

- **Audio generation is not supported** in this module. The `audio_url` type is strictly for passing existing audio inputs (e.g., loaded from datasets), not for generating new audio via model output.
- For a complete working example, see: [`tasks/audio_to_text`](https://github.com/ServiceNow/SyGra/tree/main/tasks/examples/audio_to_text)


