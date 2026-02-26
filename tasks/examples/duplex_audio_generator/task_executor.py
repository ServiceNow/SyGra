"""
Duplex Audio Generator - Task Executor

Implements the "Duplex-by-Compilation" approach with CORRECT timing:
1. Synthesize TTS for all conversation turns FIRST (get actual durations)
2. Place main turns SEQUENTIALLY on timeline with natural gaps
3. Add backchannels as SHORT overlays during the other speaker's turn
4. Apply MILD duration conformance only where needed (±15% max)

Key insight: TTS duration informs timing, NOT the other way around.
"""

import asyncio
import io
import json
import logging
import math
import os
import random
import re
import struct
import subprocess
import tempfile
import wave
from typing import Any, Optional

from sygra.core.graph.functions.node_processor import NodePostProcessorWithState
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
    # Try to find JSON in code blocks first
    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Try direct parse
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


def _get_wav_duration_ms(wav_bytes: bytes) -> int:
    """Get duration of WAV file in milliseconds."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            logging.debug(f"WAV params: frames={frames}, rate={rate}, channels={channels}, sampwidth={sampwidth}")
            duration_ms = int((frames / rate) * 1000)
            logging.debug(f"Calculated duration: {duration_ms}ms")
            return duration_ms
    except Exception as e:
        logging.warning(f"Failed to get WAV duration: {e}")
        # Fallback: estimate from byte size (16-bit mono at 24kHz)
        estimated_frames = len(wav_bytes) // 2  # 2 bytes per sample
        estimated_duration = int((estimated_frames / 24000) * 1000)
        logging.debug(f"Estimated duration from size: {estimated_duration}ms")
        return estimated_duration


def _concat_wav_segments(wav_segments: list[bytes], pause_ms: int = 50) -> bytes:
    """Concatenate WAV segments with minimal pauses."""
    if not wav_segments:
        raise ValueError("No WAV segments to concatenate")

    if len(wav_segments) == 1:
        return wav_segments[0]

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
            frames.append(wf.readframes(wf.getnframes()))

        if framerate and nchannels and sampwidth and pause_ms > 0:
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


def _mild_duration_conformance(wav_bytes: bytes, target_duration_ms: int, max_ratio: float = 0.15) -> bytes:
    """
    Apply MILD duration conformance - only adjust if within ±max_ratio (default 15%).

    If the required adjustment is more extreme, return the original audio unchanged.
    This prevents unnatural speedup/slowdown artifacts.
    """
    current_duration_ms = _get_wav_duration_ms(wav_bytes)
    if current_duration_ms <= 0 or target_duration_ms <= 0:
        return wav_bytes

    # Calculate tempo factor: current / target
    # tempo > 1 means speed up, tempo < 1 means slow down
    tempo = current_duration_ms / target_duration_ms

    # Calculate how much adjustment is needed
    adjustment_ratio = abs(1.0 - tempo)

    # Only apply if adjustment is within acceptable range
    if adjustment_ratio > max_ratio:
        logging.debug(f"Duration conformance skipped: {adjustment_ratio:.1%} exceeds {max_ratio:.1%} limit")
        return wav_bytes

    # Apply mild tempo adjustment
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as in_file:
            in_file.write(wav_bytes)
            in_path = in_file.name

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out_file:
            out_path = out_file.name

        cmd = [
            "ffmpeg", "-y", "-i", in_path,
            "-af", f"atempo={tempo:.4f}",
            "-ar", "24000",
            out_path
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=30)

        if result.returncode == 0 and os.path.exists(out_path):
            with open(out_path, "rb") as f:
                return f.read()
        return wav_bytes

    except Exception as e:
        logging.warning(f"Mild duration conformance failed: {e}")
        return wav_bytes
    finally:
        for path in [in_path, out_path]:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception:
                pass


def _truncate_audio(wav_bytes: bytes, target_duration_ms: int, fade_ms: int = 50) -> tuple[bytes, bool]:
    """
    Truncate audio to target duration with a short fade-out.
    Used when an interruption cuts off the speaker.

    Works directly with raw RIFF/WAV bytes to handle non-standard TTS headers.

    Returns: (audio_bytes, was_truncated)
    """
    try:
        # Find the "data" chunk and extract format info from "fmt " chunk
        fmt_offset = wav_bytes.find(b"fmt ")
        data_offset = wav_bytes.find(b"data")
        if fmt_offset < 0 or data_offset < 0:
            return wav_bytes, False

        # Parse fmt chunk (PCM: 16 bytes after the chunk size)
        channels = struct.unpack_from("<H", wav_bytes, fmt_offset + 10)[0]
        sample_rate = struct.unpack_from("<I", wav_bytes, fmt_offset + 12)[0]
        bits_per_sample = struct.unpack_from("<H", wav_bytes, fmt_offset + 22)[0]
        sampwidth = bits_per_sample // 8

        data_size = struct.unpack_from("<I", wav_bytes, data_offset + 4)[0]
        pcm_start = data_offset + 8
        available = len(wav_bytes) - pcm_start
        pcm_len = min(data_size, available)

        bytes_per_frame = sampwidth * channels
        target_frames = int(sample_rate * target_duration_ms / 1000)
        target_bytes = target_frames * bytes_per_frame

        if target_bytes >= pcm_len:
            return wav_bytes, False

        # Truncate the PCM data
        truncated_pcm = bytearray(wav_bytes[pcm_start:pcm_start + target_bytes])

        # Apply short fade-out to avoid click (16-bit PCM only)
        if fade_ms > 0 and sampwidth == 2:
            fade_frames = int(sample_rate * fade_ms / 1000)
            num_samples = len(truncated_pcm) // 2
            if fade_frames > 0 and num_samples > fade_frames:
                samples = list(struct.unpack(f"<{num_samples}h", bytes(truncated_pcm)))
                for i in range(fade_frames):
                    idx = num_samples - fade_frames + i
                    fade_factor = 1.0 - (i / fade_frames)
                    samples[idx] = int(samples[idx] * fade_factor)
                truncated_pcm = bytearray(struct.pack(f"<{num_samples}h", *samples))

        # Rebuild WAV: keep header up to data chunk, update sizes, append truncated PCM
        new_data_size = len(truncated_pcm)
        header = bytearray(wav_bytes[:pcm_start])
        # Patch RIFF chunk size (offset 4)
        struct.pack_into("<I", header, 4, len(header) - 8 + new_data_size)
        # Patch data chunk size
        struct.pack_into("<I", header, data_offset + 4, new_data_size)

        result = bytes(header) + bytes(truncated_pcm)
        return result, True
    except Exception as e:
        logging.warning(f"Failed to truncate audio: {e}")
        return wav_bytes, False


def _create_silent_wav(duration_ms: int, sample_rate: int = 24000,
                        channels: int = 1, sampwidth: int = 2) -> bytes:
    """Create a silent WAV file of specified duration."""
    num_frames = int(sample_rate * duration_ms / 1000)
    silence = b"\x00" * (num_frames * channels * sampwidth)

    out_buf = io.BytesIO()
    with wave.open(out_buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(silence)

    return out_buf.getvalue()


def _compute_wav_rms(wav_bytes: bytes) -> float:
    """
    Compute the RMS energy of a WAV file from raw bytes.

    Works directly with RIFF/WAV bytes to handle non-standard TTS headers.
    Returns 0.0 on failure.
    """
    try:
        data_offset = wav_bytes.find(b"data")
        if data_offset < 0 or data_offset + 8 > len(wav_bytes):
            return 0.0

        data_size = struct.unpack_from("<I", wav_bytes, data_offset + 4)[0]
        pcm_start = data_offset + 8
        available = len(wav_bytes) - pcm_start
        pcm_len = min(data_size, available)

        if pcm_len < 2:
            return 0.0

        num_samples = pcm_len // 2
        samples = struct.unpack_from(f"<{num_samples}h", wav_bytes, pcm_start)
        if not samples:
            return 0.0

        return math.sqrt(sum(s * s for s in samples) / len(samples))
    except Exception as e:
        logging.warning(f"_compute_wav_rms failed: {e}")
        return 0.0


def _attenuate_audio(wav_bytes: bytes, gain: float) -> bytes:
    """
    Scale the amplitude of a WAV by a gain factor (0.0 = silence, 1.0 = unchanged).

    Used to make backchannels and reactions sound like soft listening signals
    rather than full-volume speech from a separate speaker.

    Works directly with raw RIFF/WAV bytes to avoid issues with Python's wave
    module mishandling non-standard TTS WAV headers.
    """
    if gain >= 1.0:
        return wav_bytes

    try:
        # Find the "data" chunk by scanning for the marker.
        # WAV structure: RIFF header (12 bytes) then chunks (id + size + payload).
        data_offset = wav_bytes.find(b"data")
        if data_offset < 0 or data_offset + 8 > len(wav_bytes):
            logging.warning("_attenuate_audio: no 'data' chunk found")
            return wav_bytes

        data_size = struct.unpack_from("<I", wav_bytes, data_offset + 4)[0]
        pcm_start = data_offset + 8
        # Actual available PCM bytes (clamp to what's really there)
        available = len(wav_bytes) - pcm_start
        pcm_len = min(data_size, available)

        if pcm_len < 2:
            return wav_bytes

        # Scale 16-bit PCM samples in-place
        num_samples = pcm_len // 2
        samples = struct.unpack_from(f"<{num_samples}h", wav_bytes, pcm_start)
        scaled = struct.pack(
            f"<{num_samples}h",
            *(max(-32768, min(32767, int(s * gain))) for s in samples),
        )

        # Rebuild: header unchanged, PCM replaced
        result = bytearray(wav_bytes[:pcm_start])
        result.extend(scaled)
        # Append any trailing bytes after the PCM data
        trailing_start = pcm_start + pcm_len
        if trailing_start < len(wav_bytes):
            result.extend(wav_bytes[trailing_start:])

        return bytes(result)
    except Exception as e:
        logging.warning(f"_attenuate_audio failed: {e}")
        return wav_bytes


# Per-type gain levels for backchannels and reactions.
# These make overlay clips sound like soft listening signals rather than
# full-volume speech from a third person.
_BC_GAIN = {
    "backchannel_short": 0.40,     # soft "mm-hm", "yeah"
    "backchannel_extended": 0.50,  # slightly louder substantive reaction
    "thinking": 0.38,             # quiet murmur "hmmmm", "let me think"
    "interruption": 0.70,         # louder — intentional interjection
}
_REACTION_GAIN = 0.55  # assistant yielding / reacting to interruption


def _place_audio_on_timeline(
    audio_clips: list[tuple[int, bytes]],
    total_duration_ms: int,
    sample_rate: int = 24000,
    channels: int = 1,
    sampwidth: int = 2
) -> bytes:
    """
    Place multiple audio clips on a timeline and render to a single WAV.
    Uses additive mixing for overlapping regions.
    """
    total_samples = int(sample_rate * total_duration_ms / 1000)
    output = [0.0] * total_samples  # Use float for mixing

    for start_ms, wav_bytes in audio_clips:
        if not wav_bytes:
            continue

        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                clip_frames = wf.readframes(wf.getnframes())
                clip_samples = list(struct.unpack(f"<{len(clip_frames)//2}h", clip_frames))
        except Exception as e:
            logging.warning(f"Failed to read clip: {e}")
            continue

        start_sample = int(sample_rate * start_ms / 1000)

        # Additive mixing
        for i, sample in enumerate(clip_samples):
            pos = start_sample + i
            if 0 <= pos < total_samples:
                output[pos] += sample

    # Normalize and convert to int16
    max_val = max(abs(s) for s in output) if output else 1
    if max_val > 32767:
        scale = 32767 / max_val
        output = [s * scale for s in output]

    output_int = [max(-32768, min(32767, int(s))) for s in output]
    output_bytes = struct.pack(f"<{len(output_int)}h", *output_int)

    out_buf = io.BytesIO()
    with wave.open(out_buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(output_bytes)

    return out_buf.getvalue()


def _mix_stems_to_duplex(user_stem: bytes, assistant_stem: bytes) -> bytes:
    """Mix two audio stems into a single duplex audio file."""
    try:
        with wave.open(io.BytesIO(user_stem), "rb") as wf:
            user_params = wf.getparams()
            user_frames = wf.readframes(wf.getnframes())

        with wave.open(io.BytesIO(assistant_stem), "rb") as wf:
            assistant_frames = wf.readframes(wf.getnframes())

        user_samples = list(struct.unpack(f"<{len(user_frames)//2}h", user_frames))
        assistant_samples = list(struct.unpack(f"<{len(assistant_frames)//2}h", assistant_frames))

        max_len = max(len(user_samples), len(assistant_samples))
        user_samples.extend([0] * (max_len - len(user_samples)))
        assistant_samples.extend([0] * (max_len - len(assistant_samples)))

        # Mix with headroom
        mixed = []
        for u, a in zip(user_samples, assistant_samples):
            mixed_sample = int((u + a) * 0.7)
            mixed_sample = max(-32768, min(32767, mixed_sample))
            mixed.append(mixed_sample)

        mixed_bytes = struct.pack(f"<{len(mixed)}h", *mixed)

        out_buf = io.BytesIO()
        with wave.open(out_buf, "wb") as wf:
            wf.setnchannels(user_params.nchannels)
            wf.setsampwidth(user_params.sampwidth)
            wf.setframerate(user_params.framerate)
            wf.writeframes(mixed_bytes)

        return out_buf.getvalue()

    except Exception as e:
        logging.error(f"Failed to mix stems: {e}")
        return user_stem


# ============== Post Processors ==============


def _safe_json_extract_array(text: str) -> list:
    """Safely extract a JSON array from LLM response text."""
    # Try to find JSON array in code blocks first
    code_block_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON array
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    return []


class NaturalizeConversationPostProcessor(NodePostProcessorWithState):
    """
    Parse naturalized conversation from LLM response.

    The LLM rewrites the clean conversation with fillers, false starts,
    pause markers, and natural phrasing. Falls back to original conversation
    on parse failure.
    """

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        original_conversation = state.get("conversation", [])

        # Try to extract the naturalized conversation JSON array
        naturalized = _safe_json_extract_array(content)

        # Validate: must be a list of dicts with role and content
        if naturalized and isinstance(naturalized, list):
            valid = True
            for turn in naturalized:
                if not isinstance(turn, dict) or "role" not in turn or "content" not in turn:
                    valid = False
                    break

            if valid and len(naturalized) == len(original_conversation):
                state["naturalized_conversation"] = naturalized
                logging.info(
                    f"NaturalizeConversationPostProcessor: Successfully naturalized "
                    f"{len(naturalized)} turns"
                )
                return state

        # Fallback: use original conversation
        logging.warning(
            "NaturalizeConversationPostProcessor: Failed to parse naturalized conversation, "
            "falling back to original"
        )
        state["naturalized_conversation"] = original_conversation
        return state


class TimeAnchorPostProcessor(NodePostProcessorWithState):
    """
    Parse user backchannel/interruption placements from LLM response.

    IMPORTANT: Only USER can talk over ASSISTANT, never vice versa.
    The LLM decides WHERE to place user backchannels/interruptions during assistant turns.
    """

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        parsed = safe_json_extract(content)

        backchannel_placements = parsed.get("backchannel_placements", [])
        conversation = state.get("conversation", [])

        # Validate and filter placements - only during assistant turns
        valid_placements = []
        for placement in backchannel_placements:
            if not isinstance(placement, dict):
                continue

            # Support both "during_turn_index" and "after_turn_index" for backwards compat
            turn_index = placement.get("during_turn_index", placement.get("after_turn_index", -1))
            text = placement.get("text", "").strip()
            position = placement.get("position_in_turn", "middle")
            bc_type = placement.get("type", "backchannel")  # backchannel or interruption
            assistant_reaction = placement.get("assistant_reaction", "").strip()  # How assistant reacts to interruption

            if turn_index < 0 or not text:
                continue

            # Only allow backchannels during ASSISTANT turns
            if turn_index < len(conversation):
                turn_role = conversation[turn_index].get("role", "")
                if turn_role != "assistant":
                    logging.warning(f"Skipping backchannel during non-assistant turn {turn_index}")
                    continue

            valid_placements.append({
                "during_turn_index": int(turn_index),
                "text": text,
                "position_in_turn": position,
                "type": bc_type,
                "assistant_reaction": assistant_reaction  # e.g., "oh, go ahead" or "sure"
            })

        state["backchannel_placements"] = valid_placements
        logging.info(f"TimeAnchorPostProcessor: Found {len(valid_placements)} user backchannel/interruption placements")

        return state


# Valid backchannel types for the enhanced taxonomy
_VALID_BC_TYPES = {"backchannel_short", "backchannel_extended", "thinking", "interruption"}


class EnhancedTimeAnchorPostProcessor(NodePostProcessorWithState):
    """
    Enhanced backchannel/interruption placement parser with richer type taxonomy.

    Validates types: backchannel_short, backchannel_extended, thinking, interruption.
    Normalizes unknown types to backchannel_short.
    Validates placements against naturalized_conversation.
    """

    def apply(self, response: SygraMessage, state: SygraState) -> SygraState:
        content = response.message.content
        parsed = safe_json_extract(content)

        backchannel_placements = parsed.get("backchannel_placements", [])
        # Validate against naturalized conversation (not original)
        conversation = state.get("naturalized_conversation", state.get("conversation", []))

        valid_placements = []
        for placement in backchannel_placements:
            if not isinstance(placement, dict):
                continue

            turn_index = placement.get("during_turn_index", placement.get("after_turn_index", -1))
            text = placement.get("text", "").strip()
            position = placement.get("position_in_turn", "middle")
            bc_type = placement.get("type", "backchannel_short")
            assistant_reaction = placement.get("assistant_reaction", "").strip()

            if turn_index < 0 or not text:
                continue

            # Normalize legacy "backchannel" type to "backchannel_short"
            if bc_type == "backchannel":
                bc_type = "backchannel_short"

            # Normalize unknown types to backchannel_short
            if bc_type not in _VALID_BC_TYPES:
                logging.warning(
                    f"Unknown backchannel type '{bc_type}', normalizing to backchannel_short"
                )
                bc_type = "backchannel_short"

            # Only allow during ASSISTANT turns
            if turn_index < len(conversation):
                turn_role = conversation[turn_index].get("role", "")
                if turn_role != "assistant":
                    logging.warning(f"Skipping backchannel during non-assistant turn {turn_index}")
                    continue

            valid_placements.append({
                "during_turn_index": int(turn_index),
                "text": text,
                "position_in_turn": position,
                "type": bc_type,
                "assistant_reaction": assistant_reaction,
            })

        # --- Hard cap: at most 1 interruption per conversation ---
        # Even if the LLM generates multiple interruptions, multiple overlapping
        # interruption sequences create unintelligible chaos (each interruption
        # spawns a BC + reaction + cutoff lasting 3-4 seconds). Keep the first
        # one and drop the rest.
        interruptions = [p for p in valid_placements if p["type"] == "interruption"]
        if len(interruptions) > 1:
            kept = interruptions[0]
            dropped = len(interruptions) - 1
            valid_placements = [
                p for p in valid_placements
                if p["type"] != "interruption" or p is kept
            ]
            logging.info(
                f"EnhancedTimeAnchorPostProcessor: Capped interruptions — "
                f"kept 1, dropped {dropped}"
            )

        state["backchannel_placements"] = valid_placements
        logging.info(
            f"EnhancedTimeAnchorPostProcessor: Found {len(valid_placements)} placements "
            f"(types: {[p['type'] for p in valid_placements]})"
        )

        return state


# ============== Lambda Functions ==============


_PAUSE_MARKER_RE = re.compile(r"\[pause:(\d+)ms\]")


def _parse_pause_segments(content: str) -> list[dict]:
    """
    Parse text content with [pause:Xms] markers into alternating text/pause segments.

    Returns a list of dicts like:
      [{"type": "text", "value": "Can you tell me"},
       {"type": "pause", "duration_ms": 500},
       {"type": "text", "value": "the dates?"}]
    """
    segments = []
    last_end = 0

    for match in _PAUSE_MARKER_RE.finditer(content):
        # Text before this pause marker
        text_before = content[last_end:match.start()].strip()
        if text_before:
            segments.append({"type": "text", "value": text_before})

        pause_ms = int(match.group(1))
        # Clamp pause duration to reasonable range (100ms - 3000ms)
        pause_ms = max(100, min(pause_ms, 3000))
        segments.append({"type": "pause", "duration_ms": pause_ms})

        last_end = match.end()

    # Remaining text after last pause marker
    remaining = content[last_end:].strip()
    if remaining:
        segments.append({"type": "text", "value": remaining})

    return segments


class SynthesizeAllTurns:
    """
    Step 1: Synthesize TTS for ALL conversation turns FIRST.

    This gives us actual audio durations to calculate realistic timing.
    We synthesize main turns AND backchannels separately.

    Handles [pause:Xms] markers in naturalized conversation by splitting
    into text segments with silence gaps between them.
    """

    @staticmethod
    async def apply(lambda_node_dict: dict, state: dict):
        # Prefer naturalized conversation, fall back to original
        conversation = state.get("naturalized_conversation", state.get("conversation", []))
        backchannel_placements = state.get("backchannel_placements", [])

        user_voice = str(state.get("user_voice", "alloy"))
        assistant_voice = str(state.get("assistant_voice", "nova"))

        # Ensure voices are different and ideally one male + one female.
        # Male: echo, onyx, fable.  Female: alloy, nova, shimmer.
        _MALE_VOICES = {"echo", "onyx", "fable"}
        _FEMALE_VOICES = {"alloy", "nova", "shimmer"}
        if user_voice == assistant_voice:
            if user_voice in _MALE_VOICES:
                assistant_voice = "nova"
            else:
                assistant_voice = "echo"

        logging.info(f"SynthesizeAllTurns: Starting with {len(conversation)} turns, {len(backchannel_placements)} backchannels")

        try:
            client, model_name = await _get_tts_client()

            # Synthesize main conversation turns
            synthesized_turns = []
            for i, turn in enumerate(conversation):
                role = turn.get("role", "user")
                content = turn.get("content", "").strip()

                if not content:
                    continue

                voice = user_voice if role == "user" else assistant_voice

                # Parse [pause:Xms] markers
                segments = _parse_pause_segments(content)
                has_pauses = any(s["type"] == "pause" for s in segments)

                # If no pause markers, synthesize normally
                if not has_pauses:
                    wav_segments = []
                    # Strip any leftover markers for TTS
                    clean_content = _PAUSE_MARKER_RE.sub("", content).strip()
                    for chunk in _chunk_text_for_tts(clean_content):
                        try:
                            audio_resp = await client.create_speech(
                                model=model_name,
                                input=chunk,
                                voice=voice,
                                response_format="wav",
                                speed=1.0,
                            )
                            wav_segments.append(bytes(audio_resp.content))
                        except Exception as e:
                            logging.warning(f"TTS failed for chunk: {e}")
                else:
                    # Synthesize each text segment and create silence for pauses
                    wav_segments = []
                    for seg in segments:
                        if seg["type"] == "text":
                            for chunk in _chunk_text_for_tts(seg["value"]):
                                try:
                                    audio_resp = await client.create_speech(
                                        model=model_name,
                                        input=chunk,
                                        voice=voice,
                                        response_format="wav",
                                        speed=1.0,
                                    )
                                    wav_segments.append(bytes(audio_resp.content))
                                except Exception as e:
                                    logging.warning(f"TTS failed for segment chunk: {e}")
                        elif seg["type"] == "pause":
                            silence = _create_silent_wav(seg["duration_ms"])
                            wav_segments.append(silence)

                if wav_segments:
                    if len(wav_segments) > 1:
                        # Use 0ms pause between segments when we have explicit pauses
                        pause_between = 0 if has_pauses else 50
                        combined_audio = _concat_wav_segments(wav_segments, pause_ms=pause_between)
                    else:
                        combined_audio = wav_segments[0]

                    # Debug: check the WAV header
                    logging.info(f"SynthesizeAllTurns: Turn {i} audio size: {len(combined_audio)} bytes")

                    duration_ms = _get_wav_duration_ms(combined_audio)

                    # Sanity check: duration should be reasonable (< 60 seconds per turn)
                    if duration_ms > 60000 or duration_ms <= 0:
                        # Something is wrong - estimate from audio size
                        # WAV: 24kHz, 16-bit mono = 48000 bytes/second
                        estimated_duration = int(len(combined_audio) / 48) # bytes / (bytes_per_ms)
                        logging.warning(f"SynthesizeAllTurns: Duration {duration_ms}ms seems wrong, estimating {estimated_duration}ms from {len(combined_audio)} bytes")
                        duration_ms = max(500, min(estimated_duration, 30000))  # Clamp to reasonable range

                    logging.info(f"SynthesizeAllTurns: Turn {i} ({role}): '{content[:50]}...' duration={duration_ms}ms, has_pauses={has_pauses}")
                    synthesized_turns.append({
                        "index": i,
                        "role": role,
                        "text": content,
                        "audio": combined_audio,
                        "duration_ms": duration_ms,
                        "is_backchannel": False,
                        "has_pauses": has_pauses,
                    })

            # Synthesize user backchannels (only user talks over assistant)
            # Also synthesize assistant reactions to interruptions
            synthesized_backchannels = []
            for placement in backchannel_placements:
                turn_index = placement.get("during_turn_index", -1)
                text = placement.get("text", "")
                position = placement.get("position_in_turn", "middle")
                bc_type = placement.get("type", "backchannel")
                assistant_reaction = placement.get("assistant_reaction", "")

                # All backchannels are from the USER (only user talks over assistant)
                bc_voice = user_voice
                bc_role = "user"

                try:
                    # TTS can produce near-silent audio for ultra-short
                    # utterances ("mm-hm", "uh-huh"). We detect this via RMS
                    # and retry with an expanded text variant that gives TTS
                    # more phonemes to work with.
                    _MIN_BC_RMS = 200
                    _BC_RETRY_VARIANTS = [
                        text,                          # original
                        text.replace("-", " "),         # "mm-hm" -> "mm hm"
                        text + ", " + text,            # "mm-hm" -> "mm-hm, mm-hm"
                    ]

                    bc_audio = None
                    bc_rms = 0
                    for variant_idx, variant_text in enumerate(_BC_RETRY_VARIANTS):
                        audio_resp = await client.create_speech(
                            model=model_name,
                            input=variant_text,
                            voice=bc_voice,
                            response_format="wav",
                            speed=1.0,
                        )
                        candidate = bytes(audio_resp.content)
                        candidate_rms = _compute_wav_rms(candidate)

                        if candidate_rms >= _MIN_BC_RMS or bc_audio is None:
                            bc_audio = candidate
                            bc_rms = candidate_rms

                        if candidate_rms >= _MIN_BC_RMS:
                            if variant_idx > 0:
                                logging.info(
                                    f"SynthesizeAllTurns: Backchannel '{text}' "
                                    f"retry #{variant_idx} with '{variant_text}' "
                                    f"produced RMS={candidate_rms:.0f} (acceptable)"
                                )
                            break

                        logging.warning(
                            f"SynthesizeAllTurns: Backchannel '{variant_text}' "
                            f"produced near-silent audio (RMS={candidate_rms:.0f}), "
                            f"{'retrying' if variant_idx < len(_BC_RETRY_VARIANTS) - 1 else 'using best attempt'}"
                        )

                    bc_duration = _get_wav_duration_ms(bc_audio)

                    # Sanity check duration
                    if bc_duration > 10000 or bc_duration <= 0:
                        estimated_duration = int(len(bc_audio) / 48)
                        logging.warning(f"Backchannel duration {bc_duration}ms seems wrong, using {estimated_duration}ms")
                        bc_duration = max(200, min(estimated_duration, 3000))

                    # Synthesize assistant reaction if this is an interruption with a reaction
                    reaction_audio = None
                    reaction_duration = 0
                    if bc_type == "interruption" and assistant_reaction:
                        try:
                            reaction_resp = await client.create_speech(
                                model=model_name,
                                input=assistant_reaction,
                                voice=assistant_voice,
                                response_format="wav",
                                speed=1.0,
                            )
                            reaction_audio = bytes(reaction_resp.content)
                            reaction_duration = _get_wav_duration_ms(reaction_audio)
                            if reaction_duration > 5000 or reaction_duration <= 0:
                                estimated_duration = int(len(reaction_audio) / 48)
                                reaction_duration = max(200, min(estimated_duration, 2000))
                            logging.info(f"SynthesizeAllTurns: Assistant reaction '{assistant_reaction}' duration={reaction_duration}ms")
                        except Exception as e:
                            logging.warning(f"TTS failed for assistant reaction '{assistant_reaction}': {e}")

                    synthesized_backchannels.append({
                        "during_turn_index": turn_index,
                        "text": text,
                        "position_in_turn": position,
                        "type": bc_type,
                        "role": bc_role,
                        "audio": bc_audio,
                        "duration_ms": bc_duration,
                        "is_backchannel": True,
                        "assistant_reaction": assistant_reaction,
                        "reaction_audio": reaction_audio,
                        "reaction_duration_ms": reaction_duration
                    })
                    logging.info(f"SynthesizeAllTurns: Backchannel '{text}' duration={bc_duration}ms, type={bc_type}")
                except Exception as e:
                    logging.warning(f"TTS failed for backchannel '{text}': {e}")

            state["synthesized_turns"] = synthesized_turns
            state["synthesized_backchannels"] = synthesized_backchannels
            state["user_voice"] = user_voice
            state["assistant_voice"] = assistant_voice

            logging.info(f"SynthesizeAllTurns: Created {len(synthesized_turns)} turns, {len(synthesized_backchannels)} backchannels")

        except Exception as e:
            logging.error(f"Audio synthesis failed: {e}")
            import traceback
            logging.error(traceback.format_exc())
            state["synthesized_turns"] = []
            state["synthesized_backchannels"] = []

        return state


class CalculateTimeline:
    """
    Step 2: Calculate realistic timeline based on ACTUAL TTS durations.

    Rules:
    1. Main turns are placed SEQUENTIALLY with contextual gaps
    2. Slight overlap at turn boundaries is OK (50-150ms)
    3. backchannel_short / backchannel_extended are placed DURING the host turn
    4. "thinking" backchannels are placed AFTER the host turn ends — the listener
       must hear the full statement before they can begin processing it
    5. backchannel_extended may extend slightly beyond the turn boundary
    6. Post-interruption recovery adds extra gap
    7. No two user backchannels may overlap on the user stem
    """

    @staticmethod
    def _calculate_contextual_gap(
        prev_turn: Optional[dict],
        gap_min: int,
        gap_max: int,
        interrupted_turn_indices: set,
        thinking_bc_durations: dict,
    ) -> int:
        """
        Calculate gap based on conversation context instead of uniform random.

        Uses pre-scanned data so we know about interruptions and thinking sounds
        BEFORE placing turns (not after).
        """
        base_gap = random.randint(gap_min, gap_max)

        if prev_turn is None:
            return base_gap

        prev_text = prev_turn.get("text", "")
        prev_index = prev_turn.get("index", -1)

        # After a question: add thinking time (300-800ms)
        if prev_text.rstrip().endswith("?"):
            base_gap += random.randint(300, 800)

        # After a short acknowledgment (<30 chars): shorter gap
        elif len(prev_text) < 30:
            base_gap = max(gap_min, base_gap - random.randint(50, 150))

        # Post-interruption recovery: the interrupted person needs extra time
        # to process what happened (400-800ms extra)
        if prev_index in interrupted_turn_indices:
            base_gap += random.randint(400, 800)

        # Pre-allocate space for thinking backchannels that will be placed
        # in the gap AFTER this turn. The thinking sound fills part of this gap,
        # giving the listener time to process before their next main turn.
        if prev_index in thinking_bc_durations:
            base_gap += thinking_bc_durations[prev_index] + random.randint(100, 250)

        return base_gap

    @staticmethod
    async def apply(lambda_node_dict: dict, state: dict):
        synthesized_turns = state.get("synthesized_turns", [])
        synthesized_backchannels = state.get("synthesized_backchannels", [])
        overlap_style = state.get("overlap_style", "natural")

        logging.info(f"CalculateTimeline: Processing {len(synthesized_turns)} turns, overlap_style={overlap_style}")

        if not synthesized_turns:
            state["timeline_turns"] = []
            state["timeline_backchannels"] = []
            state["total_duration_ms"] = 0
            return state

        # Gap between turns based on overlap style
        gap_config = {
            "minimal": (200, 400),    # Clean turn-taking
            "moderate": (100, 200),   # Some overlap at boundaries
            "natural": (50, 150),     # Slight overlap common
            "heavy": (-100, 50)       # Frequent overlap (negative = overlap)
        }
        gap_min, gap_max = gap_config.get(overlap_style, (100, 200))

        # --- Pre-scan backchannels to inform turn placement ---
        # We need to know about interruptions and thinking sounds BEFORE placing
        # turns so that gaps are correctly sized.

        # Which turns will be interrupted?
        interrupted_turn_indices = set()
        for bc in synthesized_backchannels:
            if bc.get("type") == "interruption":
                interrupted_turn_indices.add(bc["during_turn_index"])

        # Which turns have a thinking backchannel after them? (turn_index -> duration)
        thinking_bc_durations = {}
        for bc in synthesized_backchannels:
            if bc.get("type") == "thinking":
                thinking_bc_durations[bc["during_turn_index"]] = bc["duration_ms"]

        # --- Place main turns sequentially with contextual gaps ---
        timeline_turns = []
        current_time_ms = 0

        for i, turn in enumerate(synthesized_turns):
            duration_ms = turn["duration_ms"]

            logging.info(f"CalculateTimeline: Processing turn {i}, duration_ms={duration_ms}, current_time_ms={current_time_ms}")

            # Add contextual gap from previous turn
            if i > 0:
                prev_turn = synthesized_turns[i - 1]
                gap = CalculateTimeline._calculate_contextual_gap(
                    prev_turn, gap_min, gap_max,
                    interrupted_turn_indices, thinking_bc_durations,
                )
                current_time_ms += gap
                # Ensure we don't go negative
                current_time_ms = max(0, current_time_ms)

            start_ms = current_time_ms
            end_ms = start_ms + duration_ms

            logging.info(f"CalculateTimeline: Turn {i} placed at {start_ms}-{end_ms}ms")

            timeline_turns.append({
                "index": turn["index"],
                "role": turn["role"],
                "text": turn["text"],
                "audio": turn["audio"],
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": duration_ms,
                "is_backchannel": False,
                "has_pauses": turn.get("has_pauses", False),
            })

            current_time_ms = end_ms

        # --- Place backchannels on the timeline ---
        #
        # IMPORTANT: All backchannels go on the USER audio stem. If two overlap
        # it sounds like a third speaker. We prevent this by:
        #   1) Sorting by priority (interruptions > thinking > short > extended)
        #   2) Skipping any backchannel that would overlap an already-placed one
        #
        # Placement rules by type:
        #   - backchannel_short: DURING the host turn, must fit within it
        #   - backchannel_extended: DURING the host turn, may extend slightly past
        #   - thinking: AFTER the host turn ends (user processes before responding)
        #   - interruption: DURING the host turn, cuts the assistant off

        timeline_backchannels = []
        timeline_reactions = []
        interruption_cutoffs = {}  # turn_index -> cutoff_time_ms

        # Priority: interruptions first (they cut turns), thinking second
        # (they need the pre-allocated gap), then the rest.
        _TYPE_PRIORITY = {"interruption": 0, "thinking": 1, "backchannel_short": 2, "backchannel_extended": 3}
        sorted_backchannels = sorted(
            synthesized_backchannels,
            key=lambda b: _TYPE_PRIORITY.get(b.get("type", "backchannel_short"), 9),
        )

        # Track occupied time ranges on the user stem
        placed_user_ranges = []  # type: list[tuple[int, int]]

        def _overlaps_placed(start, end):
            """Check if a time range overlaps with any already-placed user backchannel."""
            for p_start, p_end in placed_user_ranges:
                if start < p_end and end > p_start:
                    return True
            return False

        for bc in sorted_backchannels:
            turn_idx = bc["during_turn_index"]
            position = bc["position_in_turn"]
            bc_duration = bc["duration_ms"]
            bc_type = bc.get("type", "backchannel_short")
            reaction_audio = bc.get("reaction_audio")
            reaction_duration = bc.get("reaction_duration_ms", 0)

            # Find the assistant turn this backchannel is associated with
            target_turn = None
            for t in timeline_turns:
                if t["index"] == turn_idx:
                    target_turn = t
                    break

            if target_turn is None:
                continue

            # Only allow during assistant turns
            if target_turn["role"] != "assistant":
                logging.warning(f"Skipping backchannel during non-assistant turn {turn_idx}")
                continue

            turn_start = target_turn["start_ms"]
            turn_end = target_turn["end_ms"]
            turn_duration = turn_end - turn_start

            # --- Thinking backchannels: place AFTER the host turn ends ---
            # The user must hear the full statement/question before they can
            # start processing. "hmm let me see" belongs in the gap between
            # being asked and answering, not mid-question.
            if bc_type == "thinking":
                bc_start = turn_end + random.randint(50, 200)
                bc_end = bc_start + bc_duration

                # Verify it doesn't collide with the next user turn on the same stem
                if _overlaps_placed(bc_start, bc_end):
                    logging.info(
                        f"Skipping overlapping thinking '{bc['text']}' "
                        f"at {bc_start}-{bc_end}ms after turn {turn_idx}"
                    )
                    continue

                # Also make sure it doesn't run into the next main user turn
                next_user_start = None
                for t in timeline_turns:
                    if t["start_ms"] > turn_end and t["role"] == "user":
                        next_user_start = t["start_ms"]
                        break
                if next_user_start is not None and bc_end > next_user_start - 50:
                    logging.info(
                        f"Skipping thinking '{bc['text']}' — would collide with "
                        f"next user turn at {next_user_start}ms"
                    )
                    continue

                placed_user_ranges.append((bc_start, bc_end))
                timeline_backchannels.append({
                    "text": bc["text"],
                    "role": bc["role"],
                    "audio": bc["audio"],
                    "start_ms": bc_start,
                    "end_ms": bc_end,
                    "duration_ms": bc_duration,
                    "is_backchannel": True,
                    "type": bc_type,
                    "during_turn_index": turn_idx,
                })
                logging.info(
                    f"Thinking '{bc['text']}' placed at {bc_start}-{bc_end}ms "
                    f"(after turn {turn_idx} which ends at {turn_end}ms)"
                )
                continue

            # --- All other types: place DURING the host turn ---

            # Extended backchannels ("yeah, yeah, I see what you mean") are
            # substantive reactions — the listener must have heard enough of the
            # speaker's point before producing one. Force them to late position
            # (70%+) regardless of what the LLM suggested.
            if bc_type == "backchannel_extended":
                offset_ratio = random.uniform(0.70, 0.88)
            elif position == "early":
                offset_ratio = random.uniform(0.15, 0.30)
            elif position == "late":
                offset_ratio = random.uniform(0.70, 0.85)
            else:  # middle
                offset_ratio = random.uniform(0.35, 0.65)

            # Substantive short backchannels (>15 chars, e.g. "yeah, yeah, I got it")
            # imply comprehension — the listener must have heard enough context.
            # Force them to at least 40% through the host turn. True minimal
            # backchannels ("mm-hm", "uh-huh", "yeah") are short enough to be
            # reflexive and can appear early.
            bc_text = bc.get("text", "")
            if bc_type == "backchannel_short" and len(bc_text) > 15:
                min_offset = 0.40 + random.uniform(0, 0.15)
                if offset_ratio < min_offset:
                    logging.info(
                        f"Bumping substantive backchannel_short '{bc_text}' "
                        f"from {offset_ratio:.0%} to {min_offset:.0%}"
                    )
                    offset_ratio = min_offset

            bc_start = turn_start + int(turn_duration * offset_ratio)

            # Extended backchannels may extend slightly beyond the turn boundary
            if bc_type == "backchannel_extended":
                bc_start = max(bc_start, turn_start + 150)
            else:
                # Short backchannels and interruptions must fit within the turn
                bc_start = min(bc_start, turn_end - bc_duration - 100)
                bc_start = max(bc_start, turn_start + 150)

            bc_end = bc_start + bc_duration

            # Skip if this would overlap with an already-placed user backchannel
            if _overlaps_placed(bc_start, bc_end):
                logging.info(
                    f"Skipping overlapping backchannel '{bc['text']}' ({bc_type}) "
                    f"at {bc_start}-{bc_end}ms during turn {turn_idx}"
                )
                continue

            placed_user_ranges.append((bc_start, bc_end))

            timeline_backchannels.append({
                "text": bc["text"],
                "role": bc["role"],
                "audio": bc["audio"],
                "start_ms": bc_start,
                "end_ms": bc_end,
                "duration_ms": bc_duration,
                "is_backchannel": True,
                "type": bc_type,
                "during_turn_index": turn_idx,
            })

            # If it's an interruption, the assistant stops shortly after
            if bc_type == "interruption":
                cutoff_time = bc_start + random.randint(200, 400)
                if turn_idx not in interruption_cutoffs or cutoff_time < interruption_cutoffs[turn_idx]:
                    interruption_cutoffs[turn_idx] = cutoff_time
                    logging.info(f"Interruption at turn {turn_idx}: assistant cut off at {cutoff_time}ms")

                # Place the assistant's reaction after the user's interruption
                if reaction_audio and reaction_duration > 0:
                    reaction_start = bc_end - random.randint(50, 150)
                    reaction_end = reaction_start + reaction_duration

                    timeline_reactions.append({
                        "text": bc.get("assistant_reaction", ""),
                        "role": "assistant",
                        "audio": reaction_audio,
                        "start_ms": reaction_start,
                        "end_ms": reaction_end,
                        "duration_ms": reaction_duration,
                        "is_reaction": True,
                        "to_interruption_at": turn_idx,
                    })
                    logging.info(f"Assistant reaction at {reaction_start}ms: '{bc.get('assistant_reaction', '')}'")

        # Store reactions separately for rendering
        state["timeline_reactions"] = timeline_reactions

        # Apply interruption cutoffs to assistant turns
        for turn in timeline_turns:
            if turn["index"] in interruption_cutoffs:
                cutoff = interruption_cutoffs[turn["index"]]
                if cutoff < turn["end_ms"]:
                    original_end = turn["end_ms"]
                    turn["end_ms"] = cutoff
                    turn["interrupted"] = True
                    logging.info(f"Turn {turn['index']} cut short from {original_end}ms to {cutoff}ms")

        # --- Compact post-interruption dead air ---
        #
        # When an interruption cuts a turn short (e.g., 9000ms → 5000ms), the
        # space freed up (4000ms) was originally occupied by the assistant's full
        # utterance. The interruption BC + reaction fill some of it, but the gap
        # between the last audible event and the next main turn can still be
        # excessively long. We compact by shifting subsequent turns earlier.
        #
        # Max allowed gap from the last audible event in the interruption
        # sequence to the next main turn:
        MAX_POST_INTERRUPTION_GAP_MS = 1200

        for i, turn in enumerate(timeline_turns):
            if not turn.get("interrupted"):
                continue

            cutoff_ms = turn["end_ms"]

            # Find the last audible event in this interruption's sequence
            # (the interruption BC, the reaction, or the cutoff itself)
            last_event_end = cutoff_ms
            for bc in timeline_backchannels:
                if bc.get("during_turn_index") == turn["index"]:
                    last_event_end = max(last_event_end, bc["end_ms"])
            for rx in timeline_reactions:
                if rx.get("to_interruption_at") == turn["index"]:
                    last_event_end = max(last_event_end, rx["end_ms"])

            # Find the next main turn
            next_turn = None
            for t in timeline_turns:
                if t["start_ms"] > turn["start_ms"] and t is not turn:
                    next_turn = t
                    break

            if next_turn is None:
                continue

            effective_gap = next_turn["start_ms"] - last_event_end
            if effective_gap <= MAX_POST_INTERRUPTION_GAP_MS:
                continue

            # Shift everything from the next turn onward
            shift = effective_gap - random.randint(600, MAX_POST_INTERRUPTION_GAP_MS)
            if shift <= 0:
                continue

            logging.info(
                f"Post-interruption compaction: gap was {effective_gap}ms "
                f"after turn {turn['index']}, shifting subsequent events "
                f"by -{shift}ms"
            )

            # Shift all subsequent main turns
            for t in timeline_turns:
                if t["start_ms"] >= next_turn["start_ms"]:
                    t["start_ms"] -= shift
                    t["end_ms"] -= shift

            # Shift all subsequent backchannels
            for bc in timeline_backchannels:
                if bc["start_ms"] >= next_turn["start_ms"] + shift:
                    bc["start_ms"] -= shift
                    bc["end_ms"] -= shift

            # Shift all subsequent reactions
            for rx in timeline_reactions:
                if rx["start_ms"] >= next_turn["start_ms"] + shift:
                    rx["start_ms"] -= shift
                    rx["end_ms"] -= shift

            # Also update placed_user_ranges for any downstream checks
            # (not critical since we're past the placement phase)

        # --- Prevent main turns from overlapping with preceding reactions ---
        #
        # After placing interruption BCs and assistant reactions, a main turn
        # that was originally sequenced right after the interrupted turn may now
        # start BEFORE the reaction ends. This causes two speakers to talk at
        # full volume simultaneously — producing unintelligible audio. We sweep
        # through all main turns and push any that overlap with a preceding
        # reaction so they start cleanly after it.
        for turn in timeline_turns:
            for rx in timeline_reactions:
                # Only consider reactions that end after this turn starts
                # and started before this turn (i.e., a preceding reaction)
                if rx["end_ms"] > turn["start_ms"] and rx["start_ms"] < turn["start_ms"]:
                    gap_needed = random.randint(100, 300)
                    shift = rx["end_ms"] - turn["start_ms"] + gap_needed
                    logging.info(
                        f"Main turn {turn['index']} at {turn['start_ms']}ms overlaps "
                        f"reaction ending at {rx['end_ms']}ms — shifting by +{shift}ms"
                    )
                    # Shift this turn and all subsequent turns/BCs/reactions
                    threshold = turn["start_ms"]
                    for t in timeline_turns:
                        if t["start_ms"] >= threshold:
                            t["start_ms"] += shift
                            t["end_ms"] += shift
                    for bc in timeline_backchannels:
                        if bc["start_ms"] >= threshold:
                            bc["start_ms"] += shift
                            bc["end_ms"] += shift
                    for r in timeline_reactions:
                        if r is not rx and r["start_ms"] >= threshold:
                            r["start_ms"] += shift
                            r["end_ms"] += shift
                    break  # re-check this turn against other reactions after shift

        total_duration_ms = max(t["end_ms"] for t in timeline_turns) + 500 if timeline_turns else 0

        # Also account for any backchannels that might extend past
        if timeline_backchannels:
            max_bc_end = max(bc["end_ms"] for bc in timeline_backchannels)
            total_duration_ms = max(total_duration_ms, max_bc_end + 200)

        # Also account for reactions
        if timeline_reactions:
            max_reaction_end = max(r["end_ms"] for r in timeline_reactions)
            total_duration_ms = max(total_duration_ms, max_reaction_end + 200)

        state["timeline_turns"] = timeline_turns
        state["timeline_backchannels"] = timeline_backchannels
        state["total_duration_ms"] = total_duration_ms

        # Build time_anchored_spans for output (without audio)
        time_anchored_spans = []
        for t in timeline_turns:
            span_entry = {
                "speaker": t["role"],
                "text": t["text"],
                "start_ms": t["start_ms"],
                "end_ms": t["end_ms"],
                "is_backchannel": False,
                "has_pauses": t.get("has_pauses", False),
            }
            if t.get("interrupted"):
                span_entry["interrupted"] = True
            time_anchored_spans.append(span_entry)

        for bc in timeline_backchannels:
            time_anchored_spans.append({
                "speaker": bc["role"],
                "text": bc["text"],
                "start_ms": bc["start_ms"],
                "end_ms": bc["end_ms"],
                "is_backchannel": True,
                "type": bc.get("type", "backchannel_short"),
            })

        for r in timeline_reactions:
            time_anchored_spans.append({
                "speaker": r["role"],
                "text": r["text"],
                "start_ms": r["start_ms"],
                "end_ms": r["end_ms"],
                "is_backchannel": False,
                "is_reaction": True,
            })

        time_anchored_spans.sort(key=lambda x: x["start_ms"])
        state["time_anchored_spans"] = time_anchored_spans

        logging.info(f"CalculateTimeline: Created timeline with total_duration_ms={total_duration_ms}")
        logging.info(f"CalculateTimeline: {len(timeline_backchannels)} backchannels, {len(timeline_reactions)} reactions")

        return state


class RenderDuplexAudio:
    """
    Step 3: Render per-speaker stems and mix into duplex audio.

    - User stem: All user turns + user backchannels
    - Assistant stem: All assistant turns + assistant backchannels
    - Mixed: Both stems combined
    """

    @staticmethod
    async def apply(lambda_node_dict: dict, state: dict):
        timeline_turns = state.get("timeline_turns", [])
        timeline_backchannels = state.get("timeline_backchannels", [])
        timeline_reactions = state.get("timeline_reactions", [])
        total_duration_ms = state.get("total_duration_ms", 0)

        logging.info(f"RenderDuplexAudio: Starting with {len(timeline_turns)} turns, {len(timeline_backchannels)} backchannels, {len(timeline_reactions)} reactions")

        if not timeline_turns or total_duration_ms <= 0:
            state["user_stem_audio"] = None
            state["assistant_stem_audio"] = None
            state["duplex_mixed_audio"] = None
            return state

        # Separate by speaker, handling interruptions
        user_clips = []
        assistant_clips = []

        for turn in timeline_turns:
            audio = turn["audio"]

            # If turn was interrupted, truncate the audio
            if turn.get("interrupted", False):
                original_duration = turn.get("duration_ms", 0)
                new_end = turn["end_ms"]
                new_start = turn["start_ms"]
                new_duration = new_end - new_start

                if new_duration < original_duration and new_duration > 0:
                    audio, was_truncated = _truncate_audio(audio, new_duration)
                    if was_truncated:
                        logging.info(f"Truncated interrupted turn from {original_duration}ms to {new_duration}ms")
                    else:
                        logging.warning(f"Could not truncate turn (target={new_duration}ms), using original")

            clip = (turn["start_ms"], audio)
            if turn["role"] == "user":
                user_clips.append(clip)
            else:
                assistant_clips.append(clip)

        # --- RMS-aware volume normalization for backchannels & reactions ---
        #
        # TTS produces wildly different volumes for short vs long utterances.
        # Instead of applying a flat gain (which makes quiet clips inaudible),
        # we normalize each clip's RMS relative to the average main-turn RMS
        # for the same speaker, then scale to the desired type-specific level.
        #
        # Formula: needed_gain = (avg_main_rms * type_gain) / clip_rms

        # Compute reference RMS from main turns per speaker
        user_main_rms_values = []
        asst_main_rms_values = []
        for turn in timeline_turns:
            rms = _compute_wav_rms(turn["audio"])
            if rms > 0:
                if turn["role"] == "user":
                    user_main_rms_values.append(rms)
                else:
                    asst_main_rms_values.append(rms)

        user_avg_rms = (
            sum(user_main_rms_values) / len(user_main_rms_values)
            if user_main_rms_values else 2000.0
        )
        asst_avg_rms = (
            sum(asst_main_rms_values) / len(asst_main_rms_values)
            if asst_main_rms_values else 2000.0
        )
        logging.info(
            f"RenderDuplexAudio: Reference RMS — user_avg={user_avg_rms:.0f}, "
            f"asst_avg={asst_avg_rms:.0f}"
        )

        # All backchannels are from the user (user talks over assistant).
        # Normalize each clip's volume relative to the user's main-turn RMS.
        for bc in timeline_backchannels:
            bc_type = bc.get("type", "backchannel_short")
            type_gain = _BC_GAIN.get(bc_type, 0.45)
            target_rms = user_avg_rms * type_gain

            clip_rms = _compute_wav_rms(bc["audio"])
            if clip_rms > 10:  # avoid division by near-zero
                needed_gain = target_rms / clip_rms
                # Tiered max gain: very quiet clips (near-silent TTS) get
                # higher amplification allowance since they need more boost.
                # Normal clips are capped lower to avoid noise.
                if clip_rms < 100:
                    max_gain = 20.0  # near-silent TTS output, need heavy boost
                elif clip_rms < 500:
                    max_gain = 8.0   # quiet but has some signal
                else:
                    max_gain = 4.0   # normal range, gentle adjustment
                needed_gain = max(0.05, min(needed_gain, max_gain))
            else:
                # Clip is essentially silent — amplify heavily
                needed_gain = 20.0
                logging.warning(
                    f"Backchannel '{bc['text']}' has near-zero RMS ({clip_rms:.1f}), "
                    f"applying max amplification"
                )

            attenuated = _attenuate_audio(bc["audio"], needed_gain)
            clip = (bc["start_ms"], attenuated)
            user_clips.append(clip)
            logging.info(
                f"Backchannel '{bc['text']}' ({bc_type}): "
                f"clip_rms={clip_rms:.0f}, target_rms={target_rms:.0f}, "
                f"gain={needed_gain:.2f}"
            )

        # Assistant reactions — normalize relative to assistant main-turn RMS.
        for reaction in timeline_reactions:
            target_rms = asst_avg_rms * _REACTION_GAIN

            clip_rms = _compute_wav_rms(reaction["audio"])
            if clip_rms > 10:
                needed_gain = target_rms / clip_rms
                if clip_rms < 100:
                    max_gain = 20.0
                elif clip_rms < 500:
                    max_gain = 8.0
                else:
                    max_gain = 4.0
                needed_gain = max(0.05, min(needed_gain, max_gain))
            else:
                needed_gain = 20.0

            attenuated = _attenuate_audio(reaction["audio"], needed_gain)
            clip = (reaction["start_ms"], attenuated)
            assistant_clips.append(clip)
            logging.info(
                f"Assistant reaction at {reaction['start_ms']}ms: "
                f"clip_rms={clip_rms:.0f}, target_rms={target_rms:.0f}, "
                f"gain={needed_gain:.2f}"
            )

        sample_rate = 24000

        # Render stems
        if user_clips:
            user_stem = _place_audio_on_timeline(user_clips, total_duration_ms, sample_rate)
        else:
            user_stem = _create_silent_wav(total_duration_ms, sample_rate)

        if assistant_clips:
            assistant_stem = _place_audio_on_timeline(assistant_clips, total_duration_ms, sample_rate)
        else:
            assistant_stem = _create_silent_wav(total_duration_ms, sample_rate)

        # Mix stems
        duplex_audio = _mix_stems_to_duplex(user_stem, assistant_stem)

        # Store as data URLs
        state["user_stem_audio"] = audio_utils.get_audio_url(user_stem, mime="audio/wav")
        state["assistant_stem_audio"] = audio_utils.get_audio_url(assistant_stem, mime="audio/wav")
        state["duplex_mixed_audio"] = audio_utils.get_audio_url(duplex_audio, mime="audio/wav")

        logging.info(f"RenderDuplexAudio: Created stems and mixed audio, total_duration_ms={total_duration_ms}")
        logging.info(f"RenderDuplexAudio: user_stem has {len(user_clips)} clips (incl backchannels), assistant_stem has {len(assistant_clips)} clips (incl reactions)")

        return state


# ============== Output Generator ==============


class DuplexAudioOutputGenerator(BaseOutputGenerator):
    """Generates output with duplex audio, stems, and metadata."""

    @staticmethod
    def build_conversation_turns(data: Any, state: SygraState) -> list[dict]:
        """Build conversation turns from original input."""
        conversation = state.get("conversation", [])
        if isinstance(conversation, list):
            return conversation
        return []

    @staticmethod
    def build_time_anchored_spans(data: Any, state: SygraState) -> list[dict]:
        """Build time-anchored spans (without audio data)."""
        spans = state.get("time_anchored_spans", [])
        result = []
        for s in spans:
            entry = {
                "speaker": s.get("speaker"),
                "text": s.get("text"),
                "start_ms": s.get("start_ms"),
                "end_ms": s.get("end_ms"),
                "is_backchannel": s.get("is_backchannel", False),
            }
            if s.get("type"):
                entry["type"] = s["type"]
            if s.get("interrupted"):
                entry["interrupted"] = True
            if s.get("is_reaction"):
                entry["is_reaction"] = True
            if s.get("has_pauses"):
                entry["has_pauses"] = True
            result.append(entry)
        return result

    @staticmethod
    def build_duplex_metadata(data: Any, state: SygraState) -> dict:
        """Build metadata about the duplex audio generation."""
        return {
            "overlap_style": state.get("overlap_style", "natural"),
            "speaking_rate": state.get("speaking_rate", "normal"),
            "backchannel_frequency": state.get("backchannel_frequency", "occasional"),
            "thinking_frequency": state.get("thinking_frequency", "occasional"),
            "user_voice": state.get("user_voice", "alloy"),
            "assistant_voice": state.get("assistant_voice", "nova"),
            "total_duration_ms": state.get("total_duration_ms", 0),
            "num_turns": len(state.get("timeline_turns", [])),
            "num_backchannels": len(state.get("timeline_backchannels", [])),
            "num_reactions": len(state.get("timeline_reactions", [])),
        }
