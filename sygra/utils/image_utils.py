import base64
import io
import os
import re
from pathlib import Path
from typing import Any, Optional, Tuple

import httpx
import requests  # type: ignore[import-untyped]
from PIL import Image

from sygra.logger.logger_config import logger

# Curated list of common user-facing image file extensions
COMMON_IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
    ".ico",
    ".apng",
)


def load_image(data: Any) -> Optional[Image.Image]:
    """
    Attempt to load an image from various types of inputs.

    Args:
        data (Any): The input data which can be an Image object, bytes, a file path, or a URL.

    Returns:
        Optional[Image.Image]: The loaded PIL Image object or None if loading fails.
    """
    try:
        if isinstance(data, Image.Image):
            return data
        if isinstance(data, dict) and isinstance(data.get("bytes"), bytes):
            return Image.open(io.BytesIO(data["bytes"]))
        if isinstance(data, bytes):
            return Image.open(io.BytesIO(data))
        if isinstance(data, str):
            if data.startswith("http"):
                response = requests.get(data, timeout=5)
                response.raise_for_status()
                return Image.open(io.BytesIO(response.content))
            if os.path.exists(data):
                return Image.open(data)
        logger.warning(f"Unsupported image data format: {type(data)}")
        return None
    except Exception as e:
        logger.warning(f"Failed to load image: {e}")
        return None


def get_image_fields(record: dict[str, Any]) -> list[str]:
    """
    Identify keys in a record that likely contain image data.

    Args:
        record (dict[str, Any]): The record to inspect.

    Returns:
        list[str]: A list of keys that contain image-like data.
    """
    image_fields = set()

    for key, value in record.items():
        if is_data_url(value) or is_image_like(value):
            image_fields.add(key)
        elif isinstance(value, list):
            # Only check the first item in the list for image-like data
            if value and (is_image_like(value[0]) or is_data_url(value[0])):
                image_fields.add(key)

    if not image_fields:
        logger.warning("No image fields found in the record.")
    return list(image_fields)


def is_data_url(val: Any) -> bool:
    """
    Check if value is already a base64 data URL.

    Args:
        val (Any): The value to check.

    Returns:
        bool: True if the value is a data URL, False otherwise.
    """
    return isinstance(val, str) and val.startswith("data:image/")


def is_valid_image_bytes(data: bytes) -> bool:
    """
    Safely verify whether bytes represent a valid image.

    Args:
        data (bytes): The byte data to check.

    Returns:
        bool: True if the bytes represent a valid image, False otherwise.
    """
    try:
        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:
        return False


def is_image_like(val: Any) -> bool:
    """
    Check if a value looks like valid image content.

    Args:
        val (Any): The value to check.

    Returns:
        bool: True if the value is an image or looks like an image, False otherwise.
    """
    if isinstance(val, Image.Image):
        return True
    elif isinstance(val, dict) and isinstance(val.get("bytes"), bytes):
        return is_valid_image_bytes(val["bytes"])
    elif isinstance(val, bytes):
        return is_valid_image_bytes(val)
    elif isinstance(val, str):
        return (
            val.startswith("http") and val.lower().endswith(COMMON_IMAGE_EXTENSIONS)
        ) or val.lower().endswith(  # URL check
            COMMON_IMAGE_EXTENSIONS
        )  # Local file check
    return False


def get_image_url(image: Image.Image) -> str:
    """
    Convert a PIL Image to a base64-encoded data URL string.

    Args:
        image (Image.Image): The PIL Image to convert.

    Returns:
        str: The base64-encoded data URL string representing the image.
    """
    try:
        image_bytes_io = io.BytesIO()
        format = image.format or "PNG"
        image.save(image_bytes_io, format=format)
        encoded = base64.b64encode(image_bytes_io.getvalue()).decode("utf-8")
        mime_type = f"image/{format.lower()}"
        return f"data:{mime_type};base64,{encoded}"
    except Exception as e:
        logger.warning(f"Failed to encode image to data URL: {e}")
        return ""


def expand_image_item(item: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Expand an image item with a variable URL into multiple items if necessary.

    Args:
        item (dict[str, Any]): The image item to expand.
        state (dict[str, Any]): The current state containing variable values.

    Returns:
        list[dict[str, Any]]: A list of expanded image items.
    """
    key_match = re.findall(r"{(.*?)}", item["image_url"])
    expanded = []
    if key_match:
        assert len(key_match) == 1, "Only one variable is expected in image_url"
        var_name = key_match[0]
        val = state.get(var_name)
        if isinstance(val, list):
            for img_url in val:
                expanded.append({"type": "image_url", "image_url": img_url})
        else:
            expanded.append({"type": "image_url", "image_url": val})
    else:
        expanded.append(item)
    return expanded


def parse_image_data_url(data_url: str) -> Tuple[str, str, bytes]:
    """
    Parse an image data URL and extract MIME type, extension, and decoded content.

    Args:
        data_url (str): The data URL string (e.g., "data:image/png;base64,...")

    Returns:
        Tuple[str, str, bytes]: Tuple of (mime_type, file_extension, decoded_bytes)

    Raises:
        ValueError: If the data URL format is invalid
    """
    # Pattern: data:<mime_type>;base64,<base64_data>
    pattern = r"^data:([^;]+);base64,(.+)$"
    match = re.match(pattern, data_url)

    if not match:
        raise ValueError(f"Invalid image data URL format: {data_url[:50]}...")

    mime_type = match.group(1)
    base64_data = match.group(2)

    # Decode base64 data
    try:
        decoded_bytes = base64.b64decode(base64_data)
    except Exception as e:
        raise ValueError(f"Failed to decode base64 data: {e}")

    # Determine file extension from MIME type
    mime_to_ext = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/bmp": "bmp",
        "image/tiff": "tiff",
        "image/tif": "tif",
        "image/webp": "webp",
        "image/ico": "ico",
        "image/apng": "apng",
    }

    file_extension = mime_to_ext.get(mime_type, mime_type.split("/")[-1])

    return mime_type, file_extension, decoded_bytes


def save_image_data_url(
    data_url: str, output_dir: Path, record_id: str, field_name: str, index: int = 0
) -> str:
    """
    Save an image data URL to a file and return the file path.

    Args:
        data_url (str): The base64 data URL to save
        output_dir (Path): Directory where the file should be saved
        record_id (str): ID of the record (for unique filename)
        field_name (str): Name of the field containing the data
        index (int): Index if the field contains multiple items (default: 0)

    Returns:
        str: Relative path to the saved file

    Raises:
        ValueError: If the data URL is invalid or saving fails
    """
    try:
        # Parse the data URL
        mime_type, file_extension, decoded_bytes = parse_image_data_url(data_url)

        # Create subdirectory for images
        image_dir = output_dir / "image"
        image_dir.mkdir(parents=True, exist_ok=True)

        # Create filename: record_id_fieldname_index.extension
        filename = f"{record_id}_{field_name}_{index}.{file_extension}"
        file_path = image_dir / filename

        # Save the decoded bytes to file
        with open(file_path, "wb") as f:
            f.write(decoded_bytes)

        full_path = str(file_path.resolve())

        logger.debug(f"Saved image file: {full_path} ({len(decoded_bytes)} bytes)")
        return full_path

    except Exception as e:
        logger.error(f"Failed to save image data: {e}")
        raise


async def url_to_data_url(url: str, model_name: str = "image_model") -> str:
    """
    Fetch an image from URL and convert to base64 data URL.

    Args:
        url (str): The image URL to fetch
        model_name (str): Name of the model (for logging)

    Returns:
        str: Base64-encoded data URL
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            image_bytes = response.content

            # Convert to base64
            b64_encoded = base64.b64encode(image_bytes).decode("utf-8")

            # Determine format from content-type or default to png
            content_type = response.headers.get("content-type", "image/png")
            if "image/" in content_type:
                image_format = content_type.split("/")[-1]
            else:
                image_format = "png"

            return f"data:image/{image_format};base64,{b64_encoded}"
    except Exception as e:
        logger.error(f"[{model_name}] Failed to fetch image from URL {url}: {e}")
        # Return original URL as fallback
        return url


async def process_image_response(image_response: Any, model_name: str = "image_model") -> list[str]:
    """
    Process regular (non-streaming) image response.
    Converts all URLs to data URLs for consistency.

    Args:
        image_response: The response from OpenAI images API
        model_name (str): Name of the model (for logging)

    Returns:
        list[str]: List of base64-encoded image data URLs
    """
    images_data = []
    for img_data in image_response.data:
        # Try to get b64_json first
        if hasattr(img_data, "b64_json") and img_data.b64_json:
            b64_json = img_data.b64_json
            # Create base64 encoded data URL
            data_url = f"data:image/png;base64,{b64_json}"
            images_data.append(data_url)
        # Otherwise get URL and convert to data URL
        elif hasattr(img_data, "url") and img_data.url:
            data_url = await url_to_data_url(img_data.url, model_name)
            images_data.append(data_url)
        else:
            logger.error(f"[{model_name}] Image data has neither b64_json nor url")

    return images_data


async def process_streaming_image_response(
    stream_response: Any, model_name: str = "image_model"
) -> list[str]:
    """
    Process streaming image generation response.
    Collects all events and converts URLs to data URLs.

    Args:
        stream_response: The streaming response from OpenAI images API
        model_name (str): Name of the model (for logging)

    Returns:
        list[str]: List of base64-encoded image data URLs
    """
    images_data = []
    async for event in stream_response:
        if hasattr(event, "data"):
            for img_data in event.data:
                # Convert to data URL
                if hasattr(img_data, "b64_json") and img_data.b64_json:
                    data_url = f"data:image/png;base64,{img_data.b64_json}"
                    images_data.append(data_url)
                elif hasattr(img_data, "url") and img_data.url:
                    # Fetch URL and convert to data URL
                    data_url = await url_to_data_url(img_data.url, model_name)
                    images_data.append(data_url)

    return images_data


def extract_image_urls_from_messages(messages: list) -> tuple[list[str], str]:
    """
    Extract image data URLs and text prompt from messages.

    Extracts all image_url content and concatenates text content
    from a list of LangChain messages.

    Args:
        messages: List of LangChain message objects

    Returns:
        tuple: (image_data_urls: list[str], text_prompt: str)
            - image_data_urls: List of image data URL strings
            - text_prompt: Concatenated text content from messages

    Examples:
        >>> from langchain_core.messages import HumanMessage
        >>> messages = [HumanMessage(content=[
        ...     {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
        ...     {"type": "text", "text": "Describe this image"}
        ... ])]
        >>> image_urls, text = extract_image_urls_from_messages(messages)
        >>> len(image_urls)
        1
        >>> text
        'Describe this image'
    """
    image_data_urls = []
    text_prompt = ""

    for message in messages:
        if hasattr(message, "content"):
            content = message.content

            # Handle string content
            if isinstance(content, str):
                if content.startswith("data:image/"):
                    image_data_urls.append(content)
                else:
                    text_prompt += content + " "

            # Handle list content (multimodal)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "image_url":
                            image_url = item.get("image_url", {})
                            url = image_url.get("url", "")
                            if url:
                                image_data_urls.append(url)
                        elif item.get("type") == "text":
                            text_prompt += item.get("text", "") + " "
                        else:
                            # Unhandled content type (expected: 'audio_url' or 'text')
                            logger.warning(f"Skipping unsupported content type: {item.get('type')}")
                    else:
                        # Expected dict but got something else
                        logger.error(f"Expected dict in content list, got {type(item).__name__}: {item}")
            else:
                # Content is neither string nor list
                logger.error(f"Unexpected content format: expected str or list, got {type(content).__name__}")


    return image_data_urls, text_prompt.strip()


def create_image_file_from_data_url(image_data_url: str, index: int = 0) -> "io.BytesIO":
    """
    Create a file-like object from an image data URL.

    Parses the image data URL, extracts the image bytes, and creates
    a BytesIO object with appropriate filename.

    Args:
        image_data_url: Base64-encoded image data URL (e.g., "data:image/png;base64,...")
        index: Index for filename when processing multiple images (default: 0)

    Returns:
        io.BytesIO: File-like object containing image data with .name attribute set

    Raises:
        ValueError: If data URL is invalid or cannot be parsed

    Examples:
        >>> data_url = "data:image/png;base64,iVBORw0K..."
        >>> image_file = create_image_file_from_data_url(data_url)
        >>> image_file.name
        'image_0.png'
        >>> isinstance(image_file, io.BytesIO)
        True
    """
    import io

    mime_type, image_format, image_bytes = parse_image_data_url(image_data_url)

    image_file = io.BytesIO(image_bytes)
    image_file.name = f"image_{index}.{image_format}"

    return image_file
