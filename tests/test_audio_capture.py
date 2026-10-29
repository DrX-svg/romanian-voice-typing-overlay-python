import logging
import wave

import numpy as np
import pytest

from voice_typing_ro import audio_capture as audio


def make_recorder(index=None):
    return audio.ManualAudioRecorder(8000, 2, "int16", logging.getLogger("test"), index)


def test_device_name_helpers():
    assert audio.build_microphone_match_key("Microphone (Acme X100 USB)") == "acme x100"
    assert audio.build_microphone_match_key("Headset (Acme X100 WASAPI)") == "acme x100"
    assert audio._readable_device_name("  Microphone   (Acme) ") == "Microphone (Acme)"
    assert audio._simplify_vendor_name("Intel Smart Sound Technology for Digital Microphones") == "Intel Smart Sound"
    assert audio._advanced_display_name("Mic", "MME", 2, True) == "Mic - MME (#2) [Default]"
    assert audio._simple_display_name("Mic", True) == "Mic [Default]"


def test_device_grouping_and_filtering(fake_sd):
    names = ["Microphone (Acme X100)", "Microphone (Acme X100)", "Stereo Mix", "Microsoft Sound Mapper", "Microphone (Other Y200)", "Speakers", "Microphone (KS Z300)"]
    fake_sd.query_devices.return_value = [
        {"name": name, "max_input_channels": 0 if i == 5 else 1, "hostapi": 1 if i == 1 else (2 if i == 6 else 0)}
        for i, name in enumerate(names)
    ]
    fake_sd.query_hostapis.return_value = [{"name": "MME"}, {"name": "Windows WASAPI"}, {"name": "Windows WDM-KS"}]
    devices = audio.list_input_devices()
    assert devices[0].index is None
    assert devices[0].is_default
    assert {device.index for device in devices[1:]} == {1, 4}
    advanced = audio.list_input_devices(show_advanced_devices=True)
    assert [device.index for device in advanced] == [None, 0, 1, 2, 3, 4, 6]
    assert advanced[1].is_default
    assert "MME" in advanced[1].display_name


@pytest.mark.parametrize("index", [None, 7])
def test_recording_wav_and_callback_buffering(fake_sd, tmp_path, index):
    recorder = make_recorder(index)
    recorder.start_recording()
    kwargs = dict(samplerate=8000, channels=2, dtype="int16", callback=recorder._audio_callback)
    if index is not None:
        kwargs["device"] = index
    fake_sd.InputStream.assert_called_once_with(**kwargs)
    chunk = np.array([[1, 2], [3, 4]], dtype=np.int16)
    callback = fake_sd.InputStream.call_args.kwargs["callback"]
    callback(chunk, 2, None, None)
    chunk[:] = 99
    callback(np.array([[5, 6]], dtype=np.int16), 1, None, None)
    result = recorder.stop_recording(tmp_path / "capture.wav")
    assert result.frame_count == 3
    assert result.duration_seconds == 3 / 8000
    with wave.open(str(result.wav_path), "rb") as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getnframes(), wav.getsampwidth()) == (8000, 2, 3, 2)
        assert np.frombuffer(wav.readframes(3), dtype=np.int16).tolist() == [1, 2, 3, 4, 5, 6]
    fake_sd.InputStream.return_value.stop.assert_called_once()
    fake_sd.InputStream.return_value.close.assert_called_once()
    assert not recorder.is_recording


@pytest.mark.parametrize("empty_chunk", [False, True])
def test_empty_recording_raises(fake_sd, tmp_path, empty_chunk):
    recorder = make_recorder()
    recorder.start_recording()
    if empty_chunk:
        recorder._audio_callback(np.empty((0, 2), dtype=np.int16), 0, None, None)
    with pytest.raises(audio.AudioCaptureError):
        recorder.stop_recording(tmp_path / "empty.wav")
