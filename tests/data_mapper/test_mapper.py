import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).parent.parent.parent))

from sygra.data_mapper.mapper import DataMapper


class TestDataMapperInit(unittest.TestCase):
    def test_init_raises_when_type_missing(self):
        with self.assertRaises(ValueError):
            DataMapper(config={})

    def test_init_raises_when_type_is_empty(self):
        with self.assertRaises(ValueError):
            DataMapper(config={"type": ""})

    def test_init_creates_sft_pipeline(self):
        mapper = DataMapper(config={"type": "sft"})
        self.assertEqual(mapper.transform_type, "sft")
        self.assertIsNotNone(mapper.pipeline)
        self.assertGreater(len(mapper.pipeline), 0)

    def test_init_creates_dpo_pipeline(self):
        mapper = DataMapper(config={"type": "dpo"})
        self.assertEqual(mapper.transform_type, "dpo")
        self.assertIsNotNone(mapper.pipeline)
        self.assertGreater(len(mapper.pipeline), 0)


class TestDataMapperOrderPipeline(unittest.TestCase):
    def test_order_pipeline_with_active_false_returns_pipeline_unchanged(self):
        mapper = DataMapper(config={"type": "sft"})
        result = mapper.order_pipeline(active=False)
        self.assertEqual(result, mapper.pipeline)

    def test_order_pipeline_with_active_true_returns_ordered_list(self):
        mapper = DataMapper(config={"type": "sft"})
        result = mapper.order_pipeline(active=True)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)


class TestDataMapperMapAllItems(unittest.TestCase):
    def test_map_all_items_calls_map_single_item_for_each(self):
        mapper = DataMapper(config={"type": "sft"})
        items = [{"id": "1"}, {"id": "2"}]

        with patch.object(mapper, "map_single_item", return_value=[{"mapped": True}]) as mock_map:
            result = mapper.map_all_items(items)

        self.assertEqual(mock_map.call_count, 2)
        self.assertEqual(len(result), 2)

    def test_map_all_items_converts_non_list_to_list(self):
        mapper = DataMapper(config={"type": "sft"})
        items = iter([{"id": "1"}])

        with patch.object(mapper, "map_single_item", return_value=[]) as mock_map:
            mapper.map_all_items(items)

        mock_map.assert_called_once()

    def test_map_all_items_continues_on_item_error(self):
        mapper = DataMapper(config={"type": "sft"})
        items = [{"id": "1"}, {"id": "2"}]

        call_count = 0

        def side_effect(item):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("item error")
            return [{"mapped": True}]

        with patch.object(mapper, "map_single_item", side_effect=side_effect):
            result = mapper.map_all_items(items)

        self.assertEqual(len(result), 1)

    def test_map_single_item_returns_empty_list_on_error(self):
        mapper = DataMapper(config={"type": "sft"})
        # Item missing required fields will cause pipeline to fail gracefully
        result = mapper.map_single_item({"id": "bad_item_no_conversation"})
        self.assertIsInstance(result, list)


class TestDataMapperBuildRowsAndValidate(unittest.TestCase):
    def test_build_rows_and_validate_builds_rows_from_context(self):
        context = {
            "conversation_id": "conv-1",
            "root_message_id": "msg-1",
            "messages": [
                {
                    "message_id": "msg-1",
                    "parent_id": None,
                    "level": 0,
                    "role": "user",
                    "content": "Hello",
                    "instruction_tags": [],
                    "quality": {},
                    "length": {},
                    "data_characteristics": {},
                }
            ],
        }
        rows = DataMapper.build_rows_and_validate(context)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["conversation_id"], "conv-1")
        self.assertEqual(rows[0]["role"], "user")
        self.assertEqual(rows[0]["content"], "Hello")

    def test_build_rows_and_validate_returns_multiple_rows_for_multiple_messages(self):
        context = {
            "conversation_id": "conv-2",
            "root_message_id": "msg-1",
            "messages": [
                {
                    "message_id": "msg-1",
                    "parent_id": None,
                    "level": 0,
                    "role": "user",
                    "content": "Hi",
                    "instruction_tags": [],
                    "quality": {},
                    "length": {},
                    "data_characteristics": {},
                },
                {
                    "message_id": "msg-2",
                    "parent_id": "msg-1",
                    "level": 1,
                    "role": "assistant",
                    "content": "Hello!",
                    "instruction_tags": [],
                    "quality": {},
                    "length": {},
                    "data_characteristics": {},
                },
            ],
        }
        rows = DataMapper.build_rows_and_validate(context)
        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
