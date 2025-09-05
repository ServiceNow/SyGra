# Audio to Text

This example demonstrates how to create a multimodal pipeline for processing audio inputs and generating textual outputs using the GraSP framework. It showcases the integration of audio-capable LLMs like Qwen2-Audio-7B for tasks such as audio classification, speech recognition, and audio content analysis.

## Overview

The audio to text example is designed to:

- **Process audio inputs**: Handle various audio file formats and sources
- **Enable multimodal prompting**: Combine audio with textual instructions
- **Support audio analysis**: Identify sounds, transcribe speech, and analyze audio content
- **Showcase HuggingFace integration**: Stream data from HuggingFace datasets

## Directory Contents

- `graph_config.yaml`: Configuration file defining the workflow for audio processing

## How It Works

1. **Data Loading**: The system loads audio samples from a HuggingFace dataset:
   - Uses the "datasets-examples/doc-audio-1" repository
   - Streams data to minimize memory requirements

2. **Audio Processing**:
   - Audio files are automatically detected and handled
   - Files are converted to base64-encoded data URLs for LLM compatibility
   - Multiple audio formats are supported (.wav, .flac, .mp3, etc.)

3. **LLM Processing**:
   - The Qwen2-Audio-7B model receives both text instructions and the audio data
   - The model analyzes the audio content based on the instructions
   - In this example, it identifies the animal in the audio

4. **Result Collection**:
   - The system captures the LLM's textual analysis
   - Results are structured into standardized output formats

## Usage

To customize it:

- Modify the prompt text in `graph_config.yaml` to change the analysis task
- Replace the HuggingFace dataset with your own audio sources
- Adjust model parameters like temperature to control output variability

## Example Output

The system produces structured output containing:
- The ID of the processed record
- The reference to the original audio
- The identified animal or other requested analysis

This example demonstrates GraSP's ability to handle multimodal data processing, combining audio inputs with AI-powered analysis to generate meaningful textual insights.
