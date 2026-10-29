import json

import pytest

from voice_typing_ro import settings


@pytest.mark.parametrize("value,expected", [(None, "balanced"), (" FAST ", "fast"), ("accurate", "accurate"), ("other", "balanced")])
def test_normalize_asr_preset(value, expected):
    assert settings.normalize_asr_preset(value) == expected
    assert settings.format_asr_preset_label(value) == expected.title()


@pytest.mark.parametrize("beam,preset", [(1, "fast"), (3, "balanced"), (5, "accurate"), (2, None), (None, None)])
def test_beam_mapping(beam, preset):
    assert settings.beam_size_to_asr_preset(beam) == preset


@pytest.mark.parametrize("value,expected", [(0, .35), (.5, .5), (2, 1.0), (None, 1.0), ("bad", 1.0)])
def test_opacity(value, expected):
    assert settings.normalize_window_opacity(value) == expected


@pytest.mark.parametrize("value,expected", [(None, False), (False, False), (0, False), (True, True), ("false", True)])
def test_dark_mode(value, expected):
    assert settings.normalize_dark_mode(value) is expected


def test_missing_config_writes_defaults(temp_config):
    assert settings.load_config_data() == settings.build_default_config()
    assert json.loads(temp_config.read_text()) == settings.build_default_config()


def test_invalid_json_numbered_backups(temp_config):
    for suffix in ("", ".1", ".2"):
        temp_config.write_text("{broken", encoding="utf-8")
        assert settings.load_config_data() == settings.build_default_config()
        assert temp_config.with_name(f"config.invalid{suffix}.json").read_text() == "{broken"


def test_unknown_keys_preserved(temp_config):
    temp_config.write_text(json.dumps({"custom": 42, "audio": {"custom": "value"}}))
    config = settings.load_config_data()
    assert config["custom"] == 42
    assert config["audio"]["custom"] == "value"
    assert config["audio"]["sample_rate"] == 16000


@pytest.mark.parametrize("preset,beam", [("fast", 1), ("balanced", 3), ("accurate", 5)])
def test_runtime_round_trip(temp_config, preset, beam):
    config = settings.update_runtime_config(
        hotkey="ctrl+f9", asr_preset=preset, input_device_index=2,
        input_device_name="Mic", show_advanced_devices=True, window_opacity=.6, dark_mode=True,
    )
    assert settings.load_config_data() == config
    loaded = settings.load_settings()
    assert (loaded.asr_preset, loaded.beam_size) == (preset, beam)
    assert (loaded.hotkey_combination, loaded.input_device_index, loaded.input_device_name) == ("ctrl+f9", 2, "Mic")
    assert (loaded.show_advanced_devices, loaded.window_opacity, loaded.dark_mode) == (True, .6, True)
    assert settings.update_runtime_config(beam_size=beam)["asr_preset"] == preset


@pytest.mark.parametrize("section,key,default,invalid", [
    ("audio", "sample_rate", 16000, "bad"),
    ("audio", "sample_rate", 16000, 0),
    ("audio", "sample_rate", 16000, -1),
    ("audio", "channels", 1, "bad"),
    ("audio", "channels", 1, 0),
    ("audio", "channels", 1, -1),
    ("paste", "paste_delay_ms", 150, "bad"),
    ("paste", "paste_delay_ms", 150, -1),
    ("audio", "sample_rate", 16000, None),
    ("audio", "channels", 1, []),
    ("paste", "paste_delay_ms", 150, {}),
])
def test_invalid_integer_falls_back_per_key(temp_config, capsys, section, key, default, invalid):
    temp_config.write_text(json.dumps({section: {key: invalid}, "custom": "preserved", "ui": {"title": "Custom"}}))
    loaded = settings.load_settings()
    assert getattr(loaded, key) == default
    saved = json.loads(temp_config.read_text())
    assert saved[section][key] == default
    assert saved["custom"] == "preserved"
    assert saved["ui"]["title"] == "Custom"
    assert f"{section}.{key}" in capsys.readouterr().err
    assert not temp_config.with_name("config.invalid.json").exists()


def test_zero_paste_delay_is_valid(temp_config):
    temp_config.write_text(json.dumps({"paste": {"paste_delay_ms": 0}}))
    assert settings.load_settings().paste_delay_ms == 0
