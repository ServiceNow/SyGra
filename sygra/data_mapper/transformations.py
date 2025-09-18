import datetime
import uuid
from typing import Any

import numpy as np

from sygra.data_mapper.types import Transform, TransformMeta


class TaxonomyTransform(Transform):
    meta = TransformMeta(name="taxonomy", requires=[], provides=["categories", "subcategories"])

    def transform(self, value: Any, context: dict[str, Any]) -> None:
        """Transform the value to extract categories and subcategories into the context."""
        cats = []
        subs = []
        if isinstance(value, list):
            for t in value:
                cat = t.get("category", "")
                sub = t.get("subcategory", "")
                if cat:
                    cats.append(cat)
                if sub:
                    subs.append(sub)
        else:
            raise TypeError("Expected list, got {}".format(type(value)))

        # Save extracted categories and subcategories in the context
        context["categories"] = cats
        context["subcategories"] = subs


class ConversationTransform(Transform):
    meta = TransformMeta(
        name="conversation",
        requires=[],
        provides=["messages", "conversation_id", "root_message_id"],
    )

    def transform(self, value: Any, context: dict[str, Any]) -> None:
        """Transform the value to structure the conversation with message metadata."""

        # Convert numpy array to list if applicable
        if isinstance(value, np.ndarray):
            value = value.tolist()

        # Ensure value is a list
        if not isinstance(value, list):
            context["messages"] = []
            raise TypeError("Expected list, got {}".format(type(value)))

        metainfo = context.get("metainfo", {})

        context["metainfo"] = metainfo

        timestamp_fields = context.get("timestamp_fields", {})

        # assigning conversation ID
        conversation_id = str(context.get("source_id", f"conv_{uuid.uuid4().hex[:8]}"))

        context["conversation_id"] = conversation_id

        messages = []
        message_ids = [f"msg_{idx}_{uuid.uuid4().hex[:8]}" for idx, _ in enumerate(value, 1)]

        # Set the first message as the root message
        root_message_id = message_ids[0]
        context["root_message_id"] = root_message_id

        # Create message objects
        for idx, (msg, message_id) in enumerate(zip(value, message_ids)):
            parent_id = message_ids[idx - 1] if idx > 0 else None

            messages.append(
                {
                    "message_id": message_id,
                    "parent_id": parent_id,
                    "level": idx + 1,
                    "role": msg.get("role", ""),
                    "content": msg.get("content", ""),
                    "created_at": timestamp_fields.get(
                        "created_at", datetime.datetime.now(datetime.timezone.utc)
                    ),
                    "updated_at": datetime.datetime.now(datetime.timezone.utc),
                    "metainfo": metainfo,
                }
            )

        # Save structured messages into the context
        context["messages"] = messages


class DPOConversationTransform(Transform):
    meta = TransformMeta(
        name="dpo_conversation",
        requires=[],
        provides=["messages", "conversation_id", "root_message_id"],
    )

    # Constants for quality scoring
    CHOSEN_QUALITY_PREFIX = "chosen_response_quality."
    REJECTED_QUALITY_PREFIX = "rejected_response_quality."

    def transform(self, value: Any, context: dict[str, Any]) -> None:
        """Transform the value for DPO conversation handling with chosen/rejected response and quality scoring."""

        old_item = context.get("__old_item__", {})

        # Convert numpy array to list if applicable
        if isinstance(value, np.ndarray):
            value = value.tolist()

        # Ensure value is a list
        if not isinstance(value, list):
            context["messages"] = []
            raise TypeError("Expected list, got {}".format(type(value)))

        metainfo = context.get("metainfo", {})
        context["metainfo"] = metainfo

        timestamp_fields = context.get("timestamp_fields", {})

        # assigning conversation ID
        conversation_id = str(context.get("source_id", f"conv_{uuid.uuid4().hex[:8]}"))
        context["conversation_id"] = conversation_id

        messages: list[dict[str, Any]] = []

        message_ids = [f"msg_{idx}_{uuid.uuid4().hex[:8]}" for idx, _ in enumerate(value, 1)]

        # Set the first message as the root message
        root_message_id = message_ids[0]
        context["root_message_id"] = root_message_id

        chosen_scores = {}
        rejected_scores = {}

        # Extract quality scores for chosen and rejected responses from old_item
        for k, v in old_item.items():
            if k.startswith(self.CHOSEN_QUALITY_PREFIX):
                short_key = k[len(self.CHOSEN_QUALITY_PREFIX) :]
                chosen_scores[short_key] = v

            elif k.startswith(self.REJECTED_QUALITY_PREFIX):
                short_key = k[len(self.REJECTED_QUALITY_PREFIX) :]
                rejected_scores[short_key] = v

        # Filter out None values in scores
        chosen_scores = {k: v for k, v in chosen_scores.items() if v is not None}
        rejected_scores = {k: v for k, v in rejected_scores.items() if v is not None}

        # Create message objects, handling chosen/rejected responses
        for idx, (msg, message_id) in enumerate(zip(value, message_ids)):
            parent_id = message_ids[idx - 1] if idx > 0 else None
            role = msg.get("role", "")

            base_content = msg.get("content", None)
            chosen_arr = msg.get("chosen")
            rejected_arr = msg.get("rejected")

            base_msg_data = {
                "message_id": message_id,
                "parent_id": parent_id,
                "level": idx + 1,
                "role": role,
                "content": base_content if base_content is not None else "",
                "created_at": timestamp_fields.get(
                    "created_at", datetime.datetime.now(datetime.timezone.utc)
                ),
                "updated_at": datetime.datetime.now(datetime.timezone.utc),
                "metainfo": metainfo,
            }

            # If the role is not assistant or no chosen/rejected content exists, skip processing those
            if role != "assistant" or (not chosen_arr and not rejected_arr):
                messages.append(base_msg_data)
                continue

            # Add chosen responses with their quality score
            if chosen_arr:
                chosen_content = "\n".join(chosen_arr)
                chosen_msg_data = dict(base_msg_data)
                chosen_msg_data["message_id"] = f"msg_{idx + 1}_{uuid.uuid4().hex[:8]}"
                chosen_msg_data["content"] = chosen_content
                if chosen_scores:
                    chosen_msg_data["quality"] = chosen_scores
                messages.append(chosen_msg_data)

            # Add rejected responses with their quality score
            if rejected_arr:
                rejected_content = "\n".join(rejected_arr)
                rejected_msg_data = dict(base_msg_data)
                rejected_msg_data["message_id"] = f"msg_{idx + 1}_{uuid.uuid4().hex[:8]}"
                rejected_msg_data["content"] = rejected_content
                if rejected_scores:
                    rejected_msg_data["quality"] = rejected_scores
                messages.append(rejected_msg_data)

        # Save structured messages into the context
        context["messages"] = messages


class QualityTransform(Transform):
    meta = TransformMeta(
        name="quality",
        requires=["metadata"],
        provides=["quality"],
    )

    def transform(self, value: Any, context: dict[str, Any]) -> None:
        """Transform the value to add quality metrics like instruction following, relevance, and safety."""

        # Extract quality scores from context metadata
        instruction_following = context["metadata"].get("instruction_following", 0.0)
        relevance = context["metadata"].get("relevance", 0.0)
        safety = context["metadata"].get("safety", 0.0)

        # Save quality scores in the context
        context["quality"] = {
            "instruction_following": instruction_following,
            "relevance": relevance,
            "safety": safety,
        }


class LengthTransform(Transform):
    meta = TransformMeta(name="length", requires=["messages"], provides=["length"])

    def transform(self, value: Any, context: dict[str, Any]) -> None:
        """Transform the value to calculate and add length metrics for each message."""

        messages = context.get("messages", [])

        # Calculate character count and word count for each message
        for message in messages:
            content = message.get("content", "")

            message["length"] = {
                "char_count": len(content),
                "word_count": len(content.split()),
            }


class CopyTransform(Transform):
    meta = TransformMeta(name="copy", requires=[], provides=[])

    def transform(self, value: Any, context: dict[str, Any]) -> None:
        """Copy the value from the old key to the new key in the context."""

        step = context.get("__current_step__", {})
        old_key = step.get("old_key")
        new_key = step.get("new_key")

        if not new_key:
            new_key = old_key

        # Copy value to new key in context
        context[new_key] = value
