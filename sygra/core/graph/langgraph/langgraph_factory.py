import base64
import io
import struct
import wave
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.prompt_values import PromptValue
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langgraph.graph import StateGraph

from sygra.core.graph.backend_factory import BackendFactory
from sygra.core.graph.graph_config import GraphConfig
from sygra.core.graph.langgraph.langgraph_state import LangGraphState
from sygra.core.graph.sygra_message import SygraMessage
from sygra.utils import utils


class LangGraphFactory(BackendFactory):
    """
    A factory class to convert Nodes into Runnable objects which LangGraph framework can execute.
    """

    def create_lambda_runnable(self, exec_wrapper):
        """
        Abstract method to create a Lambda runnable.

        Args:
            exec_wrapper: Async function to execute

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        return RunnableLambda(lambda x: x, afunc=exec_wrapper)

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

    def create_weighted_sampler_runnable(self, exec_wrapper):
        """
        Create weighted sampler runnable.

        Args:
            exec_wrapper: Async function wrapper to execute

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        return RunnableLambda(exec_wrapper)

    def create_connector_runnable(self):
        """
        Create a dummy runnable for connector node.

        Returns:
            Any: backend specific runnable object like Runnable for backend=Langgraph
        """
        return RunnableLambda(lambda x: x)

    def build_workflow(self, graph_config: GraphConfig) -> StateGraph:
        """
        Return the base state graph(from backend) with state variables only,
        which can add nodes, edges, compile and execute
        Args:
            graph_config: GraphConfig object containing state variables
        Returns:
            StateGraph: LangGraph StateGraph object
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

    @staticmethod
    def make_dummy_audio_data_url(duration_sec: float = 0.2, sample_rate: int = 16000) -> str:
        """
        Create a valid mono 16-bit PCM WAV data URL containing silence.
        Duration >= 0.1s to satisfy OpenAI transcription minimum.

        Args:
            duration_sec (float): Duration of the silent audio in seconds.
            sample_rate (int): Sample rate of the audio in Hz.
        Returns:
            str: Data URL of the generated silent WAV audio.
        """
        num_samples = int(duration_sec * sample_rate)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)  # mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            silence_frame = struct.pack("<h", 0)  # one sample of silence
            wf.writeframes(silence_frame * num_samples)

        audio_bytes = buf.getvalue()
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        return f"data:audio/wav;base64,{audio_b64}"

    def get_test_message(self, model_config: dict[str, Any]) -> PromptValue:
        """
        Get a test message for model inference
        Args:
            model_config: Dictionary containing model configuration parameters
        Returns:
            PromptValue: langchain PromptValue object containing test message
        """
        from sygra.logger.logger_config import logger

        input_type = model_config.get("input_type")
        output_type = model_config.get("output_type")
        logger.debug(f"[get_test_message] model_config keys: {model_config.keys()}")
        logger.debug(f"[get_test_message] input_type: {input_type}")

        # Handling specifically for audio only input models like transcription models
        if input_type == "audio" and not output_type:
            audio_data_url = self.make_dummy_audio_data_url()

            messages = utils.convert_messages_from_chat_format_to_langchain(
                [
                    {
                        "role": "user",
                        "content": [{"type": "audio_url", "audio_url": {"url": audio_data_url}}],
                    }
                ]
            )
        else:
            # Default text message for text-based models
            messages = utils.convert_messages_from_chat_format_to_langchain(
                [{"role": "user", "content": "hello"}]
            )
        prompt = ChatPromptTemplate.from_messages(
            [*messages],
        )
        msg = prompt.invoke({})

        return msg
