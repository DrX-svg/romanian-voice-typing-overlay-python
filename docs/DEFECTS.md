# Defect log

Scope: local branch `feat/tests-and-defect-fixes`, based on `cd18f3b`.
Regression tests use fake hardware, model, GUI, and clipboard backends.

| ID | Component | Symptom | Root cause | Fix | Regression test (file::test name) | Commit hash | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | settings | Valid JSON with invalid audio integers or paste delay crashes startup or accepts invalid ranges. | Unguarded integer conversion and truthiness defaults. | Coerce each key safely, enforce positive sample rate/channels and nonnegative delay, report fallback to stderr, preserve other config keys. Zero delay remains valid. | `tests/test_settings.py::test_invalid_integer_falls_back_per_key`; `tests/test_settings.py::test_zero_paste_delay_is_valid` | `22c128f` | Fixed |
| D2 | app | Handler exceptions stop queue polling; unexpected recording stop/export failures leave controls and state unrecovered. | Rescheduling occurs after dispatch; stop catches only AudioCaptureError. | Log handler exceptions, reschedule in finally, clean up recorder and use existing error/state/control recovery for all stop/export exceptions. | `tests/test_app.py::test_handler_exception_logs_and_reschedules`; `tests/test_app.py::test_stop_failure_resets_state_and_controls` | `8718c6d` | Fixed |
| D3 | audio_capture | Streams leak when start or stop raises. | Failed start drops the stream; stop and close were sequential. | Close failed streams, use finally for stop/close, always clear stream references. | `tests/test_audio_capture.py::test_start_failure_closes_stream`; `tests/test_audio_capture.py::test_stop_failure_always_closes_stream` | `4f48462` | Fixed |
| D4 | text_inserter | Repeated OpenClipboard failures leak global memory. | Allocation happens before the freeing finally block. | Cover allocation ownership with an outer finally; transfer ownership only after SetClipboardData succeeds. | `tests/test_text_inserter.py::test_open_clipboard_failure_frees_allocation` | `3b1573b` | Fixed |
| D5 | app/settings | Temporary WAV files accumulate after transcription. | Worker has no file cleanup or retention setting. | Delete in worker finally; log deletion errors; normalize audio.keep_temp_recordings (default false) using existing boolean conventions. | `tests/test_app.py::test_transcription_worker_temp_file_policy`; `tests/test_app.py::test_temp_file_deletion_failure_only_logs`; `tests/test_settings.py::test_keep_temp_recordings_normalized`; `tests/test_settings.py::test_keep_temp_recordings_default` | `1f62794` | Fixed |
| O1 | audio_capture | Configuring dtype other than int16 allows capture but export fails. Severity: Low. | `src/voice_typing_ro/audio_capture.py:704` rejects every other dtype; settings permits arbitrary dtype strings. | Not changed; validate dtype or implement conversion in a future task. | Not added (outside scope). | — | Open |
| O2 | app | With retention enabled, recordings stopped within the same second can overwrite an earlier WAV. Severity: Low. | `src/voice_typing_ro/app.py:405` uses second-resolution filenames without collision handling. Static finding; timing scenario not executed. | Not changed; use unique filenames in a future task. | Not added (outside scope). | — | Open |
| O3 | settings | Nonfinite opacity can reach the GUI outside the intended numeric range. Severity: Low. | `src/voice_typing_ro/settings.py:90` accepts float NaN and clamping does not reject it. Static finding; GUI effect unverified. | Not changed; reject nonfinite values in a future task. | Not added (outside scope). | — | Open |

## Verification

Each D1–D5 regression run was executed before its fix: D1 had 12 failures;
D2 had 3; D3 had 3; D4 had 1; D5 had 10 failures and 3 passing retention controls.
All now pass. Full suite on Windows with Python 3.11.9: 70 total, 70 passed,
0 skipped, 0 failed. Every commit was preceded by a passing full suite and
`git diff --check`.

The 10 cases in `tests/test_app.py` and the one case in
`tests/test_text_inserter.py` are explicitly Windows-only and skip before importing
Windows modules on other platforms. CI targets Python 3.10 on Ubuntu and Windows,
installs only `requirements-dev.txt`, and runs `python -m pytest -v`.
The workflow was reviewed manually; Actions and Linux/Python 3.10 were not run
locally. No GUI, physical microphone, model inference, GPU, or real clipboard
operations were exercised.
