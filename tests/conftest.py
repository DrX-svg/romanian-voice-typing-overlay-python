import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from voice_typing_ro import audio_capture, hotkeys, settings
from voice_typing_ro.transcriber import LocalWhisperTranscriber


@pytest.fixture
def temp_config(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(settings, "CONFIG_PATH", tmp_path / "config.json")
    return settings.CONFIG_PATH


@pytest.fixture
def fake_sd(monkeypatch):
    backend = Mock()
    backend.default = SimpleNamespace(device=(0, -1))
    monkeypatch.setattr(audio_capture, "sd", backend)
    return backend


@pytest.fixture
def fake_keyboard(monkeypatch):
    backend = Mock()
    monkeypatch.setattr(hotkeys, "keyboard_lib", backend)
    return backend


@pytest.fixture
def fake_transcriber(temp_config):
    transcriber = LocalWhisperTranscriber(settings.load_settings(), logging.getLogger("test"))
    transcriber._model = Mock()
    transcriber._ready_event.set()
    return transcriber
