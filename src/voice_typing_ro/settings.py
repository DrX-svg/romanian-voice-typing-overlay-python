# Romanian Voice Typing Overlay
# Copyright (C) 2026 DrX-svg
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import copy
import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.json"
DEFAULT_MODEL_DOWNLOAD_ROOT = r"%LOCALAPPDATA%\RomanianVoiceTyping\models"
DEFAULT_CONFIG_TEMPLATE = {
    "ui": {
        "title": "Romanian Voice Typing Overlay",
        "geometry": "560x500+60+60",
        "always_on_top": True,
    },
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "dtype": "int16",
    },
    "transcription": {
        "model": "Infomaniak-AI/faster-whisper-large-v3-turbo",
        "language": "ro",
        "beam_size": 3,
        "without_timestamps": True,
        "condition_on_previous_text": False,
        "vad_filter": False,
        "device": "cpu",
        "compute_type": "int8",
        "download_root": DEFAULT_MODEL_DOWNLOAD_ROOT,
    },
    "asr_preset": "balanced",
    "hotkey": "f10",
    "hotkey_options": {
        "auto_paste_after_hotkey_transcription": True,
    },
    "paste": {
        "restore_clipboard_after_paste": True,
        "paste_delay_ms": 150,
    },
    "show_advanced_devices": False,
    "window_opacity": 1.0,
    "dark_mode": False,
    "input_device_index": None,
    "input_device_name": None,
    "paths": {
        "logs_dir": "logs",
        "temp_dir": "temp",
    },
}
_UNSET = object()
ASR_PRESET_TO_BEAM_SIZE = {
    "fast": 1,
    "balanced": 3,
    "accurate": 5,
}


def normalize_asr_preset(value: str | None) -> str:
    preset = str(value or "balanced").strip().lower()
    if preset in ASR_PRESET_TO_BEAM_SIZE:
        return preset
    return "balanced"


def beam_size_to_asr_preset(beam_size: int | None) -> str | None:
    if beam_size is None:
        return None
    for preset, preset_beam_size in ASR_PRESET_TO_BEAM_SIZE.items():
        if beam_size == preset_beam_size:
            return preset
    return None


def format_asr_preset_label(preset: str) -> str:
    return normalize_asr_preset(preset).title()


def normalize_window_opacity(value: float | int | None) -> float:
    try:
        opacity = float(value)
    except (TypeError, ValueError):
        opacity = 1.0
    return min(max(opacity, 0.35), 1.0)


def normalize_dark_mode(value: object) -> bool:
    return bool(value)


@dataclass(frozen=True)
class AppSettings:
    project_root: Path
    config_path: Path
    logs_dir: Path
    temp_dir: Path
    log_file: Path
    window_title: str
    window_geometry: str
    always_on_top: bool
    sample_rate: int
    channels: int
    dtype: str
    model_name: str
    language: str
    beam_size: int
    without_timestamps: bool
    condition_on_previous_text: bool
    vad_filter: bool
    device: str
    compute_type: str
    download_root: Path
    asr_preset: str
    hotkey_combination: str
    auto_paste_after_hotkey_transcription: bool
    restore_clipboard_after_paste: bool
    paste_delay_ms: int
    input_device_index: int | None
    input_device_name: str | None
    show_advanced_devices: bool
    window_opacity: float
    dark_mode: bool


def build_default_config() -> dict:
    return copy.deepcopy(DEFAULT_CONFIG_TEMPLATE)


def _emit_config_notice(message: str) -> None:
    print(f"[voice_typing_ro] {message}", file=sys.stderr)


def _deep_merge_defaults(defaults: dict, overrides: dict) -> dict:
    merged = copy.deepcopy(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_defaults(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_path_string(value: object, default: str) -> str:
    text = str(value or "").strip()
    return text or default


def _fallback_model_download_root() -> Path:
    return Path.home() / ".romanian_voice_typing" / "models"


def _resolve_config_path(project_root: Path, value: object, *, fallback: Path) -> Path:
    raw_value = str(value or "").strip()
    if not raw_value:
        return fallback

    expanded = os.path.expanduser(os.path.expandvars(raw_value))
    if expanded == raw_value and "%" in raw_value:
        return fallback

    path = Path(expanded)
    if path.is_absolute():
        return path
    return project_root / path


def _backup_invalid_config() -> Path:
    backup_path = CONFIG_PATH.with_name("config.invalid.json")
    index = 1
    while backup_path.exists():
        backup_path = CONFIG_PATH.with_name(f"config.invalid.{index}.json")
        index += 1

    shutil.copy2(CONFIG_PATH, backup_path)
    return backup_path


def _normalize_config(config: dict) -> dict:
    defaults = build_default_config()
    normalized = _deep_merge_defaults(defaults, config)

    ui = (
        dict(normalized["ui"])
        if isinstance(normalized.get("ui"), dict)
        else dict(defaults["ui"])
    )
    audio = (
        dict(normalized["audio"])
        if isinstance(normalized.get("audio"), dict)
        else dict(defaults["audio"])
    )
    transcription = (
        dict(normalized["transcription"])
        if isinstance(normalized.get("transcription"), dict)
        else dict(defaults["transcription"])
    )
    paste = (
        dict(normalized["paste"])
        if isinstance(normalized.get("paste"), dict)
        else dict(defaults["paste"])
    )
    paths = (
        dict(normalized["paths"])
        if isinstance(normalized.get("paths"), dict)
        else dict(defaults["paths"])
    )
    normalized["ui"] = ui
    normalized["audio"] = audio
    normalized["transcription"] = transcription
    normalized["paste"] = paste
    normalized["paths"] = paths

    hotkey_value = normalized.get("hotkey")
    if isinstance(hotkey_value, dict):
        old_hotkey = hotkey_value
        normalized["hotkey"] = str(
            old_hotkey.get("toggle_recording") or defaults["hotkey"]
        ).strip().lower().replace(" ", "")
        hotkey_options = normalized.get("hotkey_options")
        if not isinstance(hotkey_options, dict):
            hotkey_options = {}
        hotkey_options.setdefault(
            "auto_paste_after_hotkey_transcription",
            bool(old_hotkey.get("auto_paste_after_hotkey_transcription", True)),
        )
        normalized["hotkey_options"] = hotkey_options
    else:
        normalized["hotkey"] = str(
            hotkey_value or defaults["hotkey"]
        ).strip().lower().replace(" ", "")
        hotkey_options = normalized.get("hotkey_options")
        if not isinstance(hotkey_options, dict):
            hotkey_options = {}
        hotkey_options.setdefault("auto_paste_after_hotkey_transcription", True)
        normalized["hotkey_options"] = hotkey_options

    raw_beam_size = transcription.get("beam_size")
    try:
        beam_size = int(raw_beam_size)
    except (TypeError, ValueError):
        beam_size = None

    preset = normalize_asr_preset(normalized.get("asr_preset"))
    mapped_preset = beam_size_to_asr_preset(beam_size)
    if mapped_preset is not None:
        preset = mapped_preset
        beam_size = ASR_PRESET_TO_BEAM_SIZE[preset]
    else:
        beam_size = ASR_PRESET_TO_BEAM_SIZE[preset]

    ui["title"] = (
        str(ui.get("title") or defaults["ui"]["title"]).strip()
        or defaults["ui"]["title"]
    )
    ui["geometry"] = (
        str(ui.get("geometry") or defaults["ui"]["geometry"]).strip()
        or defaults["ui"]["geometry"]
    )
    ui["always_on_top"] = bool(
        ui.get("always_on_top", defaults["ui"]["always_on_top"])
    )

    audio["sample_rate"] = int(
        audio.get("sample_rate") or defaults["audio"]["sample_rate"]
    )
    audio["channels"] = int(audio.get("channels") or defaults["audio"]["channels"])
    audio["dtype"] = (
        str(audio.get("dtype") or defaults["audio"]["dtype"]).strip()
        or defaults["audio"]["dtype"]
    )

    transcription["model"] = (
        str(transcription.get("model") or defaults["transcription"]["model"]).strip()
        or defaults["transcription"]["model"]
    )
    transcription["language"] = (
        str(
            transcription.get("language") or defaults["transcription"]["language"]
        ).strip().lower()
        or defaults["transcription"]["language"]
    )
    transcription["beam_size"] = beam_size
    transcription["without_timestamps"] = bool(
        transcription.get(
            "without_timestamps",
            defaults["transcription"]["without_timestamps"],
        )
    )
    transcription["condition_on_previous_text"] = bool(
        transcription.get(
            "condition_on_previous_text",
            defaults["transcription"]["condition_on_previous_text"],
        )
    )
    transcription["vad_filter"] = bool(
        transcription.get("vad_filter", defaults["transcription"]["vad_filter"])
    )
    transcription["device"] = (
        str(transcription.get("device") or defaults["transcription"]["device"])
        .strip()
        .lower()
        or defaults["transcription"]["device"]
    )
    transcription["compute_type"] = (
        str(
            transcription.get("compute_type")
            or defaults["transcription"]["compute_type"]
        )
        .strip()
        .lower()
        or defaults["transcription"]["compute_type"]
    )
    transcription["download_root"] = _normalize_path_string(
        transcription.get("download_root"),
        defaults["transcription"]["download_root"],
    )

    normalized["asr_preset"] = preset
    normalized["show_advanced_devices"] = bool(
        normalized.get("show_advanced_devices", defaults["show_advanced_devices"])
    )
    normalized["window_opacity"] = normalize_window_opacity(
        normalized.get("window_opacity", defaults["window_opacity"])
    )
    normalized["dark_mode"] = normalize_dark_mode(
        normalized.get("dark_mode", defaults["dark_mode"])
    )
    normalized["input_device_index"] = _normalize_optional_int(
        normalized.get("input_device_index")
    )
    normalized["input_device_name"] = _normalize_optional_string(
        normalized.get("input_device_name")
    )

    paste["restore_clipboard_after_paste"] = bool(
        paste.get(
            "restore_clipboard_after_paste",
            defaults["paste"]["restore_clipboard_after_paste"],
        )
    )
    paste["paste_delay_ms"] = int(
        paste.get("paste_delay_ms") or defaults["paste"]["paste_delay_ms"]
    )

    paths["logs_dir"] = _normalize_path_string(
        paths.get("logs_dir"),
        defaults["paths"]["logs_dir"],
    )
    paths["temp_dir"] = _normalize_path_string(
        paths.get("temp_dir"),
        defaults["paths"]["temp_dir"],
    )
    return normalized


def save_config_data(config: dict) -> None:
    normalized = _normalize_config(config)
    CONFIG_PATH.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_config_data() -> dict:
    defaults = build_default_config()
    if not CONFIG_PATH.exists():
        save_config_data(defaults)
        _emit_config_notice("Created default config.json.")
        return defaults

    try:
        raw_text = CONFIG_PATH.read_text(encoding="utf-8")
        config = json.loads(raw_text)
        if not isinstance(config, dict):
            raise ValueError("config.json must contain a JSON object.")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        backup_path = _backup_invalid_config()
        save_config_data(defaults)
        _emit_config_notice(
            f"Invalid config detected. Backed it up to {backup_path.name} and regenerated defaults."
        )
        return defaults

    normalized = _normalize_config(config)
    if normalized != config:
        save_config_data(normalized)
    return normalized


def update_runtime_config(
    *,
    hotkey: str | object = _UNSET,
    asr_preset: str | object = _UNSET,
    beam_size: int | object = _UNSET,
    input_device_index: int | None | object = _UNSET,
    input_device_name: str | None | object = _UNSET,
    show_advanced_devices: bool | object = _UNSET,
    window_opacity: float | object = _UNSET,
    dark_mode: bool | object = _UNSET,
) -> dict:
    config = load_config_data()

    if hotkey is not _UNSET:
        config["hotkey"] = str(hotkey)
    if asr_preset is not _UNSET:
        normalized_preset = normalize_asr_preset(str(asr_preset))
        config["asr_preset"] = normalized_preset
        if beam_size is _UNSET:
            config["transcription"]["beam_size"] = ASR_PRESET_TO_BEAM_SIZE[
                normalized_preset
            ]
    if beam_size is not _UNSET:
        config["transcription"]["beam_size"] = int(beam_size)
        mapped_preset = beam_size_to_asr_preset(int(beam_size))
        if asr_preset is _UNSET and mapped_preset is not None:
            config["asr_preset"] = mapped_preset
    if input_device_index is not _UNSET:
        config["input_device_index"] = input_device_index
    if input_device_name is not _UNSET:
        config["input_device_name"] = input_device_name
    if show_advanced_devices is not _UNSET:
        config["show_advanced_devices"] = bool(show_advanced_devices)
    if window_opacity is not _UNSET:
        config["window_opacity"] = normalize_window_opacity(window_opacity)
    if dark_mode is not _UNSET:
        config["dark_mode"] = normalize_dark_mode(dark_mode)

    save_config_data(config)
    return config


def load_settings() -> AppSettings:
    config = load_config_data()

    project_root = PROJECT_ROOT
    logs_dir = _resolve_config_path(
        project_root,
        config["paths"].get("logs_dir"),
        fallback=project_root / "logs",
    )
    temp_dir = _resolve_config_path(
        project_root,
        config["paths"].get("temp_dir"),
        fallback=project_root / "temp",
    )
    download_root = _resolve_config_path(
        project_root,
        config["transcription"].get("download_root"),
        fallback=_fallback_model_download_root(),
    )

    return AppSettings(
        project_root=project_root,
        config_path=CONFIG_PATH,
        logs_dir=logs_dir,
        temp_dir=temp_dir,
        log_file=logs_dir / "overlay.log",
        window_title=config["ui"]["title"],
        window_geometry=config["ui"]["geometry"],
        always_on_top=bool(config["ui"]["always_on_top"]),
        sample_rate=int(config["audio"]["sample_rate"]),
        channels=int(config["audio"]["channels"]),
        dtype=str(config["audio"]["dtype"]),
        model_name=str(config["transcription"]["model"]),
        language=str(config["transcription"]["language"]),
        beam_size=int(config["transcription"]["beam_size"]),
        without_timestamps=bool(config["transcription"]["without_timestamps"]),
        condition_on_previous_text=bool(
            config["transcription"]["condition_on_previous_text"]
        ),
        vad_filter=bool(config["transcription"]["vad_filter"]),
        device=str(config["transcription"]["device"]),
        compute_type=str(config["transcription"]["compute_type"]),
        download_root=download_root,
        asr_preset=str(config["asr_preset"]),
        hotkey_combination=str(config["hotkey"]),
        auto_paste_after_hotkey_transcription=bool(
            config["hotkey_options"]["auto_paste_after_hotkey_transcription"]
        ),
        restore_clipboard_after_paste=bool(
            config["paste"]["restore_clipboard_after_paste"]
        ),
        paste_delay_ms=int(config["paste"]["paste_delay_ms"]),
        input_device_index=(
            int(config["input_device_index"])
            if config["input_device_index"] is not None
            else None
        ),
        input_device_name=(
            str(config["input_device_name"])
            if config["input_device_name"] is not None
            else None
        ),
        show_advanced_devices=bool(config["show_advanced_devices"]),
        window_opacity=float(config["window_opacity"]),
        dark_mode=bool(config["dark_mode"]),
    )


def ensure_runtime_dirs(settings: AppSettings) -> None:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.temp_dir.mkdir(parents=True, exist_ok=True)


def configure_logging(settings: AppSettings) -> logging.Logger:
    ensure_runtime_dirs(settings)

    logger = logging.getLogger("voice_typing_ro")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(threadName)s | %(message)s"
    )

    file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger
