from functools import partial
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langgraph.graph import StateGraph

from sygra.core.graph.backend_factory import BackendFactory
from sygra.core.graph.graph_config import GraphConfig
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.langgraph.langgraph_state import LangGraphState
from sygra.utils import utils


class LangGraphFactory(BackendFactory):
    """
    A factory class to convert Nodes into Runnable objects which LangGraph framework can execute.
    """

    def create_lambda_runnable(self, function_to_execute, node_config):
        """
        Abstract method to create a Lambda runnable.

        Args:
            function_to_execute: Python function to execute, if it is a class it should be callable(__call__)
            node_config:node config dictionary

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        return RunnableLambda(partial(function_to_execute, node_config))

    def create_llm_runnable(self, exec_wrapper):
        """
        Abstract method to create a LLM model runnable.

        Args:
            exec_wrapper: Async function to execute

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        return RunnableLambda(lambda x: x, afunc=exec_wrapper)

    def create_multi_llm_runnable(self, llm_dict: dict, post_process):
        """
        Abstract method to create multi LLM model runnable.

        Args:
            llm_dict: dictionary of llm model name and LLMNode
            post_process: multi LLM post processor function

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        # convert to llm runnable dict
        runnable_inputs = {k: v.to_backend() for k, v in llm_dict.items()}
        return RunnableParallel(**runnable_inputs) | RunnableLambda(post_process)

    def create_weighted_sampler_runnable(self, weighted_sampler_function, attr_config):
        """
        Abstract method to create weighted sampler runnable.

        Args:
            weighted_sampler_function: Weighted sampler function
            attr_config: attributes from the weighted sampler node

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        return RunnableLambda(partial(weighted_sampler_function, attr_config))

    def create_connector_runnable(self):
        """
        Create a dummy runnable for connector node.

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        return RunnableLambda(lambda x: x)

    def build_workflow(self, graph_config: GraphConfig):
        """
        Return the base state graph(from backend) with state variables only,
        which can add nodes, edges, compile and execute
        """
        state_schema = LangGraphState

        for state_var in graph_config.state_variables:
            if state_schema.__annotations__.get(state_var) is None:
                state_schema.__annotations__[state_var] = Any
            else:
                raise Exception(
                    f"State variable '{state_var}' is already part of the schema, rename the variable."
                )
        state_graph = StateGraph(state_schema)
        self.reset_state_schema_annotations(graph_config)
        return state_graph

    @staticmethod
    def reset_state_schema_annotations(graph_config: GraphConfig):
        """
        Reset the state schema annotations to original state.

        Args:
            state_schema: State schema class
            graph_config: GraphConfig object containing state variables

        Returns:
            None
        """
        # Reset the state schema annotations to original state
        LangGraphState.__annotations__ = {
            k: v
            for k, v in LangGraphState.__annotations__.items()
            if k not in graph_config.state_variables
        }

    def get_message_content(self, msg: SygraMessage):
        """
        Convert langgraph message to plain text

        Args:
            msg: SygraMessage containing langgraph message

        Returns:
            Text content or empty text
        """
        if isinstance(msg.message, BaseMessage):
            return msg.message.content
        else:
            return ""

    def convert_to_chat_format(self, msgs: list):
        """
        Convert langgraph message list to chat formatted list of dictionary

        Args:
            msgs: list of langgraph messages

        Returns:
            List of dictionary containing chat formatted messages
        """
        return utils.convert_messages_from_langchain_to_chat_format(msgs)

    def get_test_message(self):
        """
        Return a test message to pass into model for the specific platform
        """
        # build the ChatPrompt for model inference
        messages = utils.convert_messages_from_chat_format_to_langchain(
            [{"role": "user", "content": "hello"}]
        )
        prompt = ChatPromptTemplate.from_messages(
            [*messages],
        )
        msg = prompt.invoke({})

        return msg
