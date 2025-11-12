# GPT-4o Audio: Multimodal Audio Generation

This module introduces support for multimodal data generation pipelines using OpenAI's GPT-4o Audio model, which supports both **audio input and audio output** through the chat completions API. Unlike traditional TTS models (like `tts-1`), `gpt-4o-audio` provides contextual, conversational audio capabilities.

## Key Features

- **Unified Chat API**: Uses `chat.completions.create` endpoint (not `audio.speech.create`)
- **Bidirectional Audio**: Supports both audio input and output in the same API
- **Voice Selection**: 6 voices (alloy, echo, fable, onyx, nova, shimmer)
- **Format Support**: WAV, MP3, Opus, AAC, FLAC, PCM
- **Context-Aware**: Full conversation context for natural, interactive responses

## Supported Models

- `gpt-4o-audio-preview`

## Model Configuration in models.yaml

First, configure the model in your `sygra/config/models.yaml` or your custom models configuration:

```yaml
gpt-4o-audio-preview:
  model_type: azure_openai  # or openai
  model: gpt-4o-audio-preview
  api_version: 2025-01-01-preview
  # URL and auth_token from environment variables:
  # SYGRA_GPT-4O-AUDIO-PREVIEW_URL and SYGRA_GPT-4O-AUDIO-PREVIEW_TOKEN
  parameters:
    max_tokens: 1000
    temperature: 1.0
```

## Voice Options

| Voice    | Characteristics                    | Best For                |
|----------|-----------------------------------|-------------------------|
| `alloy`  | Neutral, balanced                  | General purpose         |
| `echo`   | Clear, professional                | Business, presentations |
| `fable`  | Warm, storytelling                 | Narratives, audiobooks  |
| `onyx`   | Deep, authoritative                | News, announcements     |
| `nova`   | Energetic, friendly                | Tutorials, guides       |
| `shimmer`| Soft, expressive                   | Conversations, dialogue |

## Audio Formats

| Format  | MIME Type    | Use Case                          | Quality |
|---------|-------------|-----------------------------------|---------|
| `wav`   | audio/wav   | High quality, uncompressed        | Highest |
| `flac`  | audio/flac  | Lossless compression              | High    |
| `mp3`   | audio/mpeg  | Good quality, smaller files       | Medium  |
| `opus`  | audio/opus  | Low latency, streaming            | Medium  |
| `aac`   | audio/aac   | Mobile-friendly                   | Medium  |
| `pcm`   | audio/pcm   | Raw audio, maximum compatibility  | Highest |

## How It Works

### Text-to-Audio Flow

1. Text prompts are sent to the model with `output_type: audio`.
2. Model generates spoken audio response.
3. Audio is returned as **base64-encoded data URL** (e.g., `data:audio/mp3;base64,...`).
4. Data URL is automatically converted to file and saved to disk.
5. Output contains absolute path to the saved audio file.

### Audio-to-Text Flow

1. Audio input is provided as `audio_url` in the prompt content.
2. System automatically converts `audio_url` format to OpenAI's `input_audio` format.
3. Model processes audio and generates text response.
4. Text response is returned directly.

### Audio-to-Audio Flow

1. Audio input is provided as `audio_url` with `output_type: audio`.
2. Model processes audio input and generates audio output.
3. Audio is returned as base64 data URL and saved to disk.
4. Output contains absolute path to the saved audio file.

## Complete Working Example

Based on `tasks/examples/gpt_4o_audio/graph_config.yaml`:

### Input Data (`test.json`)

```json
[
  {
    "id": "1",
    "text": "Latest news from the tech world."
  },
  {
    "id": "2",
    "text": "How important is synthetic audio generation?"
  }
]
```

### Graph Configuration

```yaml
data_config:
  source:
    type: "disk"
    file_path: "tasks/examples/gpt_4o_audio/test.json"

graph_config:
  nodes:
    # Node 1: Text-to-Audio (TTS)
    text_to_audio:
      output_keys: audio
      node_type: llm
      prompt:
        - user: |
            {text}
      model:
        name: gpt-4o-audio-preview
        output_type: audio  # Enable audio output
        parameters:
          audio:  # Nested audio parameters
            voice: nova
            format: mp3

    # Node 2: Audio-to-Text (Transcription)
    audio_to_text:
      output_keys: transcription
      node_type: llm
      prompt:
        - user:
            - type: text
              text: "Transcribe the following audio."
            - type: audio_url  # Audio input from previous node
              audio_url: "{audio}"
      model:
        name: gpt-4o-audio-preview
        parameters:
          max_tokens: 1000
          temperature: 0.3

    # Node 3: Audio-to-Audio (Translation)
    audio_to_audio:
      output_keys: transformed_audio
      node_type: llm
      prompt:
        - user:
            - type: audio_url
              audio_url: "{audio}"
            - type: text
              text: "Translate this audio to Hindi language."
      model:
        name: gpt-4o-audio-preview
        output_type: audio  # Enable audio output
        parameters:
          max_tokens: 1000
          temperature: 0.5
          audio:
            voice: "alloy"
            format: "mp3"

  edges:
    - from: START
      to: text_to_audio
    - from: text_to_audio
      to: audio_to_text
    - from: audio_to_text
      to: audio_to_audio
    - from: audio_to_audio
      to: END

output_config:
  output_map:
    id:
      from: id
    audio:
      from: audio
    text:
      from: text
    transcription:
      from: transcription
    transformed_audio:
      from: transformed_audio
```

### Output

```json
[
  {
    "id": "1",
    "text": "Latest news from the tech world.",
    "audio": "/path/to/multimodal_output/audio/1_audio_0.mp3",
    "transcription": "Latest news from the tech world.",
    "transformed_audio": "/path/to/multimodal_output/audio/1_transformed_audio_0.mp3"
  },
  {
    "id": "2",
    "text": "How important is synthetic audio generation?",
    "audio": "/path/to/multimodal_output/audio/2_audio_0.mp3",
    "transcription": "How important is synthetic audio generation?",
    "transformed_audio": "/path/to/multimodal_output/audio/2_transformed_audio_0.mp3"
  }
]
```

## Key Configuration Points

### 1. Nested Audio Parameters (Critical!)

GPT-4o Audio requires **nested audio parameters**:

```yaml
# ✓ Correct
parameters:
  audio:
    voice: alloy
    format: wav

# ✗ Incorrect (flat structure won't work)
parameters:
  voice: alloy
  response_format: wav
```

### 2. Audio Output

To generate audio output, set `output_type: audio` in the model configuration:

```yaml
model:
  name: gpt-4o-audio-preview
  output_type: audio  # This enables audio output
  parameters:
    audio:
      voice: nova
      format: mp3
```

### 3. Audio Input

Audio input is detected by the presence of `audio_url` in the prompt:

```yaml
prompt:
  - user:
      - type: audio_url
        audio_url: "{audio_field}"  # Base64 data URL
      - type: text
        text: "Transcribe this audio."
```

The audio must be provided as a base64-encoded data URL:
```
data:audio/wav;base64,UklGRi4AAABXQVZFZm10...
```

## Output File Organization

Generated audio files are saved to:

```
task_dir/
└── multimodal_output/
    └── audio/
        ├── {record_id}_{field_name}_0.{format}
        ├── {record_id}_{field_name}_1.{format}
        └── ...
```

- `record_id`: ID from input record
- `field_name`: Output field name from graph config
- `index`: Audio index (for multiple outputs)
- `format`: Audio format (wav, mp3, etc.)

## Notes
- If input is only text, then gpt-4o-audio-preview model will generate audio output irrespective of the output_type as it is not a text-to-text model.
- Audio input is detected by the presence of `audio_url` items in prompt content
- Audio files are automatically saved to `multimodal_output/audio/` directory

---

## See Also

- [Text to Speech](./text_to_speech.md) - Traditional TTS models (tts-1, tts-1-hd)
- [Audio to Text](./audio_to_text.md) - Whisper and other speech recognition models
- [Image Generation](./image_generation.md) - Text-to-image and image editing
- [OpenAI Audio API Documentation](https://platform.openai.com/docs/guides/audio) - Official OpenAI Audio API reference
