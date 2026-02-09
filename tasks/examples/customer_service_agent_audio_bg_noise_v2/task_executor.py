import base64
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



class AudioProcessor:
    """Professional audio processing utilities for MUSAN-based noise mixing."""

    @staticmethod
    def decode_hf_audio(audio_data) -> tuple[list[float], int]:
        """
        Decode audio from HuggingFace dataset format.
        Returns (samples as floats [-1, 1], sample_rate)

        Handles multiple formats:
        - torchcodec AudioDecoder: call get_all_samples() to get AudioSamples
        - torchcodec AudioSamples: has .data (tensor) and .sample_rate
        - Decoded dict: {'array': [...], 'sampling_rate': 16000}
        - Raw bytes: {'bytes': b'...', 'path': '...'}
        - Path only: {'path': '...'}
        """
        # Handle torchcodec AudioDecoder (new HuggingFace format)
        if hasattr(audio_data, 'get_all_samples'):
            audio_samples = audio_data.get_all_samples()
            return AudioProcessor._decode_torchcodec_samples(audio_samples)

        # Handle torchcodec AudioSamples directly
        if hasattr(audio_data, 'data') and hasattr(audio_data, 'sample_rate'):
            return AudioProcessor._decode_torchcodec_samples(audio_data)

        if isinstance(audio_data, dict):
            # HF decoded audio format: {'array': [...], 'sampling_rate': 16000, 'path': ...}
            if 'array' in audio_data:
                samples = list(audio_data['array'])
                sr = audio_data.get('sampling_rate', 16000)
                return samples, sr

            # HF raw format with bytes (when audio_decode=False)
            if 'bytes' in audio_data and audio_data['bytes'] is not None:
                audio_bytes = audio_data['bytes']
                if isinstance(audio_bytes, str):
                    audio_bytes = base64.b64decode(audio_bytes)
                return AudioProcessor.decode_audio_bytes(audio_bytes)

            # HF raw format with path only (when audio_decode=False, streaming)
            if 'path' in audio_data and audio_data['path'] is not None:
                return AudioProcessor.decode_audio_file(audio_data['path'])

        elif isinstance(audio_data, str):
            # Base64 encoded or data URL
            if audio_data.startswith('data:'):
                # Data URL format
                _, data = audio_data.split(',', 1)
                audio_bytes = base64.b64decode(data)
            else:
                audio_bytes = base64.b64decode(audio_data)
            return AudioProcessor.decode_audio_bytes(audio_bytes)

        raise ValueError(f"Unknown audio format: {type(audio_data)}")

    @staticmethod
    def _decode_torchcodec_samples(audio_samples) -> tuple[list[float], int]:
        """Decode torchcodec AudioSamples to list of floats."""
        # audio_samples.data is a torch tensor of shape [channels, samples]
        data = audio_samples.data
        sr = audio_samples.sample_rate

        # Convert to numpy and then to list
        import torch
        if isinstance(data, torch.Tensor):
            # Convert to mono if stereo (take mean across channels)
            if len(data.shape) > 1 and data.shape[0] > 1:
                data = data.mean(dim=0)
            elif len(data.shape) > 1:
                data = data.squeeze(0)

            # Convert to float list [-1, 1]
            samples = data.float().numpy().tolist()

            # Normalize if needed (int16 audio is in range [-32768, 32767])
            max_val = max(abs(min(samples)), abs(max(samples))) if samples else 1.0
            if max_val > 1.0:
                samples = [s / 32768.0 for s in samples]

            return samples, sr

        raise ValueError(f"Unexpected audio data type: {type(data)}")

    @staticmethod
    def decode_audio_bytes(audio_bytes: bytes) -> tuple[list[float], int]:
        """Decode audio bytes using soundfile (supports WAV, FLAC, OGG, etc.)."""
        try:
            import soundfile as sf
            data, sr = sf.read(io.BytesIO(audio_bytes))
            # Convert to mono if stereo
            if len(data.shape) > 1:
                data = data.mean(axis=1)
            return list(data), sr
        except Exception:
            # Fallback to WAV decoder
            return AudioProcessor.decode_wav_bytes(audio_bytes)

    @staticmethod
    def decode_audio_file(file_path: str) -> tuple[list[float], int]:
        """Decode audio from file path using soundfile."""
        try:
            import soundfile as sf
            data, sr = sf.read(file_path)
            # Convert to mono if stereo
            if len(data.shape) > 1:
                data = data.mean(axis=1)
            return list(data), sr
        except Exception as e:
            logging.warning(f"Failed to decode audio file {file_path}: {e}")
            raise ValueError(f"Cannot decode audio file: {file_path}")

    @staticmethod
    def decode_wav_bytes(wav_bytes: bytes) -> tuple[list[float], int]:
        """Decode WAV bytes to float samples. Uses soundfile for robust decoding."""
        try:
            import soundfile as sf
            data, sr = sf.read(io.BytesIO(wav_bytes))
            # Convert to mono if stereo
            if len(data.shape) > 1:
                data = data.mean(axis=1)
            return list(data), sr
        except Exception:
            # Fallback to manual WAV parsing
            pass

        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            raw_data = wf.readframes(nframes)

        # Safety check for buffer size
        expected_size = nframes * nchannels * sampwidth
        if len(raw_data) != expected_size:
            logging.warning(f"WAV buffer size mismatch: expected {expected_size}, got {len(raw_data)}")
            nframes = len(raw_data) // (nchannels * sampwidth)

        # Convert to mono if stereo
        if sampwidth == 2:
            samples = list(struct.unpack(f"<{nframes * nchannels}h", raw_data))
            if nchannels == 2:
                samples = [(samples[i] + samples[i+1]) / 2 for i in range(0, len(samples), 2)]
            # Normalize to [-1, 1]
            samples = [s / 32768.0 for s in samples]
        elif sampwidth == 1:
            samples = list(raw_data)
            if nchannels == 2:
                samples = [(samples[i] + samples[i+1]) / 2 for i in range(0, len(samples), 2)]
            samples = [(s - 128) / 128.0 for s in samples]
        else:
            raise ValueError(f"Unsupported sample width: {sampwidth}")

        return samples, framerate

    @staticmethod
    def resample(samples: list[float], orig_sr: int, target_sr: int) -> list[float]:
        """Simple linear interpolation resampling."""
        if orig_sr == target_sr:
            return samples

        ratio = target_sr / orig_sr
        new_length = int(len(samples) * ratio)
        resampled = []

        for i in range(new_length):
            orig_idx = i / ratio
            idx_floor = int(orig_idx)
            idx_ceil = min(idx_floor + 1, len(samples) - 1)
            frac = orig_idx - idx_floor
            sample = samples[idx_floor] * (1 - frac) + samples[idx_ceil] * frac
            resampled.append(sample)

        return resampled

    @staticmethod
    def calculate_rms(samples: list[float]) -> float:
        """Calculate RMS (root mean square) of audio samples."""
        if not samples:
            return 0.0
        sum_sq = sum(s * s for s in samples)
        return math.sqrt(sum_sq / len(samples))

    @staticmethod
    def normalize_rms(samples: list[float], target_rms: float = 0.1) -> list[float]:
        """Normalize audio to target RMS level."""
        current_rms = AudioProcessor.calculate_rms(samples)
        if current_rms < 1e-10:
            return samples
        scale = target_rms / current_rms
        return [s * scale for s in samples]

    @staticmethod
    def peak_normalize(samples: list[float], target_peak: float = 0.95) -> list[float]:
        """Normalize audio to target peak level."""
        if not samples:
            return samples
        peak = max(abs(s) for s in samples)
        if peak < 1e-10:
            return samples
        scale = target_peak / peak
        return [s * scale for s in samples]

    @staticmethod
    def random_crop(samples: list[float], target_length: int) -> list[float]:
        """Randomly crop audio to target length."""
        if len(samples) <= target_length:
            return samples
        max_start = len(samples) - target_length
        start = random.randint(0, max_start)
        return samples[start:start + target_length]

    @staticmethod
    def loop_with_crossfade(samples: list[float], target_length: int,
                            crossfade_samples: int = 2400) -> list[float]:
        """
        Loop audio to target length with crossfade to avoid clicks.
        crossfade_samples: ~100ms at 24kHz
        """
        if len(samples) >= target_length:
            return samples[:target_length]

        if len(samples) < crossfade_samples * 2:
            # Too short to crossfade, just tile
            tiles = (target_length // len(samples)) + 1
            tiled = samples * tiles
            return tiled[:target_length]

        result = []
        while len(result) < target_length:
            if not result:
                # First iteration, add full samples
                result.extend(samples)
            else:
                # Crossfade with previous end
                crossfade_len = min(crossfade_samples, len(result), len(samples))
                # Fade out the end of result
                for i in range(crossfade_len):
                    fade_out = 1.0 - (i / crossfade_len)
                    fade_in = i / crossfade_len
                    result[-(crossfade_len - i)] = (
                        result[-(crossfade_len - i)] * fade_out +
                        samples[i] * fade_in
                    )
                # Add the rest after crossfade
                result.extend(samples[crossfade_len:])

        return result[:target_length]

    @staticmethod
    def apply_gain_drift(samples: list[float], max_drift_db: float = 2.0,
                         drift_rate: float = 0.5) -> list[float]:
        """
        Apply subtle random gain drift over time for realism.
        max_drift_db: maximum drift in dB
        drift_rate: how fast the drift changes (lower = smoother)
        """
        if not samples:
            return samples

        result = []
        drift_value = 0.0
        drift_target = random.uniform(-max_drift_db, max_drift_db)

        for i, s in enumerate(samples):
            # Slowly move toward target
            drift_value += (drift_target - drift_value) * 0.0001 * drift_rate
            # Occasionally change target
            if random.random() < 0.00001:
                drift_target = random.uniform(-max_drift_db, max_drift_db)

            # Convert dB drift to linear gain
            gain = 10 ** (drift_value / 20.0)
            result.append(s * gain)

        return result

    @staticmethod
    def mix_with_snr(speech: list[float], noise: list[float],
                     snr_db: float) -> list[float]:
        """
        Mix speech with noise at specified SNR (Signal-to-Noise Ratio).
        Higher SNR = quieter noise relative to speech.
        """
        if not noise or not speech:
            return speech

        # Ensure same length
        if len(noise) < len(speech):
            noise = AudioProcessor.loop_with_crossfade(noise, len(speech))
        elif len(noise) > len(speech):
            noise = noise[:len(speech)]

        # Calculate current RMS levels
        speech_rms = AudioProcessor.calculate_rms(speech)
        noise_rms = AudioProcessor.calculate_rms(noise)

        if noise_rms < 1e-10 or speech_rms < 1e-10:
            return speech

        # Calculate required noise scaling for target SNR
        # SNR = 20 * log10(speech_rms / noise_rms)
        # noise_rms_target = speech_rms / (10 ** (snr_db / 20))
        target_noise_rms = speech_rms / (10 ** (snr_db / 20.0))
        noise_scale = target_noise_rms / noise_rms

        # Mix
        mixed = []
        for s, n in zip(speech, noise):
            mixed_sample = s + n * noise_scale
            # Soft clip to prevent harsh distortion
            if abs(mixed_sample) > 1.0:
                mixed_sample = math.copysign(1.0 - math.exp(-abs(mixed_sample)), mixed_sample)
            mixed.append(mixed_sample)

        return mixed

    @staticmethod
    def float_to_wav_bytes(samples: list[float], sample_rate: int = 24000) -> bytes:
        """Convert float samples to WAV bytes."""
        # Convert to 16-bit integers
        int_samples = []
        for s in samples:
            s = max(-1.0, min(1.0, s))
            int_samples.append(int(s * 32767))

        # Pack as bytes
        raw_data = struct.pack(f"<{len(int_samples)}h", *int_samples)

        # Write WAV
        out_buf = io.BytesIO()
        with wave.open(out_buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(raw_data)

        return out_buf.getvalue()


def _get_snr_range(noise_level: str) -> tuple[float, float]:
    """Get SNR range based on noise level setting."""
    snr_ranges = {
        "subtle": (15.0, 25.0),      # Noise barely audible
        "moderate": (8.0, 15.0),     # Noticeable but not distracting
        "noisy": (0.0, 8.0),         # Realistic loud environment
    }
    return snr_ranges.get(noise_level, (10.0, 20.0))


def _get_conversation_turns(state: SygraState) -> list[dict[str, str]]:
    """Extract conversation turns from chat history."""
    chat_history = state.get("__chat_history__", [])
    # Handle aliased initial_query
    initial_query = state.get("scenario->initial_query") or state.get("initial_query", "")

    conversation_nodes = {
        "ask_clarifying_question": "assistant",
        "generate_confirmation": "assistant",
        "generate_completion": "assistant",
        "generate_final_greeting": "assistant",
        "simulate_user_response": "user",
        "simulate_user_confirmation": "user",
        "simulate_user_goodbye": "user",
    }

    turns: list[dict[str, str]] = []
    seen_content = set()

    if initial_query:
        turns.append({"role": "user", "content": initial_query})
        seen_content.add(initial_query[:200])

    for entry in chat_history:
        name = entry.get("name", "")
        response = entry.get("response", "")

        if name not in conversation_nodes:
            continue

        role = conversation_nodes[name]

        if role == "user" and response:
            parsed = safe_json_extract(response)
            if parsed and "user_message" in parsed:
                response = parsed["user_message"]

        if not response:
            continue

        content_key = response[:200] if len(response) > 200 else response
        if content_key in seen_content:
            continue

        turns.append({"role": role, "content": response})
        seen_content.add(content_key)

    return turns


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

        # Handle aliased initial_query
        initial_query = state.get("scenario->initial_query") or state.get("initial_query", "")
        state["user_message"] = initial_query

        return state


class AssistantResponsePostProcessor(NodePostProcessorWithState):
    """Stores assistant's text response."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        state["assistant_response"] = content
        state["turn_count"] = state.get("turn_count", 0) + 1
        return state


class SimulateUserPreProcessor(NodePreProcessor):
    """Prepares ground truth for user simulation."""

    def apply(self, state: SygraState) -> SygraState:
        # Handle aliased fields
        ground_truth = state.get("scenario->ground_truth") or state.get("ground_truth", "")
        scenario_context = state.get("scenario->scenario_context") or state.get("scenario_context", "")
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


class UserGoodbyePostProcessor(NodePostProcessorWithState):
    """Handles user goodbye response."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        # The goodbye message might be JSON or plain text
        parsed = safe_json_extract(content)
        if parsed and "user_message" in parsed:
            state["user_message"] = parsed["user_message"]
        else:
            state["user_message"] = content.strip()
        return state



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


class FinalGreetingPostProcessor(NodePostProcessorWithState):
    """Handles final assistant greeting/goodbye."""

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        state["assistant_response"] = content
        state["conversation_concluded"] = True
        return state



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
        # Configurable max turns (default 5)
        max_turns = state.get("__graph_properties__", {}).get("max_conversation_turns", 10) // 2

        if is_complete or ready_for_confirmation or turn_count >= max_turns:
            return "generate_confirmation"
        return "ask_clarifying_question"


class UserConfirmedCondition(EdgeCondition):
    """Check if user confirmed the information."""

    def apply(state: SygraState) -> str:
        user_confirmed = state.get("user_confirmed", False)
        turn_count = state.get("turn_count", 0)
        # Configurable max turns (default 6)
        max_turns = (state.get("__graph_properties__", {}).get("max_conversation_turns", 10) // 2) + 1

        if user_confirmed or turn_count >= max_turns:
            return "generate_completion"
        return "ask_clarifying_question"



class SynthesizeWithMusanNoise:
    """
    Lambda function to synthesize audio using REAL MUSAN noise samples.

    Improvements:
    - CONTINUOUS background noise across entire conversation (not per-turn)
    - Noise applied to BOTH user AND assistant turns (duplex channel simulation)
    - Configurable noise (enabled/disabled, type, intensity)
    - Same noise sample used throughout conversation for realism

    Features:
    - Uses actual noise recordings from MUSAN dataset
    - Loops with crossfade if noise is shorter than conversation
    - RMS-based loudness normalization
    - Random SNR mixing (subtle: 15-25dB, moderate: 8-15dB, noisy: 0-8dB)
    - Optional random gain drift over time for realism
    """

    @staticmethod
    async def apply(lambda_node_dict: dict, state: SygraState):
        turns = _get_conversation_turns(state)
        if not turns:
            state["conversation_audio"] = None
            state["user_voice"] = None
            state["assistant_voice"] = None
            state["noise_enabled"] = False
            state["noise_type"] = None
            state["noise_source"] = None
            state["snr_applied"] = None
            return state

        user_voice = str(state.get("user_voice") or lambda_node_dict.get("user_voice", "echo"))
        assistant_voice = str(lambda_node_dict.get("assistant_voice", "nova"))
        noise_level = str(state.get("noise_level", "moderate"))

        # Check if noise is enabled
        noise_enabled_raw = state.get("noise_enabled", True)
        # Handle string "true"/"false" from weighted_sampler
        if isinstance(noise_enabled_raw, str):
            noise_enabled = noise_enabled_raw.lower() == "true"
        else:
            noise_enabled = bool(noise_enabled_raw)

        noise_type = str(state.get("noise_type", "any"))

        # Get MUSAN audio from the randomly joined dataset
        musan_audio = state.get("musan->audio") if noise_enabled else None
        noise_source = "musan" if musan_audio else "none"

        if user_voice == assistant_voice:
            assistant_voice = "nova" if user_voice != "nova" else "alloy"

        # Determine SNR for this conversation
        snr_min, snr_max = _get_snr_range(noise_level)
        target_snr = random.uniform(snr_min, snr_max)

        try:
            client, model_name = await _get_tts_client()

            # Load and process MUSAN noise if available and enabled
            noise_samples = None
            noise_sr = 24000

            if musan_audio and noise_enabled:
                try:
                    noise_samples, noise_sr = AudioProcessor.decode_hf_audio(musan_audio)
                    # Normalize noise
                    noise_samples = AudioProcessor.normalize_rms(noise_samples, target_rms=0.1)
                    logging.info(f"Loaded MUSAN noise: {len(noise_samples)} samples at {noise_sr}Hz")
                except Exception as e:
                    logging.warning(f"Failed to decode MUSAN audio: {e}")
                    noise_samples = None
                    noise_source = "none"

            # Step 1: Synthesize all TTS audio (clean, without noise)
            wav_segments: list[bytes] = []

            for turn in turns:
                role = str(turn.get("role", ""))
                content = str(turn.get("content", "")).strip()
                if not content:
                    continue

                voice = user_voice if role == "user" else assistant_voice

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

                # Concatenate chunks within turn
                if len(turn_segments) > 1:
                    turn_audio = _concat_wav_segments(turn_segments, pause_ms=50)
                elif turn_segments:
                    turn_audio = turn_segments[0]
                else:
                    continue

                wav_segments.append(turn_audio)

            if not wav_segments:
                state["conversation_audio"] = None
                state["user_voice"] = user_voice
                state["assistant_voice"] = assistant_voice
                state["noise_enabled"] = noise_enabled
                state["noise_type"] = noise_type if noise_enabled else None
                state["noise_source"] = noise_source
                state["snr_applied"] = None
                return state

            # Step 2: Concatenate all turns into one continuous audio
            combined_clean = _concat_wav_segments(wav_segments, pause_ms=250)

            # Step 3: Apply CONTINUOUS noise to entire conversation
            if noise_samples:
                # Decode the full conversation audio
                speech_samples, speech_sr = AudioProcessor.decode_wav_bytes(combined_clean)

                # Resample noise to match speech sample rate if needed
                processed_noise = noise_samples
                if noise_sr != speech_sr:
                    processed_noise = AudioProcessor.resample(noise_samples, noise_sr, speech_sr)

                # Loop noise with crossfade to match entire conversation length
                # This ensures continuous background noise without cuts
                if len(processed_noise) < len(speech_samples):
                    processed_noise = AudioProcessor.loop_with_crossfade(
                        processed_noise, len(speech_samples),
                        crossfade_samples=int(speech_sr * 0.1)  # 100ms crossfade
                    )
                else:
                    # If noise is longer, use random starting point for variety
                    max_start = len(processed_noise) - len(speech_samples)
                    start = random.randint(0, max_start)
                    processed_noise = processed_noise[start:start + len(speech_samples)]

                # Apply subtle gain drift over time for realism
                processed_noise = AudioProcessor.apply_gain_drift(
                    processed_noise, max_drift_db=1.5, drift_rate=0.3
                )

                # Normalize speech
                speech_samples = AudioProcessor.normalize_rms(speech_samples, target_rms=0.2)

                # Mix entire conversation with continuous noise at target SNR
                mixed = AudioProcessor.mix_with_snr(speech_samples, processed_noise, target_snr)

                # Peak normalize final mix
                mixed = AudioProcessor.peak_normalize(mixed, target_peak=0.9)

                # Convert back to WAV
                final_audio = AudioProcessor.float_to_wav_bytes(mixed, speech_sr)
            else:
                # No noise, use clean audio
                final_audio = combined_clean

            state["conversation_audio"] = audio_utils.get_audio_url(final_audio, mime="audio/wav")

        except Exception as e:
            logging.error(f"MUSAN audio synthesis failed: {e}")
            import traceback
            traceback.print_exc()
            state["conversation_audio"] = None
            noise_source = "error"
            target_snr = None

        state["user_voice"] = user_voice
        state["assistant_voice"] = assistant_voice
        state["noise_enabled"] = noise_enabled
        state["noise_type"] = noise_type if noise_enabled else None
        state["noise_source"] = noise_source
        state["snr_applied"] = round(target_snr, 1) if target_snr else None
        return state



class CustomerServiceAudioOutputGenerator(BaseOutputGenerator):
    """Generates output with both text and audio conversations, including personality and noise metadata."""

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
            "interruption_tendency": state.get("interruption_tendency", "none"),
        }

    @staticmethod
    def build_noise_metadata(data: Any, state: SygraState) -> dict:
        """Build noise configuration metadata."""
        noise_enabled_raw = state.get("noise_enabled", True)
        if isinstance(noise_enabled_raw, str):
            noise_enabled = noise_enabled_raw.lower() == "true"
        else:
            noise_enabled = bool(noise_enabled_raw)

        return {
            "enabled": noise_enabled,
            "type": state.get("noise_type", "any") if noise_enabled else None,
            "level": state.get("noise_level", "moderate") if noise_enabled else None,
            "duplex": True,  # Both sides have noise
        }
