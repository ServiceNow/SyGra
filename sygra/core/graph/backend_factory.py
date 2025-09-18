from abc import ABC, abstractmethod

from sygra.core.graph.graph_config import GraphConfig
from sygra.core.graph.sygra_message import SygraMessage


class BackendFactory(ABC):
    """
    This class helps creating backend objects from Graph Nodes. For example, LangGraph need Runnable objects.
    """

    @abstractmethod
    def create_lambda_runnable(self, function_to_execute, node_config):
        """
        Abstract method to create a Lambda runnable.

        Args:
            function_to_execute: Python function to execute, if it is a class it should be callable(__call__)
            node_config:node config dictionary

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        pass

    @abstractmethod
    def create_llm_runnable(self, exec_wrapper):
        """
        Abstract method to create a LLM model runnable.

        Args:
            exec_wrapper: Async function to execute

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        pass

    @abstractmethod
    def create_multi_llm_runnable(self, llm_dict: dict, post_process):
        """
        Abstract method to create multi LLM model runnable.

        Args:
            llm_dict: dictionary of llm model name and LLMNode
            post_process: multi LLM post processor function

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        pass

    @abstractmethod
    def create_weighted_sampler_runnable(self, weighted_sampler_function, attr_config):
        """
        Abstract method to create weighted sampler runnable.

        Args:
            weighted_sampler_function: Weighted sampler function
            attr_config: attributes from the weighted sampler node

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        pass

    @abstractmethod
    def create_connector_runnable(self):
        """
        Abstract method to create a dummy runnable for connector node.

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        pass

    @abstractmethod
    def build_workflow(self, graph_config: GraphConfig):
        """
        Return the state graph(from backend), which can add nodes, edges, compile and execute
        """
        pass

    @abstractmethod
    def get_message_content(self, msg: SygraMessage):
        """
        Convert langgraph message to plain text

        Args:
            msg: SygraMessage containing langgraph message

        Returns:
            Text content or empty text
        """
        pass

    @abstractmethod
    def convert_to_chat_format(self, msgs: list):
        """
        Convert langgraph message list to chat formatted list of dictionary

        Args:
            msgs: list of langgraph messages

        Returns:
            List of dictionary containing chat formatted messages
        """
        pass

    @abstractmethod
    def get_test_message(self):
        """
        Return a test message to pass into model for the specific platform
        """
        pass
