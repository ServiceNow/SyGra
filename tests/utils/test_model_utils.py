import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.append(str(Path(__file__).parent.parent.parent))

from sygra.utils.model_utils import (
    InputType,
    OutputType,
    detect_input_type,
    get_model_capabilities,
    get_output_type,
    has_audio_input,
    has_image_input,
    is_gpt4o_audio_model,
    should_route_to_image,
    should_route_to_speech,
    should_route_to_transcription,
    validate_input_output_compatibility,
)


def _make_chat_prompt(content):
    """Helper: create a mock ChatPromptValue with one message."""
    msg = MagicMock()
    msg.content = content
    prompt = MagicMock()
    prompt.messages = [msg]
    return prompt


class TestHasAudioInput(unittest.TestCase):
    def test_detects_audio_data_url_string(self):
        prompt = _make_chat_prompt("data:audio/wav;base64,UklGR...")
        self.assertTrue(has_audio_input(prompt))

    def test_detects_audio_url_in_list_content(self):
        prompt = _make_chat_prompt([{"type": "audio_url", "audio_url": {"url": "..."}}])
        self.assertTrue(has_audio_input(prompt))

    def test_returns_false_for_plain_text(self):
        prompt = _make_chat_prompt("Hello, world!")
        self.assertFalse(has_audio_input(prompt))

    def test_returns_false_for_image_content(self):
        prompt = _make_chat_prompt("data:image/png;base64,abc")
        self.assertFalse(has_audio_input(prompt))


class TestHasImageInput(unittest.TestCase):
    def test_detects_image_data_url_string(self):
        prompt = _make_chat_prompt("data:image/png;base64,iVBOR...")
        self.assertTrue(has_image_input(prompt))

    def test_detects_image_url_in_list_content(self):
        prompt = _make_chat_prompt([{"type": "image_url", "image_url": {"url": "..."}}])
        self.assertTrue(has_image_input(prompt))

    def test_returns_false_for_plain_text(self):
        prompt = _make_chat_prompt("Hello!")
        self.assertFalse(has_image_input(prompt))

    def test_returns_false_for_audio_content(self):
        prompt = _make_chat_prompt("data:audio/wav;base64,abc")
        self.assertFalse(has_image_input(prompt))


class TestDetectInputType(unittest.TestCase):
    def test_returns_audio_when_audio_present(self):
        prompt = _make_chat_prompt("data:audio/wav;base64,abc")
        self.assertEqual(detect_input_type(prompt), InputType.AUDIO)

    def test_returns_image_when_image_present(self):
        prompt = _make_chat_prompt("data:image/png;base64,abc")
        self.assertEqual(detect_input_type(prompt), InputType.IMAGE)

    def test_returns_text_for_plain_text(self):
        prompt = _make_chat_prompt("Hello")
        self.assertEqual(detect_input_type(prompt), InputType.TEXT)

    def test_audio_takes_priority_over_image(self):
        msg1 = MagicMock()
        msg1.content = "data:audio/wav;base64,abc"
        msg2 = MagicMock()
        msg2.content = "data:image/png;base64,abc"
        prompt = MagicMock()
        prompt.messages = [msg1, msg2]
        self.assertEqual(detect_input_type(prompt), InputType.AUDIO)


class TestGetOutputType(unittest.TestCase):
    def test_returns_text_by_default(self):
        self.assertEqual(get_output_type({}), OutputType.TEXT)

    def test_returns_audio_when_configured(self):
        self.assertEqual(get_output_type({"output_type": "audio"}), OutputType.AUDIO)

    def test_returns_image_when_configured(self):
        self.assertEqual(get_output_type({"output_type": "image"}), OutputType.IMAGE)


class TestIsGpt4oAudioModel(unittest.TestCase):
    def test_returns_true_for_gpt4o_audio_model(self):
        self.assertTrue(is_gpt4o_audio_model({"model": "gpt-4o-audio-preview"}))

    def test_returns_false_for_whisper(self):
        self.assertFalse(is_gpt4o_audio_model({"model": "whisper-1"}))

    def test_returns_false_for_regular_gpt4(self):
        self.assertFalse(is_gpt4o_audio_model({"model": "gpt-4"}))

    def test_case_insensitive(self):
        self.assertTrue(is_gpt4o_audio_model({"model": "GPT-4O-AUDIO-PREVIEW"}))


class TestShouldRouteToSpeech(unittest.TestCase):
    def test_returns_true_when_output_type_is_audio(self):
        self.assertTrue(should_route_to_speech({"output_type": "audio"}))

    def test_returns_false_for_text_output(self):
        self.assertFalse(should_route_to_speech({"output_type": "text"}))

    def test_returns_false_when_output_type_not_set(self):
        self.assertFalse(should_route_to_speech({}))


class TestShouldRouteToImage(unittest.TestCase):
    def test_returns_true_when_output_type_is_image(self):
        self.assertTrue(should_route_to_image({"output_type": "image"}))

    def test_returns_false_for_text_output(self):
        self.assertFalse(should_route_to_image({"output_type": "text"}))


class TestGetModelCapabilities(unittest.TestCase):
    def test_all_models_support_text_input(self):
        caps = get_model_capabilities({"model": "gpt-3.5"})
        self.assertIn(InputType.TEXT, caps["input_types"])

    def test_gpt4_supports_image_input(self):
        caps = get_model_capabilities({"model": "gpt-4"})
        self.assertIn(InputType.IMAGE, caps["input_types"])
        self.assertTrue(caps["is_multimodal"])

    def test_gpt4o_audio_supports_audio_input(self):
        caps = get_model_capabilities({"model": "gpt-4o-audio-preview"})
        self.assertTrue(caps["is_audio_chat"])
        self.assertIn(InputType.AUDIO, caps["input_types"])

    def test_audio_output_type_reflected(self):
        caps = get_model_capabilities({"model": "tts-1", "output_type": "audio"})
        self.assertEqual(caps["output_type"], "audio")


class TestValidateInputOutputCompatibility(unittest.TestCase):
    def test_valid_for_text_input_text_output(self):
        prompt = _make_chat_prompt("Hello")
        valid, error = validate_input_output_compatibility(prompt, {"model": "gpt-4"})
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_returns_error_for_image_input_with_non_vision_model(self):
        prompt = _make_chat_prompt("data:image/png;base64,abc")
        valid, error = validate_input_output_compatibility(prompt, {"model": "gpt-3.5-turbo"})
        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_valid_for_image_input_with_gpt4_vision(self):
        prompt = _make_chat_prompt("data:image/png;base64,abc")
        valid, error = validate_input_output_compatibility(prompt, {"model": "gpt-4-vision"})
        self.assertTrue(valid)
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
