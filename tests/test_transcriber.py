from dataclasses import replace
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("language,beam,timestamps,previous,vad", [("ro", 3, True, False, False), ("en", 5, False, True, True)])
def test_transcribe_arguments_and_segment_joining(fake_transcriber, tmp_path, language, beam, timestamps, previous, vad):
    transcriber = fake_transcriber
    transcriber.settings = replace(transcriber.settings, language=language, without_timestamps=timestamps, condition_on_previous_text=previous, vad_filter=vad)
    transcriber.set_beam_size(beam)
    transcriber._model.transcribe.return_value = (
        iter(SimpleNamespace(text=text) for text in ["  hello ", "", "  ", None, " world  "]),
        SimpleNamespace(duration=1.0),
    )
    path = tmp_path / "fake.wav"
    text, elapsed = transcriber.transcribe_file(path)
    assert text == "hello world"
    assert elapsed >= 0
    assert transcriber.beam_size == beam
    transcriber._model.transcribe.assert_called_once_with(
        str(path), language=language, beam_size=beam, without_timestamps=timestamps,
        condition_on_previous_text=previous, vad_filter=vad,
    )
