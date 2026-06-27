# Romanian Voice Typing Overlay
# Copyright (C) 2026 DrX-svg
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import re
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - runtime dependency check
    sd = None


class AudioCaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecordingResult:
    wav_path: Path
    duration_seconds: float
    frame_count: int


@dataclass(frozen=True)
class InputDeviceInfo:
    index: int | None
    name: str
    display_name: str
    is_default: bool


@dataclass(frozen=True)
class _MicrophoneCandidate:
    index: int
    name: str
    hostapi_name: str
    is_default: bool
    display_name: str
    identity_text: str
    identity_tokens: tuple[str, ...]


TECHNICAL_DEVICE_SUBSTRINGS = (
    "microsoft sound mapper",
    "primary sound capture driver",
)
SIMPLIFIED_HIDE_SUBSTRINGS = (
    "stereo mix",
    "pc speaker",
    "speaker",
    "speakers",
    "output",
    "monitor",
    "mapper",
    "sound mapper",
    "primary sound capture driver",
    "loopback",
    "virtual",
)
SIMPLIFIED_REQUIRED_KEYWORDS = (
    "microphone",
    "mic",
    "headset",
    "array",
)
SIMPLIFIED_STOPWORDS = {
    "audio",
    "array",
    "device",
    "digital",
    "directsound",
    "for",
    "gamin",
    "gaming",
    "headse",
    "headset",
    "input",
    "ks",
    "microphone",
    "microphones",
    "mme",
    "pnp",
    "technology",
    "usb",
    "wasapi",
    "wdm",
    "windows",
    "wireless",
}
HOSTAPI_PRIORITY = {
    "windows wasapi": 2,
    "wasapi": 2,
    "mme": 1,
    "directsound": 0,
    "windows directsound": 0,
    "windows wdm-ks": -10,
    "wdm-ks": -10,
}


def _get_default_input_device_index() -> int | None:
    if sd is None:
        return None

    try:
        default_device = sd.default.device
    except Exception:  # pragma: no cover - runtime-specific path
        return None

    if isinstance(default_device, (list, tuple)) and default_device:
        input_index = default_device[0]
    else:
        input_index = default_device

    if input_index is None:
        return None

    try:
        input_index = int(input_index)
    except (TypeError, ValueError):
        return None

    return input_index if input_index >= 0 else None


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _readable_device_name(raw_name: str) -> str:
    cleaned = _normalize_whitespace(raw_name)
    cleaned = cleaned.replace("Â®", "")
    cleaned = cleaned.replace("®", "")
    return _normalize_whitespace(cleaned)


def _simplify_vendor_name(name: str) -> str:
    simplified = _readable_device_name(name)
    simplified = re.sub(
        r"Intel\s*Smart\s*Sound\s*Technology(?:\s*for\s*[^)]*)?",
        "Intel Smart Sound",
        simplified,
        flags=re.IGNORECASE,
    )
    simplified = re.sub(
        r"Intel\s*Smart\s*Sound\s*Technology",
        "Intel Smart Sound",
        simplified,
        flags=re.IGNORECASE,
    )
    simplified = re.sub(
        r"\bfor\s+Digital\s+Microphones\b",
        "",
        simplified,
        flags=re.IGNORECASE,
    )
    simplified = re.sub(r"\s+\d+$", "", simplified)
    return _normalize_whitespace(simplified)


def _device_dedupe_key(name: str) -> str:
    return " ".join(_identity_tokens(name))


def build_microphone_match_key(name: str) -> str:
    return _device_dedupe_key(name)


def _is_technical_device(name: str) -> bool:
    lowered = name.casefold()
    return any(part in lowered for part in TECHNICAL_DEVICE_SUBSTRINGS)


def _get_hostapi_name(hostapis, hostapi_index: object) -> str:
    try:
        normalized_index = int(hostapi_index)
    except (TypeError, ValueError):
        return ""

    if normalized_index < 0 or normalized_index >= len(hostapis):
        return ""
    return str(hostapis[normalized_index].get("name") or "")


def _get_hostapi_priority(hostapi_name: str) -> int:
    normalized = hostapi_name.casefold()
    for name_fragment, priority in HOSTAPI_PRIORITY.items():
        if name_fragment in normalized:
            return priority
    return 99


def _is_wdm_ks_hostapi(hostapi_name: str) -> bool:
    normalized = hostapi_name.casefold()
    return "wdm-ks" in normalized


def _advanced_display_name(name: str, hostapi_name: str, index: int, is_default: bool) -> str:
    display_name = _readable_device_name(name)
    if hostapi_name:
        display_name = f"{display_name} - {hostapi_name}"
    display_name = f"{display_name} (#{index})"
    if is_default:
        display_name = f"{display_name} [Default]"
    return display_name


def _simple_display_name(name: str, is_default: bool) -> str:
    display_name = _simplify_vendor_name(name)
    if is_default:
        display_name = f"{display_name} [Default]"
    return display_name


def _is_numbered_microphone_array(name: str) -> bool:
    return bool(re.search(r"\bmicrophone\s+array\s+\d+\b", name.casefold()))


def _is_useful_microphone_name(name: str) -> bool:
    lowered = name.casefold()
    if any(part in lowered for part in SIMPLIFIED_HIDE_SUBSTRINGS):
        return False
    if _is_numbered_microphone_array(name):
        return False
    return any(keyword in lowered for keyword in SIMPLIFIED_REQUIRED_KEYWORDS)


def _is_hidden_in_simplified_mode(name: str, hostapi_name: str) -> bool:
    if _is_technical_device(name):
        return True
    if _is_wdm_ks_hostapi(hostapi_name):
        return True
    return not _is_useful_microphone_name(name)


def _extract_identity_text(name: str) -> str:
    readable_name = _readable_device_name(name)
    match = re.search(r"\(([^)]*)", readable_name)
    if match and match.group(1).strip():
        return _normalize_identity_text(match.group(1))
    return _normalize_identity_text(readable_name)


def _normalize_identity_text(name: str) -> str:
    normalized = _simplify_vendor_name(name)
    normalized = re.sub(
        r"\b(?:windows\s+directsound|windows\s+wasapi|directsound|wasapi|wdm[\s-]*ks|mme)\b",
        " ",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"\(?#\d+\)?", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    return _normalize_whitespace(normalized).casefold()


def _identity_tokens(name: str) -> tuple[str, ...]:
    normalized_identity = _extract_identity_text(name)
    tokens = re.findall(r"[a-z0-9]+", normalized_identity)
    filtered_tokens = [
        token
        for token in tokens
        if token not in SIMPLIFIED_STOPWORDS and len(token) >= 2
    ]
    if filtered_tokens:
        return tuple(filtered_tokens)
    return tuple(token for token in tokens if len(token) >= 2)


def _model_tokens(tokens: tuple[str, ...]) -> set[str]:
    return {
        token
        for token in tokens
        if re.search(r"[a-z]+\d+|\d+[a-z]+", token, flags=re.IGNORECASE)
    }


def _looks_truncated(name: str) -> bool:
    readable_name = _readable_device_name(name)
    lowered = readable_name.casefold()
    if readable_name.count("(") > readable_name.count(")"):
        return True
    return bool(
        re.search(
            r"(gamin|wireles|headse|microphon|technolog|smart)$",
            lowered,
        )
    )


def _candidate_api_priority(hostapi_name: str) -> int:
    normalized = hostapi_name.casefold()
    for fragment, priority in HOSTAPI_PRIORITY.items():
        if fragment in normalized:
            return priority
    return 0


def _build_candidate(
    index: int,
    device: dict,
    hostapis,
    default_input_index: int | None,
) -> _MicrophoneCandidate:
    name = str(device["name"])
    hostapi_name = _get_hostapi_name(hostapis, device.get("hostapi"))
    is_default = default_input_index == index
    return _MicrophoneCandidate(
        index=index,
        name=name,
        hostapi_name=hostapi_name,
        is_default=is_default,
        display_name=_simple_display_name(name, is_default),
        identity_text=_extract_identity_text(name),
        identity_tokens=_identity_tokens(name),
    )


def _candidates_match(
    left: _MicrophoneCandidate,
    right: _MicrophoneCandidate,
) -> bool:
    left_tokens = set(left.identity_tokens)
    right_tokens = set(right.identity_tokens)
    if not left_tokens or not right_tokens:
        return False

    shared_model_tokens = _model_tokens(left.identity_tokens) & _model_tokens(
        right.identity_tokens
    )
    if shared_model_tokens:
        return True

    smaller_tokens, larger_tokens = sorted(
        (left_tokens, right_tokens),
        key=len,
    )
    shared_tokens = left_tokens & right_tokens

    if len(smaller_tokens) >= 2 and smaller_tokens.issubset(larger_tokens):
        return True

    if len(shared_tokens) >= 3:
        return True

    if (
        len(shared_tokens) >= 2
        and (
            left.identity_text.startswith(right.identity_text)
            or right.identity_text.startswith(left.identity_text)
        )
    ):
        return True

    return False


def _choose_group_representative(
    candidates: list[_MicrophoneCandidate],
) -> _MicrophoneCandidate:
    group_has_headset = any("headset" in candidate.name.casefold() for candidate in candidates)

    def sort_key(candidate: _MicrophoneCandidate) -> tuple[int, int, int, int, int]:
        simplified_name = _simple_display_name(candidate.name, False)
        return (
            0 if _looks_truncated(candidate.name) else 1,
            1 if group_has_headset and "headset" in candidate.name.casefold() else 0,
            len(simplified_name),
            _candidate_api_priority(candidate.hostapi_name),
            1 if candidate.is_default else 0,
        )

    return max(candidates, key=sort_key)


def _group_label(candidates: list[_MicrophoneCandidate]) -> str:
    representative = _choose_group_representative(candidates)
    return representative.display_name.replace(" [Default]", "")


def _log_raw_input_devices(
    logger: logging.Logger | None,
    devices: list[tuple[int, dict]],
    hostapis,
    *,
    show_advanced_devices: bool,
) -> None:
    if logger is None:
        return

    logger.info(
        "Microphone discovery. show_advanced_devices=%s raw_input_devices=%s",
        show_advanced_devices,
        len(devices),
    )
    for index, device in devices:
        logger.info(
            "Microphone raw device. index=%s hostapi=%s name=%s max_input_channels=%s",
            index,
            _get_hostapi_name(hostapis, device.get("hostapi")),
            _readable_device_name(str(device["name"])),
            int(device["max_input_channels"]),
        )


def list_input_devices(
    *,
    show_advanced_devices: bool = False,
    selected_device_index: int | None = None,
    logger: logging.Logger | None = None,
) -> list[InputDeviceInfo]:
    if sd is None:
        raise AudioCaptureError(
            "sounddevice is not installed. Install it in the whisper_local environment."
        )

    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    default_input_index = _get_default_input_device_index()
    default_input_name = ""
    if default_input_index is not None and 0 <= default_input_index < len(devices):
        default_input_name = _readable_device_name(str(devices[default_input_index]["name"]))

    default_display_name = "System Default"
    if default_input_name:
        default_display_name = f"System Default - {default_input_name}"

    input_devices = [
        InputDeviceInfo(
            index=None,
            name=default_input_name or "System Default",
            display_name=default_display_name,
            is_default=True,
        )
    ]

    available_devices = []
    for index, device in enumerate(devices):
        if int(device["max_input_channels"]) <= 0:
            continue
        available_devices.append((index, device))

    _log_raw_input_devices(
        logger,
        available_devices,
        hostapis,
        show_advanced_devices=show_advanced_devices,
    )

    if show_advanced_devices:
        for index, device in available_devices:
            name = str(device["name"])
            hostapi_name = _get_hostapi_name(hostapis, device.get("hostapi"))
            is_default = default_input_index == index
            input_devices.append(
                InputDeviceInfo(
                    index=index,
                    name=name,
                    display_name=_advanced_display_name(
                        name,
                        hostapi_name,
                        index,
                        is_default,
                    ),
                    is_default=is_default,
                )
            )
        return input_devices

    candidate_groups: list[list[_MicrophoneCandidate]] = []
    hidden_devices: list[str] = []

    for index, device in available_devices:
        candidate = _build_candidate(index, device, hostapis, default_input_index)
        name = candidate.name
        hostapi_name = candidate.hostapi_name
        if _is_hidden_in_simplified_mode(name, hostapi_name):
            hidden_devices.append(
                f"{_readable_device_name(name)} [{hostapi_name or 'unknown hostapi'}]"
            )
            continue

        matching_group = None
        for group in candidate_groups:
            if any(_candidates_match(candidate, existing_candidate) for existing_candidate in group):
                matching_group = group
                break

        if matching_group is None:
            candidate_groups.append([candidate])
        else:
            matching_group.append(candidate)

    filtered_devices: list[InputDeviceInfo] = []
    for group in candidate_groups:
        representative = _choose_group_representative(group)
        hidden_duplicates = [
            candidate
            for candidate in group
            if candidate.index != representative.index
        ]
        filtered_devices.append(
            InputDeviceInfo(
                index=representative.index,
                name=representative.name,
                display_name=representative.display_name,
                is_default=representative.is_default,
            )
        )
        if logger is not None:
            logger.info(
                "Microphone simplified group. group=%s representative=%s members=%s hidden_duplicates=%s",
                _group_label(group),
                representative.display_name,
                [
                    f"{_readable_device_name(candidate.name)} [{candidate.hostapi_name or 'unknown hostapi'}]"
                    for candidate in group
                ],
                [
                    f"{_readable_device_name(candidate.name)} [{candidate.hostapi_name or 'unknown hostapi'}]"
                    for candidate in hidden_duplicates
                ],
            )

    filtered_devices.sort(
        key=lambda device_info: (
            not device_info.is_default,
            device_info.display_name.casefold(),
            device_info.index if device_info.index is not None else -1,
        )
    )

    if logger is not None and hidden_devices:
        logger.info(
            "Microphone simplified hidden technical devices=%s",
            hidden_devices,
        )

    for device_info in filtered_devices:
        input_devices.append(device_info)

    return input_devices


class ManualAudioRecorder:
    def __init__(
        self,
        sample_rate: int,
        channels: int,
        dtype: str,
        logger: logging.Logger,
        input_device_index: int | None = None,
        input_device_name: str | None = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.logger = logger
        self.input_device_index = input_device_index
        self.input_device_name = input_device_name
        self._stream = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._is_recording = False

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def set_input_device(
        self,
        input_device_index: int | None,
        input_device_name: str | None,
    ) -> None:
        if self._is_recording:
            raise AudioCaptureError("Cannot change microphone while recording.")

        self.input_device_index = input_device_index
        self.input_device_name = input_device_name
        self.logger.info(
            "Input device updated. index=%s name=%s",
            self.input_device_index,
            self.input_device_name or "System Default",
        )

    def start_recording(self) -> None:
        if sd is None:
            raise AudioCaptureError(
                "sounddevice is not installed. Install it in the whisper_local environment."
            )
        if self._is_recording:
            raise AudioCaptureError("Recording is already in progress.")

        self._chunks = []

        try:
            stream_kwargs = {
                "samplerate": self.sample_rate,
                "channels": self.channels,
                "dtype": self.dtype,
                "callback": self._audio_callback,
            }
            if self.input_device_index is not None:
                stream_kwargs["device"] = self.input_device_index

            self._stream = sd.InputStream(
                **stream_kwargs,
            )
            self._stream.start()
        except Exception as exc:  # pragma: no cover - device-specific runtime path
            self._stream = None
            raise AudioCaptureError(f"Could not start microphone capture: {exc}") from exc

        self._is_recording = True
        self.logger.info(
            "Recording started. sample_rate=%s channels=%s dtype=%s input_device_index=%s input_device_name=%s",
            self.sample_rate,
            self.channels,
            self.dtype,
            self.input_device_index,
            self.input_device_name or "System Default",
        )

    def stop_recording(self, output_path: Path) -> RecordingResult:
        if not self._is_recording or self._stream is None:
            raise AudioCaptureError("Recording is not active.")

        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
            self._is_recording = False

        with self._lock:
            chunks = list(self._chunks)
            self._chunks = []

        if not chunks:
            raise AudioCaptureError("No audio was captured.")

        audio = np.concatenate(chunks, axis=0)
        if audio.size == 0:
            raise AudioCaptureError("Captured audio buffer is empty.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_wav(output_path, audio)

        frame_count = int(audio.shape[0])
        duration_seconds = frame_count / float(self.sample_rate)
        self.logger.info(
            "Recording stopped. Saved WAV to %s (%.2fs, %s frames).",
            output_path,
            duration_seconds,
            frame_count,
        )
        return RecordingResult(
            wav_path=output_path,
            duration_seconds=duration_seconds,
            frame_count=frame_count,
        )

    def cleanup(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            self.logger.exception("Error while cleaning up audio stream.")
        finally:
            self._stream = None
            self._is_recording = False

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if status:
            self.logger.warning("Microphone stream status: %s", status)
        with self._lock:
            self._chunks.append(indata.copy())

    def _write_wav(self, output_path: Path, audio: np.ndarray) -> None:
        if self.dtype != "int16":
            raise AudioCaptureError(f"Unsupported dtype for WAV export: {self.dtype}")

        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio.astype(np.int16).tobytes())
