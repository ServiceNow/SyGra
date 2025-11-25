# Audio to Text Data Generation

This module introduces support for multimodal data generation pipelines that convert **audio** to **text**. SyGra supports two distinct approaches for audio-to-text conversion:

1. **Audio Understanding LLMs** - Models like `Qwen2-Audio-7B` that can reason about, analyze, and answer questions about audio content
2. **Dedicated Transcription Models** - Models like `Whisper` and `gpt-4o-transcribe` optimized specifically for accurate speech-to-text conversion

## Key Features

### Audio Understanding LLMs
- Supports **audio-only** and **audio+text** prompts
- Audio reasoning, classification, and Q&A capabilities
- Uses standard chat completions API
- Contextual understanding of audio content

### Dedicated Transcription Models
- Accurate speech-to-text conversion
- Multilingual support (50+ languages)
- Multiple output formats (JSON, SRT, VTT, text)
- Word and segment-level timestamps
- Optimized for transcription accuracy

### Common Features
- Converts audio fields into **base64-encoded data URLs** compatible with LLM APIs
- Compatible with HuggingFace datasets, streaming, and on-disk formats
- Automatically handles **lists of audio** per field
- Seamless round-tripping between loading, prompting, and output publishing

## Choosing the Right Approach

| Use Case | Recommended Approach |
|----------|---------------------|
| Accurate speech-to-text transcription | **Transcription Models** |
| Generating subtitles with timestamps | **Transcription Models** |
| Multilingual transcription | **Transcription Models** |
| Audio classification or event detection | **Audio Understanding LLMs** |
| Answering questions about audio | **Audio Understanding LLMs** |
| Audio reasoning or analysis | **Audio Understanding LLMs** |
| Combining audio with text context | **Audio Understanding LLMs** |

---

# Part 1: Audio Understanding with LLMs

This section covers audio understanding using LLMs like `Qwen2-Audio-7B` that can reason about audio content.

## Supported Audio Input Types

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

---

# Part 2: Speech-to-Text Transcription

This section covers dedicated transcription models optimized for accurate speech-to-text conversion.

## Supported Transcription Models

- `whisper-1` - OpenAI's Whisper model, general-purpose transcription
- `gpt-4o-transcribe` - OpenAI's GPT-4o-based transcription model with improved accuracy

## Transcription Model Configuration

Configure the transcription model in your `sygra/config/models.yaml`:

```yaml
transcribe:
  model: gpt-4o-transcribe  # or whisper-1
  input_type: audio  # Required for transcription routing
  model_type: azure_openai  # or openai
  api_version: 2025-03-01-preview
  # URL and auth_token from environment variables:
  # SYGRA_TRANSCRIBE_URL and SYGRA_TRANSCRIBE_TOKEN
  parameters:
    language: en  # Optional: ISO-639-1 language code
    response_format: json  # json, verbose_json, text, srt, vtt
    temperature: 0  # 0-1, controls randomness
```

### Critical Configuration: `input_type: audio`

Transcription requires `input_type: audio` in the model configuration to route to the transcription API:

```yaml
# ✓ Correct - Routes to transcription API
transcribe:
  model: whisper-1
  input_type: audio
  model_type: openai

# ✗ Incorrect - Will not route to transcription API
transcribe:
  model: whisper-1
  model_type: openai
```

## Supported Languages

Transcription models support 50+ languages including:

| Language | Code | Language | Code |
|----------|------|----------|------|
| English | en | Spanish | es |
| French | fr | German | de |
| Italian | it | Portuguese | pt |
| Dutch | nl | Russian | ru |
| Chinese | zh | Japanese | ja |
| Korean | ko | Arabic | ar |
| Hindi | hi | Turkish | tr |

For a complete list, see [OpenAI Whisper Documentation](https://platform.openai.com/docs/guides/speech-to-text).

## Response Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| `json` | JSON with transcribed text only | Simple transcription |
| `verbose_json` | JSON with text, timestamps, and metadata | Detailed analysis |
| `text` | Plain text only | Direct text output |
| `srt` | SubRip subtitle format with timestamps | Video subtitles |
| `vtt` | WebVTT subtitle format with timestamps | Web video subtitles |

### Example Outputs

**JSON Format:**
```json
{
  "text": "Hello, how are you today?"
}
```

**Verbose JSON Format:**
```json
{
  "task": "transcribe",
  "language": "english",
  "duration": 2.5,
  "text": "Hello, how are you today?",
  "segments": [
    {
      "id": 0,
      "seek": 0,
      "start": 0.0,
      "end": 2.5,
      "text": " Hello, how are you today?",
      "temperature": 0.0,
      "avg_logprob": -0.2
    }
  ]
}
```

**SRT Format:**
```
1
00:00:00,000 --> 00:00:02,500
Hello, how are you today?
```

## Transcription Example Configuration

Based on `tasks/examples/transcription_apis/graph_config.yaml`:

### Input Data (`test.json`)

```json
[
  {
    "id": "1",
    "audio": "/path/to/audio/meeting_recording.mp3"
  },
  {
    "id": "2",
    "audio": "/path/to/audio/interview.wav"
  }
]
```

### Graph Configuration

```yaml
data_config:
  source:
    type: "disk"
    file_path: "tasks/examples/transcription_apis/test.json"

graph_config:
  nodes:
    audio_to_text:
      output_keys: transcription
      node_type: llm
      prompt:
        - user:
            - type: audio_url
              audio_url: "{audio}"
      model:
        name: transcribe

  edges:
    - from: START
      to: audio_to_text
    - from: audio_to_text
      to: END

output_config:
  output_map:
    id:
      from: id
    audio:
      from: audio
    transcription:
      from: transcription
```

### Output

```json
[
  {
    "id": "1",
    "audio": "/path/to/audio/meeting_recording.mp3",
    "transcription": "Welcome everyone to today's meeting. Let's start with the agenda..."
  },
  {
    "id": "2",
    "audio": "/path/to/audio/interview.wav",
    "transcription": "Thank you for joining us today. Can you tell us about your background?"
  }
]
```

## Advanced Transcription Features

### Language Specification

Specifying the language improves accuracy and speed:

```yaml
model:
  name: transcribe
  parameters:
    language: es  # Spanish
    response_format: json
    temperature: 0
```

### Timestamps (Verbose JSON)

For detailed timestamp information:

```yaml
model:
  name: transcribe
  parameters:
    response_format: verbose_json
    timestamp_granularities: ["word", "segment"]  # Word and segment-level timestamps
```

### Context Prompt

Provide context to improve accuracy on specific terms:

```yaml
prompt:
  - user:
      - type: audio_url
        audio_url: "{audio}"
      - type: text
        text: "The audio contains technical terms like Kubernetes, Docker, and CI/CD."
```

The text prompt is automatically passed as the `prompt` parameter to the transcription API.

## Comparison: Transcription vs Audio-Understanding LLMs

| Feature | Transcription Models | Audio LLMs (Qwen2-Audio) |
|---------|---------------------|---------------------------|
| **Primary Use** | Speech-to-text conversion | Audio understanding, reasoning, Q&A |
| **API Endpoint** | `audio.transcriptions.create` | `chat.completions.create` |
| **Output** | Transcribed text only | Contextual text responses |
| **Timestamps** | Yes (word/segment level) | No |
| **Multiple Formats** | Yes (JSON, SRT, VTT, text) | No (text only) |
| **Language Support** | 50+ languages | Varies by model |
| **Best For** | Accurate transcription, subtitles | Audio reasoning, classification, Q&A |
| **Configuration** | `input_type: audio` required | Standard LLM config |
| **Supported Audio** | MP3, MP4, MPEG, MPGA, M4A, WAV, WEBM, FLAC, OGG | Same |

## Best Practices for Transcription

### 1. Language Specification
Always specify the language if known:
```yaml
parameters:
  language: en  # or es, fr, de, etc.
```

### 2. Temperature Setting
Use temperature 0 for deterministic transcription:
```yaml
parameters:
  temperature: 0  # Recommended for transcription
```

### 3. Audio Quality
- Use high-quality audio files (16kHz or higher sample rate)
- Minimize background noise for better accuracy
- Ensure clear speech with minimal overlapping speakers

### 4. Context Prompts
Provide context for technical terms or specific vocabulary:
```yaml
- type: text
  text: "This audio discusses machine learning models including BERT, GPT, and transformers."
```

### 5. File Size Limits
- Maximum audio file size: 25 MB (OpenAI limit)
- For longer audio, split into chunks before transcription

---

## Notes

- **Audio generation is not supported** in this module. The `audio_url` type is strictly for passing existing audio inputs (e.g., loaded from datasets), not for generating new audio via model output.
- **Transcription models** require `input_type: audio` in model configuration to route to the transcription API.
- For audio understanding LLM examples, see: [`tasks/examples/audio_to_text`](https://github.com/ServiceNow/SyGra/tree/main/tasks/examples/audio_to_text)
- For transcription examples, see: [`tasks/examples/transcription_apis`](https://github.com/ServiceNow/SyGra/tree/main/tasks/examples/transcription_apis)

---

## See Also

- [GPT-4o Audio](./gpt_4o_audio.md) - Multimodal audio generation and understanding with GPT-4o
- [Text to Speech](./text_to_speech.md) - Text-to-speech generation
- [Image to Text](./image_to_text.md) - Vision-based multimodal pipelines
- [OpenAI Whisper Documentation](https://platform.openai.com/docs/guides/speech-to-text) - Official OpenAI Whisper API reference


