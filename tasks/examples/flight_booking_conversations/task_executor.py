import json
import io
import random
import re
import wave
from typing import Any

from sygra.core.base_task_executor import DefaultTaskExecutor
from sygra.core.graph.functions.lambda_function import LambdaFunction
from sygra.core.graph.sygra_state import SygraState
from sygra.core.models.client.client_factory import ClientFactory
from sygra.core.models.client.openai_azure_client import OpenAIAzureClient
from sygra.core.models.client.openai_client import OpenAIClient
from sygra.processors.output_record_generator import BaseOutputGenerator
from sygra.utils import audio_utils
from sygra.utils import utils

_SCENARIOS_CACHE: list[dict[str, Any]] | None = None
_TTS_CLIENT: OpenAIClient | OpenAIAzureClient | None = None
_TTS_MODEL_NAME: str | None = None


def _load_scenarios(task_name: str) -> list[dict[str, Any]]:
    global _SCENARIOS_CACHE
    if _SCENARIOS_CACHE is not None:
        return _SCENARIOS_CACHE

    path = utils.get_file_in_task_dir(task_name, "scenarios.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("scenarios.json must be a JSON array")

    _SCENARIOS_CACHE = data
    return data


def _stable_rng(state: SygraState) -> random.Random:
    sid = str(state.get("id", ""))
    seed = 0
    for ch in sid:
        seed = (seed * 131 + ord(ch)) % (2**32)
    return random.Random(seed)


def _get_conversation_turns(state: SygraState) -> list[dict[str, str]]:
    raw = state.get("raw_conversation", "")
    parsed = _extract_json(str(raw))

    conversation = parsed.get("conversation") if isinstance(parsed, dict) else parsed
    if not isinstance(conversation, list):
        return []

    normalized: list[dict[str, str]] = []
    for turn in conversation:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        content = turn.get("content")
        if isinstance(role, str) and isinstance(content, str):
            normalized.append({"role": role, "content": content})
            continue

        if len(turn.keys()) == 1:
            k = next(iter(turn))
            v = turn[k]
            if isinstance(k, str) and isinstance(v, str) and k in {"user", "assistant"}:
                normalized.append({"role": k, "content": v})

    return normalized


def _get_tts_config() -> dict[str, Any]:
    model_configs = utils.load_model_config()
    cfg = model_configs.get("tts_openai")
    if not isinstance(cfg, dict):
        raise ValueError("Model 'tts_openai' is not configured. Add it to sygra/config/models.yaml")
    return cfg


async def _get_tts_client() -> tuple[OpenAIClient | OpenAIAzureClient, str]:
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


def _concat_wav_segments(wav_segments: list[bytes], pause_ms: int = 120) -> bytes:
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


class SynthesizeConversationAudio:
    @staticmethod
    async def apply(lambda_node_dict: dict, state: SygraState):
        turns = _get_conversation_turns(state)
        if not turns:
            state["conversation_audio"] = None
            return state

        user_voice = str(state.get("user_voice") or lambda_node_dict.get("user_voice", "nova"))
        assistant_voice = str(
            state.get("assistant_voice") or lambda_node_dict.get("assistant_voice", "alloy")
        )
        if user_voice == assistant_voice:
            assistant_voice = "alloy" if user_voice != "alloy" else "nova"

        client, model_name = await _get_tts_client()

        wav_segments: list[bytes] = []
        for t in turns:
            role = str(t.get("role", ""))
            content = str(t.get("content", "")).strip()
            if not content:
                continue

            voice = user_voice if role == "user" else assistant_voice
            for chunk in _chunk_text_for_tts(content):
                audio_resp = await client.create_speech(
                    model=model_name,
                    input=chunk,
                    voice=voice,
                    response_format="wav",
                    speed=1.0,
                )
                wav_segments.append(bytes(audio_resp.content))

        combined = _concat_wav_segments(wav_segments)
        state["conversation_audio"] = audio_utils.get_audio_url(combined, mime="audio/wav")
        state["user_voice"] = user_voice
        state["assistant_voice"] = assistant_voice
        return state


class PickScenario(LambdaFunction):
    @staticmethod
    def apply(lambda_node_dict: dict, state: SygraState):
        task_name = utils.current_task or ""
        scenarios = _load_scenarios(task_name)

        weights = []
        for s in scenarios:
            w = s.get("weight", 1)
            weights.append(int(w) if isinstance(w, (int, float, str)) else 1)

        rng = _stable_rng(state)
        chosen = rng.choices(population=scenarios, weights=weights, k=1)[0]

        state["scenario_id"] = chosen.get("scenario_id", "")
        state["scenario_name"] = chosen.get("name", "")
        state["scenario_description"] = chosen.get("description", "")
        state["scenario_goal"] = chosen.get("goal") or ""
        state["scenario_outcome"] = chosen.get("outcome") or "success"
        state["failure_reason"] = chosen.get("failure_reason") or ""
        state["coverage_tags"] = chosen.get("coverage_tags", [])
        state["category"] = chosen.get("category") or "Travel"
        state["subcategory"] = chosen.get("subcategory") or "Flight booking"
        return state


class ValidateConversationResolution:
    @staticmethod
    def apply(lambda_node_dict: dict, state: SygraState):
        turns = _get_conversation_turns(state)
        state["conversation_complete"] = False
        state["completion_notes"] = "missing_or_invalid_conversation"
        if not turns:
            return state

        # Expect strict alternation starting with user and ending with assistant
        if turns[0].get("role") != "user":
            state["completion_notes"] = "does_not_start_with_user"
            return state
        if turns[-1].get("role") != "assistant":
            state["completion_notes"] = "does_not_end_with_assistant"
            return state

        for i in range(1, len(turns)):
            if turns[i].get("role") == turns[i - 1].get("role"):
                state["completion_notes"] = "roles_not_alternating"
                return state

        outcome = str(state.get("scenario_outcome", "success") or "success").lower()
        wrapup_style = str(state.get("wrapup_style") or "none").lower()

        # If wrapup is enabled, resolution should occur before the last 3 messages.
        max_resolution_idx = len(turns) - 4 if wrapup_style != "none" and len(turns) >= 4 else len(turns) - 1

        def _is_success_resolution(text: str) -> bool:
            has_confirm = any(
                k in text
                for k in [
                    "confirmation",
                    "booked",
                    "booking confirmed",
                    "ticket issued",
                    "pnr",
                    "record locator",
                ]
            )
            has_next = any(k in text for k in ["next", "email", "receipt", "e-ticket", "check-in", "itinerary"])
            return has_confirm and has_next

        def _is_failure_resolution(text: str) -> bool:
            has_fail = any(
                k in text
                for k in [
                    "unable",
                    "can't",
                    "cannot",
                    "no flights",
                    "not available",
                    "unavailable",
                    "declined",
                    "failed",
                ]
            )
            has_alt = any(
                k in text
                for k in [
                    "alternative",
                    "alternatives",
                    "options",
                    "instead",
                    "recommend",
                    "try",
                    "flexible",
                    "different date",
                    "nearby",
                ]
            )
            return has_fail and has_alt

        resolution_found = False
        for idx, t in enumerate(turns[: max_resolution_idx + 1]):
            if t.get("role") != "assistant":
                continue
            text = str(t.get("content", "")).lower()
            if outcome == "success" and _is_success_resolution(text):
                resolution_found = True
                break
            if outcome != "success" and _is_failure_resolution(text):
                resolution_found = True
                break

        if not resolution_found:
            state["completion_notes"] = (
                "success_resolution_not_detected" if outcome == "success" else "failure_resolution_not_detected"
            )
            return state

        # Optional: validate wrap-up pattern if enabled
        if wrapup_style != "none" and len(turns) >= 2:
            ask_idx = len(turns) - 2
            ask_text = str(turns[ask_idx].get("content", "")).lower() if ask_idx >= 0 else ""
            if "anything else" not in ask_text and "help" not in ask_text:
                state["completion_notes"] = "resolution_detected_but_wrapup_prompt_missing"
                state["conversation_complete"] = True
                return state

        state["conversation_complete"] = True
        state["completion_notes"] = (
            "success_resolution_detected" if outcome == "success" else "failure_resolution_detected"
        )
        return state


def _extract_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        pass

    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    list_match = re.search(r"\[[\s\S]*\]", text)
    if list_match:
        return json.loads(list_match.group(0))

    obj_match = re.search(r"\{[\s\S]*\}", text)
    if obj_match:
        return json.loads(obj_match.group(0))

    raise ValueError("No JSON found in model output")


class FlightBookingOutputGenerator(BaseOutputGenerator):
    @staticmethod
    def build_conversation(data: Any, state: SygraState) -> list[dict[str, str]]:
        parsed = _extract_json(str(data))

        conversation = parsed.get("conversation") if isinstance(parsed, dict) else parsed
        if not isinstance(conversation, list):
            return []

        normalized: list[dict[str, str]] = []
        for turn in conversation:
            if not isinstance(turn, dict):
                continue
            role = turn.get("role")
            content = turn.get("content")
            if isinstance(role, str) and isinstance(content, str):
                normalized.append({"role": role, "content": content})
                continue

            if len(turn.keys()) == 1:
                k = next(iter(turn))
                v = turn[k]
                if isinstance(k, str) and isinstance(v, str):
                    if k in {"user", "assistant"}:
                        normalized.append({"role": k, "content": v})

        return normalized

    @staticmethod
    def build_taxonomy(data: Any, state: SygraState) -> list[dict[str, Any]]:
        return [
            {
                "category": state.get("category"),
                "subcategory": state.get("subcategory"),
                "scenario_id": state.get("scenario_id"),
                "scenario_name": state.get("scenario_name"),
                "scenario_goal": state.get("scenario_goal"),
                "scenario_outcome": state.get("scenario_outcome"),
                "failure_reason": state.get("failure_reason"),
                "wrapup_style": state.get("wrapup_style"),
                "coverage_tags": state.get("coverage_tags"),
            }
        ]

    @staticmethod
    def build_metadata(data: Any, state: SygraState) -> dict[str, Any]:
        return {
            "scenario_id": state.get("scenario_id"),
            "scenario_goal": state.get("scenario_goal"),
            "scenario_outcome": state.get("scenario_outcome"),
            "failure_reason": state.get("failure_reason"),
            "conversation_complete": state.get("conversation_complete"),
            "completion_notes": state.get("completion_notes"),
            "num_turns": state.get("num_turns"),
            "user_detail_level": state.get("user_detail_level"),
            "include_upgrade_offer": state.get("include_upgrade_offer"),
            "include_baggage": state.get("include_baggage"),
            "include_seat_meal_prefs": state.get("include_seat_meal_prefs"),
            "tone": state.get("tone"),
            "locale": state.get("locale"),
            "wrapup_style": state.get("wrapup_style"),
            "user_voice": state.get("user_voice"),
            "assistant_voice": state.get("assistant_voice"),
        }


class TaskExecutor(DefaultTaskExecutor):
    def init_dataset(self):
        num_records = int(getattr(self.args, "num_records", 10) or 10)
        return [{"id": f"flight_booking_{i}"} for i in range(num_records)]
