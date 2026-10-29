import logging
import queue
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def app_stub():
    from voice_typing_ro.app import VoiceTypingOverlayApp

    app = VoiceTypingOverlayApp.__new__(VoiceTypingOverlayApp)
    app.logger = logging.getLogger("test")
    app.root = Mock()
    app.gui = Mock()
    app.event_queue = queue.Queue()
    app.is_transcribing = False
    app.is_pasting = False
    app.pending_auto_paste = True
    app.current_recording_origin = "hotkey"
    app._refresh_controls = Mock()
    return app


@pytest.mark.skipif(sys.platform != "win32", reason="app imports Windows clipboard APIs")
def test_handler_exception_logs_and_reschedules(app_stub, caplog):
    app_stub.event_queue.put(("broken", {}))
    app_stub.event_queue.put(("next", {}))
    app_stub._handle_event = Mock(side_effect=[RuntimeError("handler failed"), None])
    app_stub.process_events()
    app_stub.root.after.assert_called_once_with(100, app_stub.process_events)
    assert "handler failed" in caplog.text
    assert app_stub._handle_event.call_count == 2


@pytest.mark.skipif(sys.platform != "win32", reason="app imports Windows clipboard APIs")
@pytest.mark.parametrize("error", [OSError("export failed"), RuntimeError("stop failed")])
def test_stop_failure_resets_state_and_controls(app_stub, tmp_path, monkeypatch, error):
    from voice_typing_ro import app as app_module

    monkeypatch.setattr(app_module.messagebox, "showerror", Mock())
    app_stub.settings = SimpleNamespace(temp_dir=tmp_path)
    app_stub.recorder = Mock()
    app_stub.recorder.stop_recording.side_effect = error
    app_stub.stop_and_transcribe("button")
    app_stub.recorder.cleanup.assert_called_once_with()
    assert not app_stub.is_transcribing
    assert not app_stub.pending_auto_paste
    assert app_stub.current_recording_origin is None
    app_stub.gui.set_status.assert_called_once_with("Error")
    app_stub._refresh_controls.assert_called_once_with()


@pytest.mark.skipif(sys.platform != "win32", reason="app imports Windows clipboard APIs")
@pytest.mark.parametrize("failure", [None, "expected", "unexpected"])
@pytest.mark.parametrize("keep", [False, True])
def test_transcription_worker_temp_file_policy(app_stub, tmp_path, failure, keep):
    from voice_typing_ro.transcriber import TranscriberError

    wav = tmp_path / "recording.wav"
    wav.write_bytes(b"fake audio")
    app_stub.settings = SimpleNamespace(keep_temp_recordings=keep)
    app_stub.transcriber = Mock()
    app_stub.transcriber.transcribe_file.return_value = ("text", .1)
    if failure:
        app_stub.transcriber.transcribe_file.side_effect = (
            TranscriberError("failed") if failure == "expected" else RuntimeError("failed")
        )
    app_stub._transcribe_worker(wav)
    assert wav.exists() is keep
    event, payload = app_stub.event_queue.get_nowait()
    assert event == ("transcription_error" if failure else "transcription_complete")


@pytest.mark.skipif(sys.platform != "win32", reason="app imports Windows clipboard APIs")
def test_temp_file_deletion_failure_only_logs(app_stub, tmp_path, monkeypatch, caplog):
    from pathlib import Path

    app_stub.settings = SimpleNamespace(keep_temp_recordings=False)
    app_stub.transcriber = Mock()
    app_stub.transcriber.transcribe_file.return_value = ("text", .1)
    monkeypatch.setattr(Path, "unlink", Mock(side_effect=OSError("access denied")))
    app_stub._transcribe_worker(tmp_path / "recording.wav")
    assert "access denied" in caplog.text
    assert app_stub.event_queue.get_nowait()[0] == "transcription_complete"
