import unittest

from langchain_core.prompt_values import ChatPromptValue

from sygra.core.graph.langgraph.langgraph_factory import LangGraphFactory


class TestLangGraphFactory(unittest.TestCase):
    def test_get_test_message_audio_input(self):
        """Test get_test_message with audio input type."""
        factory = LangGraphFactory()
        model_config = {"model": "whisper-1", "input_type": "audio"}
        chat_prompt = factory.get_test_message(model_config)

        self.assertIsInstance(chat_prompt, ChatPromptValue)
        messages = chat_prompt.messages
        self.assertIsInstance(messages, list)
        
        # For audio input, content should be a list with audio_url and text
        self.assertIsInstance(messages[0].content, list)
        self.assertTrue(
            any(
                message_content.get("type") == "audio_url"
                for message_content in messages[0].content
            ),
            "Should contain audio_url in content"
        )

    def test_get_test_message_text_only(self):
        """Test get_test_message with default text input (no input_type)."""
        factory = LangGraphFactory()
        model_config = {"model": "gpt-4"}
        chat_prompt = factory.get_test_message(model_config)

        self.assertIsInstance(chat_prompt, ChatPromptValue)
        messages = chat_prompt.messages
        self.assertIsInstance(messages, list)
        # For text-only, content should be a simple string
        self.assertEqual(messages[0].content, "hello")
