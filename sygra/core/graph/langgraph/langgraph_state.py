import operator
from typing import Annotated, Sequence

from langchain_core.messages import BaseMessage

from sygra.core.graph.sygra_state import SygraState


class LangGraphState(SygraState):
    """
    This class defines predfined state variables/schema.

    This will be passed to SygraStateGraph to inject other state variables.
    """

    # messages is mandatory field used for message passing between nodes
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # chat history for the node which enabled chat history
    __chat_history__: Annotated[list, operator.add]
