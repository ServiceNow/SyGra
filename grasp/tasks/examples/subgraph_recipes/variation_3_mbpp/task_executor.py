from typing import Any

from datasets import load_dataset
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import END

from grasp.core.base_task_executor import BaseTaskExecutor
from grasp.utils import utils


def critique_answer_node_pre_process(state):
    if not state["messages"]:
        state["messages"] = []

    # We need to convert user turns to assistant and vice versa
    cls_map = {"ai": HumanMessage, "human": AIMessage}
    translated = [cls_map[msg.type](content=msg.content) for msg in state["messages"]]
    state.update({"messages": translated})
    return state


def should_continue(state):
    # End after 4 iterations or the last feedback response contains "NO MORE FEEDBACK"
    messages = state["messages"]
    if len(messages) > 8 or (
        len(messages) > 1 and "no more feedback" in messages[-1].content.lower()
    ):
        return END
    return "generate_answer"


class TaskExecutor(BaseTaskExecutor):
    def init_dataset(self) -> list[dict]:
        final_dataset = []
        for split in ["train", "validation", "prompt"]:
            dataset = load_dataset("mbpp", "sanitized", split=split)
            dataset = dataset.to_list()
            for data in dataset:
                data["id"] = data["task_id"]
            final_dataset.extend(dataset)
        return final_dataset

    def output_record_generator(self, state) -> dict[str, Any]:
        # TODO: Convert "messages", "execution_error", "id" to a constant
        chat_format_messages = []
        if "messages" not in state:
            return None

        chat_format_messages = utils.convert_messages_from_langchain_to_chat_format(
            state["messages"]
        )
        if (
            len(chat_format_messages) < 1
            or "no more feedback"
            not in chat_format_messages[-1]["content"].lower().strip()
        ):
            return None
        # remove the last message if it contains "no more feedback"
        chat_format_messages = chat_format_messages[:-1]
        chat_format_messages.insert(
            0,
            {
                "role": "user",
                "content": state["rephrased_text"].replace(
                    "PARAPHRASED QUESTION: ", ""
                ),
            },
        )
        return {
            "id": state.get("id", ""),
            "conversation": chat_format_messages,
            "taxonomy": [{"category": "Coding", "subcategory": ""}],
            "annotation_type": ["mistral-large"],
            "language": ["en"],
            "tags": ["mbpp", "reannotate", "self-critique"],
        }
