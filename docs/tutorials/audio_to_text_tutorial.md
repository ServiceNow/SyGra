# Audio Classification

This tutorial demonstrates how to build a multimodal pipeline for processing audio files and generating textual output using the GraSP framework. You’ll learn to integrate audio-capable LLMs for audio classification, speech recognition, or content analysis.

> **Key Features You’ll Learn**  
> `multimodal processing`, `audio classification`, `base64 encoding`, `audio-capable LLMs`, `HuggingFace dataset integration`

---

## Prerequisites

- GraSP framework installed (see [Installation Guide](../installation.md))
- Access to an LLM that supports audio input (e.g., Qwen2-Audio-7B)
- Basic knowledge of audio file formats

---

## What You’ll Build

You’ll create a pipeline that:
- **Loads audio samples** from a HuggingFace dataset
- **Processes audio files** (detects, encodes, and prepares for LLM input)
- **Sends audio and instructions to an LLM**
- **Receives and structures the LLM’s analysis**

---

## Step 1: Project Structure

```
audio_to_text/
├── graph_config.yaml    # Workflow for audio processing
```

## Step 2: Pipeline Implementation

### Graph Configuration (`graph_config.yaml`)

The `graph_config.yaml` file defines the workflow for the audio-to-text task. Here’s what it does:

- **Data Source**: Loads audio samples from the HuggingFace `datasets-examples/doc-audio-1` repository, with streaming enabled for efficiency.
- **Nodes**: Defines a single node named `identify_animal` of type `llm`. This node is configured with:
  - **Prompt**: Combines a text instruction ("Identify the animal in the provided audio.") and the audio file (as a base64-encoded URL) for multimodal input.
  - **Model**: Uses the `qwen_2_audio_7b` model with parameters suitable for audio analysis.
- **Edges**: Sets up a simple workflow from `START` to `identify_animal` and then to `END`.
- **Output Config**: Maps the output fields (`id`, `audio`, `animal`) from the state to the final output structure.

### Reference Implementation

See the GraSP repository for the complete example:

- Graph configuration: [audio_to_text/graph_config.yaml](https://github.com/ServiceNow/GraSP/blob/main/tasks/examples/audio_to_text/graph_config.yaml)

## Step 3: Output Collection

- The system captures the LLM’s analysis (e.g., animal identification) and structures results in a standardized JSON format for downstream use.

## Step 4: Running the Pipeline

From your GraSP project root, run:

```bash
python main.py --task path/to/your/audio_to_text
```

---

## Example Output

```json
[
    {
        "id": "sample1",
        "audio_url": "data:audio/wav;base64,UklGRuQAAABXQVZFZm10IBAAAAABAAEA...",
        "analysis": "The audio contains the sound of a dog barking."
    },
    {
        "id": "sample2",
        "audio_url": "data:audio/wav;base64,UklGRuQAAABXQVZFZm10IBAAAAABAAEA...",
        "analysis": "The audio contains the sound of a cat meowing."
    }
]
```

---

## Try It Yourself

- Add new audio samples or use your own recordings
- Modify the prompt to instruct the LLM to perform different analyses (e.g., speech-to-text)

---

## Next Steps

- Explore [image to QnA](image_to_qna_tutorial.md) for multimodal image processing
- Learn about [structured output](structured_output_tutorial.md) for standardized results
