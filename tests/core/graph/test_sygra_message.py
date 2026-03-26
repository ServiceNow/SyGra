import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from sygra.core.graph.sygra_message import SygraMessage


class TestSygraMessage(unittest.TestCase):
    def test_init_stores_message(self):
        msg = SygraMessage("hello")
        self.assertEqual(msg._message, "hello")

    def test_message_property_returns_stored_message(self):
        msg = SygraMessage({"role": "user", "content": "hi"})
        self.assertEqual(msg.message, {"role": "user", "content": "hi"})

    def test_stores_none_message(self):
        msg = SygraMessage(None)
        self.assertIsNone(msg.message)

    def test_stores_list_message(self):
        messages = [1, 2, 3]
        msg = SygraMessage(messages)
        self.assertEqual(msg.message, [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
