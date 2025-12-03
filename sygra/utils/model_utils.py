"""
Utility functions for model input/output type detection and validation.

This module provides helper functions to detect and validate model input and output types,
making model routing logic cleaner and more maintainable.
"""

from typing import Any, Optional

from langchain_core.prompt_values import ChatPromptValue

from sygra.logger.logger_config import logger


class InputType:
    """Constants for input types"""

    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"


class OutputType:
    """Constants for output types"""

    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"


def detect_input_type(input_value: ChatPromptValue) -> str:
    """
    Detect the input type from message content.

    Checks message content for audio, image, or text data and returns the
    detected input type. Prioritizes special content types over plain text.

    Args:
        input_value: ChatPromptValue containing messages to analyze

    Returns:
        str: Detected input type (InputType.AUDIO, InputType.IMAGE, InputType.TEXT)

    Examples:
        >>> messages = [HumanMessage(content="Hello")]
        >>> input_value = ChatPromptValue(messages=messages)
        >>> detect_input_type(input_value)
        'text'

        >>> messages = [HumanMessage(content=[
        ...     {"type": "audio_url", "audio_url": {"url": "data:audio/wav;base64,..."}}
        ... ])]
        >>> input_value = ChatPromptValue(messages=messages)
        >>> detect_input_type(input_value)
        'audio'
    """
    has_audio = has_audio_input(input_value)
    has_image = has_image_input(input_value)

    # Prioritize audio/image over text
    if has_audio:
        return InputType.AUDIO
    elif has_image:
        return InputType.IMAGE
    else:
        return InputType.TEXT


def has_audio_input(input_value: ChatPromptValue) -> bool:
    """
    Check if input messages contain audio content.

    Detects audio in two formats:
    1. String data URLs starting with "data:audio/"
    2. Multimodal content with type "audio_url"

    Args:
        input_value: ChatPromptValue containing messages to check

    Returns:
        bool: True if audio content is detected, False otherwise

    Examples:
        >>> # String data URL
        >>> messages = [HumanMessage(content="data:audio/wav;base64,UklGR...")]
        >>> has_audio_input(ChatPromptValue(messages=messages))
        True

        >>> # Multimodal content
        >>> messages = [HumanMessage(content=[
        ...     {"type": "audio_url", "audio_url": {"url": "..."}}
        ... ])]
        >>> has_audio_input(ChatPromptValue(messages=messages))
        True

        >>> # Text only
        >>> messages = [HumanMessage(content="Hello")]
        >>> has_audio_input(ChatPromptValue(messages=messages))
        False
    """
    for message in input_value.messages:
        if hasattr(message, "content"):
            content = message.content

            # Check if content is a string starting with audio data URL
            if isinstance(content, str) and content.startswith("data:audio/"):
                return True

            # Check if content is a list with audio_url items
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "audio_url":
                        return True

    return False


def has_image_input(input_value: ChatPromptValue) -> bool:
    """
    Check if input messages contain image content.

    Detects images in two formats:
    1. String data URLs starting with "data:image/"
    2. Multimodal content with type "image_url"

    Args:
        input_value: ChatPromptValue containing messages to check

    Returns:
        bool: True if image content is detected, False otherwise

    Examples:
        >>> # String data URL
        >>> messages = [HumanMessage(content="data:image/png;base64,iVBORw0K...")]
        >>> has_image_input(ChatPromptValue(messages=messages))
        True

        >>> # Multimodal content
        >>> messages = [HumanMessage(content=[
        ...     {"type": "image_url", "image_url": {"url": "..."}}
        ... ])]
        >>> has_image_input(ChatPromptValue(messages=messages))
        True

        >>> # Text only
        >>> messages = [HumanMessage(content="Hello")]
        >>> has_image_input(ChatPromptValue(messages=messages))
        False
    """
    for message in input_value.messages:
        if hasattr(message, "content"):
            content = message.content

            # Check if content is a string starting with image data URL
            if isinstance(content, str) and content.startswith("data:image/"):
                return True

            # Check if content is a list with image_url items
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        return True

    return False


def get_output_type(model_config: dict[str, Any]) -> str:
    """
    Get the output type from model configuration.

    Checks the model_config for an explicit output_type setting.
    Defaults to TEXT if not specified.

    Args:
        model_config: Model configuration dictionary

    Returns:
        str: Output type (OutputType.AUDIO, OutputType.IMAGE, or OutputType.TEXT)

    Examples:
        >>> config = {"name": "tts_model", "output_type": "audio"}
        >>> get_output_type(config)
        'audio'

        >>> config = {"name": "dalle", "output_type": "image"}
        >>> get_output_type(config)
        'image'

        >>> config = {"name": "gpt4"}
        >>> get_output_type(config)
        'text'
    """
    output_type = str(model_config.get("output_type", OutputType.TEXT))
    return output_type


def is_gpt4o_audio_model(model_config: dict[str, Any]) -> bool:
    """
    Check if the model is a GPT-4o-audio model.

    GPT-4o-audio models use chat.completions.create with special audio handling,
    different from standard TTS or transcription models.

    Args:
        model_config: Model configuration dictionary

    Returns:
        bool: True if model is GPT-4o-audio, False otherwise

    Examples:
        >>> config = {"model": "gpt-4o-audio-preview"}
        >>> is_gpt4o_audio_model(config)
        True

        >>> config = {"model": "whisper-1"}
        >>> is_gpt4o_audio_model(config)
        False
    """
    model_name = str(model_config.get("model", "")).lower()
    return "gpt-4o-audio" in model_name


def should_route_to_transcription(
    input_value: ChatPromptValue, model_config: dict[str, Any]
) -> bool:
    """
    Determine if request should route to transcription.

    Transcription is triggered when audio input is detected and the model
    is not a GPT-4o-audio model (which has its own handling).

    Args:
        input_value: ChatPromptValue containing messages
        model_config: Model configuration dictionary

    Returns:
        bool: True if should route to transcription, False otherwise

    Examples:
        >>> messages = [HumanMessage(content=[
        ...     {"type": "audio_url", "audio_url": {"url": "..."}}
        ... ])]
        >>> config = {"model": "whisper-1"}
        >>> should_route_to_transcription(
        ...     ChatPromptValue(messages=messages), config
        ... )
        True

        >>> # GPT-4o-audio handles audio differently
        >>> config = {"model": "gpt-4o-audio-preview"}
        >>> should_route_to_transcription(
        ...     ChatPromptValue(messages=messages), config
        ... )
        False
    """
    # presence of input type as audio and output_type as text is mandatory for transcription routing
    if (
        model_config.get("input_type", None) == InputType.AUDIO
        and model_config.get("output_type", OutputType.TEXT) == OutputType.TEXT
    ):
        if has_audio_input(input_value) and not is_gpt4o_audio_model(model_config):
            return True
        else:
            logger.error("Transcription routing requested but no audio input detected.")
    return False


def should_route_to_speech(model_config: dict[str, Any]) -> bool:
    """
    Determine if request should route to TTS (text-to-speech).

    TTS is triggered when output_type is explicitly set to "audio".

    Args:
        model_config: Model configuration dictionary

    Returns:
        bool: True if should route to TTS, False otherwise

    Examples:
        >>> config = {"name": "tts", "output_type": "audio"}
        >>> should_route_to_speech(config)
        True

        >>> config = {"name": "whisper"}
        >>> should_route_to_speech(config)
        False
    """
    return get_output_type(model_config) == OutputType.AUDIO


def should_route_to_image(model_config: dict[str, Any]) -> bool:
    """
    Determine if request should route to image generation/editing.

    Image processing is triggered when output_type is explicitly set to "image".

    Args:
        model_config: Model configuration dictionary

    Returns:
        bool: True if should route to image processing, False otherwise

    Examples:
        >>> config = {"name": "dalle", "output_type": "image"}
        >>> should_route_to_image(config)
        True

        >>> config = {"name": "gpt4"}
        >>> should_route_to_image(config)
        False
    """
    return get_output_type(model_config) == OutputType.IMAGE


def get_model_capabilities(model_config: dict[str, Any]) -> dict[str, Any]:
    """
    Get a summary of model capabilities based on configuration.

    Returns a dictionary describing what the model supports based on
    its configuration and name.

    Args:
        model_config: Model configuration dictionary

    Returns:
        dict: Dictionary with capability flags:
            - input_types: List of supported input types
            - output_type: Configured output type
            - is_audio_chat: Whether it's a GPT-4o-audio model
            - is_multimodal: Whether it supports multiple input types

    Examples:
        >>> config = {"model": "gpt-4-vision", "output_type": "text"}
        >>> caps = get_model_capabilities(config)
        >>> caps["input_types"]
        ['text', 'image']

        >>> config = {"model": "tts-1", "output_type": "audio"}
        >>> caps = get_model_capabilities(config)
        >>> caps["output_type"]
        'audio'
    """
    output_type = get_output_type(model_config)
    is_audio_chat = is_gpt4o_audio_model(model_config)

    # Determine supported input types based on model name and config
    input_types = [InputType.TEXT]  # All models support text

    model_name = str(model_config.get("model", "")).lower()

    # Vision models support images
    if "vision" in model_name or "gpt-4" in model_name or "gpt-4o" in model_name:
        input_types.append(InputType.IMAGE)

    # Audio chat models support audio input
    if is_audio_chat:
        input_types.append(InputType.AUDIO)

    # Transcription models support audio input (detected by usage, not config)
    # This is handled dynamically via has_audio_input()

    return {
        "input_types": input_types,
        "output_type": output_type,
        "is_audio_chat": is_audio_chat,
        "is_multimodal": len(input_types) > 1,
        "supports_audio_input": InputType.AUDIO in input_types,
        "supports_image_input": InputType.IMAGE in input_types,
    }


def validate_input_output_compatibility(
    input_value: ChatPromptValue, model_config: dict[str, Any]
) -> tuple[bool, Optional[str]]:
    """
    Validate that input and output types are compatible.

    Checks for common configuration issues and returns validation result.

    Args:
        input_value: ChatPromptValue containing messages
        model_config: Model configuration dictionary

    Returns:
        tuple: (is_valid: bool, error_message: Optional[str])
            - is_valid: True if configuration is valid
            - error_message: Error description if invalid, None if valid

    Examples:
        >>> # Valid: text input, text output
        >>> messages = [HumanMessage(content="Hello")]
        >>> config = {"model": "gpt-4"}
        >>> valid, error = validate_input_output_compatibility(
        ...     ChatPromptValue(messages=messages), config
        ... )
        >>> valid
        True

        >>> # Valid: audio input with transcription-capable model
        >>> messages = [HumanMessage(content=[
        ...     {"type": "audio_url", "audio_url": {"url": "..."}}
        ... ])]
        >>> config = {"model": "whisper-1"}
        >>> valid, error = validate_input_output_compatibility(
        ...     ChatPromptValue(messages=messages), config
        ... )
        >>> valid
        True
    """
    input_type = detect_input_type(input_value)
    get_output_type(model_config)
    capabilities = get_model_capabilities(model_config)

    # Audio input is valid for transcription or audio chat models
    if input_type == InputType.AUDIO:
        if not capabilities["supports_audio_input"]:
            # Check if model name suggests transcription support
            model_name = str(model_config.get("model", "")).lower()
            if "whisper" not in model_name and "transcribe" not in model_name:
                return (
                    False,
                    f"Model {model_name} may not support audio input. "
                    f"Consider using whisper-1 or gpt-4o-audio models.",
                )

    # Image input is valid for vision models
    if input_type == InputType.IMAGE:
        if not capabilities["supports_image_input"]:
            model_name = str(model_config.get("model", "")).lower()
            return (
                False,
                f"Model {model_name} does not support image input. "
                f"Consider using a vision-capable model like gpt-4-vision.",
            )

    # All validations passed
    return (True, None)
