"""
Customer Service Agent with Realistic Audio - Task Executor

This module contains processors for generating realistic voice conversations
with distinct voices for user and assistant using TTS.

Features:
- Varied user moods and speech patterns
- Background noise overlay on user audio
- Emotional expressions and fillers in speech
- Accent hints through voice selection

Based on the flight_booking_conversations pattern for audio synthesis.
"""

import array
import io
import json
import logging
import math
import random
import re
import struct
import wave
from typing import Any

from sygra.core.graph.functions.edge_condition import EdgeCondition
from sygra.core.graph.functions.node_processor import (
    NodePostProcessorWithState,
    NodePreProcessor,
)
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState
from sygra.core.models.client.client_factory import ClientFactory
from sygra.processors.output_record_generator import BaseOutputGenerator
from sygra.utils import audio_utils, utils


# ============== TTS Client Cache ==============
_TTS_CLIENT = None
_TTS_MODEL_NAME = None


def safe_json_extract(text: str) -> dict:
    """Safely extract JSON from LLM response text."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    return {}


def _get_tts_config() -> dict[str, Any]:
    """Load TTS model configuration."""
    model_configs = utils.load_model_config()
    cfg = model_configs.get("tts_openai")
    if not isinstance(cfg, dict):
        raise ValueError("Model 'tts_openai' is not configured. Add it to sygra/config/models.yaml")
    return cfg


async def _get_tts_client():
    """Get or create TTS client (cached)."""
    global _TTS_CLIENT, _TTS_MODEL_NAME
    if _TTS_CLIENT is not None and _TTS_MODEL_NAME is not None:
        return _TTS_CLIENT, _TTS_MODEL_NAME

    cfg = _get_tts_config()
    url = cfg.get("url")
    if isinstance(url, list):
        url = url[0] if url else None
    auth_token = cfg.get("auth_token")
    if isinstance(auth_token, list):
        auth_token = auth_token[0] if auth_token else None

    if not isinstance(url, str) or not url:
        raise ValueError("Missing TTS URL for 'tts_openai' (set SYGRA_TTS_OPENAI_URL)")
    if not isinstance(auth_token, str) or not auth_token:
        raise ValueError("Missing TTS token for 'tts_openai' (set SYGRA_TTS_OPENAI_TOKEN)")

    client = ClientFactory.create_client(cfg, url, auth_token, async_client=True)
    _TTS_CLIENT = client
    _TTS_MODEL_NAME = str(cfg.get("model"))
    return client, _TTS_MODEL_NAME


def _concat_wav_segments(wav_segments: list[bytes], pause_ms: int = 150) -> bytes:
    """Concatenate WAV segments with pauses between them."""
    if not wav_segments:
        raise ValueError("No WAV segments to concatenate")

    frames: list[bytes] = []
    params = None
    nchannels = sampwidth = framerate = None

    for seg in wav_segments:
        with wave.open(io.BytesIO(seg), "rb") as wf:
            if params is None:
                params = wf.getparams()
                nchannels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
            else:
                if (
                    wf.getnchannels() != nchannels
                    or wf.getsampwidth() != sampwidth
                    or wf.getframerate() != framerate
                ):
                    raise ValueError("Inconsistent WAV parameters across segments")

            frames.append(wf.readframes(wf.getnframes()))

        # Add pause between segments
        if framerate is not None and nchannels is not None and sampwidth is not None and pause_ms > 0:
            pause_frames = int(framerate * (pause_ms / 1000.0))
            frames.append(b"\x00" * pause_frames * nchannels * sampwidth)

    out_buf = io.BytesIO()
    with wave.open(out_buf, "wb") as out_wf:
        assert params is not None
        out_wf.setnchannels(params.nchannels)
        out_wf.setsampwidth(params.sampwidth)
        out_wf.setframerate(params.framerate)
        out_wf.writeframes(b"".join(frames))
    return out_buf.getvalue()


def _chunk_text_for_tts(text: str, max_chars: int = 3800) -> list[str]:
    """Split long text into chunks for TTS (max 4096 chars typically)."""
    cleaned = " ".join(text.strip().split())
    if len(cleaned) <= max_chars:
        return [cleaned] if cleaned else []

    parts: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + max_chars, len(cleaned))
        window = cleaned[start:end]
        cut = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
        if cut != -1 and end != len(cleaned) and cut > max_chars * 0.5:
            end = start + cut + 2
        parts.append(cleaned[start:end].strip())
        start = end
    return [p for p in parts if p]


# ============== Background Noise Generation ==============


def _generate_white_noise(num_samples: int, amplitude: float = 0.05) -> list[int]:
    """Generate white noise samples."""
    return [int(random.gauss(0, amplitude * 32767)) for _ in range(num_samples)]


def _generate_pink_noise(num_samples: int, amplitude: float = 0.03) -> list[int]:
    """Generate pink noise using simple filtering."""
    white = [random.gauss(0, 1) for _ in range(num_samples)]
    pink = []
    b0 = b1 = b2 = b3 = b4 = b5 = b6 = 0.0
    for w in white:
        b0 = 0.99886 * b0 + w * 0.0555179
        b1 = 0.99332 * b1 + w * 0.0750759
        b2 = 0.96900 * b2 + w * 0.1538520
        b3 = 0.86650 * b3 + w * 0.3104856
        b4 = 0.55000 * b4 + w * 0.5329522
        b5 = -0.7616 * b5 - w * 0.0168980
        pink_sample = b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362
        b6 = w * 0.115926
        pink.append(int(pink_sample * amplitude * 3200))
    return pink


def _generate_coffee_shop_noise(num_samples: int, sample_rate: int = 24000) -> list[int]:
    """Generate coffee shop ambiance (chatter, cups, background hum)."""
    noise = []
    for i in range(num_samples):
        # Base ambient hum (low frequency)
        hum = 0.02 * math.sin(2 * math.pi * 60 * i / sample_rate)
        # Random chatter simulation (filtered noise bursts)
        chatter = random.gauss(0, 0.015) if random.random() < 0.3 else 0
        # Occasional cup clinks (high frequency bursts)
        clink = 0.03 * math.sin(2 * math.pi * 2000 * i / sample_rate) if random.random() < 0.001 else 0
        sample = hum + chatter + clink
        noise.append(int(sample * 32767))
    return noise


def _generate_street_noise(num_samples: int, sample_rate: int = 24000) -> list[int]:
    """Generate street ambiance (traffic, wind, distant sounds)."""
    noise = []
    # Pre-generate wind patterns
    wind_phase = random.random() * 2 * math.pi
    for i in range(num_samples):
        # Low rumble (traffic)
        traffic = 0.03 * math.sin(2 * math.pi * 40 * i / sample_rate + random.gauss(0, 0.1))
        # Wind (modulated noise)
        wind_mod = 0.5 + 0.5 * math.sin(2 * math.pi * 0.2 * i / sample_rate + wind_phase)
        wind = random.gauss(0, 0.02 * wind_mod)
        # Occasional car pass (volume swell)
        car_pass = 0
        if random.random() < 0.0001:
            car_pass = 0.04 * math.sin(2 * math.pi * 100 * i / sample_rate)
        sample = traffic + wind + car_pass
        noise.append(int(sample * 32767))
    return noise


def _generate_office_noise(num_samples: int, sample_rate: int = 24000) -> list[int]:
    """Generate office ambiance (AC hum, keyboard, muffled voices)."""
    noise = []
    for i in range(num_samples):
        # HVAC hum
        hvac = 0.015 * math.sin(2 * math.pi * 120 * i / sample_rate)
        # Occasional keyboard clicks
        keyboard = 0
        if random.random() < 0.005:
            keyboard = 0.02 * math.sin(2 * math.pi * 3000 * i / sample_rate) * math.exp(-0.001 * (i % 100))
        # Muffled distant voices
        voices = random.gauss(0, 0.008) if random.random() < 0.15 else 0
        sample = hvac + keyboard + voices
        noise.append(int(sample * 32767))
    return noise


def _generate_home_with_kids_noise(num_samples: int, sample_rate: int = 24000) -> list[int]:
    """Generate home with kids ambiance (TV, toys, footsteps)."""
    noise = []
    for i in range(num_samples):
        # TV in background (low murmur)
        tv = random.gauss(0, 0.012) if random.random() < 0.25 else 0
        # Occasional toy sounds
        toy = 0.025 * math.sin(2 * math.pi * 800 * i / sample_rate) if random.random() < 0.002 else 0
        # Footsteps (thumps)
        footstep = 0
        if random.random() < 0.0003:
            footstep = 0.05 * math.exp(-0.005 * (i % 200))
        sample = tv + toy + footstep
        noise.append(int(sample * 32767))
    return noise


def _generate_car_noise(num_samples: int, sample_rate: int = 24000) -> list[int]:
    """Generate car interior ambiance (engine, road noise, wind)."""
    noise = []
    engine_phase = random.random() * 2 * math.pi
    for i in range(num_samples):
        # Engine idle (rhythmic low frequency)
        engine = 0.025 * math.sin(2 * math.pi * 30 * i / sample_rate + engine_phase)
        engine += 0.01 * math.sin(2 * math.pi * 60 * i / sample_rate + engine_phase)
        # Road noise (filtered noise)
        road = random.gauss(0, 0.02)
        # Wind buffeting
        wind = 0.01 * math.sin(2 * math.pi * 0.5 * i / sample_rate) * random.gauss(0, 0.5)
        sample = engine + road + wind
        noise.append(int(sample * 32767))
    return noise


def _generate_background_noise(noise_type: str, num_samples: int, sample_rate: int = 24000) -> list[int]:
    """Generate background noise based on type."""
    noise_generators = {
        "none": lambda n, sr: [0] * n,
        "coffee_shop": _generate_coffee_shop_noise,
        "street": _generate_street_noise,
        "office": _generate_office_noise,
        "home_with_kids": _generate_home_with_kids_noise,
        "car": _generate_car_noise,
    }
    generator = noise_generators.get(noise_type, lambda n, sr: [0] * n)
    return generator(num_samples, sample_rate)


def _mix_audio_with_noise(audio_bytes: bytes, noise_type: str, noise_volume: float = 0.3) -> bytes:
    """Mix WAV audio with background noise."""
    if noise_type == "none" or not audio_bytes:
        return audio_bytes

    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            params = wf.getparams()
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            audio_data = wf.readframes(nframes)

        # Validate data
        if nframes == 0 or len(audio_data) == 0:
            return audio_bytes

        # Convert audio to samples (only support 16-bit audio)
        if sampwidth != 2:
            return audio_bytes

        # Calculate expected sample count
        expected_samples = nframes * nchannels
        actual_bytes = len(audio_data)
        actual_samples = actual_bytes // 2  # 2 bytes per sample for 16-bit

        if actual_samples == 0:
            return audio_bytes

        # Use actual samples to avoid buffer mismatch
        audio_samples = list(struct.unpack(f"<{actual_samples}h", audio_data[:actual_samples * 2]))

        # Generate noise for the same duration
        noise_samples = _generate_background_noise(noise_type, len(audio_samples), framerate)

        # Mix audio with noise
        mixed = []
        for audio_sample, noise_sample in zip(audio_samples, noise_samples):
            # Add noise at reduced volume
            mixed_sample = int(audio_sample + noise_sample * noise_volume)
            # Clip to prevent overflow
            mixed_sample = max(-32768, min(32767, mixed_sample))
            mixed.append(mixed_sample)

        # Convert back to bytes
        mixed_bytes = struct.pack(f"<{len(mixed)}h", *mixed)

        # Write output WAV
        out_buf = io.BytesIO()
        with wave.open(out_buf, "wb") as out_wf:
            out_wf.setnchannels(nchannels)
            out_wf.setsampwidth(sampwidth)
            out_wf.setframerate(framerate)
            out_wf.writeframes(mixed_bytes)

        return out_buf.getvalue()

    except Exception as e:
        logging.warning(f"Failed to mix audio with noise: {e}. Returning original audio.")
        return audio_bytes


def _get_conversation_turns(state: SygraState) -> list[dict[str, str]]:
    """Extract conversation turns from chat history."""
    chat_history = state.get("__chat_history__", [])
    initial_query = state.get("initial_query", "")

    # Nodes that are part of the conversation
    conversation_nodes = {
        "ask_clarifying_question": "assistant",
        "generate_confirmation": "assistant",
        "generate_completion": "assistant",
        "simulate_user_response": "user",
        "simulate_user_confirmation": "user",
    }

    turns: list[dict[str, str]] = []
    seen_content = set()

    # Add initial user query
    if initial_query:
        turns.append({"role": "user", "content": initial_query})
        seen_content.add(initial_query[:200])

    # Process chat history
    for entry in chat_history:
        name = entry.get("name", "")
        response = entry.get("response", "")

        if name not in conversation_nodes:
            continue

        role = conversation_nodes[name]

        # For user responses, try to extract clean message from JSON
        if role == "user" and response:
            parsed = safe_json_extract(response)
            if parsed and "user_message" in parsed:
                response = parsed["user_message"]

        if not response:
            continue

        # Skip duplicates
        content_key = response[:200] if len(response) > 200 else response
        if content_key in seen_content:
            continue

        turns.append({"role": role, "content": response})
        seen_content.add(content_key)

    return turns


# ============== Analysis Processor ==============


class AnalyzeQueryPostProcessor(NodePostProcessorWithState):
    """Analyzes the initial query and initializes state."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        parsed = safe_json_extract(content)

        state["required_fields"] = parsed.get("required_fields", [])
        state["provided_fields"] = parsed.get("provided_fields", {})
        state["missing_fields"] = parsed.get("missing_fields", [])
        state["analysis_summary"] = parsed.get("analysis_summary", "")
        state["collected_info"] = parsed.get("provided_fields", {}).copy()
        state["turn_count"] = 0
        state["request_completed"] = False

        # Set initial user message
        state["user_message"] = state.get("initial_query", "")

        return state


# ============== Assistant Processors ==============


class AssistantResponsePostProcessor(NodePostProcessorWithState):
    """Stores assistant's text response."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        state["assistant_response"] = content
        state["turn_count"] = state.get("turn_count", 0) + 1
        return state


# ============== User Simulation Processors ==============


class SimulateUserPreProcessor(NodePreProcessor):
    """Prepares ground truth for user simulation."""

    def apply(self, state: SygraState) -> SygraState:
        ground_truth = state.get("ground_truth", "")
        scenario_context = state.get("scenario_context", "")
        state["ground_truth_info"] = ground_truth if ground_truth else scenario_context
        return state


class UserResponsePostProcessor(NodePostProcessorWithState):
    """Stores user's text response."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        parsed = safe_json_extract(content)
        if parsed and "user_message" in parsed:
            state["user_message"] = parsed["user_message"]
        else:
            state["user_message"] = content
        return state


class UserConfirmationPostProcessor(NodePostProcessorWithState):
    """Handles user confirmation response."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        parsed = safe_json_extract(content)

        if parsed:
            state["user_message"] = parsed.get("user_message", content)
            state["user_confirmed"] = parsed.get("user_confirmed", False)
        else:
            state["user_message"] = content
            lower_content = content.lower()
            state["user_confirmed"] = any(
                word in lower_content
                for word in ["yes", "correct", "confirm", "looks good", "that's right", "perfect", "great"]
            )

        return state


# ============== Update and Completion Processors ==============


class UpdateCheckPostProcessor(NodePostProcessorWithState):
    """Updates collected info and checks completeness."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        parsed = safe_json_extract(content)

        new_collected = parsed.get("collected_info", {})
        existing_collected = state.get("collected_info", {})
        existing_collected.update(new_collected)
        state["collected_info"] = existing_collected

        state["missing_fields"] = parsed.get("missing_fields", [])
        state["is_complete"] = parsed.get("is_complete", False)
        state["ready_for_confirmation"] = parsed.get("ready_for_confirmation", False)

        return state


class CompletionPostProcessor(NodePostProcessorWithState):
    """Marks request as completed."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        state["assistant_response"] = response.message.content
        state["request_completed"] = True
        return state


# ============== Edge Conditions ==============


class NeedsClarificationCondition(EdgeCondition):
    """Check if clarifying questions are needed."""

    def apply(state: SygraState) -> str:
        missing_fields = state.get("missing_fields", [])
        if not missing_fields or len(missing_fields) == 0:
            return "generate_confirmation"
        return "ask_clarifying_question"


class CheckCompletenessCondition(EdgeCondition):
    """Check if all information has been collected."""

    def apply(state: SygraState) -> str:
        is_complete = state.get("is_complete", False)
        ready_for_confirmation = state.get("ready_for_confirmation", False)
        turn_count = state.get("turn_count", 0)
        max_turns = 5

        if is_complete or ready_for_confirmation or turn_count >= max_turns:
            return "generate_confirmation"
        return "ask_clarifying_question"


class UserConfirmedCondition(EdgeCondition):
    """Check if user confirmed the information."""

    def apply(state: SygraState) -> str:
        user_confirmed = state.get("user_confirmed", False)
        turn_count = state.get("turn_count", 0)
        max_turns = 6

        if user_confirmed or turn_count >= max_turns:
            return "generate_completion"
        return "ask_clarifying_question"


# ============== Audio Synthesis Lambda ==============


class SynthesizeRealisticConversationAudio:
    """
    Lambda function to synthesize realistic audio for the conversation.
    - Uses TTS to generate audio for each turn with distinct voices
    - Overlays background noise on user audio segments
    - Supports different noise types: coffee_shop, street, office, home_with_kids, car
    """

    @staticmethod
    async def apply(lambda_node_dict: dict, state: SygraState):
        turns = _get_conversation_turns(state)
        if not turns:
            state["conversation_audio"] = None
            state["user_voice"] = None
            state["assistant_voice"] = None
            state["background_noise_applied"] = None
            return state

        # Get voices from state (sampled) or config
        user_voice = str(state.get("user_voice") or lambda_node_dict.get("user_voice", "echo"))
        assistant_voice = str(lambda_node_dict.get("assistant_voice", "nova"))

        # Get background noise type from state (sampled)
        background_noise = str(state.get("background_noise", "none"))

        # Ensure voices are different
        if user_voice == assistant_voice:
            assistant_voice = "nova" if user_voice != "nova" else "alloy"

        try:
            client, model_name = await _get_tts_client()

            wav_segments: list[bytes] = []
            for turn in turns:
                role = str(turn.get("role", ""))
                content = str(turn.get("content", "")).strip()
                if not content:
                    continue

                voice = user_voice if role == "user" else assistant_voice

                # Handle long text by chunking
                turn_segments: list[bytes] = []
                for chunk in _chunk_text_for_tts(content):
                    audio_resp = await client.create_speech(
                        model=model_name,
                        input=chunk,
                        voice=voice,
                        response_format="wav",
                        speed=1.0,
                    )
                    turn_segments.append(bytes(audio_resp.content))

                # For user turns, mix with background noise
                if role == "user" and background_noise != "none" and turn_segments:
                    # Concatenate turn segments first
                    if len(turn_segments) > 1:
                        turn_audio = _concat_wav_segments(turn_segments, pause_ms=50)
                    else:
                        turn_audio = turn_segments[0]
                    # Apply background noise
                    turn_audio_with_noise = _mix_audio_with_noise(turn_audio, background_noise, noise_volume=0.25)
                    wav_segments.append(turn_audio_with_noise)
                else:
                    wav_segments.extend(turn_segments)

            # Concatenate all segments with pauses
            if wav_segments:
                combined = _concat_wav_segments(wav_segments, pause_ms=250)
                state["conversation_audio"] = audio_utils.get_audio_url(combined, mime="audio/wav")
            else:
                state["conversation_audio"] = None

        except Exception as e:
            logging.error(f"Realistic audio synthesis failed: {e}")
            state["conversation_audio"] = None

        state["user_voice"] = user_voice
        state["assistant_voice"] = assistant_voice
        state["background_noise_applied"] = background_noise if background_noise != "none" else None
        return state


# Keep original for backwards compatibility
class SynthesizeConversationAudio:
    """
    Lambda function to synthesize audio for the entire conversation.
    Uses TTS to generate audio for each turn with distinct voices.
    """

    @staticmethod
    async def apply(lambda_node_dict: dict, state: SygraState):
        turns = _get_conversation_turns(state)
        if not turns:
            state["conversation_audio"] = None
            state["user_voice"] = None
            state["assistant_voice"] = None
            return state

        # Get voices from config or state
        user_voice = str(state.get("user_voice") or lambda_node_dict.get("user_voice", "echo"))
        assistant_voice = str(state.get("assistant_voice") or lambda_node_dict.get("assistant_voice", "nova"))

        # Ensure voices are different
        if user_voice == assistant_voice:
            assistant_voice = "nova" if user_voice != "nova" else "alloy"

        try:
            client, model_name = await _get_tts_client()

            wav_segments: list[bytes] = []
            for turn in turns:
                role = str(turn.get("role", ""))
                content = str(turn.get("content", "")).strip()
                if not content:
                    continue

                voice = user_voice if role == "user" else assistant_voice

                # Handle long text by chunking
                for chunk in _chunk_text_for_tts(content):
                    audio_resp = await client.create_speech(
                        model=model_name,
                        input=chunk,
                        voice=voice,
                        response_format="wav",
                        speed=1.0,
                    )
                    wav_segments.append(bytes(audio_resp.content))

            # Concatenate all segments with pauses
            if wav_segments:
                combined = _concat_wav_segments(wav_segments, pause_ms=200)
                state["conversation_audio"] = audio_utils.get_audio_url(combined, mime="audio/wav")
            else:
                state["conversation_audio"] = None

        except Exception as e:
            logging.error(f"Audio synthesis failed: {e}")
            state["conversation_audio"] = None

        state["user_voice"] = user_voice
        state["assistant_voice"] = assistant_voice
        return state


# ============== Output Generator ==============


class CustomerServiceAudioOutputGenerator(BaseOutputGenerator):
    """Generates output with both text and audio conversations, including personality metadata."""

    @staticmethod
    def build_conversation(data: Any, state: SygraState) -> list[dict]:
        """Build text conversation from chat history."""
        return _get_conversation_turns(state)

    @staticmethod
    def build_personality_metadata(data: Any, state: SygraState) -> dict:
        """Build personality metadata from sampled attributes."""
        return {
            "mood": state.get("user_mood", "neutral"),
            "speech_style": state.get("speech_style", "fluent"),
            "accent_hint": state.get("accent_hint", "neutral"),
            "emotional_expressions": state.get("emotional_expressions", "none"),
            "background_noise": state.get("background_noise", "none"),
            "interruption_tendency": state.get("interruption_tendency", "none"),
        }
