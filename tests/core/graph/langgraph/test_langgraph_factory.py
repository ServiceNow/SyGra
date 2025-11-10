import unittest

from langchain_core.prompt_values import ChatPromptValue

from sygra.core.graph.langgraph.langgraph_factory import LangGraphFactory


class TestLangGraphFactory(unittest.TestCase):
    def test_get_test_message_multimodal(self):
        factory = LangGraphFactory()
        chat_prompt = factory.get_test_message(is_multi_modal=True)

        # Should return a LangChain BaseMessage (e.g., HumanMessage)

        self.assertIsInstance(chat_prompt, ChatPromptValue)
        messages = chat_prompt.messages
        # For multimodal, there should be list of messages
        self.assertIsInstance(messages, list)
        # For multimodal, content should be a list of parts with a text part saying "hello"
        self.assertTrue(
            any(
                message_content.get("type") == "text" and message_content.get("text") == "hello"
                for message_content in messages[0].content
            )
        )

    def test_get_test_message_text_only(self):
        factory = LangGraphFactory()
        chat_prompt = factory.get_test_message(is_multi_modal=False)


        self.assertIsInstance(chat_prompt, ChatPromptValue)
        messages = chat_prompt.messages
        self.assertIsInstance(messages, list)
        self.assertEqual(messages[0].content, "hello")
