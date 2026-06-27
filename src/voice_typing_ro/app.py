# Romanian Voice Typing Overlay
# Copyright (C) 2026 DrX-svg
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog

from .audio_capture import (
    AudioCaptureError,
    InputDeviceInfo,
    ManualAudioRecorder,
    build_microphone_match_key,
    list_input_devices,
)
from .gui_overlay import VoiceTypingOverlay
from .hotkeys import GlobalHotkeyManager
from .settings import (
    ASR_PRESET_TO_BEAM_SIZE,
    configure_logging,
    format_asr_preset_label,
    load_settings,
    normalize_dark_mode,
    normalize_asr_preset,
    normalize_window_opacity,
    update_runtime_config,
)
from .text_inserter import PasteResult, WindowTarget, WindowsTextInserter
from .transcriber import LocalWhisperTranscriber, TranscriberError


class VoiceTypingOverlayApp:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.logger = configure_logging(self.settings)
        self.logger.info("Application startup.")

        self.event_queue: queue.Queue[tuple[str, dict]] = queue.Queue()
        self.is_transcribing = False
        self.is_pasting = False
        self.pending_auto_paste = False
        self.current_recording_origin: str | None = None
        self.last_transcript_text = ""
        self.last_target_window: WindowTarget | None = None
        self.microphone_options: list[InputDeviceInfo] = []
        self.microphone_option_by_label: dict[str, InputDeviceInfo] = {}
        self.current_input_device_index = self.settings.input_device_index
        self.current_input_device_name = self.settings.input_device_name
        self.show_advanced_devices = self.settings.show_advanced_devices
        self.current_asr_preset = normalize_asr_preset(self.settings.asr_preset)
        self.current_beam_size = int(self.settings.beam_size)
        self.current_window_opacity = normalize_window_opacity(
            self.settings.window_opacity
        )
        self.dark_mode_enabled = normalize_dark_mode(self.settings.dark_mode)

        self.transcriber = LocalWhisperTranscriber(self.settings, self.logger)
        self.recorder = ManualAudioRecorder(
            sample_rate=self.settings.sample_rate,
            channels=self.settings.channels,
            dtype=self.settings.dtype,
            logger=self.logger,
            input_device_index=self.current_input_device_index,
            input_device_name=self.current_input_device_name,
        )

        self.root = tk.Tk()
        self.overlay_hwnd = int(self.root.winfo_id())
        self.text_inserter = WindowsTextInserter(
            logger=self.logger,
            restore_clipboard_after_paste=self.settings.restore_clipboard_after_paste,
            paste_delay_ms=self.settings.paste_delay_ms,
        )
        self.hotkey_manager = GlobalHotkeyManager(
            hotkey=self.settings.hotkey_combination,
            logger=self.logger,
            callback=self._queue_hotkey_event,
        )
        self.gui = VoiceTypingOverlay(
            self.root,
            self.settings,
            on_start_recording=self.start_recording_from_button,
            on_stop_transcribe=self.stop_and_transcribe_from_button,
            on_clear=self.clear_transcript,
            on_copy=self.copy_transcript,
            on_paste=self.paste_last_transcript_from_button,
            on_change_hotkey=self.change_hotkey,
            on_refresh_microphones=self.refresh_microphones_from_button,
            on_microphone_selected=self.select_microphone_by_label,
            on_toggle_advanced_devices=self.toggle_show_advanced_devices,
            on_asr_preset_selected=self.change_asr_preset,
            on_opacity_changed=self.change_window_opacity,
            on_dark_mode_toggled=self.toggle_dark_mode,
        )
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.gui.set_status("Loading model")
        self.gui.set_target_status("No target window captured.")
        self.gui.set_hotkey_display("Registering...")
        self.gui.set_microphone_options([], None)
        self.gui.set_show_advanced_devices(self.show_advanced_devices)
        self.gui.set_asr_preset_display(self.current_asr_preset)
        self.gui.set_opacity_display(self.current_window_opacity)
        self.gui.set_window_opacity(self.current_window_opacity)
        self.gui.set_dark_mode_enabled(self.dark_mode_enabled)
        self._refresh_controls()

    def run(self) -> None:
        self._register_hotkey()
        self.refresh_microphones(initial=True)
        self.transcriber.load_async(self._on_model_loaded)
        self.root.after(100, self.process_events)
        self.root.mainloop()

    def _on_model_loaded(self, success: bool, error_message: str | None) -> None:
        self.event_queue.put(
            (
                "model_loaded",
                {
                    "success": success,
                    "error_message": error_message,
                },
            )
        )

    def start_recording_from_button(self) -> None:
        self.start_recording(trigger="button")

    def stop_and_transcribe_from_button(self) -> None:
        self.stop_and_transcribe(trigger="button")

    def paste_last_transcript_from_button(self) -> None:
        self.paste_last_transcript(trigger="button")

    def refresh_microphones_from_button(self) -> None:
        self.refresh_microphones(initial=False)

    def toggle_show_advanced_devices(self, enabled: bool) -> None:
        if self.recorder.is_recording or self.is_transcribing or self.is_pasting:
            self.gui.set_show_advanced_devices(self.show_advanced_devices)
            self.gui.set_status("Cannot change device filter while busy.")
            return

        self.show_advanced_devices = bool(enabled)
        update_runtime_config(show_advanced_devices=self.show_advanced_devices)
        self.logger.info(
            "Advanced microphone device filter updated. show_advanced_devices=%s",
            self.show_advanced_devices,
        )
        self.refresh_microphones(initial=False)
        if not self._is_busy():
            if self.show_advanced_devices:
                self.gui.set_status("Advanced microphone devices shown")
            else:
                self.gui.set_status("Microphone list simplified")

    def change_asr_preset(self, preset: str) -> None:
        normalized_preset = normalize_asr_preset(preset)
        beam_size = ASR_PRESET_TO_BEAM_SIZE[normalized_preset]
        if (
            normalized_preset == self.current_asr_preset
            and beam_size == self.current_beam_size
        ):
            self.gui.set_asr_preset_display(self.current_asr_preset)
            return

        self.current_asr_preset = normalized_preset
        self.current_beam_size = beam_size
        self.transcriber.set_beam_size(beam_size)
        self.gui.set_asr_preset_display(self.current_asr_preset)
        update_runtime_config(
            asr_preset=self.current_asr_preset,
            beam_size=self.current_beam_size,
        )
        self.logger.info(
            "ASR preset updated. preset=%s beam_size=%s",
            self.current_asr_preset,
            self.current_beam_size,
        )
        if not self._is_busy():
            self.gui.set_status(
                f"ASR preset: {format_asr_preset_label(self.current_asr_preset)}"
            )

    def change_window_opacity(self, opacity: float) -> None:
        normalized_opacity = normalize_window_opacity(opacity)
        if abs(normalized_opacity - self.current_window_opacity) < 0.005:
            self.gui.set_opacity_display(self.current_window_opacity)
            self.gui.set_window_opacity(self.current_window_opacity)
            return

        self.current_window_opacity = normalized_opacity
        self.gui.set_opacity_display(self.current_window_opacity)
        self.gui.set_window_opacity(self.current_window_opacity)
        update_runtime_config(window_opacity=self.current_window_opacity)
        self.logger.info(
            "Overlay opacity updated. window_opacity=%.2f",
            self.current_window_opacity,
        )
        if not self._is_busy():
            self.gui.set_status(
                f"Opacity: {int(round(self.current_window_opacity * 100))}%"
            )

    def toggle_dark_mode(self, enabled: bool) -> None:
        normalized_enabled = normalize_dark_mode(enabled)
        if normalized_enabled == self.dark_mode_enabled:
            self.gui.set_dark_mode_enabled(self.dark_mode_enabled)
            return

        self.dark_mode_enabled = normalized_enabled
        self.gui.set_dark_mode_enabled(self.dark_mode_enabled)
        update_runtime_config(dark_mode=self.dark_mode_enabled)
        self.logger.info("Dark mode updated. dark_mode=%s", self.dark_mode_enabled)
        if not self._is_busy():
            self.gui.set_status(
                "Dark mode enabled" if self.dark_mode_enabled else "Dark mode disabled"
            )

    def change_hotkey(self) -> None:
        if self.recorder.is_recording or self.is_transcribing or self.is_pasting:
            self.gui.set_status("Busy")
            return

        new_hotkey = simpledialog.askstring(
            "Change Hotkey",
            (
                "Enter a hotkey string.\n\n"
                "Examples:\n"
                "ctrl+alt+c\n"
                "ctrl+alt+space\n"
                "f9\n"
                "ctrl+shift+v"
            ),
            parent=self.root,
            initialvalue=self.hotkey_manager.current_hotkey,
        )
        if new_hotkey is None:
            return

        normalized_hotkey = new_hotkey.strip().lower().replace(" ", "")
        if not normalized_hotkey:
            self.logger.warning("Hotkey change rejected because the new value was empty.")
            self.gui.set_status("Hotkey cannot be empty.")
            return

        result = self.hotkey_manager.reregister_hotkey(normalized_hotkey)
        self.gui.set_hotkey_display(result.active_display_hotkey)
        if result.registered:
            update_runtime_config(hotkey=result.active_hotkey)
            self.logger.info(
                "Hotkey updated via GUI. active_hotkey=%s display=%s",
                result.active_hotkey,
                result.active_display_hotkey,
            )
            self.gui.set_status(f"Hotkey updated to {result.active_display_hotkey}")
        else:
            self.logger.warning("Hotkey update failed: %s", result.message)
            self.gui.set_status(result.message)

        self._refresh_controls()

    def refresh_microphones(self, *, initial: bool) -> None:
        if self.recorder.is_recording:
            self.gui.set_status("Cannot refresh microphones while recording.")
            return

        configured_index = self.current_input_device_index
        configured_name = self.current_input_device_name

        try:
            options = list_input_devices(
                show_advanced_devices=self.show_advanced_devices,
                selected_device_index=self.current_input_device_index,
                logger=self.logger,
            )
        except AudioCaptureError as exc:
            self.microphone_options = []
            self.microphone_option_by_label = {}
            self.logger.error("Could not refresh microphone list: %s", exc)
            self.gui.set_microphone_options([], None)
            self.gui.set_status(
                "Microphone list unavailable" if initial else "Could not refresh microphones"
            )
            self._refresh_controls()
            return

        self.microphone_options = options
        self.microphone_option_by_label = {
            option.display_name: option for option in self.microphone_options
        }

        selected_option, fallback_reason = self._resolve_microphone_option()
        selected_label = selected_option.display_name if selected_option is not None else None
        self.gui.set_microphone_options(
            [option.display_name for option in self.microphone_options],
            selected_label,
        )

        if selected_option is not None:
            self._apply_microphone_selection(
                selected_option,
                persist=fallback_reason is not None,
            )

        if fallback_reason == "cleaned_match":
            self.logger.info(
                "Microphone selection remapped to clean representative. configured_index=%s configured_name=%s new_index=%s new_name=%s",
                configured_index,
                configured_name,
                selected_option.index if selected_option is not None else None,
                selected_option.name if selected_option is not None else None,
            )
            self.gui.set_status("Microphone list cleaned; selected closest matching device")
        elif fallback_reason == "hidden_default":
            fallback_label = (
                "System Default"
                if selected_option is None or selected_option.index is None
                else selected_option.display_name
            )
            self.logger.warning(
                "Selected microphone hidden in simplified mode. configured_index=%s configured_name=%s fallback=%s",
                configured_index,
                configured_name,
                fallback_label,
            )
            self.gui.set_status(
                f"Selected mic hidden in simplified mode; using {fallback_label}"
            )
        elif fallback_reason == "unavailable":
            self.logger.warning(
                "Configured microphone unavailable. Falling back to system default. configured_index=%s configured_name=%s",
                configured_index,
                configured_name,
            )
            self.gui.set_status("Selected microphone unavailable. Using system default.")
        elif not initial and not self._is_busy():
            if self.show_advanced_devices:
                self.gui.set_status("Advanced microphone devices refreshed")
            else:
                self.gui.set_status("Microphones refreshed")

        self._refresh_controls()

    def select_microphone_by_label(self, selected_label: str) -> None:
        if not selected_label:
            return

        if self.recorder.is_recording:
            self.logger.warning("Microphone change ignored while recording.")
            self.gui.set_status("Cannot change microphone while recording.")
            self._sync_microphone_selection()
            return

        option = self.microphone_option_by_label.get(selected_label)
        if option is None:
            self.logger.warning("Selected microphone label not found: %s", selected_label)
            self.gui.set_status("Selected microphone is no longer available.")
            self._sync_microphone_selection()
            return

        self._apply_microphone_selection(option, persist=True)
        self.gui.set_status(f"Microphone selected: {option.display_name}")
        self._refresh_controls()

    def start_recording(self, trigger: str) -> None:
        if self.is_transcribing or self.is_pasting:
            self.logger.info("Start recording ignored via %s because the app is busy.", trigger)
            return

        if not self.transcriber.is_ready:
            self.logger.info(
                "Start recording ignored via %s because the model is not ready.",
                trigger,
            )
            self._set_idle_status()
            return

        try:
            self.recorder.start_recording()
        except AudioCaptureError as exc:
            self._set_error(str(exc), exc)
            return

        self.current_recording_origin = trigger
        self.pending_auto_paste = False
        self.logger.info(
            "Recording started via %s. target=%s",
            trigger,
            self.text_inserter.describe_target(self.last_target_window),
        )
        self.gui.set_status("Recording")
        self._refresh_controls()

    def stop_and_transcribe(self, trigger: str) -> None:
        if self.is_transcribing or self.is_pasting:
            self.logger.info("Stop ignored via %s because the app is busy.", trigger)
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        temp_wav_path = self.settings.temp_dir / f"recording_{timestamp}.wav"

        try:
            result = self.recorder.stop_recording(temp_wav_path)
        except AudioCaptureError as exc:
            self._set_error(str(exc), exc)
            return

        started_via_hotkey = self.current_recording_origin == "hotkey"
        self._ensure_valid_target_window()
        self.pending_auto_paste = (
            started_via_hotkey
            and trigger == "hotkey"
            and self.settings.auto_paste_after_hotkey_transcription
        )
        self.current_recording_origin = None
        self.is_transcribing = True
        self.gui.set_status("Transcribing")
        self._refresh_controls()
        self.logger.info(
            "Recording stopped via %s. Queued transcription for %s (%.2fs). auto_paste=%s target=%s",
            trigger,
            result.wav_path,
            result.duration_seconds,
            self.pending_auto_paste,
            self.text_inserter.describe_target(self.last_target_window),
        )

        worker = threading.Thread(
            target=self._transcribe_worker,
            args=(result.wav_path,),
            name="transcriber",
            daemon=True,
        )
        worker.start()

    def _transcribe_worker(self, wav_path: Path) -> None:
        try:
            transcript, elapsed = self.transcriber.transcribe_file(wav_path)
        except TranscriberError as exc:
            self.event_queue.put(
                (
                    "transcription_error",
                    {"error_message": str(exc)},
                )
            )
        except Exception as exc:  # pragma: no cover - runtime-specific path
            self.logger.exception("Unexpected transcription failure.")
            self.event_queue.put(
                (
                    "transcription_error",
                    {"error_message": str(exc)},
                )
            )
        else:
            self.event_queue.put(
                (
                    "transcription_complete",
                    {
                        "transcript": transcript,
                        "elapsed": elapsed,
                    },
                )
            )

    def clear_transcript(self) -> None:
        self.gui.clear_transcript()
        self.last_transcript_text = ""
        self.logger.info("Transcript cleared.")
        self._set_idle_status()
        self._refresh_controls()

    def copy_transcript(self) -> None:
        transcript = self.gui.get_transcript().strip()
        if not transcript:
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(transcript)
        self.root.update()
        self.logger.info("Transcript copied to clipboard. chars=%s", len(transcript))
        self._set_idle_status()
        self._refresh_controls()

    def paste_last_transcript(self, trigger: str) -> None:
        if self.recorder.is_recording or self.is_transcribing or self.is_pasting:
            self.logger.info("Paste ignored via %s because the app is busy.", trigger)
            return

        transcript = self.last_transcript_text.strip()
        if not transcript:
            self.logger.warning("No transcript is available to paste yet.")
            self.gui.set_status("No transcript to paste")
            return

        self._ensure_valid_target_window()

        self.is_pasting = True
        self.gui.set_status("Pasting")
        self._refresh_controls()
        self.logger.info(
            "Paste requested via %s. target=%s chars=%s",
            trigger,
            self.text_inserter.describe_target(self.last_target_window),
            len(transcript),
        )
        try:
            result = self.text_inserter.paste_text(
                transcript,
                self.last_target_window,
                overlay_hwnd=self.overlay_hwnd,
            )
        except Exception as exc:  # pragma: no cover - runtime-specific path
            self.logger.exception("Unexpected paste failure.")
            result = PasteResult(
                success=False,
                status_text="Paste failed, copied to clipboard",
                message=(
                    f"Unexpected paste failure: {exc}. "
                    "Transcript may still be in the clipboard."
                ),
                target=self.last_target_window,
                used_window=None,
                restored_clipboard=False,
                invalidate_target=False,
                paste_mode="clipboard_only",
                clipboard_has_transcript=True,
            )

        self._handle_paste_complete(result, trigger)

    def process_events(self) -> None:
        try:
            while True:
                event_name, payload = self.event_queue.get_nowait()
                self._handle_event(event_name, payload)
        except queue.Empty:
            pass

        if self.root.winfo_exists():
            self.root.after(100, self.process_events)

    def _handle_event(self, event_name: str, payload: dict) -> None:
        if event_name == "model_loaded":
            if payload["success"]:
                self._set_idle_status()
                self.logger.info("Model is ready.")
            else:
                self.gui.set_status("Error")
                messagebox.showerror("Model Load Error", payload["error_message"])
            self._refresh_controls()
            return

        if event_name == "hotkey_pressed":
            self._handle_hotkey_pressed(payload.get("captured_target"))
            return

        if event_name == "transcription_complete":
            self.is_transcribing = False
            transcript = str(payload["transcript"]).strip()
            elapsed = payload["elapsed"]
            self.last_transcript_text = transcript
            display_text = transcript or "[No speech detected]"
            self.gui.append_transcript(display_text)
            self.logger.info(
                "Transcription completed. elapsed=%.2fs chars=%s auto_paste=%s",
                elapsed,
                len(transcript),
                self.pending_auto_paste,
            )
            if self.pending_auto_paste and transcript:
                self.paste_last_transcript(trigger="hotkey")
                return

            if self.pending_auto_paste and not transcript:
                self.logger.warning("Auto-paste skipped because the transcript is empty.")

            self.pending_auto_paste = False
            self._set_idle_status()
            self._refresh_controls()
            return

        if event_name == "transcription_error":
            self.is_transcribing = False
            self.pending_auto_paste = False
            self.gui.set_status("Error")
            messagebox.showerror("Transcription Error", payload["error_message"])
            self.logger.error("Transcription failed: %s", payload["error_message"])
            self._refresh_controls()
            return

    def _refresh_controls(self) -> None:
        self._ensure_valid_target_window()

        is_busy = self.recorder.is_recording or self.is_transcribing or self.is_pasting
        has_displayed_transcript = bool(self.gui.get_transcript().strip())
        has_last_transcript = bool(self.last_transcript_text.strip())
        can_start = self.transcriber.is_ready and not is_busy
        can_stop = self.recorder.is_recording
        can_clear = True
        can_copy = has_displayed_transcript and not is_busy
        can_paste = has_last_transcript and not is_busy
        can_change_hotkey = not is_busy
        can_change_microphone = not is_busy and bool(self.microphone_options)
        can_refresh_microphones = not is_busy
        can_toggle_advanced_devices = not is_busy

        self.gui.set_controls(
            can_start=can_start,
            can_stop=can_stop,
            can_clear=can_clear,
            can_copy=can_copy,
            can_paste=can_paste,
            can_change_hotkey=can_change_hotkey,
            can_change_microphone=can_change_microphone,
            can_refresh_microphones=can_refresh_microphones,
            can_toggle_advanced_devices=can_toggle_advanced_devices,
        )

    def _set_error(self, message: str, exc: Exception) -> None:
        self.gui.set_status("Error")
        self.logger.error("%s: %s", message, exc)
        messagebox.showerror("Voice Typing Error", message)
        self.is_transcribing = False
        self.is_pasting = False
        self.pending_auto_paste = False
        self.current_recording_origin = None
        self._refresh_controls()

    def _register_hotkey(self) -> None:
        result = self.hotkey_manager.register()
        self.gui.set_hotkey_display(result.active_display_hotkey)
        if result.registered:
            self.logger.info("Initial hotkey registration succeeded: %s", result.message)
        else:
            self.logger.error("Initial hotkey registration failed: %s", result.message)
            self.gui.set_status("Hotkey registration failed. Buttons still work.")
        self._refresh_controls()

    def _queue_hotkey_event(self) -> None:
        captured_target = None
        if not self.recorder.is_recording and not self.is_transcribing and not self.is_pasting:
            captured_target = self.text_inserter.capture_foreground_window(
                exclude_hwnd=self.overlay_hwnd,
            )
        self.event_queue.put(
            (
                "hotkey_pressed",
                {"captured_target": captured_target},
            )
        )

    def _handle_hotkey_pressed(self, captured_target: WindowTarget | None) -> None:
        if self.is_transcribing or self.is_pasting:
            self.logger.info("Hotkey ignored because the app is busy.")
            self.gui.set_status("Busy")
            return

        if self.recorder.is_recording:
            self.stop_and_transcribe(trigger="hotkey")
            return

        if not self.transcriber.is_ready:
            self.logger.info("Hotkey ignored because the model is not ready.")
            self._set_idle_status()
            return

        if captured_target is not None:
            self._set_target_window(captured_target)
        else:
            self.last_target_window = None
            self.gui.set_target_status("No target window captured.")
            self.logger.warning("Hotkey start did not capture a target window.")

        self.start_recording(trigger="hotkey")

    def _set_target_window(self, target: WindowTarget) -> None:
        self.last_target_window = target
        self.gui.set_target_status(f"Captured {self._target_label(target)}")
        self.logger.info(
            "Target window captured. hwnd=%s title=%s",
            self._format_hwnd(target.hwnd),
            target.title or "<untitled>",
        )

    def _ensure_valid_target_window(self) -> bool:
        if self.text_inserter.is_target_available(
            self.last_target_window,
            overlay_hwnd=self.overlay_hwnd,
        ):
            return True

        if self.last_target_window is not None:
            self.logger.warning(
                "Captured target window is no longer valid. hwnd=%s",
                self._format_hwnd(self.last_target_window.hwnd),
            )
        self.last_target_window = None
        self.gui.set_target_status("No target window captured.")
        return False

    def _handle_paste_complete(self, result: PasteResult, trigger: str) -> None:
        self.is_pasting = False
        self.pending_auto_paste = False

        if result.invalidate_target:
            self.last_target_window = None
            self.gui.set_target_status("No target window captured.")

        if result.success:
            self.logger.info(
                "Paste completed via %s. mode=%s used_window=%s message=%s",
                trigger,
                result.paste_mode,
                self.text_inserter.describe_target(result.used_window),
                result.message,
            )
            self.gui.set_status(result.status_text)
            self._refresh_controls()
            return

        self.logger.warning(
            "Paste failed via %s. mode=%s clipboard_has_transcript=%s message=%s",
            trigger,
            result.paste_mode,
            result.clipboard_has_transcript,
            result.message,
        )
        self.gui.set_status(result.status_text)
        self._refresh_controls()

    def _resolve_microphone_option(self) -> tuple[InputDeviceInfo | None, str | None]:
        if not self.microphone_options:
            return None, None

        if self.current_input_device_index is None:
            return self._default_microphone_option(), None

        for option in self.microphone_options:
            if option.index == self.current_input_device_index:
                return option, None

        if self.current_input_device_name:
            matched_option = self._find_closest_visible_microphone(
                self.current_input_device_name
            )
            if matched_option is not None:
                if self.show_advanced_devices:
                    return matched_option, None
                return matched_option, "cleaned_match"

        default_option = self._default_microphone_option()
        if default_option is not None:
            if self.show_advanced_devices:
                return default_option, "unavailable"
            return default_option, "hidden_default"
        return self.microphone_options[0], "unavailable"

    def _default_microphone_option(self) -> InputDeviceInfo | None:
        if not self.microphone_options:
            return None

        for option in self.microphone_options:
            if option.index is None:
                return option
        for option in self.microphone_options:
            if option.is_default:
                return option
        return self.microphone_options[0]

    def _find_closest_visible_microphone(
        self,
        microphone_name: str,
    ) -> InputDeviceInfo | None:
        target_key = build_microphone_match_key(microphone_name)
        if not target_key:
            return None

        for option in self.microphone_options:
            if option.index is None:
                continue
            if build_microphone_match_key(option.name) == target_key:
                return option
        return None

    def _apply_microphone_selection(
        self,
        option: InputDeviceInfo,
        *,
        persist: bool,
    ) -> None:
        previous_index = self.current_input_device_index
        previous_name = self.current_input_device_name

        self.recorder.set_input_device(option.index, option.name)
        self.current_input_device_index = option.index
        self.current_input_device_name = option.name
        self._sync_microphone_selection()
        self.logger.info(
            "Microphone selected. index=%s name=%s display=%s",
            self.current_input_device_index,
            self.current_input_device_name,
            option.display_name,
        )

        if persist:
            update_runtime_config(
                input_device_index=self.current_input_device_index,
                input_device_name=self.current_input_device_name,
            )
            self.logger.info(
                "Microphone selection saved to config. previous_index=%s previous_name=%s",
                previous_index,
                previous_name,
            )

    def _sync_microphone_selection(self) -> None:
        selected_option = None
        for option in self.microphone_options:
            if option.index == self.current_input_device_index:
                selected_option = option
                break

        if selected_option is None and self.current_input_device_index is None:
            selected_option = self._default_microphone_option()

        if selected_option is None:
            return

        self.gui.set_microphone_options(
            [option.display_name for option in self.microphone_options],
            selected_option.display_name,
        )

    def _is_busy(self) -> bool:
        return self.recorder.is_recording or self.is_transcribing or self.is_pasting

    def _set_idle_status(self) -> None:
        if self.transcriber.load_error is not None:
            self.gui.set_status("Error")
            return
        if self.transcriber.is_ready:
            self.gui.set_status("Ready")
            return
        self.gui.set_status("Loading model")

    def _target_label(self, target: WindowTarget) -> str:
        description = self.text_inserter.describe_target(target)
        if len(description) > 90:
            return description[:87] + "..."
        return description

    def _format_hwnd(self, hwnd: int) -> str:
        return f"0x{hwnd:08X}"

    def on_close(self) -> None:
        self.logger.info("Application shutting down.")
        self.hotkey_manager.unregister()
        self.recorder.cleanup()
        self.gui.close_side_panel()
        self.root.destroy()


def main() -> None:
    app = VoiceTypingOverlayApp()
    app.run()


if __name__ == "__main__":
    main()
