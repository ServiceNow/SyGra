# Text to Speech Data Generation

This module introduces support for multimodal data generation pipelines that accept **text** as input and produce **audio outputs** using text-to-speech (TTS) models. It expands traditional text-only pipelines to support audio generation tasks like audiobook creation, voice narration, and multi-voice dialogue generation.

## Key Features

- Supports **text-to-audio** generation using OpenAI TTS models.
- Converts text inputs into **base64-encoded audio data URLs** compatible with standard audio formats.
- Compatible with HuggingFace datasets, streaming, and on-disk formats.
- Supports multiple voice options and audio formats.
- Variable **speed control** (0.25x to 4.0x).
- Automatic handling of multimodal outputs with file saving capabilities.

## Supported Models

**Currently, we only support OpenAI TTS models:**

- `tts-1` - Standard quality, optimized for speed
- `tts-1-hd` - High-definition quality, optimized for quality
- `gpt-4o-mini-tts` - OpenAI's newest and most reliable text-to-speech mode

Both models support all voice options and audio formats listed below.

## Input Requirements

### Text Input

Each text field to be converted to speech must:

- Be a string containing the text to synthesize
- Not exceed **4096 characters** (OpenAI TTS limit)
- Be specified in the model configuration
- Can be local dataset or from HuggingFace datasets

### Voice Options
You can choose from the following voices: https://platform.openai.com/docs/guides/text-to-speech#voice-options

### Audio Formats
You can choose from the following audio formats: https://platform.openai.com/docs/guides/text-to-speech#supported-output-formats

### Supported languages
The TTS models support multiple languages, including but not limited to: https://platform.openai.com/docs/guides/text-to-speech#supported-languages

## How Text-to-Speech Generation Works

1. Text input is extracted from the specified field in each record.
2. The TTS model generates audio from the text.
3. Audio is returned as a **base64-encoded data URL** (e.g., `data:audio/mp3;base64,...`).
4. The data URL is converted to a file and saved to disk.
5. The output json/jsonl gives the absolute path to the audio file.

## Model Configuration

The model configuration for TTS generation must specify `output_type: audio` and include TTS-specific parameters:

```yaml
tts_openai:
  model: tts
  output_type: audio 
  model_type: azure_openai 
  api_version: 2025-03-01-preview
  parameters:
    voice: "alloy"
    response_format: "wav"
```

## Example Configuration: Audiobook Generation

```yaml
data_config:
  source:
    type: "disk"
    file_path: "data/chapters.json"

graph_config:
  nodes:
    generate_chapter_audio:
      node_type: llm
      output_keys: audio
      prompt:
        - user: |
           "{chapter_text}"
      model:
        parameters:
          voice: nova
          response_format: mp3
          speed: 1.0
  
  edges:
    - from: START
      to: generate_chapter_audio
    - from: generate_chapter_audio
      to: END

output_config:
  output_map:
    id:
      from: "id"
    chapter_number:
      from: "chapter_number"
    chapter_text:
      from: "chapter_text"
    audio:
      from: "audio"
```

### Input Data (`data/chapters.json`)

```json
[
  {
    "id": "1",
    "chapter_number": 1,
    "chapter_text": "Chapter One: The Beginning. It was a dark and stormy night..."
  },
  {
    "id": "2",
    "chapter_number": 2,
    "chapter_text": "Chapter Two: The Journey. The next morning brought clear skies..."
  }
]
```

### Output

```json
[
  {
    "id": "1",
    "chapter_number": 1,
    "chapter_text": "Chapter One: The Beginning. It was a dark and stormy night...",
    "audio": "/path/to/multimodal_output/audio/1_audio_0.mp3"
  },
  {
    "id": "2",
    "chapter_number": 2,
    "chapter_text": "Chapter Two: The Journey. The next morning brought clear skies...",
    "audio": "/path/to/multimodal_output/audio/2_audio_0.mp3"
  }
]
```

---

## Notes

- **Text-to-speech generation is currently only supported for OpenAI TTS models.** Support for additional providers may be added in future releases.
- The output_type in model configuration must be set to `audio` to enable TTS generation.
- Audio files are automatically saved and managed.

---

## See Also

- [Audio to Text](./audio_to_text.md) - For speech recognition and audio transcription
- [Image to Text](./image_to_text.md) - For vision-based multimodal pipelines
- [OpenAI TTS Documentation](https://platform.openai.com/docs/guides/text-to-speech) - Official OpenAI TTS API reference
