import asyncio
import json
import time
from inspect import isclass, signature
from typing import Any, Optional, Type

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from sygra.core.graph.langgraph.langchain_callback import MetadataTrackingCallback
from sygra.core.graph.nodes.llm_node import LLMNode
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.models.model_factory import ModelFactory
from sygra.core.models.structured_output.structured_output_config import StructuredOutputConfig
from sygra.logger.logger_config import logger
from sygra.utils import constants, utils


class AgentNode(LLMNode):
    """
    This node creates and executes an agent using `create_react_agent`.
    Inherits from LLMNode
    """

    REQUIRED_KEYS: list[str] = ["model", "prompt"]

    def __init__(self, node_name: str, config: dict):
        super().__init__(node_name, config)

        self.inject_system_messages = self.node_config.get("inject_system_messages", [])

        # Initialize structured output for agent response format
        self._response_format: Optional[Type[BaseModel]] = None
        structured_output_raw = self.node_config.get("model", {}).get("structured_output")
        if structured_output_raw is not None:
            so_config = StructuredOutputConfig(structured_output_raw, key_present=True)
            if so_config.enabled:
                self._response_format = so_config.get_pydantic_model()
                if self._response_format:
                    logger.info(
                        f"[{node_name}] Structured output enabled for agent with schema: "
                        f"{self._response_format.__name__}"
                    )

    def _initialize_model(self):
        """
        Initialize the LLM model using ModelFactory by overriding the base behavior from llm_node.

        This method calls `ModelFactory.create_model` to initialize the model using the
        configuration from the node configuration.
        """

        self.model = ModelFactory.create_model(
            self.node_config["model"], constants.MODEL_BACKEND_LANGGRAPH
        )

    async def _exec_wrapper(self, state: dict[str, Any]) -> dict[str, Any]:

        start_time = time.time()
        success = True
        # Capture tokens immediately after model call to avoid race conditions
        captured_tokens = {"prompt": 0, "completion": 0, "total": 0}

        try:
            graph_factory = utils.get_graph_factory(constants.BACKEND)

            # Pre-processing
            state = (
                self.pre_process().apply(state)
                if isclass(self.pre_process)
                else self.pre_process(state)
            )
            chat_history_enabled = self.node_config.get("chat_history", False)

            # Generate and inject prompt
            prompt_tmpl = self._generate_prompt(state)
            prompt = prompt_tmpl.invoke(state)
            prompt = self._inject_history(state, prompt)

            request_msgs = graph_factory.convert_to_chat_format(prompt.to_messages())
            chat_history = state.get(constants.VAR_CHAT_HISTORY, [])
            logger.info(f"Chat history length: {len(chat_history)} at {self.name}")

            # Construct system prompt
            full_agent_prompt = self._compose_agent_prompt(state, prompt)

            callback = MetadataTrackingCallback(
                model_name=self._get_model_name(self.model) or "unknown"
            )

            # Create the ReAct agent
            agent_kwargs: dict[str, Any] = {
                "model": self.model,
                "tools": self.tools,
                "prompt": full_agent_prompt,
                "name": state.get("_agent_name"),
            }
            if self._response_format is not None:
                agent_kwargs["response_format"] = self._response_format
            agent = create_react_agent(**agent_kwargs)

            # Remove redundant system message at the beginning
            if isinstance(prompt.messages[0], SystemMessage):
                prompt.messages = prompt.messages[1:]

            # Run the agent with callback to track LLM calls
            agent_recursion_limit = self.node_config.get("recursion_limit", 200)
            agent_timeout = self.node_config.get("timeout", None)
            coro = agent.ainvoke(
                {"messages": prompt.to_messages()},
                config={"callbacks": [callback], "recursion_limit": agent_recursion_limit},  # type: ignore
            )
            try:
                response = (
                    await asyncio.wait_for(coro, timeout=agent_timeout)
                    if agent_timeout
                    else await coro
                )
            except asyncio.TimeoutError:
                raise RuntimeError(
                    f"Agent node timed out after {agent_timeout}s "
                    f"(recursion_limit={agent_recursion_limit})"
                )

            # Capture tokens after agent execution
            captured_tokens = self._capture_token_usage(self.model)

            ai_response = None
            # Log tool call summary
            tool_calls_summary = []
            for m in response["messages"]:
                if isinstance(m, AIMessage):
                    if hasattr(m, "tool_calls") and m.tool_calls:
                        for tc in m.tool_calls:
                            tool_calls_summary.append(tc.get("name", "unknown"))
            if tool_calls_summary:
                logger.info(f"Agent {self.name}: tool calls made: {tool_calls_summary}")

            # Pick the last AIMessage with content (fallback for empty final message)
            last_ai_with_content = None
            for m in response["messages"]:
                if isinstance(m, AIMessage):
                    clen = (
                        len(m.content)
                        if isinstance(m.content, str)
                        else len(str(m.content)) if m.content else 0
                    )
                    if clen > 0 and not getattr(m, "tool_calls", None):
                        last_ai_with_content = m
                    ai_response = m

            # If the last AIMessage is empty, use the last one that had content
            if ai_response and not ai_response.content and last_ai_with_content:
                logger.info(
                    f"Agent {self.name}: last AIMessage empty, using earlier one with content"
                )
                ai_response = last_ai_with_content

            # If structured output is enabled and response contains parsed data,
            # replace AIMessage content with the validated JSON serialization
            structured_response = response.get("structured_response")
            if structured_response is not None and ai_response is not None:
                if isinstance(structured_response, BaseModel):
                    ai_response = AIMessage(content=structured_response.model_dump_json())
                elif isinstance(structured_response, dict):
                    ai_response = AIMessage(content=json.dumps(structured_response))

            responseMsg = SygraMessage(ai_response)

            # Post-processing
            post_process_sig = (
                signature(self.post_process().apply)
                if isclass(self.post_process)
                else signature(self.post_process)
            )
            if len(post_process_sig.parameters) == 1:
                updated_state = (
                    self.post_process().apply(responseMsg)
                    if isclass(self.post_process)
                    else self.post_process(ai_response)  # type: ignore
                )
            else:
                updated_state = (
                    self.post_process().apply(responseMsg, state)
                    if isclass(self.post_process)
                    else self.post_process(ai_response, state)  # type: ignore
                )

            # Store chat history
            if chat_history_enabled:
                if not updated_state.get(constants.VAR_CHAT_HISTORY):
                    updated_state[constants.VAR_CHAT_HISTORY] = []
                updated_state[constants.VAR_CHAT_HISTORY].append(
                    {
                        constants.KEY_NAME: self.name,
                        constants.KEY_REQUEST: request_msgs,
                        constants.KEY_RESPONSE: graph_factory.get_message_content(responseMsg),
                    }
                )

            return updated_state

        except Exception:
            success = False
            raise
        finally:
            self._record_execution_metadata(start_time, success, self.model, captured_tokens)

    def _compose_agent_prompt(self, state: dict[str, Any], prompt) -> str:
        """
        Combines the base agent prompt with conditional injections based on chat history length.
        """
        messages = prompt.to_messages()
        base_prompt_candidate = next(
            (msg.content for msg in messages if isinstance(msg, SystemMessage)), None
        ) or state.get("_agent_prompt", "")
        # Ensure we always operate on a string; content can sometimes be a list for multimodal
        base_prompt_str: str = (
            base_prompt_candidate
            if isinstance(base_prompt_candidate, str)
            else str(base_prompt_candidate)
        )
        chat_history = state.get(constants.VAR_CHAT_HISTORY, [])

        for inject in self.inject_system_messages:
            for turn_index, message in inject.items():
                if len(chat_history) // 2 == turn_index:
                    base_prompt_str = f"{base_prompt_str}\n{message}"
                    break

        return base_prompt_str

    def to_backend(self) -> Any:
        """
        Convert the Node object to backend platform specific Runnable object.

        Returns:
             Any: platform specific runnable object like Runnable in LangGraph.
        """
        return utils.backend_factory.create_llm_runnable(self._exec_wrapper)

    def validate_node(self):
        """
        Override the method to add required validation for this Node type
        It throws Exception
        Returns:
            None
        """

        # validate the required keys
        self.validate_config_keys(self.REQUIRED_KEYS, self.node_type, self.node_config)
